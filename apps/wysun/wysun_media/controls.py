"""Painted player controls. Colours, corners, spacing, type, icons and motion all come from the host's tokens.

Controls float over video and images, so they use the HUD palette (``hud``, ``on_hud``,
``hud_accent``…) that every theme variant defines for exactly that purpose.
"""
from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetricsF, QPainter
from PySide6.QtWidgets import QAbstractButton, QToolTip, QWidget

from . import host, shape


def unit():
    """Base measure of the controls, from the theme's icon size."""
    return float(host.get().token('icon_size'))


def clock(seconds):
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    return f'{hours}:{rest // 60:02}:{rest % 60:02}' if hours else f'{rest // 60}:{rest % 60:02}'


def _luminance(colour):
    def linear(channel):
        return channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4
    return .2126 * linear(colour.redF()) + .7152 * linear(colour.greenF()) + .0722 * linear(colour.blueF())


def hud_ink(token='accent'):
    """``token``'s colour when it can be seen on the HUD (3:1 against it), otherwise the HUD's own text colour.

    The HUD is dark in every theme, but an accent follows the scheme and can be dark too (a light theme's primary);
    a progress bar or a focus ring in it would disappear.
    """
    h = host.get()
    ink, base = h.color(token, 255), h.color('hud', 255)
    light, dark = sorted((_luminance(ink), _luminance(base)), reverse=True)
    return ink if (light + .05) / (dark + .05) >= 3.0 else h.color('on_hud')


def _keyboard_focus(reason):
    return reason in (Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)


class ControlButton(QAbstractButton):
    """Circular icon button (``corner_full``) with hover and press layers and a keyboard focus ring."""

    def __init__(self, symbol, label, parent=None, *, variant='standard', scale=2.0, filled=False):
        super().__init__(parent)
        self.symbol, self.variant, self.scale, self.filled = symbol, variant, scale, filled
        self._hover = self._focus_ring = False
        self.set_label(label)
        self.setFocusPolicy(Qt.TabFocus)
        self.setCursor(Qt.PointingHandCursor)

    def set_label(self, label):
        self.setAccessibleName(label)
        self.setToolTip(label)

    def set_symbol(self, symbol):
        if symbol != self.symbol:
            self.symbol = symbol
            self.update()

    def sizeHint(self):
        side = round(unit() * self.scale)
        return QSize(side, side)

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self._focus_ring = _keyboard_focus(event.reason())
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._focus_ring = False
        super().focusOutEvent(event)

    def _background(self, h):
        if self.variant == 'filled':
            return h.color('accent_pressed' if self.isDown() else 'accent_hover' if self._hover else 'accent')
        if self.isChecked():
            return h.color('hud_accent', 140)
        return h.color('hud_hover') if self.variant == 'tonal' else None

    def _tint(self, h):
        if not self.isEnabled():
            return h.color('hud_muted', 110)
        if self.variant == 'filled':
            return h.color('on_accent')
        return h.color('on_hud')

    def paintEvent(self, _event):
        h = host.get()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        outline = self._outline(rect)
        background = self._background(h)
        if background is not None:
            painter.fillPath(outline, background)
        if self.isEnabled() and self.variant != 'filled' and (self._hover or self.isDown()):
            painter.fillPath(outline, h.color('hud_hover'))          # state layer; pressed stacks a second one
            if self.isDown():
                painter.fillPath(outline, h.color('hud_hover'))
        if self._focus_ring:
            painter.setPen(hud_ink('focus'))
            painter.drawPath(self._outline(rect.adjusted(1, 1, -1, -1)))
        h.symbol(painter, rect, self.symbol, self._tint(h), round(unit() * 1.2 * self.scale / 2), self.filled)

    def _outline(self, rect):
        return shape.rounded(rect, 'full')


