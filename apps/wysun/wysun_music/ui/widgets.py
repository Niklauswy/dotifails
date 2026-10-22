"""Painted Material 3 controls shared by every Music surface.

They mirror the shell media widget (Details.qml / StyledSlider): round tonal
icon buttons, a filled play button, a wavy progress line while playing.
"""
import math

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QPixmapCache, QRadialGradient
from PySide6.QtWidgets import QAbstractButton, QLabel, QSizePolicy, QWidget

from theme_tokens import color, tokens
from ui_motion import reduced_motion
from .shapes import artwork, clip_pixmap, cookie, squircle
from .style import metric, paint_symbol, text_font

VARIANTS = ('ghost', 'tonal', 'filled')


class StateLayer:
    """Hover/press amount animated with the theme's fast motion token."""

    def __init__(self, widget):
        self.widget = widget
        self.amount = 0.0
        self.animation = QVariantAnimation(widget)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self._set)

    def _set(self, value):
        self.amount = float(value)
        self.widget.update()

    def to(self, target):
        self.animation.stop()
        if reduced_motion(self.widget.window()):
            self._set(target)
            return
        self.animation.setDuration(metric('motion_fast'))
        self.animation.setStartValue(self.amount)
        self.animation.setEndValue(float(target))
        self.animation.start()


class IconButton(QAbstractButton):
    """Round icon button: ``ghost`` (bare), ``tonal`` (container) or ``filled`` (accent).

    Filled buttons morph like M3 Expressive media controls: a circle while
    paused, a soft square while the ``pause`` symbol shows (audio playing).
    """

    def __init__(self, symbol, label, callback=None, variant='ghost', size=36, checkable=False,
                 dot=False, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.variant = variant
        self.dot = dot  # small "active" dot under checkable toggles
        self.outline = False  # keep the outlined glyph when checked/filled (glyphs with inner detail)
        self.icon_scale = .6
        self.layer = StateLayer(self)
        self.shape = StateLayer(self)  # 0 = circle, 1 = squircle
        self.setCheckable(checkable)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.set_label(label)
        if callback:
            self.clicked.connect(lambda _=False: callback())

    def set_label(self, label):
        self.setToolTip(label)
        self.setAccessibleName(label.split(' · ')[0])

    def set_symbol(self, symbol):
        if symbol != self.symbol:
            self.symbol = symbol
            if self.variant == 'filled':
                self.shape.to(1.0 if symbol == 'pause' else 0.0)
            self.update()

    def sizeHint(self):
        return self.size()

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.isDown():
            scale = .94
            painter.translate(rect.center())
            painter.scale(scale, scale)
            painter.translate(-rect.center())
        active = self.isChecked()
        if self.variant == 'filled':
            background, ink = ('accent', 'on_accent') if self.isEnabled() else ('disabled_surface', 'disabled')
        elif self.variant == 'tonal':
            background, ink = ('selection', 'selection_text') if active else ('fill', 'glyph')
        else:
            background, ink = None, 'accent' if active else 'glyph'
        if not self.isEnabled():
            ink = 'disabled'
        painter.setPen(Qt.NoPen)
        outline = squircle(rect, 1 - self.shape.amount)
        if self.shape.amount < .01:
            outline = QPainterPath()
            outline.addEllipse(rect)
        if background:
            painter.setBrush(color(background))
            painter.drawPath(outline)
        if self.layer.amount and self.isEnabled():
            painter.setBrush(color('tint', round(18 * self.layer.amount)))
            painter.drawPath(outline)
        if self.hasFocus() and self.focusPolicy() != Qt.NoFocus and self.window().isActiveWindow():
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(outline)
        icon_rect = rect.adjusted(0, -2, 0, -2) if self.dot and active else rect
        paint_symbol(painter, icon_rect, self.symbol, ink, rect.height() * self.icon_scale,
                     filled=(active or self.variant == 'filled') and not self.outline)
        if self.dot and active:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('accent'))
            painter.drawEllipse(QPointF(rect.center().x(), rect.bottom() - 3), 2, 2)


