"""Music's artwork pieces: cover art, its shadow and the placeholders for missing covers."""
import math

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QPixmapCache, QRadialGradient
from PySide6.QtWidgets import QAbstractButton, QLabel, QSizePolicy, QWidget

from wysun_core.qt_theme import color, tokens
from wysun_core.ui.motion import reduced_motion
from wysun_core.ui.shapes import artwork, clip_pixmap, cookie
from wysun_core.ui.style import metric, text_font
from wysun_core.ui.style import paint_symbol
class CoverArt(QWidget):
    """Artwork of a track or collection with a tonal placeholder.

    ``shape`` is ``square`` (themed radius), ``round`` or ``cookie``; a cookie
    can spin slowly while audio plays, like the shell media widget's cover.
    """

    clicked = Signal()
    turned = Signal()  # each spin step, for effects that move in step with the record

    SPIN_SECONDS = 23.5  # one turn, same pace as the shell's Cookie12Sided cover

    def __init__(self, covers, size=56, round_shape=False, parent=None, shape=None):
        super().__init__(parent)
        self.covers = covers
        self.shape = shape or ('round' if round_shape else 'square')
        self.key = None
        self.collection = None
        self.placeholder = 'music_note'
        self.rotation = 0.0
        self._spinning = False
        self._spin = QTimer(self, interval=50)
        self._spin.timeout.connect(self._turn)
        self.setFixedSize(size, size)
        covers.updated.connect(self._updated)

    @property
    def round_shape(self):
        return self.shape == 'round'

    def set_track(self, key):
        self.key, self.collection = key, None
        self.update()

    def set_collection(self, collection, placeholder='queue_music'):
        self.key, self.collection = None, collection
        self.placeholder = placeholder
        self.update()

    def set_spinning(self, spinning):
        self._spinning = spinning and self.shape == 'cookie'
        self._sync_spin()

    def _sync_spin(self):
        if self._spinning and self.isVisible() and not reduced_motion(self.window()):
            self._spin.start()
        else:
            self._spin.stop()

    def _turn(self):
        self.rotation = (self.rotation - 360 * self._spin.interval() / 1000 / self.SPIN_SECONDS) % 360
        self.update()
        self.turned.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_spin()

    def hideEvent(self, event):
        self._spin.stop()
        super().hideEvent(event)

    def _updated(self, key):
        if key == self.key or (self.collection and (key == self.collection.id or key in self.collection.keys[:12])):
            self.update()

    def radius(self):
        return self.width() / 2 if self.shape != 'square' else min(tokens()['rounding.medium'], self.width() / 6)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        size, ratio = self.width(), self.devicePixelRatioF()
        if self.shape == 'cookie':
            inset = max(1, size * .04)  # room for the soft shadow
            outline = cookie(QRectF(self.rect()).adjusted(inset, inset, -inset, -inset), 12, self.rotation)
            painter.setPen(Qt.NoPen)
            # A turning cookie casts an almost round shadow: one cached soft disc.
            painter.drawPixmap(0, 0, soft_shadow(size, inset, self.devicePixelRatioF()))
            path = self.covers.path(self.key) if self.key else None
            pixmap = artwork(path, size, ratio) if path else None
            if pixmap is not None:
                # The artwork stays upright; only the scalloped mask turns.
                clip_pixmap(pixmap, outline, painter, QRectF(self.rect()).adjusted(inset, inset, -inset, -inset))
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color('surface_raised'))
                painter.drawPath(outline)
                paint_symbol(painter, QRectF(self.rect()), self.placeholder, 'subtle', size * .36)
            return
        radius = self.radius()
        if self.collection is not None:
            pixmap = self.covers.collection_pixmap(self.collection, size, radius, ratio)
        else:
            pixmap = self.covers.pixmap(self.key, size, radius, ratio) if self.key else None
        if pixmap is not None:
            painter.drawPixmap(0, 0, pixmap)
            return
        paint_placeholder(painter, QRectF(self.rect()), radius, self.placeholder)


def soft_shadow(size, inset, ratio):
    """Blurred round shadow under a ``size`` square cover, cached per theme."""
    shade = color('shadow')
    key = f'wm-shadow:{size}:{inset}:{ratio}:{shade.name(QColor.HexArgb)}'
    found = QPixmapCache.find(key)
    if found is not None and not found.isNull():
        return found
    pixmap = QPixmap(round(size * ratio), round(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    centre = QPointF(size / 2, size / 2 + inset * .7)
    gradient = QRadialGradient(centre, size / 2)
    solid, clear = QColor(shade), QColor(shade)
    clear.setAlpha(0)
    gradient.setColorAt(.86, solid)
    gradient.setColorAt(1, clear)
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawEllipse(centre, size / 2, size / 2)
    painter.end()
    QPixmapCache.insert(key, pixmap)
    return pixmap


def draw_art(painter, rect, pixmap, radius, symbol='music_note'):
    """Artwork when it is loaded, otherwise the tonal placeholder."""
    if pixmap is not None:
        painter.drawPixmap(rect.topLeft(), pixmap)
    else:
        paint_placeholder(painter, QRectF(rect), radius, symbol)


def paint_favorites_cover(painter, rect, radius):
    """"Tus me gusta" artwork: accent tile with a filled heart."""
    painter.setPen(Qt.NoPen)
    painter.setBrush(color('accent'))
    painter.drawRoundedRect(rect, radius, radius)
    paint_symbol(painter, rect, 'favorite', 'on_accent', rect.height() * .45, filled=True)


def paint_placeholder(painter, rect, radius, symbol='music_note'):
    painter.setPen(Qt.NoPen)
    painter.setBrush(color('surface_raised'))
    painter.drawRoundedRect(rect, radius, radius)
    painter.setBrush(color('tint', 10))
    painter.drawRoundedRect(rect, radius, radius)
    paint_symbol(painter, rect, symbol, 'subtle', rect.height() * .42)