class PlayButton(ControlButton):
    """The one animated piece: a circle while paused that settles into a rounded square while playing."""

    def __init__(self, label, parent=None):
        super().__init__('play_arrow', label, parent, variant='filled', scale=3.0, filled=True)
        self.morph = shape.Morph(self)
        self.morph.changed.connect(lambda _: self.update())

    def set_playing(self, playing):
        self.set_symbol('pause' if playing else 'play_arrow')
        self.morph.go(1.0 if playing else 0.0)

    def _outline(self, rect):
        full, resting = shape.radius('full', rect), shape.radius('l', rect)
        return shape.rounded(rect, shape.lerp(full, resting, self.morph.value))


class Pill(QAbstractButton):
    """Text in a ``corner_full`` capsule (playback speed); highlighted when it differs from the default."""

    def __init__(self, text, label, parent=None):
        super().__init__(parent)
        self._hover = self._focus_ring = False
        self.highlight = False
        self.setText(text)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setFocusPolicy(Qt.TabFocus)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        metrics = QFontMetricsF(host.get().font('small', 600))
        return QSize(round(metrics.horizontalAdvance(self.text()) + unit() * 1.6), round(unit() * 1.8))

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self._focus_ring = _keyboard_focus(event.reason())
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._focus_ring = False
        super().focusOutEvent(event)

    def paintEvent(self, _event):
        h = host.get()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        outline = shape.rounded(rect, 'full')
        if self.highlight:
            painter.fillPath(outline, h.color('accent_pressed' if self.isDown() else 'accent_hover' if self._hover else 'accent'))
            ink = h.color('on_accent')
        else:
            painter.fillPath(outline, h.color('hud_hover'))
            if self._hover or self.isDown():
                painter.fillPath(outline, h.color('hud_hover'))
            ink = h.color('on_hud')
        if self._focus_ring:
            painter.setPen(hud_ink('focus'))
            painter.drawPath(shape.rounded(rect.adjusted(1, 1, -1, -1), 'full'))
        painter.setFont(h.font('small', 600))
        painter.setPen(ink)
        painter.drawText(rect, Qt.AlignCenter, self.text())


