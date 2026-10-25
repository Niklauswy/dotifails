"""Left column: search, "Escuchar", "Biblioteca" and the playlists, in one quiet list.

No containers of its own: the column sits on the window material and the
content area is the only raised surface, so the eye goes to the music.
"""
from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from wysun_core.qt_theme import color, tokens
from wysun_core.ui.style import metric, text_font
from wysun_core.ui.style import paint_symbol
from wysun_core.ui.panels import NavItem, SearchField, section_label
from wysun_core.ui.widgets import IconButton
from .widgets import draw_art, paint_favorites_cover

LISTEN = (('home', 'home', 'Inicio', ('home',)), ('search', 'explore', 'Explorar', ('search', '')),
          ('downloads', 'download', 'Añadir música', ('downloads',)))
LIBRARY = (('all', 'music_note', 'Canciones', ('collection', 'all')),
           ('artists', 'artist', 'Artistas', ('artists',)),
           ('albums', 'album', 'Álbumes', ('albums',)),
           ('recent', 'history', 'Recientes', ('collection', 'recent')),
           ('favorites', 'favorite', 'Tus me gusta', ('collection', 'favorites')))


class CollectionNavItem(NavItem):
    """A playlist row: its artwork instead of a symbol."""

    def __init__(self, label, collection, covers, parent=None):
        super().__init__('queue_music', label, parent)
        self.collection, self.covers = collection, covers
        self.setFixedHeight(40)
        covers.updated.connect(self._cover)

    def _cover(self, key):
        if key == self.collection.id or key in self.collection.keys[:12]:
            self.update()

    def paint_leading(self, painter, pad):
        side = 28
        cover = QRect(pad - 2, (self.height() - side) // 2, side, side)
        if self.collection.kind == 'favorites':
            paint_favorites_cover(painter, QRectF(cover), 6)
        else:
            pixmap = self.covers.collection_pixmap(self.collection, side, 6, self.devicePixelRatioF())
            draw_art(painter, cover, pixmap, 6, 'queue_music')
        return cover.right() + metric('space_m')


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

        self.search = SearchField('Buscar en tu biblioteca')
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
            item = CollectionNavItem(collection.title, collection, self.covers)
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
