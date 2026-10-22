"""Song table: a keys-only model, a painted delegate and a virtualised view.

The model stores track keys; everything else is looked up while painting, so
switching playlists is a single ``beginResetModel`` regardless of their size.
"""
from dataclasses import dataclass

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QListView, QStyle, QStyledItemDelegate, QWidget

from music_library import artists
from theme_tokens import color, tokens
from .style import metric, paint_symbol, stamp, text_font
from .widgets import draw_art

KEY_ROLE = Qt.UserRole + 1
ROW_HEIGHT = 56


@dataclass
class Columns:
    """Horizontal layout shared by the delegate and the header."""
    index: QRect
    cover: QRect
    title: QRect
    album: QRect
    heart: QRect
    duration: QRect
    more: QRect


def columns(rect, numbered=True, album=True, cover_size=40):
    pad = metric('space_m')
    left = rect.left() + pad
    index = QRect(left, rect.top(), 32 if numbered else 0, rect.height())
    left = index.right() + (pad if numbered else 0)
    cover = QRect(left, rect.top() + (rect.height() - cover_size) // 2, cover_size, cover_size)
    if not cover_size:
        cover = QRect(left - metric('space_m'), rect.top(), 0, rect.height())
    more = QRect(rect.right() - pad - 32, rect.top(), 32, rect.height())
    duration = QRect(more.left() - 56, rect.top(), 52, rect.height())
    heart = QRect(duration.left() - 36, rect.top(), 32, rect.height())
    title_left = cover.right() + metric('space_m')
    free = heart.left() - metric('space_m') - title_left
    album_width = free * 2 // 5 if album and rect.width() > 720 else 0
    title = QRect(title_left, rect.top(), free - album_width, rect.height())
    album = QRect(title.right() + metric('space_m'), rect.top(), max(0, album_width - metric('space_m')), rect.height())
    return Columns(index, cover, title, album, heart, duration, more)


class TrackModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keys = []

    def set_keys(self, keys):
        keys = list(keys)
        if keys == self.keys:
            return
        self.beginResetModel()
        self.keys = keys
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.keys)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (KEY_ROLE, Qt.DisplayRole):
            return self.keys[index.row()]
        return None

    def refresh(self):
        """Repaint rows (favourite / playing marks) without resetting the view."""
        if self.keys:
            self.dataChanged.emit(self.index(0), self.index(len(self.keys) - 1))


