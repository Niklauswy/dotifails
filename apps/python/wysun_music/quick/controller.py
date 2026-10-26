"""What the QML UI asks of the library: navigation destinations, routes and (in later parts) page data."""
from PySide6.QtCore import Property, QObject, Signal, Slot

from wysun_music.library import FAVORITES, RECENT
from . import routes

LISTEN = ({'id': 'home', 'icon': 'home', 'label': 'Inicio', 'railOrder': 0},
          {'id': 'search', 'icon': 'explore', 'label': 'Explorar', 'railOrder': 1},
          {'id': 'downloads', 'icon': 'download', 'label': 'Añadir música', 'railLabel': 'Añadir', 'railOrder': 4})
LIBRARY = ({'id': 'library:songs', 'icon': 'music_note', 'label': 'Canciones', 'rail': False},
           {'id': 'library:artists', 'icon': 'artist', 'label': 'Artistas', 'rail': False},
           {'id': 'library:albums', 'icon': 'album', 'label': 'Álbumes', 'railLabel': 'Biblioteca',
            'railIcon': 'library_music', 'railOrder': 2},
           {'id': 'collection:' + RECENT, 'icon': 'history', 'label': 'Recientes', 'rail': False},
           {'id': 'collection:' + FAVORITES, 'icon': 'favorite', 'label': 'Tus me gusta', 'rail': False},
           {'id': 'library:lists', 'icon': 'queue_music', 'label': 'Listas', 'drawer': False, 'railOrder': 3})


class MusicController(QObject):
    destinationsChanged = Signal()
    hideRequested = Signal()
    navigateRequested = Signal(str)

    def __init__(self, library, covers, player, cover_urls=None, test=False, parent=None):
        super().__init__(parent)
        self.library, self.covers, self.player = library, covers, player
        self.urls = cover_urls
        self.test = test
        self.route = routes.restore((library.store.get('ui', {}) if not test else {}).get('route'))
        library.changed.connect(self.destinationsChanged)
        player.track_changed.connect(lambda _: self.destinationsChanged.emit())
        player.state_changed.connect(self.destinationsChanged)
        if cover_urls is not None:
            cover_urls.revisionChanged.connect(self.destinationsChanged)

    # ------------------------------------------------------------ navigation
    def _playlists(self):
        playing = self.player.queue.context if self.player.current and self.player.playing else None
        items = []
        for collection in self.library.collections():
            if collection.kind in ('favorites', 'album'):
                continue        # favourites and albums have their own library entries
            covers = self.urls.collection(collection.id) if self.urls is not None else []
            items.append({'id': 'collection:' + collection.id, 'icon': 'queue_music', 'label': collection.title,
                          'image': covers[0] if covers else '', 'rail': False,
                          'trailingIcon': 'graphic_eq' if collection.id == playing else ''})
        return items

    def _destinations(self):
        return ([{'header': 'Escuchar'}, *LISTEN, {'divider': True}, {'header': 'Biblioteca'}, *LIBRARY,
                 {'divider': True}, {'header': 'Playlists', 'action': 'add', 'actionId': 'new-playlist',
                                     'actionLabel': 'Nueva playlist · Ctrl+N'}, *self._playlists()])

    destinations = Property('QVariantList', _destinations, notify=destinationsChanged)

    @Property(str, constant=True)
    def initialRoute(self):
        return self.route

    @Slot(str, result=bool)
    def routeExists(self, route):
        if not routes.valid(route):
            return False
        kind, _, rest = route.partition(':')
        return kind != 'collection' or self.library.collection(rest) is not None

    @Slot(str)
    def saveRoute(self, route):
        if routes.valid(route):
            self.route = route

    def save_ui(self):
        if not self.test:
            self.library.store.put('ui', dict(route=routes.store(self.route)))

    @Slot()
    def requestHide(self):
        self.hideRequested.emit()
