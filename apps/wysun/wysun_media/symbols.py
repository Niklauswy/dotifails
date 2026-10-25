"""Material Symbols drawn as ligatures of the packaged font, outlined or filled.

Hosts whose own toolkit already paints symbols (Wysun) pass that painter to the host adapter; hosts without
one (Recorder) use this. ``filled`` keeps the outer contours of a glyph and fills them, because the font's
FILL axis is not reachable from PySide6.
"""
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPainterPath

FAMILY = 'Material Symbols Rounded'


@lru_cache(maxsize=64)
def _font(family, pixels):
    font = QFont(family)
    font.setPixelSize(max(8, pixels))
    return font


@lru_cache(maxsize=256)
def _filled_path(family, name, pixels):
    """Glyph outline centred on the origin, outer contours only."""
    font = _font(family, pixels)
    path = QPainterPath()
    path.addText(0, 0, font, name)
    polygons = path.toSubpathPolygons()
    bounds = [polygon.boundingRect() for polygon in polygons]
    solid = QPainterPath()
    solid.setFillRule(Qt.WindingFill)
    for index, polygon in enumerate(polygons):
        inside = any(other != index and bounds[other] != bounds[index] and bounds[other].contains(bounds[index]) for other in range(len(bounds)))
        if not inside:
            solid.addPolygon(polygon)
            solid.closeSubpath()
    metrics = QFontMetricsF(font)
    return solid.simplified().translated(-metrics.horizontalAdvance(name) / 2, (metrics.ascent() - metrics.descent()) / 2)


def paint(painter, rect, name, ink, size, filled=False, family=FAMILY):
    """Draw ligature ``name`` centred in ``rect`` with colour ``ink`` (a QColor)."""
    size, rect = round(size), QRectF(rect)
    painter.save()
    if filled:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(rect.center())
        painter.fillPath(_filled_path(family, name, size), ink)
    else:
        painter.setFont(_font(family, size))
        painter.setPen(ink)
        painter.drawText(rect, Qt.AlignCenter, name)
    painter.restore()
