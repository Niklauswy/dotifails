"""Window furniture: tab strip, selection capsule, status line and the raised surface."""
import time

from PySide6.QtCore import QEasingCurve, QRect, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from theme_tokens import color, tokens
from ui_motion import reduced_motion
from wysun_music.ui.sidebar import Panel
from .kit import IconButton, StateLayer, metric, paint_symbol, text_font


class Surface(Panel):
    """Raised rounded surface that tells its owner when it is resized (overlay placement)."""

    resized = Signal()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()


class TabStrip(QWidget):
    selected = Signal(int)
    close_requested = Signal(int)
    new_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels, self.tips, self.current, self.hover, self.hover_close = [], [], 0, None, False
        self.setFixedHeight(38)
        self.setMouseTracking(True)

    def set_tabs(self, labels, current):
        self.labels, self.current = list(labels), current
        self.update()

    def _boxes(self):
        width = min(200, max(110, (self.width() - 52) // max(1, len(self.labels))))
        return [QRectF(number * (width + 4), 3, width, 32) for number in range(len(self.labels))]

    def _plus(self):
        boxes = self._boxes()
        left = boxes[-1].right() + 6 if boxes else 0
        return QRectF(left, 3, 32, 32)

    def mouseMoveEvent(self, event):
        point = event.position()
        hover = next((n for n, box in enumerate(self._boxes()) if box.contains(point)), None)
        close = hover is not None and point.x() > self._boxes()[hover].right() - 28
        if (hover, close) != (self.hover, self.hover_close):
            self.hover, self.hover_close = hover, close
            self.setCursor(Qt.PointingHandCursor if hover is not None or self._plus().contains(point) else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        self.hover = None
        self.update()

    def mouseReleaseEvent(self, event):
        point = event.position()
        for number, box in enumerate(self._boxes()):
            if box.contains(point):
                if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and point.x() > box.right() - 28):
                    self.close_requested.emit(number)
                elif event.button() == Qt.LeftButton:
                    self.selected.emit(number)
                return
        if event.button() == Qt.LeftButton and self._plus().contains(point):
            self.new_requested.emit()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for number, (label, box) in enumerate(zip(self.labels, self._boxes())):
            active = number == self.current
            painter.setPen(Qt.NoPen)
            if active:
                painter.setBrush(color('nav_selected'))
                painter.drawRoundedRect(box, 16, 16)
            elif self.hover == number:
                painter.setBrush(color('tint', 14))
                painter.drawRoundedRect(box, 16, 16)
            paint_symbol(painter, QRectF(box.left() + 8, box.top(), 22, box.height()), 'folder', 'accent' if active else 'muted', 17, filled=active)
            painter.setFont(text_font('small', 600 if active else 450))
            painter.setPen(color('text_strong' if active else 'muted'))
            area = QRectF(box.left() + 34, box.top(), box.width() - 62, box.height())
            painter.drawText(area, Qt.AlignLeft | Qt.AlignVCenter, painter.fontMetrics().elidedText(label, Qt.ElideRight, int(area.width())))
            if active or self.hover == number:
                if self.hover == number and self.hover_close:
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(color('tint', 30))
                    painter.drawEllipse(QRectF(box.right() - 28, box.top() + 5, 22, 22))
                paint_symbol(painter, QRectF(box.right() - 28, box.top() + 5, 22, 22), 'close', 'text' if self.hover_close and self.hover == number else 'muted', 15)
        paint_symbol(painter, self._plus(), 'add', 'muted', 20)


class TabArea(QWidget):
    """Stack of ``FolderTab`` pages with a strip that appears from the second tab on."""

    currentChanged = Signal(int)
    tabCloseRequested = Signal(int)
    new_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.strip = TabStrip()
        self.strip.hide()
        self.strip.selected.connect(self.setCurrentIndex)
        self.strip.close_requested.connect(self.tabCloseRequested)
        self.strip.new_requested.connect(self.new_requested)
        self.stack = QStackedWidget()
        column.addWidget(self.strip)
        column.addWidget(self.stack, 1)
        self.titles, self.tips = [], []

    def count(self):
        return self.stack.count()

    def widget(self, index):
        return self.stack.widget(index)

    def currentWidget(self):
        return self.stack.currentWidget()

    def currentIndex(self):
        return self.stack.currentIndex()

    def addTab(self, page, title):
        self.stack.addWidget(page)
        self.titles.append(title)
        self.tips.append('')
        self._sync()
        return self.stack.count() - 1

    def removeTab(self, index):
        self.stack.removeWidget(self.stack.widget(index))
        del self.titles[index], self.tips[index]
        self._sync()
        self.currentChanged.emit(self.stack.currentIndex())

    def setCurrentIndex(self, index):
        if 0 <= index < self.count() and index != self.stack.currentIndex():
            self.stack.setCurrentIndex(index)
            self._sync()
            self.currentChanged.emit(index)

    def setTabText(self, index, text):
        self.titles[index] = text
        self._sync()

    def setTabToolTip(self, index, text):
        self.tips[index] = text

    def _sync(self):
        self.strip.set_tabs(self.titles, self.stack.currentIndex())
        self.strip.setVisible(self.count() > 1)


class SelectionBar(QWidget):
    """Floating capsule with the actions of the current selection."""

    action = Signal(str)

    ACTIONS = (('open', 'open_in_new', 'Abrir · Enter'), ('copy', 'content_copy', 'Copiar · Ctrl+C'),
               ('rename', 'drive_file_rename_outline', 'Cambiar nombre · F2'),
               ('trash', 'delete', 'Eliminar (a la papelera) · Supr'), ('options', 'more_horiz', 'Más opciones · Alt+K'))

    def __init__(self, parent):
        super().__init__(parent)
        self.count = 0
        self.progress = 0.0
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 6, 8, 6)
        row.setSpacing(2)
        self.label_width = 118
        row.addSpacing(self.label_width)
        self.buttons = {}
        for key, symbol, tip in self.ACTIONS:
            button = IconButton(symbol, tip, lambda key=key: self.action.emit(key), size=38)
            self.buttons[key] = button
            row.addWidget(button)
        row.addSpacing(4)
        self.clear = IconButton('close', 'Quitar la selección · Esc', lambda: self.action.emit('clear'), variant='tonal', size=34)
        row.addWidget(self.clear)
        self.anim = QVariantAnimation(self, duration=tokens()['motion_enter'])
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self._move)
        self.setFixedHeight(54)
        self.setFixedWidth(self.sizeHint().width())
        self.hide()

    def set_count(self, count, renamable):
        previous = self.count
        self.count = count
        self.buttons['rename'].setEnabled(renamable)
        self.update()
        if count and not previous:
            self._animate(1.0)
        elif previous and not count:
            self._animate(0.0)

    def _animate(self, target):
        self.anim.stop()
        if reduced_motion(self.window()):
            self._move(target)
            return
        self.anim.setStartValue(self.progress)
        self.anim.setEndValue(target)
        self.anim.start()

    def _move(self, value):
        self.progress = float(value)
        self.setVisible(self.progress > 0.01)
        self.place()

    def place(self):
        parent = self.parentWidget()
        if parent is None:
            return
        rise = round((1 - self.progress) * 24)
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 40 + rise)
        self.raise_()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(max(0.0, min(1.0, self.progress * 1.3)))
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.setPen(color('line_strong'))
        painter.setBrush(color('surface_raised'))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setFont(text_font('small', 650))
        painter.setPen(color('text_strong'))
        text = f'{self.count} seleccionado' + ('' if self.count == 1 else 's')
        painter.drawText(QRect(20, 0, self.label_width - 8, self.height()), Qt.AlignLeft | Qt.AlignVCenter, text)


