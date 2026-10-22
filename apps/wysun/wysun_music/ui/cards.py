"""Cards, posters, bento tiles, chart rows and responsive shelves.

Cards are editorial rather than boxed: the artwork carries the item, captions
sit underneath on the page. Artists wear an M3 cookie that turns a little on
hover; posters grow a caption block in their artwork's own colour.
"""
from PySide6.QtCore import QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from theme_tokens import color, tokens
from .shapes import artwork, blurred, clip_pixmap, cookie
from .style import metric, paint_symbol, text_font
from .widgets import LinkLabel, StateLayer, draw_art, paint_favorites_cover


class Tile(QWidget):
    """Base for clickable painted items: hover layer, open on click, play button."""

    opened = Signal()
    play_requested = Signal()

    def __init__(self, covers, title, subtitle='', collection=None, track=None, round_cover=False,
                 placeholder='queue_music', parent=None):
        super().__init__(parent)
        self.covers = covers
        self.title, self.subtitle = title, subtitle
        self.collection, self.track = collection, track
        self.round_cover = round_cover
        self.placeholder = placeholder
        self.playing = False
        self.layer = StateLayer(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self.setToolTip(title if not subtitle else f'{title}\n{subtitle}')
        covers.updated.connect(self._updated)

    def _updated(self, key):
        if key == self.track or (self.collection and (key == self.collection.id or key in self.collection.keys[:12])):
            self.update()

    def art_key(self):
        """Key whose image represents this tile (own art, else the first track's)."""
        if self.track:
            return self.track
        if self.collection is None:
            return None
        if self.covers.path(self.collection.id):
            return self.collection.id
        return next((k for k in self.collection.keys[:4] if self.covers.path(k)), None)

    def tone(self):
        if self.collection is not None:
            return self.covers.collection_tone(self.collection)
        return self.covers.tone(self.track) if self.track else None

    def cover_pixmap(self, size, radius):
        ratio = self.devicePixelRatioF()
        if self.collection is not None:
            return self.covers.collection_pixmap(self.collection, size, radius, ratio)
        return self.covers.pixmap(self.track, size, radius, ratio) if self.track else None

    def draw_cover(self, painter, rect, radius):
        if self.collection is not None and self.collection.kind == 'favorites':
            paint_favorites_cover(painter, QRectF(rect), radius)
            return
        draw_art(painter, rect, self.cover_pixmap(rect.width(), radius), radius, self.placeholder)

    def draw_cookie(self, painter, rect, sides=9, rotation=0.0):
        """Artist portrait (or first cover) masked by an M3 cookie."""
        outline = cookie(QRectF(rect), sides, rotation)
        key = self.art_key()
        path = self.covers.path(key) if key else None
        pixmap = artwork(path, rect.width(), self.devicePixelRatioF()) if path else None
        if pixmap is not None:
            clip_pixmap(pixmap, outline, painter, rect)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('surface_raised'))
            painter.drawPath(outline)
            paint_symbol(painter, QRectF(rect), self.placeholder, 'subtle', rect.height() * .38)

    def play_rect(self):
        return QRect()

    def draw_play(self, painter, rect, lifted=True):
        """Accent play button that rises in on hover (always shown while playing)."""
        amount = 1.0 if self.playing else self.layer.amount
        if amount <= 0.01:
            return
        painter.save()
        painter.setOpacity(amount)
        shifted = QRectF(rect).translated(0, (1 - amount) * 8 if lifted else 0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('shadow'))
        painter.drawEllipse(shifted.translated(0, 2))
        painter.setBrush(color('accent'))
        painter.drawEllipse(shifted)
        paint_symbol(painter, shifted, 'pause' if self.playing else 'play_arrow', 'on_accent',
                     shifted.height() * .55, filled=True)
        painter.restore()

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self.rect().contains(event.position().toPoint()):
            return
        if self.play_rect().contains(event.position().toPoint()):
            self.play_requested.emit()
        else:
            self.opened.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            (self.play_requested if event.modifiers() & Qt.ControlModifier else self.opened).emit()
        else:
            super().keyPressEvent(event)

    def paint_focus(self, painter, rect, radius):
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(color('focus'))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), radius, radius)

    def draw_captions(self, painter, top, left, width, centered=False):
        align = (Qt.AlignHCenter if centered else Qt.AlignLeft) | Qt.AlignVCenter
        painter.setFont(text_font('body', 600))
        metrics = painter.fontMetrics()
        painter.setPen(color('text'))
        painter.drawText(QRect(left, top, width, metrics.height()), align,
                         metrics.elidedText(self.title, Qt.ElideRight, width))
        if self.subtitle:
            painter.setFont(text_font('small'))
            small = painter.fontMetrics()
            painter.setPen(color('muted'))
            painter.drawText(QRect(left, top + metrics.height() + 1, width, small.height()), align,
                             small.elidedText(self.subtitle, Qt.ElideRight, width))


