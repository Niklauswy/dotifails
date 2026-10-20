"""Presentation layer over the recorded monitor: what you see is what is recorded.

One transparent, pinned window covers the monitor and paints three things that
the screen capture records as they are:

* a camera bubble (circle or rounded rectangle) that can be dragged and resized
  with the wheel, fed by its own local camera process;
* drawings made with the side toolbar: arrows, numbered markers, rectangles and
  a highlighter;
* the toolbar itself, hidden at the left edge until the pointer reaches it.

Outside those areas the window has no input region, so clicks reach the
applications underneath. While a drawing tool is active the whole monitor
accepts input until Esc returns to the pointer.
"""
import json
import math
import os
import subprocess
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF, QRegion
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget, QFrame

from .camera_preview import CameraPreview

TITLE = 'Wysun Recorder · Presentación'
EDGE = 6
COLORS = ('#E5484D', '#F5B83D', '#3E8BF0', '#30A46C', '#FFFFFF')
TOOLS = (('pointer', 'Puntero · Esc'), ('arrow', 'Flecha · A'), ('number', 'Número · N'),
         ('rect', 'Recuadro · R'), ('marker', 'Resaltador · H'))
BUBBLE = {'small': .20, 'medium': .28, 'large': .38}


class BubbleCamera(CameraPreview):
    """Same bounded local camera process, sized and paced for the recording."""
    WIDTH = 640
    HEIGHT = 480
    FRAME_BYTES = WIDTH * HEIGHT * 3

    def _command(self, device):
        program, args = super()._command(device)
        # Fill the frame (centre crop) instead of letterboxing: the bubble crops again.
        index = args.index('-vf') + 1
        args[index] = f'fps=30,scale={self.WIDTH}:{self.HEIGHT}:force_original_aspect_ratio=increase,crop={self.WIDTH}:{self.HEIGHT}'
        return program, args

    def hideEvent(self, event):
        # Never shown itself; the presentation layer owns its lifetime.
        QWidget.hideEvent(self, event)


def arrow_head(start, end, size):
    """Triangle at ``end`` pointing away from ``start``."""
    angle = math.atan2(end.y() - start.y(), end.x() - start.x())
    left = QPointF(end.x() - size * math.cos(angle - .45), end.y() - size * math.sin(angle - .45))
    right = QPointF(end.x() - size * math.cos(angle + .45), end.y() - size * math.sin(angle + .45))
    return QPolygonF([end, left, right])


