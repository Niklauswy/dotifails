"""Left column: search, "Escuchar", "Biblioteca" and the playlists, in one quiet list.

No containers of its own: the column sits on the window material and the
content area is the only raised surface, so the eye goes to the music.
"""
from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from theme_tokens import color, tokens
from .style import metric, paint_symbol, text_font
from .widgets import IconButton, StateLayer, draw_art, paint_favorites_cover

OUTLINE_ONLY = {'explore', 'history', 'album', 'download', 'artist'}  # glyphs whose filled form loses detail
LISTEN = (('home', 'home', 'Inicio', ('home',)), ('search', 'explore', 'Explorar', ('search', '')),
          ('downloads', 'download', 'Añadir música', ('downloads',)))
LIBRARY = (('all', 'music_note', 'Canciones', ('collection', 'all')),
           ('artists', 'artist', 'Artistas', ('artists',)),
           ('albums', 'album', 'Álbumes', ('albums',)),
           ('recent', 'history', 'Recientes', ('collection', 'recent')),
           ('favorites', 'favorite', 'Tus me gusta', ('collection', 'favorites')))


class Panel(QWidget):
    """Rounded raised surface, like the shell's StyledRect containers."""

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('surface'))
        radius = tokens()['radius_l']
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)


class SearchField(QLineEdit):
    """Pill search with a painted Material search glyph."""

    def __init__(self):
        super().__init__()
        self.setObjectName('musicSearch')
        self.setPlaceholderText('Buscar')
        self.setAccessibleName('Buscar en tu biblioteca')
        self.setToolTip('Buscar · Ctrl+K')
        self.setClearButtonEnabled(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        paint_symbol(painter, QRectF(8, 0, 24, self.height()), 'search', 'muted', 20)


class NavItem(QWidget):
    """Sidebar row: symbol + label (or artwork + label for playlists); pill when active."""

    clicked = Signal()
    menu_requested = Signal(object)  # global position

    def __init__(self, symbol, label, parent=None, collection=None, covers=None):
        super().__init__(parent)
        self.symbol, self.label = symbol, label
        self.collection, self.covers = collection, covers
        self.active = False
        self.playing = False
        self.layer = StateLayer(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(label)
        self.setToolTip(label if len(label) > 22 else '')
        self.setFixedHeight(40 if collection is not None else 36)
        if covers is not None and collection is not None:
            covers.updated.connect(self._cover)

    def _cover(self, key):
        if key == self.collection.id or key in self.collection.keys[:12]:
            self.update()

    def set_active(self, active):
        if active != self.active:
            self.active = active
            self.update()

    def set_playing(self, playing):
        if playing != self.playing:
            self.playing = playing
            self.update()

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def contextMenuEvent(self, event):
        self.menu_requested.emit(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        if self.active or self.layer.amount:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('nav_selected') if self.active else color('tint', round(12 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        pad = metric('space_m')
        if self.collection is not None:
            side = 28
            cover = QRect(pad - 2, (self.height() - side) // 2, side, side)
            if self.collection.kind == 'favorites':
                paint_favorites_cover(painter, QRectF(cover), 6)
            else:
                pixmap = self.covers.collection_pixmap(self.collection, side, 6, self.devicePixelRatioF())
                draw_art(painter, cover, pixmap, 6, 'queue_music')
            text_left = cover.right() + metric('space_m')
        else:
            paint_symbol(painter, QRect(pad - 4, 0, 28, self.height()), self.symbol,
                         'accent' if self.active else 'glyph', 21,
                         filled=self.active and self.symbol not in OUTLINE_ONLY)
            text_left = pad + 24 + metric('space_s')
        right = self.width() - pad - (22 if self.playing else 0)
        painter.setFont(text_font('body', 600 if self.active else 450))
        painter.setPen(color('text_strong' if self.active else 'text'))
        painter.drawText(QRect(text_left, 0, right - text_left, self.height()), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self.label, Qt.ElideRight, right - text_left))
        if self.playing:
            paint_symbol(painter, QRect(self.width() - pad - 20, 0, 20, self.height()), 'graphic_eq', 'accent', 18)
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(color('focus'))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)


def section_label(text):
    label = QLabel(text.upper())
    font = text_font('caption', 700)
    font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1.1)
    label.setFont(font)
    label.setObjectName('muted')
    label.setContentsMargins(metric('space_m'), metric('space_m'), 0, metric('space_xs'))
    return label


class Sidebar(QWidget):
    navigate = Signal(tuple)
    create_playlist = Signal()
    menu_requested = Signal(object, object)   # Collection, global position

    def __init__(self, library, covers, player, parent=None):
        super().__init__(parent)
        self.library, self.covers, self.player = library, covers, player
        self.route = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(metric('space_xs'), 0, 0, 0)
        layout.setSpacing(metric('space_s'))

        self.search = SearchField()
        layout.addWidget(self.search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        self.column = QVBoxLayout(content)
        self.column.setContentsMargins(0, 0, metric('space_xs'), metric('space_m'))
        self.column.setSpacing(1)
        self.items = {}
        for title, entries in (('Escuchar', LISTEN), ('Biblioteca', LIBRARY)):
            self.column.addWidget(section_label(title))
            for key, symbol, label, route in entries:
                item = NavItem(symbol, label)
                item.clicked.connect(lambda route=route: self.navigate.emit(route))
                self.items[key] = (item, route)
                self.column.addWidget(item)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(section_label('Playlists'), 1)
        add = IconButton('add', 'Nueva playlist · Ctrl+N', self.create_playlist.emit, size=28)
        header.addWidget(add, 0, Qt.AlignBottom)
        self.column.addLayout(header)
        self.playlists = QVBoxLayout()
        self.playlists.setSpacing(1)
        self.column.addLayout(self.playlists)
        self.column.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.playlist_items = []

        library.changed.connect(self.refresh)
        player.track_changed.connect(lambda _: self._sync_playing())
        player.state_changed.connect(self._sync_playing)
        self.refresh()

    def refresh(self):
        for item in self.playlist_items:
            item.hide()
            item.deleteLater()
        self.playlist_items = []
        for collection in self.library.collections():
            if collection.kind in ('favorites', 'album'):
                continue  # favorites and albums have their own library entries
            item = NavItem('queue_music', collection.title, collection=collection, covers=self.covers)
            route = ('collection', collection.id)
            item.clicked.connect(lambda route=route: self.navigate.emit(route))
            item.menu_requested.connect(lambda position, c=collection: self.menu_requested.emit(c, position))
            self.playlists.addWidget(item)
            self.playlist_items.append(item)
        if self.route:
            self.set_route(self.route)
        self._sync_playing()

    def set_route(self, route):
        self.route = route
        for item, target in self.items.values():
            item.set_active(route[:1] == target[:1] if target[0] in ('search', 'home', 'downloads', 'artists', 'albums')
                            else route == target)
        for item in self.playlist_items:
            item.set_active(route == ('collection', item.collection.id))

    def _sync_playing(self):
        context = self.player.queue.context if self.player.current else None
        for item in self.playlist_items:
            item.set_playing(item.collection.id == context and self.player.playing)