class Track(QWidget):
    """Horizontal slider: a rounded track, an accent fill and a slim vertical handle.

    ``changing(ratio)`` fires while dragging, ``committed(ratio)`` when the user lets go
    (or clicks, or uses the keyboard); setting the value from code never emits.
    """

    changing = Signal(float)
    committed = Signal(float)
    step = 0.05

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.ratio = 0.0
        self._drag = False
        self._hover = None
        self._focus_ring = False
        self.setAccessibleName(label)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.TabFocus)
        self.setCursor(Qt.PointingHandCursor)

    @property
    def dragging(self):
        return self._drag

    def sizeHint(self):
        return QSize(round(unit() * 6), round(unit() * 1.8))

    def set_ratio(self, ratio):
        ratio = min(1.0, max(0.0, float(ratio)))
        if not self._drag and ratio != self.ratio:
            self.ratio = ratio
            self.update()

    # ------------------------------------------------------------- geometry
    def _inset(self):
        return float(host.get().token('space_s'))

    def lane(self):
        inset = self._inset()
        return QRectF(inset, 0, max(1.0, self.width() - 2 * inset), self.height())

    def _ratio_at(self, x):
        lane = self.lane()
        return min(1.0, max(0.0, (x - lane.left()) / lane.width()))

    def _thickness(self):
        base = float(host.get().token('space_xs'))
        return base * 1.5 if self._drag or self._hover is not None or self._focus_ring else base

    # ---------------------------------------------------------------- input
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self._drag = True
            self.ratio = self._ratio_at(event.position().x())
            self.changing.emit(self.ratio)
            self.update()

    def mouseMoveEvent(self, event):
        self._hover = event.position().x()
        if self._drag:
            self.ratio = self._ratio_at(event.position().x())
            self.changing.emit(self.ratio)
        else:
            self.hovered(event)
        self.update()

    def mouseReleaseEvent(self, event):
        if self._drag and event.button() == Qt.LeftButton:
            self._drag = False
            self.committed.emit(self.ratio)
            self.update()

    def hovered(self, event):
        """Hook for subclasses (preview bubble)."""

    def leaveEvent(self, event):
        self._hover = None
        self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120
        if steps:
            self.set_ratio(self.ratio + steps * self.step)
            self.committed.emit(self.ratio)
        event.accept()

    def keyPressEvent(self, event):
        delta = {Qt.Key_Left: -self.step, Qt.Key_Right: self.step, Qt.Key_Down: -self.step, Qt.Key_Up: self.step}.get(event.key())
        if delta is None:
            to = {Qt.Key_Home: 0.0, Qt.Key_End: 1.0}.get(event.key())
            if to is None:
                return super().keyPressEvent(event)
            self.ratio = to
        else:
            self.ratio = min(1.0, max(0.0, self.ratio + delta))
        self.committed.emit(self.ratio)
        self.update()

    def focusInEvent(self, event):
        self._focus_ring = _keyboard_focus(event.reason())
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._focus_ring = False
        super().focusOutEvent(event)

    # ---------------------------------------------------------------- paint
    def segments(self):
        """Fractions (start, end) the track is split into; one unless a subclass cuts it."""
        return [(0.0, 1.0)]

    def paintEvent(self, _event):
        h = host.get()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        lane, thickness = self.lane(), self._thickness()
        top = lane.center().y() - thickness / 2
        gap = float(h.token('space_xs')) / 2
        cut = [(a, b) for a, b in self.segments()]
        for index, (start, end) in enumerate(cut):
            left = lane.left() + lane.width() * start + (gap if index else 0)
            right = lane.left() + lane.width() * end - (gap if index < len(cut) - 1 else 0)
            box = QRectF(left, top, max(1.0, right - left), thickness)
            painter.fillPath(shape.rounded(box, 'full'), h.color('hud_muted', 80))
            fill = min(box.right(), lane.left() + lane.width() * self.ratio)
            if fill > box.left():
                painter.save()
                painter.setClipRect(QRectF(box.left(), box.top(), fill - box.left(), box.height()))
                painter.fillPath(shape.rounded(box, 'full'), hud_ink('accent'))
                painter.restore()
        self.paint_extras(painter, h, lane, top, thickness)
        handle = QRectF(0, 0, float(h.token('space_xs')), unit() * 1.3)
        handle.moveCenter(QPointF(lane.left() + lane.width() * self.ratio, lane.center().y()))
        if self._drag:
            handle.adjust(1, 1, -1, -1)
        painter.fillPath(shape.rounded(handle, 'full'), hud_ink('accent'))
        if self._focus_ring:
            painter.setPen(hud_ink('focus'))
            painter.drawPath(shape.rounded(handle.adjusted(-2, -2, 2, 2), 'full'))

    def paint_extras(self, painter, h, lane, top, thickness):
        """Hook for subclasses (loop range)."""


