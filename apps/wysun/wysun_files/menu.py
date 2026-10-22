"""Material action menu: rounded raised card, symbol + label + keycaps, a pill that glides between rows.

Fully keyboard driven (arrows, Home/End, Enter, Esc) and animated in with a short lift and fade.
"""
from PySide6.QtCore import QEasingCurve, QPoint, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QFontMetrics, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

from theme_tokens import color, tokens
from ui_motion import reduced_motion
from .kit import metric, paint_symbol, text_font

ROW = 40
SEPARATOR = 13
PAD = 8


class ActionMenu(QWidget):
    triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.entries = []          # dicts: symbol, text, callback, keys, enabled, danger, checked | {'separator': True}
        self.index = -1
        self.pill = QRectF()
        self.progress = 1.0
        self.glide = QVariantAnimation(self, duration=tokens()['motion_fast'] + 60)
        self.glide.setEasingCurve(QEasingCurve.OutCubic)
        self.glide.valueChanged.connect(self._glide_step)
        self._from = self._to = QRectF()
        self.intro = QVariantAnimation(self, duration=tokens()['motion_enter'])
        self.intro.setEasingCurve(QEasingCurve.OutCubic)
        self.intro.setStartValue(0.0)
        self.intro.setEndValue(1.0)
        self.intro.valueChanged.connect(self._intro_step)

    # ------------------------------------------------------------- building
    def add(self, symbol, text, callback, keys='', enabled=True, danger=False, checked=False):
        self.entries.append(dict(symbol=symbol, text=text, callback=callback, keys=keys, enabled=enabled, danger=danger,
                                 checked=checked, separator=False))
        return self

    def separator(self):
        if self.entries and not self.entries[-1]['separator']:
            self.entries.append(dict(separator=True))
        return self

    def _rows(self):
        """[(entry index, QRectF)] laid out top to bottom."""
        top, rows = PAD, []
        for number, entry in enumerate(self.entries):
            height = SEPARATOR if entry['separator'] else ROW
            rows.append((number, QRectF(PAD, top, self.width() - PAD * 2, height)))
            top += height
        return rows

    def _measure(self):
        font = text_font('body', 500)
        keys_font = text_font('caption', 650)
        label = QFontMetrics(font)
        caps = QFontMetrics(keys_font)
        widest = 0
        for entry in self.entries:
            if entry['separator']:
                continue
            keys = self._caps(entry['keys'])
            keys_width = sum(caps.horizontalAdvance(k) + 16 + 4 for k in keys)
            widest = max(widest, label.horizontalAdvance(entry['text']) + (keys_width + 20 if keys else 0))
        width = max(250, widest + 52 + PAD * 2 + 24)
        height = PAD * 2 + sum(SEPARATOR if e['separator'] else ROW for e in self.entries)
        return QSize(width, height)

    @staticmethod
    def _caps(keys):
        return [k for k in keys.replace(' + ', '+').split('+') if k] if keys else []

    # ---------------------------------------------------------------- showing
    def popup(self, point):
        size = self._measure()
        self.resize(size)
        screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = min(max(area.left() + 6, point.x()), area.right() - size.width() - 6)
        y = point.y() if point.y() + size.height() <= area.bottom() - 6 else max(area.top() + 6, point.y() - size.height())
        self.move(x, y)
        self.index = next((n for n, e in enumerate(self.entries) if not e['separator'] and e['enabled']), -1)
        self.pill = self._rect_of(self.index)
        self.show()
        self.setFocus()
        if reduced_motion(self.window()):
            self._intro_step(1.0)
        else:
            self._intro_step(0.0)
            self.intro.start()

    exec = popup

    def _intro_step(self, value):
        self.progress = float(value)
        self.update()

    def _rect_of(self, index):
        for number, rect in self._rows():
            if number == index:
                return QRectF(rect)
        return QRectF()

    # -------------------------------------------------------------- selection
    def _select(self, index):
        if index == self.index or not 0 <= index < len(self.entries):
            return
        self.index = index
        target = self._rect_of(index)
        self.glide.stop()
        if reduced_motion(self.window()) or self.pill.isNull():
            self.pill = target
            self.update()
            return
        self._from, self._to = QRectF(self.pill), target
        self.glide.setStartValue(0.0)
        self.glide.setEndValue(1.0)
        self.glide.start()

    def _glide_step(self, t):
        t = float(t)
        a, b = self._from, self._to
        self.pill = QRectF(a.left() + (b.left() - a.left()) * t, a.top() + (b.top() - a.top()) * t, b.width(),
                           a.height() + (b.height() - a.height()) * t)
        self.update()

    def _step(self, direction):
        index = self.index
        for _ in range(len(self.entries)):
            index = (index + direction) % len(self.entries)
            entry = self.entries[index]
            if not entry['separator'] and entry['enabled']:
                self._select(index)
                return

    def _activate(self, index):
        entry = self.entries[index] if 0 <= index < len(self.entries) else None
        if entry and not entry['separator'] and entry['enabled']:
            callback = entry['callback']
            self.close()
            QTimer.singleShot(0, callback)       # after the popup is gone, so dialogs can take focus

    # ------------------------------------------------------------------ input
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Down:
            self._step(1)
        elif key == Qt.Key_Up:
            self._step(-1)
        elif key in (Qt.Key_Home, Qt.Key_PageUp):
            self.index = -1
            self._step(1)
        elif key in (Qt.Key_End, Qt.Key_PageDown):
            self.index = 0
            self._step(-1)
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_Right):
            self._activate(self.index)
        elif key in (Qt.Key_Escape, Qt.Key_Left):
            self.close()
        else:
            text = event.text().lower()
            if text:                                 # first letter jumps to the next matching row
                for offset in range(1, len(self.entries) + 1):
                    number = (self.index + offset) % len(self.entries)
                    entry = self.entries[number]
                    if not entry['separator'] and entry['enabled'] and entry['text'].lower().startswith(text):
                        self._select(number)
                        break

    def mouseMoveEvent(self, event):
        for number, rect in self._rows():
            entry = self.entries[number]
            if rect.contains(event.position()) and not entry['separator'] and entry['enabled']:
                self._select(number)
                return

    def mouseReleaseEvent(self, event):
        for number, rect in self._rows():
            if rect.contains(event.position()) and event.button() == Qt.LeftButton:
                self._activate(number)
                return

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        p = self.progress
        painter.setOpacity(min(1.0, p * 1.4))
        painter.translate(0, -8 * (1 - p))
        outer = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        radius = tokens()['radius_l'] + 2
        painter.setPen(color('line_strong'))
        painter.setBrush(color('surface_raised'))
        painter.drawRoundedRect(outer, radius, radius)
        if not self.pill.isNull():
            painter.setPen(Qt.NoPen)
            danger = 0 <= self.index < len(self.entries) and self.entries[self.index].get('danger')
            painter.setBrush(color('danger_soft', 70) if danger else color('nav_selected'))
            painter.drawRoundedRect(self.pill, 16, 16)
        caps_font = text_font('caption', 650)
        for number, rect in self._rows():
            entry = self.entries[number]
            if entry['separator']:
                painter.setPen(color('divider'))
                painter.drawLine(int(rect.left() + 10), int(rect.center().y()), int(rect.right() - 10), int(rect.center().y()))
                continue
            ink = 'disabled' if not entry['enabled'] else 'danger' if entry['danger'] else 'text_strong' if number == self.index else 'text'
            paint_symbol(painter, QRectF(rect.left() + 8, rect.top(), 28, rect.height()), 'check' if entry['checked'] else entry['symbol'],
                         ink if not entry['checked'] else 'accent', 20, filled=number == self.index and entry['symbol'] in ('folder', 'delete'))
            painter.setFont(text_font('body', 600 if number == self.index else 500))
            painter.setPen(color(ink))
            painter.drawText(QRectF(rect.left() + 46, rect.top(), rect.width() - 60, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, entry['text'])
            right = rect.right() - 12
            painter.setFont(caps_font)
            metrics = painter.fontMetrics()
            for key in reversed(self._caps(entry['keys'])):
                width = metrics.horizontalAdvance(key) + 16
                cap = QRectF(right - width, rect.center().y() - 11, width, 22)
                painter.setPen(Qt.NoPen)
                painter.setBrush(color('tint', 24 if number == self.index else 16))
                painter.drawRoundedRect(cap, 7, 7)
                painter.setPen(color('disabled' if not entry['enabled'] else 'muted'))
                painter.drawText(cap, Qt.AlignCenter, key)
                right -= width + 4