def place_window(widget, rect, title=TITLE):
    """Float, size, position and pin our own window with Hyprland; True if done."""
    if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        return False
    try:
        rows = json.loads(subprocess.run(['hyprctl', '-j', 'clients'], capture_output=True, text=True, timeout=2).stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    address = next((r['address'] for r in rows if r.get('pid') == os.getpid() and str(r.get('title', '')).startswith(title)), None)
    if not address:
        return False
    x, y, w, h = rect
    target = f'window="address:{address}"'
    script = (f'hl.dispatch(hl.dsp.window.float({{action="enable",{target}}})); '
              f'hl.dispatch(hl.dsp.window.resize({{x={int(w)},y={int(h)},{target}}})); '
              f'hl.dispatch(hl.dsp.window.move({{x={int(x)},y={int(y)},{target}}}))')
    pinned = next((r.get('pinned') for r in rows if r['address'] == address), False)
    if not pinned:
        script += f'; hl.dispatch(hl.dsp.window.pin({{{target}}}))'
    try:
        subprocess.run(['hyprctl', 'eval', script], capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def tool_icon(kind, color='#E6EBF3', size=22):
    """Presentation tool glyphs drawn to match the outline icon family."""
    from PySide6.QtGui import QIcon, QPixmap
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size * 2 / 24, size * 2 / 24)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if kind == 'pointer':
        p.setBrush(QColor(color))
        p.drawPolygon(QPolygonF([QPointF(6, 3), QPointF(6, 19), QPointF(10, 15), QPointF(13, 21), QPointF(15.5, 20), QPointF(12.5, 14), QPointF(18, 14)]))
    elif kind == 'arrow':
        p.drawLine(QPointF(5, 19), QPointF(17, 7))
        p.setBrush(QColor(color))
        p.drawPolygon(arrow_head(QPointF(5, 19), QPointF(19, 5), 7))
    elif kind == 'number':
        p.drawEllipse(QRectF(3.5, 3.5, 17, 17))
        p.setFont(QFont('Inter', 9, QFont.Bold))
        p.drawText(QRectF(3.5, 3.5, 17, 17), Qt.AlignCenter, '1')
    elif kind == 'rect':
        p.drawRoundedRect(QRectF(4, 6, 16, 12), 3, 3)
    elif kind == 'marker':
        stroke = QColor(color)
        stroke.setAlpha(150)
        p.setPen(QPen(stroke, 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(5, 17), QPointF(19, 7))
    elif kind == 'shape':
        p.drawEllipse(QRectF(3, 6, 9, 9))
        p.drawRoundedRect(QRectF(13, 6, 9, 9), 2, 2)
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


class Toolbar(QFrame):
    toolChosen = Signal(str)

    def __init__(self, overlay):
        super().__init__(overlay)
        self.overlay = overlay
        self.setObjectName('presenterToolbar')
        self.setStyleSheet('#presenterToolbar{background:rgba(16,20,29,232);border:1px solid rgba(255,255,255,30);border-radius:16px;}'
                           'QToolButton{background:transparent;border:0;border-radius:10px;color:#E6EBF3;font-size:18px;min-width:40px;min-height:40px;}'
                           'QToolButton:hover{background:rgba(255,255,255,26);}'
                           'QToolButton:checked{background:#2569CA;color:white;}'
                           'QFrame#sep{background:rgba(255,255,255,30);max-height:1px;min-height:1px;}')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(4)
        self.buttons = {}
        from .icons import icon
        for key, tip in TOOLS:
            b = self.button(tool_icon(key), tip, lambda _=False, k=key: overlay.set_tool(k), checkable=True)
            self.buttons[key] = b
            layout.addWidget(b)
        layout.addWidget(self.separator())
        self.color = self.button(None, 'Color · C', overlay.next_color)
        layout.addWidget(self.color)
        layout.addWidget(self.button(icon('undo', '#E6EBF3', 22), 'Deshacer · Ctrl+Z', overlay.undo))
        layout.addWidget(self.button(icon('trash', '#E6EBF3', 22), 'Borrar todo · Supr', overlay.clear))
        layout.addWidget(self.separator())
        self.camera = self.button(icon('camera', '#E6EBF3', 22), 'Cámara: mostrar u ocultar', overlay.toggle_camera)
        layout.addWidget(self.camera)
        self.shape = self.button(tool_icon('shape'), 'Cámara: círculo o recuadro', overlay.toggle_shape)
        layout.addWidget(self.shape)
        layout.addWidget(self.separator())
        self.pause = self.button(icon('pause', '#E6EBF3', 22), 'Pausar o reanudar', overlay.request_pause)
        layout.addWidget(self.pause)
        self.stop = self.button(icon('stop', '#FF8A8F', 22), 'Terminar grabación', overlay.request_stop)
        layout.addWidget(self.stop)
        self.adjustSize()

    def button(self, glyph, tip, callback, checkable=False):
        from PySide6.QtCore import QSize
        b = QToolButton(self)
        if glyph is not None:
            b.setIcon(glyph)
            b.setIconSize(QSize(22, 22))
        b.setToolTip(tip)
        b.setAccessibleName(tip)
        b.setCheckable(checkable)
        b.setFocusPolicy(Qt.NoFocus)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(callback)
        return b

    def enterEvent(self, event):
        self.overlay.hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.overlay.hide_timer.start()
        super().leaveEvent(event)

    def separator(self):
        line = QFrame(self)
        line.setObjectName('sep')
        return line

    def sync(self):
        for key, button in self.buttons.items():
            button.setChecked(key == self.overlay.tool)
        from PySide6.QtGui import QIcon, QPixmap
        swatch = QPixmap(44, 44)
        swatch.fill(Qt.transparent)
        p = QPainter(swatch)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 200), 2))
        p.setBrush(QColor(self.overlay.color))
        p.drawEllipse(QRectF(9, 9, 26, 26))
        p.end()
        swatch.setDevicePixelRatio(2)
        self.color.setIcon(QIcon(swatch))
        from PySide6.QtCore import QSize
        self.color.setIconSize(QSize(22, 22))
        self.camera.setEnabled(self.overlay.camera_device is not None)
        self.shape.setEnabled(self.overlay.camera_visible)