class SeekBar(Track):
    """Position slider in seconds: chapter gaps, an A-B loop range and a time bubble under the pointer."""

    scrubbed = Signal(float)             # seconds, while dragging
    seekRequested = Signal(float)        # seconds, on release / click / key / wheel
    step = 0.01

    def __init__(self, parent=None):
        super().__init__('Posición de reproducción', parent)
        self.duration = 0.0
        self.chapters = []               # [(seconds, title)]
        self.loop = (None, None)
        self.changing.connect(lambda r: self.scrubbed.emit(r * self.duration))
        self.committed.connect(lambda r: self.seekRequested.emit(r * self.duration))

    def set_duration(self, seconds):
        self.duration = max(0.0, float(seconds or 0.0))
        self.setEnabled(self.duration > 0)
        self.update()

    def set_position(self, seconds):
        self.set_ratio(seconds / self.duration if self.duration else 0.0)

    def set_chapters(self, chapters):
        self.chapters = [(float(c.get('time', 0)), c.get('title') or '') for c in chapters or []]
        self.update()

    def set_loop(self, a, b):
        self.loop = (a, b)
        self.update()

    def segments(self):
        if not self.duration or len(self.chapters) < 2:
            return [(0.0, 1.0)]
        edges = [0.0] + [min(1.0, t / self.duration) for t, _ in self.chapters if 0 < t < self.duration] + [1.0]
        return [(a, b) for a, b in zip(edges, edges[1:]) if b > a]

    def hovered(self, event):
        if not self.duration:
            return
        seconds = self._ratio_at(event.position().x()) * self.duration
        title = next((name for time, name in reversed(self.chapters) if time <= seconds and name), '')
        QToolTip.showText(event.globalPosition().toPoint() - QPoint(0, round(unit() * 2)),
                          clock(seconds) + (f' · {title}' if title else ''), self)

    def paint_extras(self, painter, h, lane, top, thickness):
        a, b = self.loop
        if not self.duration or a is None:
            return
        left = lane.left() + lane.width() * min(1.0, a / self.duration)
        right = lane.left() + lane.width() * min(1.0, (b if b is not None else a) / self.duration)
        marks = QRectF(0, 0, float(h.token('space_xs')) / 2 + 1, thickness + float(h.token('space_s')))
        for x in ((left, right) if b is not None else (left,)):
            marks.moveCenter(QPointF(x, top + thickness / 2))
            painter.fillPath(shape.rounded(marks, 'full'), h.color('on_hud'))
        if b is not None:
            band = QRectF(left, top, max(1.0, right - left), thickness)
            painter.fillPath(shape.rounded(band, 'full'), h.color('on_hud', 120))


class VolumeSlider(Track):
    """0–150 %; the handle crosses full scale at two thirds of the track."""

    volumeChanged = Signal(float)        # percent, user-driven
    MAX = 150.0

    def __init__(self, parent=None):
        super().__init__('Volumen', parent)
        self.changing.connect(lambda r: self.volumeChanged.emit(round(r * self.MAX)))
        self.committed.connect(lambda r: self.volumeChanged.emit(round(r * self.MAX)))

    def set_volume(self, percent):
        self.set_ratio(percent / self.MAX)

    def sizeHint(self):
        return QSize(round(unit() * 5), round(unit() * 1.8))


class Row:
    def __init__(self, kind, text='', callback=None, checked=None, detail='', enabled=True, symbol=''):
        self.kind, self.text, self.callback, self.checked = kind, text, callback, checked
        self.detail, self.enabled, self.symbol = detail, enabled, symbol