class Card(Tile):
    """Artwork with captions underneath; artists become a turning cookie."""

    WIDTH, CAPTION, PADDING = 172, 52, 0

    def sizeHint(self):
        return QSize(self.WIDTH, self.WIDTH + self.CAPTION)

    def cover_rect(self):
        side = self.width()
        if self.round_cover:
            side = round(side * .9)
            return QRect((self.width() - side) // 2, round(self.width() * .05), side, side)
        return QRect(0, 0, side, side)

    def play_rect(self):
        cover = self.cover_rect()
        side = 44
        if self.round_cover:
            return QRect(cover.right() - side + 2, cover.bottom() - side + 2, side, side)
        return QRect(cover.left() + 10, cover.bottom() - side - 10, side, side)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        radius = tokens()['radius_m']
        cover = self.cover_rect()
        if self.round_cover:
            self.draw_cookie(painter, cover, 9, 22 * self.layer.amount)
        else:
            if self.layer.amount:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color('shadow', round(70 * self.layer.amount)))
                painter.drawRoundedRect(QRectF(cover).adjusted(2, 6, -2, 4), radius, radius)
            self.draw_cover(painter, cover, radius)
            if self.layer.amount:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color('scrim', round(40 * self.layer.amount)))
                painter.drawRoundedRect(QRectF(cover), radius, radius)
        self.draw_play(painter, self.play_rect())
        self.draw_captions(painter, cover.bottom() + metric('space_s'), 2, self.width() - 4, centered=self.round_cover)
        self.paint_focus(painter, cover, radius)


