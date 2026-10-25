"""The stage for audio files: cover art (or a note) in a cookie that turns slowly while the music plays."""
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from . import host, shape

TURN_DEGREES_PER_SECOND = 360 / 24
FRAME_MS = 50


class AudioStage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cover = None
        self.title = self.subtitle = ''
        self.rotation = 0.0
        self.playing = False
        self._timer = QTimer(self, interval=FRAME_MS)
        self._timer.timeout.connect(self._turn)

    def set_cover(self, image):
        self.cover = QPixmap.fromImage(image) if image is not None and not image.isNull() else None
        self.update()

    def set_text(self, title, subtitle=''):
        self.title, self.subtitle = title, subtitle
        self.update()

    def set_playing(self, playing):
        self.playing = playing
        self._sync()

    def _sync(self):
        if self.playing and self.isVisible() and not host.get().reduced_motion():
            self._timer.start()
        else:
            self._timer.stop()

    def _turn(self):
        self.rotation = (self.rotation + TURN_DEGREES_PER_SECOND * FRAME_MS / 1000) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _event):
        h = host.get()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), h.color('well'))
        space = float(h.token('space_xl'))
        text_height = float(h.token('space_xl')) * 2.2
        side = max(40.0, min(self.width() - 2 * space, self.height() - 2 * space - text_height - self._bar_room(), 360.0))
        box = QRectF(0, 0, side, side)
        box.moveCenter(QRectF(self.rect()).center())
        box.moveTop(max(space, (self.height() - side - text_height - self._bar_room()) / 2))
        painter.setPen(Qt.NoPen)
        painter.setBrush(h.color('accent', 28))
        painter.drawPath(shape.cookie(box.adjusted(-space / 2, -space / 2, space / 2, space / 2), 12, -self.rotation * .6))
        outline = shape.cookie(box, 12, self.rotation)
        if self.cover is not None:
            painter.save()
            painter.setClipPath(outline)
            painter.drawPixmap(box, self.cover, QRectF(self._square(self.cover)))
            painter.restore()
        else:
            painter.setBrush(h.color('tile'))
            painter.drawPath(outline)
            painter.setBrush(h.color('accent', 38))
            painter.drawPath(outline)
            h.symbol(painter, box, 'music_note', 'accent', round(side * .36), True)
        top = box.bottom() + space / 2 + space
        painter.setPen(h.color('text_strong'))
        painter.setFont(h.font('heading', 650))
        painter.drawText(QRectF(space, top, self.width() - 2 * space, space * 1.2), Qt.AlignHCenter | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self.title, Qt.ElideMiddle, int(self.width() - 2 * space)))
        if self.subtitle:
            painter.setPen(h.color('muted'))
            painter.setFont(h.font('small'))
            painter.drawText(QRectF(space, top + space * 1.2, self.width() - 2 * space, space), Qt.AlignHCenter | Qt.AlignVCenter,
                             painter.fontMetrics().elidedText(self.subtitle, Qt.ElideRight, int(self.width() - 2 * space)))

    def _bar_room(self):
        return float(getattr(self, 'reserve', 0))

    @staticmethod
    def _square(pixmap):
        side = min(pixmap.width(), pixmap.height())
        return QRectF((pixmap.width() - side) / 2, (pixmap.height() - side) / 2, side, side)