class PopupMenu(QWidget):
    """Floating list for speeds, tracks and actions, in the HUD palette with ``corner_m`` corners."""

    dismissed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.rows, self._current = [], -1

    # --------------------------------------------------------------- content
    def add_item(self, text, callback, checked=None, detail='', enabled=True, symbol=''):
        self.rows.append(Row('item', text, callback, checked, detail, enabled, symbol))
        return self

    def add_header(self, text):
        self.rows.append(Row('header', text))
        return self

    def add_info(self, label, value):
        self.rows.append(Row('info', label, detail=value))
        return self

    def add_separator(self):
        self.rows.append(Row('separator'))
        return self

    def _height(self, row):
        base = unit() * 2
        return {'item': base, 'header': base * .8, 'info': base * .8, 'separator': float(host.get().token('space_s'))}[row.kind]

    def _pad(self):
        return float(host.get().token('space_xs'))

    def _layout(self):
        y, boxes = self._pad(), []
        for row in self.rows:
            boxes.append(QRectF(self._pad(), y, self.width() - 2 * self._pad(), self._height(row)))
            y += self._height(row)
        return boxes

    def _measure(self):
        h = host.get()
        metrics, small = QFontMetricsF(h.font('body', 500)), QFontMetricsF(h.font('small'))
        gutter = unit() * 2.2
        widest = max((metrics.horizontalAdvance(r.text) + (small.horizontalAdvance(r.detail) + unit() if r.detail else 0)
                      for r in self.rows), default=0)
        height = 2 * self._pad() + sum(self._height(r) for r in self.rows)
        self.resize(round(max(unit() * 11, gutter + widest + unit() * 1.5)), round(height))

    def popup_above(self, anchor):
        """Open over ``anchor`` (right edges aligned), or below when there is no room above."""
        self._measure()
        screen = anchor.screen().availableGeometry()
        gap = round(float(host.get().token('space_s')))
        corner = anchor.mapToGlobal(QPoint(anchor.width(), 0))
        x = min(max(screen.left(), corner.x() - self.width()), screen.right() - self.width())
        y = corner.y() - self.height() - gap
        if y < screen.top():
            y = anchor.mapToGlobal(QPoint(0, anchor.height())).y() + gap
        self.move(x, y)
        self._current = -1
        self.show()

    # ------------------------------------------------------------- behaviour
    def _row_at(self, point):
        for index, box in enumerate(self._layout()):
            if box.contains(point) and self.rows[index].kind == 'item' and self.rows[index].enabled:
                return index
        return -1

    def mouseMoveEvent(self, event):
        index = self._row_at(event.position())
        if index != self._current:
            self._current = index
            self.update()

    def mouseReleaseEvent(self, event):
        index = self._row_at(event.position())
        if index >= 0:
            self._activate(index)

    def leaveEvent(self, event):
        self._current = -1
        self.update()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.dismissed.emit()

    def keyPressEvent(self, event):
        items = [i for i, r in enumerate(self.rows) if r.kind == 'item' and r.enabled]
        key = event.key()
        if key == Qt.Key_Escape:
            self.close()
        elif key in (Qt.Key_Down, Qt.Key_Up) and items:
            order = items if key == Qt.Key_Down else items[::-1]
            later = [i for i in order if (i > self._current if key == Qt.Key_Down else i < self._current)]
            self._current = (later or order)[0]
            self.update()
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self._current >= 0:
            self._activate(self._current)

    def _activate(self, index):
        callback = self.rows[index].callback
        self._current = -1                  # a closed menu has nothing selected: a second key press must not run it again
        self.close()
        if callback is not None:
            QTimer.singleShot(0, callback)

    def paintEvent(self, _event):
        h = host.get()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outer = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.fillPath(shape.rounded(outer, 'm'), h.color('hud'))
        painter.setPen(h.color('hud_line'))
        painter.drawPath(shape.rounded(outer, 'm'))
        gutter = unit() * 2.2
        for index, (row, box) in enumerate(zip(self.rows, self._layout())):
            if row.kind == 'separator':
                painter.fillRect(QRectF(box.left() + unit() * .5, box.center().y(), box.width() - unit(), 1), h.color('hud_line'))
                continue
            if row.kind == 'item' and index == self._current:
                painter.fillPath(shape.rounded(box, 's'), h.color('hud_hover'))
            muted = row.kind in ('header', 'info') or not row.enabled
            painter.setPen(h.color('hud_muted' if muted else 'on_hud'))
            painter.setFont(h.font('small' if row.kind == 'header' else 'body', 600 if row.kind == 'header' else 500))
            if row.checked:
                h.symbol(painter, QRectF(box.left(), box.top(), gutter, box.height()), 'check', hud_ink('accent'), round(unit()))
            elif row.symbol:
                h.symbol(painter, QRectF(box.left(), box.top(), gutter, box.height()), row.symbol, 'on_hud', round(unit()))
            painter.drawText(QRectF(box.left() + gutter, box.top(), box.width() - gutter - unit() * .5, box.height()),
                             Qt.AlignLeft | Qt.AlignVCenter, row.text)
            if row.detail:
                painter.setFont(h.font('small'))
                painter.setPen(h.color('hud_muted'))
                painter.drawText(QRectF(box.left(), box.top(), box.width() - unit() * .6, box.height()),
                                 Qt.AlignRight | Qt.AlignVCenter, row.detail)


