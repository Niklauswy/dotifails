"""Material 3 Expressive shapes and artwork backdrops.

The shell media widget draws its cover in a rotating ``Cookie12Sided`` over
drifting shapes (M3Shapes). Music speaks the same language with plain
QPainterPaths: scalloped cookies for artists and the playing cover, a
circle↔squircle morph for the play button and a blurred artwork backdrop.
"""
from functools import lru_cache
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap, QPixmapCache, QTransform

# Lobes and depth (fraction of the radius) of the cookie variants used here.
COOKIES = {4: .13, 6: .1, 7: .09, 9: .075, 12: .05}


@lru_cache(maxsize=32)
def _unit_cookie(sides, depth):
    """Cookie of radius 1 at the origin: rounded lobes, soft valleys."""
    path = QPainterPath()
    steps = sides * 24
    for index in range(steps + 1):
        angle = index / steps * 2 * math.pi
        # A shallow cosine ripple: round lobes, gentle valleys (M3 Cookie).
        radius = 1 - depth + depth * (1 + math.cos(sides * angle)) / 2
        point = QPointF(math.cos(angle - math.pi / 2) * radius, math.sin(angle - math.pi / 2) * radius)
        if index:
            path.lineTo(point)
        else:
            path.moveTo(point)
    path.closeSubpath()
    return path


def cookie(rect, sides=12, rotation=0.0):
    """Cookie inscribed in ``rect`` (a square), optionally rotated in degrees."""
    rect = QRectF(rect)
    transform = QTransform()
    transform.translate(rect.center().x(), rect.center().y())
    transform.rotate(rotation)
    transform.scale(rect.width() / 2, rect.height() / 2)
    return transform.map(_unit_cookie(sides, COOKIES.get(sides, .1)))


def squircle(rect, roundness):
    """Rounded rectangle from a circle (``roundness`` 1) to a soft square (0)."""
    rect = QRectF(rect)
    side = min(rect.width(), rect.height())
    radius = side * (.28 + .22 * roundness)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def pill(rect):
    rect = QRectF(rect)
    path = QPainterPath()
    path.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
    return path


def clip_pixmap(pixmap, path, painter, target=None):
    """Draw ``pixmap`` over ``target`` (default: the path's bounds), clipped to the shape."""
    painter.save()
    painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    painter.setClipPath(path)
    painter.drawPixmap(QRectF(target) if target is not None else path.boundingRect(), pixmap, QRectF(pixmap.rect()))
    painter.restore()