class PosterCard(Tile):
    """Artwork over a caption block tinted with the artwork's own colour."""

    WIDTH = 196

    def play_rect(self):
        side = 40
        art = self.width()
        return QRect(self.width() - side - 10, art - side // 2, side, side)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        radius = tokens()['radius_m']
        rect = QRectF(self.rect())
        shape = QPainterPath()
        shape.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(shape)
        tone = self.tone()
        # theme-exception: caption block takes the user's artwork tone; text uses on_hud on it.
        block = QColor(tone) if tone is not None else color('media')
        painter.fillRect(rect, block)
        side = self.width()
        self.draw_cover(painter, QRect(0, 0, side, side), 0)
        if self.layer.amount:
            painter.fillRect(rect, color('tint', round(14 * self.layer.amount)))
        painter.restore()
        pad = metric('space_m')
        top = side + metric('space_s')
        width = self.width() - 2 * pad - 44
        painter.setFont(text_font('body', 700))
        metrics = painter.fontMetrics()
        painter.setPen(color('on_hud'))
        painter.drawText(QRect(pad, top, width, metrics.height()), Qt.AlignLeft | Qt.AlignVCenter,
                         metrics.elidedText(self.title, Qt.ElideRight, width))
        painter.setFont(text_font('small', 500))
        painter.setPen(color('on_hud', 190))
        painter.drawText(QRect(pad, top + metrics.height() + 2, self.width() - 2 * pad, self.height() - top - metrics.height()),
                         Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.subtitle)
        self.draw_play(painter, self.play_rect(), lifted=False)
        self.paint_focus(painter, self.rect(), radius)


class BentoTile(Tile):
    """Home hero tiles.

    ``style``: ``resume`` (blurred artwork, big cover, the song), ``accent``
    (favourites: accent container with a heart cookie) or ``tonal`` (a mix).
    """

    def __init__(self, covers, title, subtitle, style='resume', symbol='shuffle', eyebrow='', **kwargs):
        super().__init__(covers, title, subtitle, **kwargs)
        self.style, self.symbol, self.eyebrow = style, symbol, eyebrow
        self.setMinimumHeight(180)

    def play_rect(self):
        if self.style != 'resume':
            return QRect()
        side = 52
        pad = metric('space_l')
        return QRect(self.width() - side - pad, self.height() - side - pad, side, side)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        radius = tokens()['radius_l']
        rect = QRectF(self.rect())
        shape = QPainterPath()
        shape.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(shape)
        pad = metric('space_l')
        if self.style == 'resume':
            ink, soft = 'text_strong', 'text'
            painter.fillRect(rect, color('surface_raised'))
            key = self.art_key()
            path = self.covers.path(key) if key else None
            backdrop = blurred(path, self.width(), self.height()) if path else None
            if backdrop is not None:
                painter.drawPixmap(self.rect(), backdrop)
            painter.fillRect(rect, color('surface', 150))
            side = self.height() - 2 * pad
            cover = QRect(pad, pad, side, side)
            painter.restore()
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('shadow'))
            painter.drawRoundedRect(QRectF(cover).translated(0, 4), tokens()['radius_m'], tokens()['radius_m'])
            self.draw_cover(painter, cover, tokens()['radius_m'])
            text_left = cover.right() + pad
            painter.save()
        else:
            accent = self.style == 'accent'
            ink, soft = ('on_accent', 'on_accent') if accent else ('text_strong', 'muted')
            painter.fillRect(rect, color('accent' if accent else 'nav_selected'))
            painter.fillRect(rect, color('tint', round(10 * self.layer.amount)))
            # A cookie badge in the corner, turning a little with the hover.
            side = min(self.height() * .62, self.width() * .42)
            badge = QRectF(self.width() - side - pad * .6, self.height() - side - pad * .6, side, side)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('on_accent' if accent else 'accent', 40 if accent else 52))
            painter.drawPath(cookie(badge, 12 if accent else 7, 20 * self.layer.amount))
            paint_symbol(painter, badge, self.symbol, ink, side * .42, filled=True)
            text_left = pad
        painter.restore()
        width = self.width() - text_left - pad
        y = pad
        if self.eyebrow:
            font = text_font('caption', 700)
            font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1.1)
            painter.setFont(font)
            painter.setPen(color(soft))
            painter.drawText(QRect(text_left, y, width, 18), Qt.AlignLeft | Qt.AlignVCenter, self.eyebrow.upper())
            y += 22
        painter.setFont(text_font('title', 800, 1.05))
        metrics = painter.fontMetrics()
        painter.setPen(color(ink))
        title_rect = QRect(text_left, y, width - (60 if self.style == 'resume' else 0), metrics.height() * 2 + 4)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.title)
        bounds = metrics.boundingRect(title_rect, Qt.AlignLeft | Qt.TextWordWrap, self.title)
        painter.setFont(text_font('body', 500))
        painter.setPen(color(soft))
        sub = painter.fontMetrics()
        painter.drawText(QRect(text_left, min(bounds.bottom(), title_rect.bottom()) + 4, width - 64, sub.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, sub.elidedText(self.subtitle, Qt.ElideRight, width - 64))
        if self.style == 'resume':
            # Always visible on the hero, not only on hover.
            button = QRectF(self.play_rect())
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('accent'))
            painter.drawEllipse(button)
            if self.layer.amount:
                painter.setBrush(color('tint', round(18 * self.layer.amount)))
                painter.drawEllipse(button)
            paint_symbol(painter, button, 'pause' if self.playing else 'play_arrow', 'on_accent',
                         button.height() * .55, filled=True)
        self.paint_focus(painter, self.rect(), radius)