class Toast(QWidget):
    """Brief feedback pill ('1.5×', 'Volumen 80 %') that fades by itself."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.text = ''
        self.symbol = ''
        self.fade = shape.Morph(self, 'motion_exit')
        self.fade.jump(0.0)
        self.fade.changed.connect(lambda _: self.update())
        self._timer = QTimer(self, singleShot=True, interval=1100)
        self._timer.timeout.connect(lambda: self.fade.go(0.0))
        self.hide()

    def say(self, text, symbol=''):
        self.text, self.symbol = text, symbol
        metrics = QFontMetricsF(host.get().font('body', 600))
        width = metrics.horizontalAdvance(text) + unit() * (3.4 if symbol else 2.0)
        self.resize(round(width), round(unit() * 2))
        self.reposition()
        self.fade.jump(1.0)
        self.show()
        self.raise_()
        self._timer.start()

    def reposition(self):
        parent = self.parentWidget()
        if parent is not None:
            self.move((parent.width() - self.width()) // 2, round(float(host.get().token('space_l'))))

    def paintEvent(self, _event):
        h = host.get()
        if self.fade.value <= 0.01 and not self.fade.running:
            self.hide()
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self.fade.value)
        rect = QRectF(self.rect())
        painter.fillPath(shape.rounded(rect, 'full'), h.color('hud'))
        painter.setPen(h.color('hud_line'))
        painter.drawPath(shape.rounded(rect.adjusted(.5, .5, -.5, -.5), 'full'))
        left = rect.left()
        if self.symbol:
            h.symbol(painter, QRectF(left + unit() * .4, rect.top(), unit() * 1.6, rect.height()), self.symbol, 'on_hud', round(unit()))
            left += unit() * 1.6
        painter.setFont(h.font('body', 600))
        painter.setPen(h.color('on_hud'))
        painter.drawText(QRectF(left, rect.top(), rect.right() - left, rect.height()), Qt.AlignCenter, self.text)


class Capsule(QWidget):
    """The floating bar's background: ``corner_l`` in the HUD material."""

    def paintEvent(self, _event):
        h = host.get()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.fillPath(shape.rounded(rect, 'l'), h.color('hud'))
        painter.setPen(h.color('hud_line'))
        painter.drawPath(shape.rounded(rect, 'l'))


class Rounding(QWidget):
    """Paints the slivers outside a rounded frame in the colour behind the player, rounding the corners
    of surfaces that cannot be clipped (an OpenGL widget)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.corner, self.backdrop = 'none', 'surface'

    def set_corner(self, corner, backdrop=None):
        self.corner = corner
        self.backdrop = backdrop or self.backdrop
        self.update()

    def paintEvent(self, _event):
        if self.corner == 'none':
            return
        h = host.get()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillPath(shape.frame_outside(QRectF(self.rect()), self.corner), h.color(self.backdrop))


class Clock(QWidget):
    """Elapsed or remaining time in tabular width, so the seek bar does not jitter."""

    def __init__(self, align=Qt.AlignLeft, parent=None):
        super().__init__(parent)
        self.text, self.align = '0:00', align

    def set_seconds(self, seconds, remaining=False):
        text = ('−' if remaining and seconds else '') + clock(seconds)
        if text != self.text:
            self.text = text
            self.update()

    def sizeHint(self):
        metrics = QFontMetricsF(host.get().font('small', 600))
        return QSize(round(metrics.horizontalAdvance('−0:00:00')), round(unit() * 1.6))

    def paintEvent(self, _event):
        h = host.get()
        painter = QPainter(self)
        painter.setFont(h.font('small', 600))
        painter.setPen(h.color('hud_muted'))
        painter.drawText(QRectF(self.rect()), self.align | Qt.AlignVCenter, self.text)
