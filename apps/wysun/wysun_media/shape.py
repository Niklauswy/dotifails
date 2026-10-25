"""Material 3 shape: the corner scale from the theme tokens, drawn as paths, and morphing between corners.

Corner radii come from ``corner_none … corner_full`` of the theme tokens.
"""
import math
from functools import lru_cache

from PySide6.QtCore import QEasingCurve, QObject, QPointF, QRectF, QVariantAnimation, Signal
from PySide6.QtGui import QPainterPath, QTransform

from . import host

CORNERS = ('none', 'xs', 's', 'm', 'l', 'xl', 'full')


def radius(corner, rect=None):
    """Pixels for a scale step (``'l'``), clamped to half the shorter side of ``rect`` when given."""
    value = float(host.get().token('corner_' + corner)) if isinstance(corner, str) else float(corner)
    if rect is not None:
        value = min(value, min(rect.width(), rect.height()) / 2)
    return value


def rounded(rect, corner='m', *, top=True, bottom=True):
    """Rounded rectangle; ``top=False`` / ``bottom=False`` square off that edge's corners."""
    rect = QRectF(rect)
    r = radius(corner, rect)
    top_r, bottom_r = (r if top else 0.0), (r if bottom else 0.0)
    path = QPainterPath()
    path.moveTo(rect.left() + top_r, rect.top())
    path.lineTo(rect.right() - top_r, rect.top())
    if top_r:
        path.arcTo(QRectF(rect.right() - 2 * top_r, rect.top(), 2 * top_r, 2 * top_r), 90, -90)
    path.lineTo(rect.right(), rect.bottom() - bottom_r)
    if bottom_r:
        path.arcTo(QRectF(rect.right() - 2 * bottom_r, rect.bottom() - 2 * bottom_r, 2 * bottom_r, 2 * bottom_r), 0, -90)
    path.lineTo(rect.left() + bottom_r, rect.bottom())
    if bottom_r:
        path.arcTo(QRectF(rect.left(), rect.bottom() - 2 * bottom_r, 2 * bottom_r, 2 * bottom_r), 270, -90)
    path.lineTo(rect.left(), rect.top() + top_r)
    if top_r:
        path.arcTo(QRectF(rect.left(), rect.top(), 2 * top_r, 2 * top_r), 180, -90)
    path.closeSubpath()
    return path


def frame_outside(rect, corner='xl'):
    """The four corner slivers that lie outside a rounded ``rect``: painted in the parent's colour they
    round the corners of something that cannot be clipped (an OpenGL surface)."""
    outer = QPainterPath()
    outer.addRect(QRectF(rect))
    return outer.subtracted(rounded(rect, corner))


def lerp(a, b, t):
    return a + (b - a) * t


def easing():
    """The theme's motion curve (a QEasingCurve name such as 'OutCubic')."""
    name = str(host.get().token('motion_easing'))
    return QEasingCurve(getattr(QEasingCurve.Type, name, QEasingCurve.Type.OutCubic))


class Morph(QObject):
    """A value that glides between 0 and 1 with the theme's motion tokens; instant with reduced motion."""

    changed = Signal(float)

    def __init__(self, parent=None, speed='motion_fast'):
        super().__init__(parent)
        self.value = 0.0
        self._speed = speed
        self._animation = QVariantAnimation(self)
        self._animation.valueChanged.connect(self._step)

    def _step(self, value):
        self.value = float(value)
        self.changed.emit(self.value)

    def go(self, target):
        target = float(target)
        self._animation.stop()
        if host.get().reduced_motion() or self.value == target:
            self._step(target)
            return
        self._animation.setDuration(int(host.get().token(self._speed)))
        self._animation.setEasingCurve(easing())
        self._animation.setStartValue(self.value)
        self._animation.setEndValue(target)
        self._animation.start()

    def jump(self, target):
        self._animation.stop()
        self._step(float(target))

    @property
    def running(self):
        return self._animation.state() == QVariantAnimation.Running


@lru_cache(maxsize=8)
def _unit_cookie(sides, depth):
    """Cookie of radius 1 at the origin: round lobes and soft valleys (the Material 3 Expressive cookie)."""
    path = QPainterPath()
    steps = sides * 24
    for index in range(steps + 1):
        angle = index / steps * 2 * math.pi
        reach = 1 - depth + depth * (1 + math.cos(sides * angle)) / 2
        point = QPointF(math.cos(angle - math.pi / 2) * reach, math.sin(angle - math.pi / 2) * reach)
        path.moveTo(point) if index == 0 else path.lineTo(point)
    path.closeSubpath()
    return path


def cookie(rect, sides=12, rotation=0.0, depth=0.05):
    """A cookie inscribed in ``rect`` (a square), rotated by ``rotation`` degrees."""
    rect = QRectF(rect)
    transform = QTransform()
    transform.translate(rect.center().x(), rect.center().y())
    transform.rotate(rotation)
    transform.scale(rect.width() / 2, rect.height() / 2)
    return transform.map(_unit_cookie(sides, depth))