def artwork(path, side, ratio=1.0):
    """Square, unrounded artwork pixmap (shapes clip it while painting)."""
    key = f'wm-square:{path}:{side}:{ratio}'
    found = QPixmapCache.find(key)
    if found is not None and not found.isNull():
        return found
    image = QImage(path)
    if image.isNull():
        return None
    pixels = max(1, round(side * ratio))
    image = image.scaled(pixels, pixels, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    image = image.copy((image.width() - pixels) // 2, (image.height() - pixels) // 2, pixels, pixels)
    result = QPixmap.fromImage(image)
    result.setDevicePixelRatio(ratio)
    QPixmapCache.insert(key, result)
    return result


def filled(path, width, height, ratio=1.0):
    """Artwork cropped to fill a ``width``×``height`` box (centre crop)."""
    width, height = max(1, int(width)), max(1, int(height))
    key = f'wm-fill:{path}:{width}x{height}:{ratio}'
    found = QPixmapCache.find(key)
    if found is not None and not found.isNull():
        return found
    image = QImage(path)
    if image.isNull():
        return None
    pixels_w, pixels_h = round(width * ratio), round(height * ratio)
    image = image.scaled(pixels_w, pixels_h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    image = image.copy((image.width() - pixels_w) // 2, (image.height() - pixels_h) // 3, pixels_w, pixels_h)
    result = QPixmap.fromImage(image)
    result.setDevicePixelRatio(ratio)
    QPixmapCache.insert(key, result)
    return result


def blurred(path, width, height):
    """Soft, oversized artwork for backdrops: downscale hard, upscale smooth twice.

    Cheap enough for the UI thread and cached per size; the colours are the
    user's own artwork, so callers lay a themed scrim on top for legibility.
    """
    width, height = max(1, int(width)), max(1, int(height))
    key = f'wm-blur:{path}:{width}x{height}'
    found = QPixmapCache.find(key)
    if found is not None and not found.isNull():
        return found
    image = QImage(path)
    if image.isNull():
        return None
    # Halving steps average neighbours (a cheap box blur); doubling steps back up
    # interpolate smoothly, so no blocky smears survive at full size.
    small = image.scaled(64, 64, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    for side in (32, 16, 10):
        small = small.scaled(side, side, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    w, h = 10, 10
    while w * 2 < width or h * 2 < height:
        w, h = min(width, w * 2), min(height, h * 2)
        small = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    result = QPixmap.fromImage(small.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    QPixmapCache.insert(key, result)
    return result


@lru_cache(maxsize=1)
def grain_tile():
    """128 px tile of faint random specks. Tiled over gradients it breaks up
    colour banding and gives the backdrop a printed, physical texture."""
    rng = random.Random(3)
    image = QImage(128, 128, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    for y in range(128):
        for x in range(128):
            value = rng.random()
            if value > .55:
                shade = 255 if value > .8 else 0
                alpha = rng.randint(6, 18)
                # Premultiplied: colour channels never exceed alpha.
                level = alpha if shade else 0
                image.setPixel(x, y, (alpha << 24) | (level << 16) | (level << 8) | level)  # theme-exception: neutral film grain, alpha ≤ 18
    return QPixmap.fromImage(image)


class Drift:
    """A handful of M3 shapes floating behind the full player (shell BackgroundShapes)."""

    KINDS = ('cookie4', 'cookie6', 'cookie9', 'cookie12', 'circle', 'pill', 'gem')

    def __init__(self, count=11, seed=7):
        rng = random.Random(seed)
        self.items = [dict(kind=rng.choice(self.KINDS), x=rng.random(), y=rng.random(), size=rng.uniform(.06, .17),
                           vx=rng.uniform(-.012, .012), vy=rng.uniform(-.01, .01), angle=rng.uniform(0, 360),
                           spin=rng.uniform(-9, 9), alpha=rng.choice((1.0, 1.0, .45, .7)))
                      for _ in range(count)]

    def step(self, seconds):
        for item in self.items:
            item['x'] = (item['x'] + item['vx'] * seconds) % 1.2
            item['y'] = (item['y'] + item['vy'] * seconds) % 1.2
            item['angle'] = (item['angle'] + item['spin'] * seconds) % 360

    def paint(self, painter, rect, tint, opacity):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        unit = min(rect.width(), rect.height())
        for item in self.items:
            side = unit * item['size']
            x = rect.left() + (item['x'] - .1) * rect.width()
            y = rect.top() + (item['y'] - .1) * rect.height()
            box = QRectF(x - side / 2, y - side / 2, side, side)
            painter.setOpacity(opacity * item['alpha'])
            # Lit from the top-left: a gradient fill reads as volume, not a flat sticker.
            light = QLinearGradient(box.topLeft(), box.bottomRight())
            light.setColorAt(0, tint)
            faded = QColor(tint)
            faded.setAlphaF(tint.alphaF() * .25)
            light.setColorAt(1, faded)
            painter.setBrush(light)
            painter.drawPath(self._path(item['kind'], box, item['angle']))
        painter.restore()

    @staticmethod
    def _path(kind, box, angle):
        if kind.startswith('cookie'):
            return cookie(box, int(kind[6:]), angle)
        path = QPainterPath()
        if kind == 'circle':
            path.addEllipse(box)
            return path
        if kind == 'pill':
            path.addRoundedRect(box.adjusted(0, box.height() * .3, 0, -box.height() * .3), box.height() * .2,
                                box.height() * .2)
        else:  # gem: a soft rotated square
            path.addRoundedRect(box.adjusted(box.width() * .15, box.height() * .15, -box.width() * .15,
                                             -box.height() * .15), box.width() * .18, box.width() * .18)
        transform = QTransform()
        transform.translate(box.center().x(), box.center().y())
        transform.rotate(angle)
        transform.translate(-box.center().x(), -box.center().y())
        return transform.map(path)