class TrackDelegate(QStyledItemDelegate):
    def __init__(self, view, library, covers, player):
        super().__init__(view)
        self.view, self.library, self.covers, self.player = view, library, covers, player

    def sizeHint(self, option, index):
        return QSize(200, ROW_HEIGHT)

    def paint(self, painter, option, index):
        key = index.data(KEY_ROLE)
        track = self.library.track(key)
        rect = option.rect
        hovered = bool(option.state & QStyle.State_MouseOver)
        selected = bool(option.state & QStyle.State_Selected)
        current = key == self.player.current
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        radius = tokens()['radius_s']
        if selected or hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('row_selected' if selected else 'row_hover'))
            painter.drawRoundedRect(QRectF(rect).adjusted(0, 1, 0, -1), radius, radius)
        elif self.view.striped and index.row() % 2:
            # Zebra rows keep long lists readable without dividers.
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('tint', 6))
            painter.drawRoundedRect(QRectF(rect).adjusted(0, 1, 0, -1), radius, radius)
        layout = columns(rect, self.view.numbered, self.view.has_album, 40 if self.view.show_covers else 0)
        # Index, or a play affordance on hover, or the "now playing" mark.
        if self.view.numbered:
            if hovered:
                paint_symbol(painter, layout.index, 'pause' if current and self.player.playing else 'play_arrow',
                             'text', 20, filled=True)
            elif current:
                paint_symbol(painter, layout.index, 'graphic_eq' if self.player.playing else 'volume_up', 'accent', 18)
            else:
                painter.setFont(text_font('body'))
                painter.setPen(color('muted'))
                painter.drawText(layout.index, Qt.AlignCenter, str(index.row() + 1))
        size, cover_radius = layout.cover.width(), min(tokens()['radius_s'], 6)
        if size:
            draw_art(painter, layout.cover, self.covers.pixmap(key, size, cover_radius,
                                                               painter.device().devicePixelRatioF()), cover_radius)
        title_font = text_font('body', 500)
        painter.setFont(title_font)
        metrics = painter.fontMetrics()
        line = layout.title
        top = QRect(line.left(), rect.top() + rect.height() // 2 - metrics.height() - 1, line.width(), metrics.height())
        painter.setPen(color('accent' if current else 'text'))
        painter.drawText(top, Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(track.get('title', ''), Qt.ElideRight, line.width()))
        painter.setFont(text_font('small'))
        small = painter.fontMetrics()
        bottom = QRect(line.left(), rect.top() + rect.height() // 2 + 2, line.width(), small.height())
        painter.setPen(color('text' if hovered else 'muted'))
        painter.drawText(bottom, Qt.AlignLeft | Qt.AlignVCenter, small.elidedText(track.get('artist', ''), Qt.ElideRight, line.width()))
        if layout.album.width() > 40:
            painter.setPen(color('muted'))
            painter.drawText(layout.album, Qt.AlignLeft | Qt.AlignVCenter,
                             small.elidedText(self.library.album(key), Qt.ElideRight, layout.album.width()))
        favorite = key in self.library.favorites
        if favorite or hovered:
            paint_symbol(painter, layout.heart, 'favorite', 'accent' if favorite else 'muted', 18, filled=favorite)
        painter.setPen(color('muted'))
        painter.drawText(layout.duration, Qt.AlignRight | Qt.AlignVCenter, stamp(self.library.duration(key)))
        if hovered:
            paint_symbol(painter, layout.more, 'more_horiz', 'text', 20)
        painter.restore()

    def hit(self, rect, point):
        """Which part of a row was clicked: play, heart, more, artist or row."""
        layout = columns(rect, self.view.numbered, self.view.has_album, 40 if self.view.show_covers else 0)
        if layout.heart.contains(point):
            return 'heart'
        if layout.more.contains(point):
            return 'more'
        if self.view.numbered and layout.index.contains(point) or (layout.cover.width() and layout.cover.contains(point)):
            return 'play'
        if layout.title.contains(point) and point.y() > rect.top() + rect.height() // 2:
            return 'artist'
        return 'row'


class TrackView(QListView):
    play_requested = Signal(str)
    menu_requested = Signal(list, object)       # keys, global position
    artist_requested = Signal(str)

    def __init__(self, library, covers, player, numbered=True, parent=None):
        super().__init__(parent)
        self.library, self.player = library, player
        self.numbered = numbered
        self.has_album = False
        self.show_covers = True
        self.album_column = True
        self.striped = False
        self.header = None  # optional TrackHeader kept in sync with the album column
        self.model_ = TrackModel(self)
        self.setModel(self.model_)
        self.delegate = TrackDelegate(self, library, covers, player)
        self.setItemDelegate(self.delegate)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.doubleClicked.connect(lambda index: self.play_requested.emit(index.data(KEY_ROLE)))
        self.setAccessibleName('Canciones')
        covers.updated.connect(self._cover_updated)
        player.track_changed.connect(lambda _: self.viewport().update())
        player.state_changed.connect(self.viewport().update)
        library.favorites_changed.connect(self.viewport().update)

    @property
    def keys(self):
        return self.model_.keys

    def set_keys(self, keys):
        # The album column only appears when the list actually has albums.
        self.has_album = self.album_column and any(self.library.album(k) for k in keys)
        if self.header is not None:
            self.header.has_album = self.has_album
            self.header.update()
        self.model_.set_keys(keys)

    def selected_keys(self):
        rows = sorted(index.row() for index in self.selectionModel().selectedRows())
        return [self.model_.keys[row] for row in rows]

    def _cover_updated(self, key):
        if key in self.model_.keys:
            self.viewport().update()

    def _context_menu(self, point):
        index = self.indexAt(point)
        if not index.isValid():
            return
        if not self.selectionModel().isSelected(index):
            self.setCurrentIndex(index)
        self.menu_requested.emit(self.selected_keys(), self.viewport().mapToGlobal(point))

    def mouseReleaseEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if event.button() == Qt.LeftButton and index.isValid() and not event.modifiers():
            key = index.data(KEY_ROLE)
            part = self.delegate.hit(self.visualRect(index), event.position().toPoint())
            if part == 'heart':
                self.library.toggle_favorite(key)
                return
            if part == 'more':
                self.setCurrentIndex(index)
                self.menu_requested.emit([key], event.globalPosition().toPoint())
                return
            if part == 'play':
                if key == self.player.current:
                    self.player.toggle()
                else:
                    self.play_requested.emit(key)
                return
            if part == 'artist':
                names = artists(self.library.track(key))
                if names:
                    self.artist_requested.emit(names[0])
                    return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        index = self.currentIndex()
        if index.isValid() and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ControlModifier:
                names = artists(self.library.track(index.data(KEY_ROLE)))
                if names:
                    self.artist_requested.emit(names[0])
            else:
                self.play_requested.emit(index.data(KEY_ROLE))
            return
        if index.isValid() and event.key() == Qt.Key_F and not event.modifiers():
            self.library.toggle_favorite(index.data(KEY_ROLE))
            return
        if index.isValid() and event.key() == Qt.Key_Menu:
            self.menu_requested.emit(self.selected_keys(), self.viewport().mapToGlobal(self.visualRect(index).center()))
            return
        super().keyPressEvent(event)

    def leaveEvent(self, event):
        self.viewport().update()
        super().leaveEvent(event)

    def fit_height(self, rows=None):
        """For short embedded lists (search, queue): no inner scrolling. Call after set_keys."""
        count = len(self.keys) if rows is None else min(rows, len(self.keys))
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(count * ROW_HEIGHT + 2)


class TrackHeader(QWidget):
    """Column captions aligned with ``columns()``."""

    def __init__(self, numbered=True, parent=None):
        super().__init__(parent)
        self.numbered = numbered
        self.has_album = True
        self.show_covers = True
        self.setFixedHeight(36)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        layout = columns(self.rect(), self.numbered, self.has_album, 40 if self.show_covers else 0)
        painter.setFont(text_font('small', 500))
        painter.setPen(color('muted'))
        if self.numbered:
            painter.drawText(layout.index, Qt.AlignCenter, '#')
        start = layout.cover.left() if self.show_covers else layout.title.left()
        painter.drawText(QRect(start, 0, layout.title.right() - start, self.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, 'Título')
        if layout.album.width() > 40:
            painter.drawText(layout.album, Qt.AlignLeft | Qt.AlignVCenter, 'Álbum')
        paint_symbol(painter, QRectF(layout.duration).adjusted(layout.duration.width() - 20, 0, 0, 0), 'schedule', 'muted', 16)
        painter.setPen(QPen(color('divider'), 1))
        painter.drawLine(metric('space_m'), self.height() - 1, self.width() - metric('space_m'), self.height() - 1)