class PillButton(QAbstractButton):
    """Text button with a leading symbol: ``filled`` (accent) or ``tonal``."""

    def __init__(self, symbol, label, callback=None, variant='filled', height=44, parent=None):
        super().__init__(parent)
        self.symbol, self.variant = symbol, variant
        self.layer = StateLayer(self)
        self.setText(label)
        self.setAccessibleName(label)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFont(text_font('body', 600))
        self.setFixedHeight(height)
        if callback:
            self.clicked.connect(lambda _=False: callback())

    def set_content(self, symbol, label):
        self.symbol = symbol
        self.setText(label)
        self.setAccessibleName(label)
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        icon = round(self.height() * .5)
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + icon + metric('space_l') * 2 + metric('space_s'),
                     self.height())

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        if self.isDown():
            painter.translate(rect.center())
            painter.scale(.97, .97)
            painter.translate(-rect.center())
        radius = rect.height() / 2
        if self.variant == 'filled':
            background, ink = ('accent', 'on_accent') if self.isEnabled() else ('disabled_surface', 'disabled')
        else:
            background, ink = ('fill', 'text') if self.isEnabled() else ('disabled_surface', 'disabled')
        painter.setPen(Qt.NoPen)
        painter.setBrush(color(background))
        painter.drawRoundedRect(rect, radius, radius)
        if self.layer.amount and self.isEnabled():
            painter.setBrush(color('tint', round(18 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
        icon = round(rect.height() * .5)
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        left = rect.center().x() - (icon + metric('space_s') + text_width) / 2
        paint_symbol(painter, QRectF(left, 0, icon, self.height()), self.symbol, ink, icon, filled=True)
        painter.setFont(self.font())
        painter.setPen(color(ink))
        painter.drawText(QRectF(left + icon + metric('space_s'), 0, text_width + 2, self.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, self.text())


class Chip(QAbstractButton):
    """Pill filter toggle."""

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setText(label)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.layer = StateLayer(self)
        self.setFont(text_font('small', 500))
        self.setFixedHeight(32)

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + metric('space_l', 2), 32)

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        radius = rect.height() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('accent' if self.isChecked() else 'fill'))
        painter.drawRoundedRect(rect, radius, radius)
        if self.layer.amount:
            painter.setBrush(color('tint', round(16 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        if not self.isChecked():
            painter.setPen(QPen(color('line'), tokens()['border']))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(color('on_accent' if self.isChecked() else 'text'))
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignCenter, self.text())


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
        return self.width() / 2 if self.shape != 'square' else min(tokens()['radius_m'], self.width() / 6)

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


class Slider(QWidget):
    """Horizontal value 0..1 with hover handle; optional animated wave (progress)."""

    moved = Signal(float)      # while dragging, for live labels
    released = Signal(float)   # committed value

    WAVE_LENGTH = 26.0
    WAVE_AMPLITUDE = 2.6

    def __init__(self, label, wavy=False, step=.05, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.wavy = wavy
        self.step = step
        self.dragging = False
        self.animate_wave = False
        self.phase = 0.0
        self.wave_amount = 0.0
        self.layer = StateLayer(self)
        self._wave_timer = QTimer(self, interval=33)
        self._wave_timer.timeout.connect(self._tick)
        self.setAccessibleName(label)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(20)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value):
        if self.dragging:
            return
        value = max(0.0, min(1.0, value))
        if abs(value - self.value) * max(1, self.width()) >= .5:
            self.value = value
            self.update()

    def set_playing(self, playing):
        """The wave animates only while audio plays and the slider is visible."""
        self.animate_wave = self.wavy and playing
        self._sync_timer()

    def _sync_timer(self):
        if reduced_motion(self.window()):
            # Static wave: still tells "playing" apart from "paused", without motion.
            self._wave_timer.stop()
            self.wave_amount = 1.0 if self.animate_wave else 0.0
            self.update()
            return
        if self.isVisible() and (self.animate_wave or self.wave_amount):
            self._wave_timer.start()
        else:
            self._wave_timer.stop()

    def _tick(self):
        target = 1.0 if self.animate_wave else 0.0
        self.wave_amount += (target - self.wave_amount) * .18
        if abs(target - self.wave_amount) < .02:
            self.wave_amount = target
        if self.animate_wave:
            self.phase = (self.phase + .19) % (2 * math.pi)
        self.update()
        if not self.animate_wave and not self.wave_amount:
            self._wave_timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        self._wave_timer.stop()
        super().hideEvent(event)

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.dragging:
            self.layer.to(0.0)
        super().leaveEvent(event)

    def _value_at(self, x):
        margin = self.height() / 2
        return max(0.0, min(1.0, (x - margin) / max(1.0, self.width() - 2 * margin)))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.dragging = True
            self.value = self._value_at(event.position().x())
            self.moved.emit(self.value)
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.value = self._value_at(event.position().x())
            self.moved.emit(self.value)
            self.update()

    def mouseReleaseEvent(self, event):
        if self.dragging and event.button() == Qt.LeftButton:
            self.dragging = False
            self.value = self._value_at(event.position().x())
            self.released.emit(self.value)
            if not self.underMouse():
                self.layer.to(0.0)
            self.update()

    def wheelEvent(self, event):
        if not self.wavy and self.isEnabled():
            self.value = max(0.0, min(1.0, self.value + (self.step if event.angleDelta().y() > 0 else -self.step)))
            self.released.emit(self.value)
            self.update()
            event.accept()

    def keyPressEvent(self, event):
        steps = {Qt.Key_Left: -self.step, Qt.Key_Down: -self.step, Qt.Key_Right: self.step, Qt.Key_Up: self.step}
        if event.key() in steps and self.isEnabled():
            self.value = max(0.0, min(1.0, self.value + steps[event.key()]))
            self.released.emit(self.value)
            self.update()
        elif event.key() in (Qt.Key_Home, Qt.Key_End):
            self.value = 0.0 if event.key() == Qt.Key_Home else 1.0
            self.released.emit(self.value)
            self.update()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        hover = self.layer.amount if self.isEnabled() else 0.0
        thickness = 4 + 2 * hover
        margin = self.height() / 2
        y = self.height() / 2
        start, end = margin, self.width() - margin
        x = start + (end - start) * self.value
        active = color('accent' if self.isEnabled() else 'disabled')
        gap = 6 if self.wavy else 0
        painter.setPen(QPen(color('track'), thickness, Qt.SolidLine, Qt.RoundCap))
        if x + gap < end:
            painter.drawLine(QPointF(min(end, x + gap), y), QPointF(end, y))
        pen = QPen(active, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        if x > start:
            amplitude = self.WAVE_AMPLITUDE * self.wave_amount
            if amplitude > .05:
                path = QPainterPath(QPointF(start, y))
                step = 2.0
                position = start
                while position < x:
                    position = min(x, position + step)
                    angle = (position - start) / self.WAVE_LENGTH * 2 * math.pi - self.phase
                    path.lineTo(position, y + math.sin(angle) * amplitude)
                painter.drawPath(path)
            else:
                painter.drawLine(QPointF(start, y), QPointF(x, y))
        if self.wavy:
            # M3 progress: a vertical bar handle, like the shell slider.
            painter.setPen(QPen(active, 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(x, y - 7 - 2 * hover), QPointF(x, y + 7 + 2 * hover))
        elif hover or self.dragging or self.hasFocus():
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('slider_handle'))
            painter.drawEllipse(QPointF(x, y), 6, 6)
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(QPen(color('focus'), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(x, y), 9, 9)


class ElidedLabel(QLabel):
    """One line, elided, with the complete text in tooltip and accessible name."""

    def __init__(self, text='', role='body', weight=400, tint='text', scale=1.0, parent=None):
        super().__init__(parent)
        self._full = ''
        self.tint = tint
        self.role, self.weight, self.scale = role, weight, scale
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.setTextFormat(Qt.PlainText)
        self.refresh_font()
        self.setText(text)

    def refresh_font(self):
        """Fonts follow the theme's type scale; colours are read while painting."""
        self.setFont(text_font(self.role, self.weight, self.scale))

    def setText(self, text):
        self._full = str(text)
        self.setToolTip(self._full if len(self._full) > 24 else '')
        self.setAccessibleName(self._full)
        self.update()

    def text(self):
        return self._full

    def sizeHint(self):
        return QSize(80, self.fontMetrics().height() + 2)

    def minimumSizeHint(self):
        return QSize(0, self.fontMetrics().height() + 2)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(color(self.tint) if isinstance(self.tint, str) else self.tint)
        text = self.fontMetrics().elidedText(self._full, Qt.ElideRight, self.width())
        painter.drawText(self.rect(), int(self.alignment() or (Qt.AlignLeft | Qt.AlignVCenter)), text)


class LinkLabel(ElidedLabel):
    """Elided label that underlines on hover and emits ``activated``."""

    activated = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.hovered = False

    def enterEvent(self, event):
        self.hovered = True
        self._underline()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self._underline()
        super().leaveEvent(event)

    def _underline(self):
        font = self.font()
        font.setUnderline(self.hovered)
        self.setFont(font)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.activated.emit()
        super().mouseReleaseEvent(event)