class StatusLine(QWidget):
    """Counts and free space; an accent segment glides while a job runs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.left, self.right, self.busy, self.phase = '', '', False, 0.0
        self.setFixedHeight(32)
        self.timer = QTimer(self, interval=24)
        self.timer.timeout.connect(self._tick)

    def set_text(self, left, right=''):
        self.left, self.right = left, right
        self.update()

    def set_busy(self, busy):
        self.busy = busy
        if busy:
            self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def _tick(self):
        self.phase = (self.phase + .018) % 1.0
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pad = metric('space_l')
        painter.setFont(text_font('caption', 500))
        painter.setPen(color('muted'))
        painter.drawText(QRect(pad, 0, self.width() // 2, self.height()), Qt.AlignLeft | Qt.AlignVCenter, self.left)
        painter.drawText(QRect(self.width() // 2, 0, self.width() // 2 - pad, self.height()), Qt.AlignRight | Qt.AlignVCenter, self.right)
        if self.busy:
            track = QRectF(pad, 0, self.width() - pad * 2, 3)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('track'))
            painter.drawRoundedRect(track, 1.5, 1.5)
            segment = track.width() * .3
            x = track.left() + (track.width() + segment) * self.phase - segment
            visible = QRectF(max(track.left(), x), 0, min(track.right(), x + segment) - max(track.left(), x), 3)
            painter.setBrush(color('accent'))
            if visible.width() > 0:
                painter.drawRoundedRect(visible, 1.5, 1.5)


class Segmented(QWidget):
    """Two-way icon switch (grid | list) whose thumb glides between the segments."""

    changed = Signal(int)

    def __init__(self, symbols, labels, parent=None):
        super().__init__(parent)
        self.symbols, self.labels, self.index, self.position = symbols, labels, 0, 0.0
        self.setFixedSize(40 * len(symbols) + 8, 40)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('Vista')
        self.anim = QVariantAnimation(self, duration=tokens()['motion_enter'])
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self._glide)
        self.setToolTip(' · '.join(labels))

    def set_index(self, index, animate=True):
        if index == self.index and self.position == index:
            return
        self.index = index
        self.anim.stop()
        if animate and not reduced_motion(self.window()) and self.isVisible():
            self.anim.setStartValue(self.position)
            self.anim.setEndValue(float(index))
            self.anim.start()
        else:
            self._glide(float(index))

    def _glide(self, value):
        self.position = float(value)
        self.update()

    def mouseReleaseEvent(self, event):
        index = min(len(self.symbols) - 1, max(0, int((event.position().x() - 4) // 40)))
        if event.button() == Qt.LeftButton and index != self.index:
            self.set_index(index)
            self.changed.emit(index)

    def keyPressEvent(self, event):
        step = {Qt.Key_Left: -1, Qt.Key_Right: 1}.get(event.key())
        if step and 0 <= self.index + step < len(self.symbols):
            self.set_index(self.index + step)
            self.changed.emit(self.index)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('well'))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        thumb = QRectF(4 + self.position * 40, 4, 40, 32)
        painter.setBrush(color('accent'))
        painter.drawRoundedRect(thumb, 16, 16)
        for number, symbol in enumerate(self.symbols):
            near = max(0.0, 1 - abs(self.position - number))
            cell = QRectF(4 + number * 40, 4, 40, 32)
            paint_symbol(painter, cell, symbol, 'on_accent' if near > .5 else 'glyph', 20, filled=near > .5 and False)
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(color('focus'))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(track.adjusted(1, 1, -1, -1), track.height() / 2 - 1, track.height() / 2 - 1)


class Hero(QWidget):
    """Folder title with a slowly turning cookie, counts, and the kind filter chips."""

    kind_changed = Signal(str)
    KINDS = (('all', 'Todo'), ('folders', 'Carpetas'), ('images', 'Imágenes'), ('videos', 'Vídeos'), ('audio', 'Audio'),
             ('documents', 'Documentos'), ('code', 'Código'))

    def __init__(self, parent=None):
        super().__init__(parent)
        from .kit import Chip
        self.title, self.subtitle, self.rotation, self.glyph = '', '', 0.0, 'folder'
        self.setFixedHeight(112)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 70, 0, 4)
        row.setSpacing(6)
        self.chips = {}
        for key, label in self.KINDS:
            chip = Chip(label)
            chip.setChecked(key == 'all')
            chip.clicked.connect(lambda _=False, key=key: self._pick(key))
            self.chips[key] = chip
            row.addWidget(chip, 0, Qt.AlignVCenter)
        row.addStretch()
        self.spin = QVariantAnimation(self, duration=700)
        self.spin.setStartValue(0.0)
        self.spin.setEndValue(360.0)
        self.spin.setEasingCurve(QEasingCurve.OutCubic)
        self.spin.valueChanged.connect(self._turn)

    def _pick(self, key):
        for name, chip in self.chips.items():
            chip.setChecked(name == key)
        self.kind_changed.emit(key)

    def show_kind(self, kind):
        for name, chip in self.chips.items():
            chip.setChecked(name == kind)

    def set_info(self, title, subtitle):
        changed = title != self.title
        self.title, self.subtitle = title, subtitle
        self.update()
        if changed and self.isVisible() and not reduced_motion(self.window()):
            self.spin.stop()               # one graceful turn per folder instead of a constant spin
            self.spin.start()

    def _turn(self, value):
        self.rotation = float(value)
        self.update(QRect(0, 0, 64, 69))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        used = 0
        for chip in self.chips.values():                 # hide the tail that does not fit
            used += chip.sizeHint().width() + 6
            chip.setVisible(used <= self.width())

    def paintEvent(self, event):
        from .kit import cookie
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        box = QRectF(0, 12, 52, 52)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('accent', 60))
        painter.drawPath(cookie(box.adjusted(-3, -3, 3, 3), 12, -self.rotation * .5))
        painter.setBrush(color('accent'))
        painter.drawPath(cookie(box, 12, self.rotation))
        paint_symbol(painter, box, self.glyph, 'on_accent', 26, filled=True)
        if event.rect().right() < 66:
            return                                   # spin frames only repaint the cookie
        left = 66
        painter.setFont(text_font('title', 700, .95))
        painter.setPen(color('text_strong'))
        room = self.width() - left - 12
        painter.drawText(QRect(left, 8, max(80, room), 36), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self.title, Qt.ElideRight, max(80, room)))
        painter.setFont(text_font('small', 450))
        painter.setPen(color('muted'))
        painter.drawText(QRect(left, 44, max(80, room), 22), Qt.AlignLeft | Qt.AlignVCenter, self.subtitle)