class PresenterOverlay(QWidget):
    pauseRequested = Signal()
    stopRequested = Signal()

    def __init__(self, monitor_rect, *, camera_device=None, camera_style=None, place=place_window):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle(TITLE)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.monitor = list(monitor_rect)
        self.resize(int(self.monitor[2]), int(self.monitor[3]))
        self._place = place
        self.tool = 'pointer'
        self.color = COLORS[0]
        self.shapes = []
        self.current = None
        self.next_number = 1
        style = dict(camera_style or {})
        self.camera_shape = style.get('shape', 'circle')
        self.camera_size = style.get('size', 'medium')
        self.camera_device = camera_device
        self.camera_visible = camera_device is not None
        self.camera_image = QImage()
        self.camera = None
        self.bubble = self._initial_bubble(style.get('corner', 'bottom-right'))
        self._drag = None
        self.toolbar = Toolbar(self)
        self.toolbar_x = -self.toolbar.width() - 4.
        self._toolbar_target = self.toolbar_x
        self.toolbar.move(int(self.toolbar_x), (self.height() - self.toolbar.height()) // 2)
        self.slide = QTimer(self)
        self.slide.setInterval(16)
        self.slide.timeout.connect(self._animate)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(1200)
        self.hide_timer.timeout.connect(self.hide_toolbar)
        self.toolbar.sync()

    # Lifetime -----------------------------------------------------------
    def present(self):
        self.show()
        self._update_input()
        tries = [0]

        def place():
            tries[0] += 1
            if self._place(self, self.monitor) or tries[0] >= 15:
                self._update_input()
                return
            QTimer.singleShot(120, self, place)
        QTimer.singleShot(0, self, place)

    def start_camera(self):
        if self.camera_device is None or self.camera is not None:
            return
        self.camera = BubbleCamera()
        self.camera.frameReady.connect(self._frame)
        self.camera.set_device(self.camera_device)

    def shutdown(self, on_released=None):
        """Hide now; ``on_released`` runs once the camera device is free."""
        self.slide.stop()
        self.hide_timer.stop()
        self.hide()
        camera, self.camera = self.camera, None
        if camera is not None:
            camera.stop(lambda: (camera.deleteLater(), on_released() if on_released else None))
        elif on_released:
            QTimer.singleShot(0, on_released)
        self.deleteLater()

    def _frame(self, image):
        self.camera_image = image
        if self.camera_visible:
            self.update(self.bubble.toAlignedRect().adjusted(-4, -4, 4, 4))

    # Geometry -----------------------------------------------------------
    def _bubble_size(self):
        tall = max(80., self.height() * BUBBLE.get(self.camera_size, .28))
        return (tall, tall) if self.camera_shape == 'circle' else (tall * 4 / 3, tall)

    def _initial_bubble(self, corner):
        w, h = self._bubble_size()
        margin = max(16., self.height() * .035)
        x = self.width() - w - margin if corner.endswith('right') else margin
        y = self.height() - h - margin if corner.startswith('bottom') else margin
        return QRectF(x, y, w, h)

    def _resize_bubble(self):
        center = self.bubble.center()
        w, h = self._bubble_size()
        self.bubble = QRectF(0, 0, w, h)
        self.bubble.moveCenter(center)
        self._clamp_bubble()

    def _clamp_bubble(self):
        b = self.bubble
        b.moveLeft(min(max(0., b.left()), self.width() - b.width()))
        b.moveTop(min(max(0., b.top()), self.height() - b.height()))

    def _update_input(self):
        handle = self.windowHandle()
        if handle is None:
            return
        if self.tool != 'pointer':
            handle.setMask(QRegion())  # whole window while drawing
            return
        region = QRegion(0, 0, EDGE, self.height())
        if self.toolbar_x > -self.toolbar.width():
            region = region.united(QRegion(self.toolbar.geometry().adjusted(-8, -8, 8, 8)))
        if self.camera_visible and self.camera_device is not None:
            region = region.united(QRegion(self.bubble.toAlignedRect()))
        handle.setMask(region)

    # Toolbar ------------------------------------------------------------
    def show_toolbar(self):
        self.hide_timer.stop()
        self._toolbar_target = 12.
        self.slide.start()
        self._update_input()

    def hide_toolbar(self):
        if self.toolbar.underMouse():
            self.hide_timer.start()
            return
        self._toolbar_target = -self.toolbar.width() - 4.
        self.slide.start()

    def _animate(self):
        delta = self._toolbar_target - self.toolbar_x
        self.toolbar_x = self._toolbar_target if abs(delta) < 1 else self.toolbar_x + delta * .3
        self.toolbar.move(int(self.toolbar_x), (self.height() - self.toolbar.height()) // 2)
        if self.toolbar_x == self._toolbar_target:
            self.slide.stop()
            self._update_input()

    # Tools ----------------------------------------------------------------
    def set_tool(self, tool):
        self.tool = tool
        self.current = None
        self.setCursor(Qt.ArrowCursor if tool == 'pointer' else Qt.CrossCursor)
        if tool != 'pointer':
            self.activateWindow()
            self.setFocus()
        self.toolbar.sync()
        self._update_input()
        self.hide_timer.start()

    def next_color(self):
        self.color = COLORS[(COLORS.index(self.color) + 1) % len(COLORS)]
        self.toolbar.sync()

    def undo(self):
        if self.shapes:
            removed = self.shapes.pop()
            if removed[0] == 'number':
                self.next_number = max(1, self.next_number - 1)
            self.update()

    def clear(self):
        self.shapes.clear()
        self.next_number = 1
        self.update()

    def toggle_camera(self):
        if self.camera_device is None:
            return
        self.camera_visible = not self.camera_visible
        self.toolbar.sync()
        self._update_input()
        self.update()

    def toggle_shape(self):
        self.camera_shape = 'rounded' if self.camera_shape == 'circle' else 'circle'
        self._resize_bubble()
        self._update_input()
        self.update()

    def request_pause(self):
        self.pauseRequested.emit()

    def request_stop(self):
        self.stopRequested.emit()

    # Input ----------------------------------------------------------------
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.set_tool('pointer')
        elif key == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            self.undo()
        elif key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.clear()
        elif key == Qt.Key_C:
            self.next_color()
        else:
            tool = {Qt.Key_A: 'arrow', Qt.Key_N: 'number', Qt.Key_R: 'rect', Qt.Key_H: 'marker'}.get(key)
            if tool:
                self.set_tool(tool)
            else:
                super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        point = event.position()
        if point.x() <= EDGE + 2:
            self.show_toolbar()
        elif not self.toolbar.geometry().adjusted(-24, -24, 24, 24).contains(point.toPoint()) and self._toolbar_target > 0 and not self.hide_timer.isActive():
            self.hide_timer.start()
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            offset = self._drag
            self.bubble.moveTopLeft(point - offset)
            self._clamp_bubble()
            self.update()
            return
        if self.current is not None and event.buttons() & Qt.LeftButton:
            kind = self.current[0]
            if kind == 'marker':
                self.current[1].append(point)
            else:
                self.current[1][1] = point
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        point = event.position()
        if self.camera_visible and self.camera_device is not None and self.bubble.contains(point):
            self._drag = point - self.bubble.topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            return
        if self.tool == 'pointer':
            return
        if self.tool == 'number':
            self.shapes.append(('number', point, self.color, self.next_number))
            self.next_number += 1
            self.update()
            return
        self.current = [self.tool, [point] if self.tool == 'marker' else [point, point], self.color]
        self.update()

    def mouseReleaseEvent(self, event):
        if self._drag is not None:
            self._drag = None
            self.setCursor(Qt.ArrowCursor if self.tool == 'pointer' else Qt.CrossCursor)
            self._update_input()
            return
        if self.current is not None:
            kind, points, color = self.current
            long_enough = len(points) > 2 if kind == 'marker' else (points[1] - points[0]).manhattanLength() > 6
            if long_enough:
                self.shapes.append((kind, list(points), color))
            self.current = None
            self.update()

    def wheelEvent(self, event):
        if self.camera_visible and self.bubble.contains(event.position()):
            order = list(BUBBLE)
            step = 1 if event.angleDelta().y() > 0 else -1
            self.camera_size = order[min(len(order) - 1, max(0, order.index(self.camera_size) + step))]
            self._resize_bubble()
            self._update_input()
            self.update()

    # Painting -------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for shape in self.shapes:
            self._paint_shape(p, shape)
        if self.current is not None:
            self._paint_shape(p, tuple(self.current))
        if self.camera_visible and self.camera_device is not None:
            self._paint_bubble(p)
        if self.tool != 'pointer':
            p.setPen(QPen(QColor(229, 72, 77, 150), 3))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5))

    def _paint_shape(self, p, shape):
        kind = shape[0]
        color = QColor(shape[2])
        if kind == 'number':
            center, number = shape[1], shape[3]
            p.setPen(QPen(QColor(0, 0, 0, 60), 2))
            p.setBrush(color)
            p.drawEllipse(center, 19, 19)
            p.setPen(QColor('#16151C') if shape[2] in ('#FFFFFF', '#F5B83D') else QColor('#FFFFFF'))
            p.setFont(QFont('Inter', 15, QFont.Bold))
            p.drawText(QRectF(center.x() - 19, center.y() - 19, 38, 38), Qt.AlignCenter, str(number))
        elif kind == 'arrow':
            start, end = shape[1]
            p.setPen(QPen(color, 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(color)
            angle = math.atan2(end.y() - start.y(), end.x() - start.x())
            shaft = QPointF(end.x() - 14 * math.cos(angle), end.y() - 14 * math.sin(angle))
            p.drawLine(start, shaft)
            p.drawPolygon(arrow_head(start, end, 26))
        elif kind == 'rect':
            start, end = shape[1]
            p.setPen(QPen(color, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(start, end).normalized(), 8, 8)
        elif kind == 'marker':
            points = shape[1]
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            color.setAlpha(110)
            p.setPen(QPen(color, 22, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

    def _paint_bubble(self, p):
        b = self.bubble
        path = QPainterPath()
        if self.camera_shape == 'circle':
            path.addEllipse(b)
        else:
            path.addRoundedRect(b, b.height() / 8, b.height() / 8)
        p.save()
        p.setClipPath(path)
        p.fillRect(b, QColor('#18263A'))
        if not self.camera_image.isNull():
            image = self.camera_image
            scale = max(b.width() / image.width(), b.height() / image.height())
            w, h = image.width() * scale, image.height() * scale
            p.drawImage(QRectF(b.center().x() - w / 2, b.center().y() - h / 2, w, h), image)
        else:
            p.setPen(QColor('#BAC9DD'))
            p.drawText(b, Qt.AlignCenter, 'Cámara')
        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 210), 3))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
