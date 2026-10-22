"""Hand-painted file icons: a folder that peeks its papers on hover, pages with an extension badge,
cookies for audio, a screen for video and thumbnails for images. Colours are theme tokens only."""
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap, QPolygonF

from file_media import AUDIO, VIDEOS
from theme_tokens import color, tokens
from .kinds import describe
from .kit import clip_pixmap, cookie, paint_symbol, squircle, text_font


def _rounded(rect, radius):
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def folder(painter, rect, lift=0.0, selected=False):
    """Back panel with tab, two papers that rise with ``lift`` and the front panel."""
    w, h = rect.width(), rect.height()
    r = max(4.0, h * .13)
    painter.setPen(Qt.NoPen)
    back = _rounded(QRectF(rect.left(), rect.top() + h * .16, w, h * .84), r).united(
        _rounded(QRectF(rect.left(), rect.top(), w * .46, h * .34), r))
    painter.setBrush(color('accent', 150))
    painter.drawPath(back)
    for number, (inset, tilt) in enumerate(((.12, -1.6), (.18, 1.2))):
        rise = h * .20 * lift * (1 - number * .25)
        paper = QRectF(rect.left() + w * inset, rect.top() + h * .24 - rise, w * (1 - 2 * inset), h * .5)
        painter.save()
        painter.translate(paper.center())
        painter.rotate(tilt * lift)
        painter.translate(-paper.center())
        painter.setBrush(color('text', 235 if number == 0 else 175))
        painter.drawRoundedRect(paper, r * .5, r * .5)
        painter.restore()
    front = QRectF(rect.left(), rect.top() + h * .34 + lift * 1.5, w, h * .66 - lift * 1.5)
    painter.setBrush(color('accent'))
    painter.drawRoundedRect(front, r, r)
    painter.setBrush(color('tint', 34))
    painter.drawRoundedRect(QRectF(front.left(), front.top(), front.width(), 2.4), 1.2, 1.2)


def page(painter, rect, tone, suffix, selected=False):
    """Sheet with a folded corner, a faint glyph and the extension on a badge."""
    w, h = rect.width() * .74, rect.height()
    sheet = QRectF(rect.center().x() - w / 2, rect.top(), w, h)
    fold = min(w, h) * .3
    outline = _rounded(sheet, max(5.0, w * .1))
    corner = QPainterPath()
    corner.addPolygon(QPolygonF([QPointF(sheet.right() - fold, sheet.top() - 1), QPointF(sheet.right() + 1, sheet.top() - 1),
                                 QPointF(sheet.right() + 1, sheet.top() + fold)]))
    painter.setPen(Qt.NoPen)
    painter.setBrush(color('tile'))
    painter.drawPath(outline.subtracted(corner))
    painter.setBrush(color(tone, 38))
    painter.drawPath(outline.subtracted(corner))
    flap = QPainterPath()
    flap.addPolygon(QPolygonF([QPointF(sheet.right() - fold, sheet.top()), QPointF(sheet.right(), sheet.top() + fold),
                               QPointF(sheet.right() - fold, sheet.top() + fold)]))
    painter.setBrush(color(tone, 120))
    painter.drawPath(flap.intersected(outline))
    label = (suffix or 'file').upper()[:4]
    painter.setFont(text_font('caption', 800, max(.7, h / 78)))
    width = painter.fontMetrics().horizontalAdvance(label) + h * .22
    badge = QRectF(sheet.left() + w * .12, sheet.bottom() - h * .30, width, h * .2)
    painter.setBrush(color(tone))
    painter.drawRoundedRect(badge, badge.height() / 2, badge.height() / 2)
    painter.setPen(color('on_accent'))
    painter.drawText(badge, Qt.AlignCenter, label)


def screen(painter, rect, tone):
    box = QRectF(rect.left(), rect.top() + rect.height() * .1, rect.width(), rect.height() * .8)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color('tile'))
    painter.drawRoundedRect(box, box.height() * .22, box.height() * .22)
    painter.setBrush(color(tone, 46))
    painter.drawRoundedRect(box, box.height() * .22, box.height() * .22)
    disc = QRectF(0, 0, box.height() * .56, box.height() * .56)
    disc.moveCenter(box.center())
    painter.setBrush(color(tone))
    painter.drawEllipse(disc)
    paint_symbol(painter, disc, 'play_arrow', 'on_accent', disc.height() * .66, filled=True)


def disc(painter, rect, tone):
    side = min(rect.width(), rect.height())
    box = QRectF(0, 0, side, side)
    box.moveCenter(rect.center())
    outline = cookie(box, 9)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color('tile'))
    painter.drawPath(outline)
    painter.setBrush(color(tone, 56))
    painter.drawPath(outline)
    paint_symbol(painter, box, 'music_note', tone, side * .46, filled=True)


_CACHE = {}


def _draw(painter, rect, path, is_dir, hover, selected):
    suffix = Path(path).suffix.lower()
    _symbol, tone, _label = describe(path, is_dir)
    if is_dir:
        folder(painter, rect, hover, selected)
    elif suffix in VIDEOS:
        screen(painter, rect, tone)
    elif suffix in AUDIO:
        disc(painter, rect, tone)
    else:
        page(painter, rect, tone, suffix.lstrip('.'), selected)


def paint_icon(painter, rect, path, is_dir, thumbnail=None, hover=0.0, selected=False):
    """Resting icons are pre-rendered once per kind/size/theme; hovered ones are drawn live."""
    if thumbnail is None and hover < .01:
        ratio = painter.device().devicePixelRatioF() if painter.device() else 1.0
        values = tokens()
        suffix = '' if is_dir else Path(path).suffix.lower()
        key = (is_dir, suffix, round(rect.width()), round(rect.height()), ratio, values['accent'], values['tile'], values['text'], values['on_accent'])
        pixmap = _CACHE.get(key)
        if pixmap is None:
            if len(_CACHE) > 300:
                _CACHE.clear()
            pixmap = QPixmap(round(rect.width() * ratio) + 4, round(rect.height() * ratio) + 4)
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(Qt.transparent)
            inner = QPainter(pixmap)
            inner.setRenderHint(QPainter.Antialiasing)
            _draw(inner, QRectF(1, 1, rect.width(), rect.height()), path, is_dir, 0.0, False)
            inner.end()
            _CACHE[key] = pixmap
        painter.drawPixmap(QPointF(rect.left() - 1, rect.top() - 1), pixmap)
        return
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    if thumbnail is None:
        _draw(painter, rect, path, is_dir, hover, selected)
        painter.restore()
        return
    painter.restore()
    _paint_thumbnail(painter, rect, thumbnail)


def _paint_thumbnail(painter, rect, thumbnail):
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    outline = squircle(rect, .55)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color('well'))
    painter.drawPath(outline)
    scale = max(rect.width() / thumbnail.width(), rect.height() / thumbnail.height())
    target = QRectF(0, 0, thumbnail.width() * scale, thumbnail.height() * scale)
    target.moveCenter(rect.center())
    clip_pixmap(thumbnail, outline, painter, target)
    painter.restore()
