"""Playback timeline: click anywhere to jump, drag from anywhere to scrub."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QToolTip, QWidget
from .tokens import color


def clock(seconds):
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    return f'{hours}:{rest // 60:02}:{rest % 60:02}' if hours else f'{rest // 60}:{rest % 60:02}'


class SeekBar(QWidget):
    """A tall hit area around a thin track; emits seconds, never fractions."""
    seekRequested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 0.
        self.position = 0.
        self._drag = None
        self._hover = None
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(28)
        self.setAccessibleName('Posición de reproducción')

    def isSliderDown(self):
        return self._drag is not None

    def set_duration(self, seconds):
        self.duration = max(0., float(seconds or 0))
        self.update()

    def set_position(self, seconds):
        if self._drag is None:
            self.position = min(max(0., float(seconds or 0)), self.duration or float(seconds or 0))
            self.update()

    def _track(self):
        return QRectF(8, self.height() / 2 - 2, max(1., self.width() - 16), 4)

    def _seconds_at(self, x):
        track = self._track()
        ratio = min(1., max(0., (x - track.left()) / track.width()))
        return ratio * self.duration

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self.duration:
            return
        self._drag = self._seconds_at(event.position().x())
        self.position = self._drag
        self.seekRequested.emit(self._drag)
        self.update()

    def mouseMoveEvent(self, event):
        self._hover = event.position().x()
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            self._drag = self._seconds_at(event.position().x())
            self.position = self._drag
            self.seekRequested.emit(self._drag)
        if self.duration:
            QToolTip.showText(event.globalPosition().toPoint(), clock(self._seconds_at(event.position().x())), self)
        self.update()

    def mouseReleaseEvent(self, event):
        if self._drag is not None:
            self.seekRequested.emit(self._drag)
            self._drag = None
            self.update()

    def leaveEvent(self, event):
        self._hover = None
        self.update()

    def keyPressEvent(self, event):
        step = {Qt.Key_Left: -5, Qt.Key_Right: 5, Qt.Key_Home: -10 ** 9, Qt.Key_End: 10 ** 9}.get(event.key())
        if step is None or not self.duration:
            return super().keyPressEvent(event)
        self.position = min(self.duration, max(0., self.position + step))
        self.seekRequested.emit(self.position)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        track = self._track()
        active = self._hover is not None or self._drag is not None or self.hasFocus()
        if active:
            track = track.adjusted(0, -1, 0, 1)
        painter.setBrush(color('track'))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        if self._hover is not None and self.duration:
            hover = QRectF(track.left(), track.top(), min(track.width(), max(0., self._hover - track.left())), track.height())
            painter.setBrush(color('line_strong'))
            painter.drawRoundedRect(hover, track.height() / 2, track.height() / 2)
        ratio = self.position / self.duration if self.duration else 0.
        done = QRectF(track.left(), track.top(), track.width() * min(1., ratio), track.height())
        painter.setBrush(color('accent'))
        painter.drawRoundedRect(done, track.height() / 2, track.height() / 2)
        if self.duration:
            radius = 7 if active else 5
            painter.setBrush(color('surface'))
            painter.setPen(color('focus') if self.hasFocus() else color('accent'))
            painter.drawEllipse(QPointF(done.right(), track.center().y()), radius, radius)