class ChartRow(Tile):
    """Compact ranked song: big number, small cover, title and artist."""

    HEIGHT = 60

    def __init__(self, covers, rank, title, subtitle, track, parent=None):
        super().__init__(covers, title, subtitle, track=track, placeholder='music_note', parent=parent)
        self.rank = rank

    def sizeHint(self):
        return QSize(260, self.HEIGHT)

    def play_rect(self):
        return self.rect()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = tokens()['radius_s']
        if self.layer.amount:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('row_hover'))
            painter.setOpacity(self.layer.amount)
            painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
            painter.setOpacity(1)
        side = self.height() - 12
        cover = QRect(6, 6, side, side)
        self.draw_cover(painter, cover, min(8, radius))
        if self.layer.amount or self.playing:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('scrim', 120))
            painter.drawRoundedRect(QRectF(cover), min(8, radius), min(8, radius))
            paint_symbol(painter, cover, 'pause' if self.playing else 'play_arrow', 'on_hud', 24, filled=True)
        rank = QRect(cover.right() + metric('space_s'), 0, 34, self.height())
        painter.setFont(text_font('title', 800, .95))
        painter.setPen(color('accent'))
        painter.drawText(rank, Qt.AlignCenter, str(self.rank))
        left = rank.right() + metric('space_s')
        width = self.width() - left - metric('space_s')
        painter.setFont(text_font('body', 600))
        metrics = painter.fontMetrics()
        painter.setPen(color('text'))
        painter.drawText(QRect(left, self.height() // 2 - metrics.height(), width, metrics.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(self.title, Qt.ElideRight, width))
        painter.setFont(text_font('small'))
        small = painter.fontMetrics()
        painter.setPen(color('muted'))
        painter.drawText(QRect(left, self.height() // 2 + 1, width, small.height()), Qt.AlignLeft | Qt.AlignVCenter,
                         small.elidedText(self.subtitle, Qt.ElideRight, width))
        self.paint_focus(painter, self.rect(), radius)


class QuickTile(Tile):
    """Compact shortcut: cover on the left, title, play button on hover."""

    WIDTH, HEIGHT = 260, 64

    def sizeHint(self):
        return QSize(self.WIDTH, self.HEIGHT)

    def play_rect(self):
        side = 36
        return QRect(self.width() - side - metric('space_m'), (self.height() - side) // 2, side, side)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = tokens()['radius_s']
        rect = QRectF(self.rect())
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('tint', round(10 + 12 * self.layer.amount)))
        painter.drawRoundedRect(rect, radius, radius)
        side = self.height()
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(clip)
        self.draw_cover(painter, QRect(0, 0, side, side), 0)
        painter.restore()
        painter.setFont(text_font('body', 600))
        play = self.play_rect()
        width = (play.left() if self.layer.amount or self.playing else self.width()) - side - 2 * metric('space_m')
        painter.setPen(color('text'))
        painter.drawText(QRect(side + metric('space_m'), 0, width, self.height()), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self.title, Qt.ElideRight, width))
        self.draw_play(painter, play)
        self.paint_focus(painter, self.rect(), radius)


class FlowRow(QWidget):
    """Lays children in equal columns that fit the width; ``rows`` caps the count shown."""

    def __init__(self, item_width, item_height=None, rows=1, extra_height=0, gap=None, parent=None):
        """``item_height=None`` makes items square plus ``extra_height`` (cards with captions)."""
        super().__init__(parent)
        self.item_width, self.item_height, self.rows = item_width, item_height, rows
        self.extra_height = extra_height
        self.gap = gap
        self.items = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_items(self, widgets):
        for widget in self.items:
            widget.hide()
            widget.deleteLater()
        self.items = list(widgets)
        for widget in self.items:
            widget.setParent(self)
        self._layout()

    def _gap(self):
        return self.gap if self.gap is not None else metric('space_l')

    def _columns(self):
        gap = self._gap()
        return max(1, (self.width() + gap) // (self.item_width + gap))

    def _layout(self):
        gap = self._gap()
        columns = self._columns()
        width = (self.width() - gap * (columns - 1)) / columns
        height = self.item_height or round(width) + self.extra_height
        capacity = columns * self.rows if self.rows else len(self.items)
        row_gap = gap if self.item_height is None or self.item_height > 100 else metric('space_xs')
        for index, widget in enumerate(self.items):
            if index >= capacity:
                widget.hide()
                continue
            row, column = divmod(index, columns)
            widget.setGeometry(round(column * (width + gap)), row * (height + row_gap), round(width), height)
            widget.show()
        shown = min(len(self.items), capacity)
        rows = (shown + columns - 1) // columns
        self.setFixedHeight(max(0, rows * (height + row_gap) - row_gap))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout()


class Shelf(QWidget):
    """Section title, optional "Ver todo" link and a FlowRow."""

    show_all = Signal()

    def __init__(self, title, item_width=Card.WIDTH, item_height=None, rows=1, extra_height=Card.CAPTION,
                 subtitle='', parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metric('space_m'))
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title = QLabel(title)
        self.title.setFont(text_font('heading', 750, 1.3))
        titles.addWidget(self.title)
        self.caption = QLabel(subtitle)
        self.caption.setObjectName('muted')
        self.caption.setVisible(bool(subtitle))
        titles.addWidget(self.caption)
        header.addLayout(titles, 1)
        self.more = LinkLabel('Ver todo', 'small', 600, 'muted')
        self.more.setFixedWidth(self.more.fontMetrics().horizontalAdvance('Ver todo') + 4)
        self.more.activated.connect(self.show_all.emit)
        self.more.hide()
        header.addWidget(self.more, 0, Qt.AlignBottom)
        layout.addLayout(header)
        self.row = FlowRow(item_width, item_height, rows, extra_height=extra_height)
        layout.addWidget(self.row)

    def set_items(self, widgets, expandable=False):
        self.row.set_items(widgets)
        self.more.setVisible(expandable)
        self.setVisible(bool(widgets))

    def refresh_fonts(self):
        self.title.setFont(text_font('heading', 750, 1.3))
