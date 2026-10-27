"""What the QML UI asks of the library: navigation destinations, routes, and the data of every page as models
and plain maps. Wording and rules follow the Widgets UI it replaces (greeting, bento, shelves, bylines)."""
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from wysun_music.library import FAVORITES, RECENT, Collection
from wysun_music.store import artists, normalize
from . import routes
from .models import CardListModel, TrackListModel
from .text import greeting, long_duration, songs, today

SORTS = ('custom', 'title', 'artist', 'album', 'duration')
FILTER_FROM = 8           # the in-list filter shows for collections longer than this
SEARCH_SONGS = 5


def lead_artist(library, keys):
    """The album's artist when its songs agree, else «Varios artistas»."""
    names = {(artists(library.track(k)) or [''])[0] for k in keys[:8]}
    names.discard('')
    return names.pop() if len(names) == 1 else 'Varios artistas' if names else ''

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
    homeChanged = Signal()
    collectionChanged = Signal()
    searchChanged = Signal()

    def __init__(self, library, covers, player, cover_urls=None, test=False, parent=None):
        super().__init__(parent)
        self.library, self.covers, self.player = library, covers, player
        self.urls = cover_urls
        self.test = test
        self.route = routes.restore((library.store.get('ui', {}) if not test else {}).get('route'))
        self._playing_context = None
        library.changed.connect(self.destinationsChanged)
        player.track_changed.connect(lambda _: self._playing_changed())
        player.state_changed.connect(self._playing_changed)
        player.queue_changed.connect(self._playing_changed)
        if cover_urls is not None:
            cover_urls.revisionChanged.connect(self.destinationsChanged)
        make_tracks = lambda: TrackListModel(library, player, cover_urls, self)
        make_cards = lambda: CardListModel(library, player, cover_urls, self)
        self._home = {}
        self.homeRecent, self.homeChart = make_tracks(), make_tracks()
        self.homePlaylists, self.homeAlbums, self.homeArtists = make_cards(), make_cards(), make_cards()
        self.libraryAlbums, self.libraryArtists, self.libraryLists = make_cards(), make_cards(), make_cards()
        self.librarySongs = make_tracks()
        self.collectionTracks, self.artistAlbums = make_tracks(), make_cards()
        self.searchSongs, self.searchArtists, self.searchLists, self.explore = (make_tracks(), make_cards(),
                                                                              make_cards(), make_cards())
        self._collection_id, self._filter, self._sort = None, '', 'custom'
        self._collection = {}
        self._query, self._search = '', {}
        # Library edits arrive in bursts (a download batch): rebuild once they settle.
        self._refresh = QTimer(self, singleShot=True, interval=120)
        self._refresh.timeout.connect(self.refresh)
        library.changed.connect(self._refresh.start)
        library.history_changed.connect(self._history)
        library.favorites_changed.connect(self._favorites)
        player.track_changed.connect(lambda _: self._bento())
        self.refresh()

    # ------------------------------------------------------------ navigation
    def _playing_changed(self):
        """The drawer only changes when the list that plays (its now-playing mark) changes."""
        context = self.player.queue.context if self.player.current and self.player.playing else None
        if context != self._playing_context:
            self._playing_context = context
            self.destinationsChanged.emit()

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

    # -------------------------------------------------------------- models
    for _name in ('homeRecent', 'homeChart', 'homePlaylists', 'homeAlbums', 'homeArtists', 'libraryAlbums',
                  'libraryArtists', 'libraryLists', 'librarySongs', 'collectionTracks', 'artistAlbums',
                  'searchSongs', 'searchArtists', 'searchLists', 'explore'):
        locals()[_name + 'Model'] = Property(QObject, (lambda name: lambda self: getattr(self, name))(_name),
                                             constant=True)
    del _name

    def _history(self):
        """A play was counted: only Inicio and an open «Recientes» change."""
        self._build_home()
        if self._collection_id == RECENT:
            self._render_collection()

    def _favorites(self):
        """Hearts update in place in every list; models only reset where their rows change (Tus me gusta)."""
        self._refresh.start()

    @Slot()
    def refresh(self):
        """Rebuild every page's data from the library (cheap: models hold keys, rows read on demand)."""
        self._build_home()
        self._build_library()
        if self._collection_id is not None:
            self.openCollection(self._collection_id)
        self.setQuery(self._query, True)

    # ---------------------------------------------------------------- home
    def _album_subtitle(self, collection):
        return lead_artist(self.library, collection.keys) or songs(len(collection.keys))

    def _build_home(self):
        library = self.library
        collections = library.collections()
        others = [c for c in collections if c.id != FAVORITES and c.keys]
        recent = library.collection(RECENT)
        self.homeRecent.setKeys(recent.keys[:12])
        self.homePlaylists.set([c for c in others if c.kind != 'album'])
        self.homeAlbums.set([c for c in others if c.kind == 'album'], self._album_subtitle)
        self.homeChart.setKeys([k for k in library.store.most_played(9) if library.available(k)])
        ranked = sorted(library.artists().items(), key=lambda item: -len(item[1]))[:12]
        self.homeArtists.set([library.collection('artist:' + name) for name, _ in ranked], lambda c: songs(len(c.keys)))
        self._bento()

    def _bento(self):
        library, player = self.library, self.player
        recent = library.collection(RECENT)
        favorites = library.collection(FAVORITES)
        current = player.current or (recent.keys[0] if recent.keys else None)
        if current:
            track = library.track(current)
            resume = dict(style='resume', eyebrow='Sonando ahora' if player.current else 'Sigue escuchando',
                          title=track.get('title', ''), subtitle=track.get('artist', ''), key=current,
                          context=recent.id, action='resume')
        else:
            resume = dict(style='resume', eyebrow='Bienvenido', title='Empieza por aquí',
                          subtitle='Toda tu biblioteca, al azar', key='', action='mix')
        self._home = dict(
            greeting=greeting(), date=today(),
            bento=[resume,
                   dict(style='accent', eyebrow='Colección', title='Tus me gusta', subtitle=songs(len(favorites.keys)),
                        symbol='favorite', collection=FAVORITES, action='open'),
                   dict(style='tonal', eyebrow='Para ti', title='Mezcla', subtitle='Toda tu biblioteca, al azar',
                        symbol='shuffle', action='mix', enabled=bool(library.all_keys())),
                   dict(style='wide', eyebrow='Recientes', title='Lo último que escuchaste',
                        subtitle=' · '.join(dict.fromkeys(library.track(k).get('title', '') for k in recent.keys[:3])),
                        symbol='history', collection=RECENT, action='open', enabled=bool(recent.keys))],
            summary=self._summary(),
            empty=not library.all_keys())
        self.homeChanged.emit()

    def _summary(self):
        count = len(self.library.all_keys())
        playlists = sum(c.editable for c in self.library.collections())
        return (f'{count} canción disponible' if count == 1 else f'{count} canciones disponibles') + \
            f' · {playlists} playlist' + ('' if playlists == 1 else 's')

    @Property('QVariantMap', notify=homeChanged)
    def home(self):
        return self._home

    # ------------------------------------------------------------- library
    def _build_library(self):
        library = self.library
        self.libraryAlbums.set(sorted((c for c in library.collections() if c.kind == 'album' and c.keys),
                                      key=lambda c: normalize(c.title)), self._album_subtitle)
        ranked = sorted(library.artists().items(), key=lambda item: (-len(item[1]), normalize(item[0])))
        self.libraryArtists.set([library.collection('artist:' + name) for name, _ in ranked],
                                lambda c: songs(len(c.keys)))
        self.librarySongs.setKeys(library.all_keys())
        lists = [library.collection(FAVORITES), library.collection(RECENT)]
        lists += [c for c in library.collections() if c.kind not in ('favorites', 'album')]
        self.libraryLists.set(lists)

    # ---------------------------------------------------------- collection
    def _render_collection(self):
        library, collection = self.library, self.library.collection(self._collection_id)
        if collection is None:
            self._collection = dict(exists=False, id=self._collection_id)
            self.collectionTracks.setKeys([])
            self.collectionChanged.emit()
            return
        keys = list(collection.keys)
        query = normalize(self._filter)
        if query:
            keys = [k for k in keys if query in normalize(library.track(k).get('title', '') + ' '
                                                          + library.track(k).get('artist', ''))]
        if self._sort != 'custom':
            sorters = {'title': lambda k: normalize(library.track(k).get('title', '')),
                       'artist': lambda k: normalize(library.track(k).get('artist', '')),
                       'album': lambda k: normalize(library.album(k)), 'duration': library.duration}
            keys.sort(key=sorters[self._sort])
        self.collectionTracks.setKeys(keys)
        total = sum(library.duration(k) for k in collection.keys)
        meta = [songs(len(collection.keys)), long_duration(total)]
        if collection.date:
            meta.insert(0, 'Actualizado ' + collection.date)
        byline = {'album': lead_artist(library, collection.keys), 'user': 'Tu playlist',
                  'favorites': 'Guardadas por ti', 'recent': 'Tus últimas canciones'}.get(collection.kind, '')
        albums = []
        if collection.kind == 'artist':
            albums = library.artist_albums(collection.title)
            byline = f'{len(albums)} álbum' + ('es' if len(albums) != 1 else '') if albums else ''
        self.artistAlbums.set(albums, self._album_subtitle)
        self._collection = dict(exists=True, id=collection.id, title=collection.title, kind=collection.kind,
                                label=collection.label, byline=byline, meta=' · '.join(meta),
                                editable=collection.editable, source=collection.source, count=len(collection.keys),
                                filterable=len(collection.keys) > FILTER_FROM, sort=self._sort, filter=self._filter,
                                initials=''.join(w[0] for w in collection.title.split()[:2]).upper()
                                if collection.kind == 'artist' else '')
        self.collectionChanged.emit()

    @Slot(str, result='QVariantMap')
    def openCollection(self, collection_id):
        if collection_id != self._collection_id:
            self._filter, self._sort = '', 'custom'
        self._collection_id = collection_id
        self._render_collection()
        return self._collection

    @Property('QVariantMap', notify=collectionChanged)
    def collection(self):
        return self._collection

    @Slot(str)
    def setFilter(self, text):
        self._filter = text
        self._render_collection()

    @Slot(str)
    def setSort(self, sort):
        self._sort = sort if sort in SORTS else 'custom'
        self._render_collection()

    # -------------------------------------------------------------- search
    @Slot(str)
    @Slot(str, bool)
    def setQuery(self, text, force=False):
        query = text.strip()
        if query == self._query and not force and self._search:
            return
        self._query = query
        library = self.library
        words = normalize(query)
        if not words:
            collections = [c for c in library.collections() if c.keys]
            ranked = sorted(library.artists().items(), key=lambda item: -len(item[1]))[:8]
            self.explore.set(collections + [library.collection('artist:' + n) for n, _ in ranked])
            self._search = dict(query='', searching=False, empty=False)
            self.searchChanged.emit()
            return
        keys = library.search(query)
        names = [n for n in library.artists() if words in normalize(n)]
        names.sort(key=lambda n: (not normalize(n).startswith(words), -len(library.artists()[n])))
        lists = [c for c in library.collections() if words in normalize(c.title) and c.keys]
        self.searchSongs.setKeys(keys[:SEARCH_SONGS])
        self.searchArtists.set([library.collection('artist:' + n) for n in names[:12]], lambda c: 'Artista')
        self.searchLists.set(lists[:12])
        if names:
            top = dict(kind='artist', id='artist:' + names[0], title=names[0], subtitle='Artista')
        elif keys:
            track = library.track(keys[0])
            top = dict(kind='song', key=keys[0], title=track.get('title', ''),
                       subtitle='Canción · ' + track.get('artist', ''))
        else:
            top = {}
        self._search = dict(query=query, searching=True, top=top, songCount=len(keys),
                            allSongs=f'Ver las {songs(len(keys))}', empty=not (keys or names or lists),
                            emptyText=f'No encontramos «{query}» en tu biblioteca. Prueba otras palabras o búscalo '
                                      'en «Añadir música».')
        self.searchChanged.emit()

    @Property('QVariantMap', notify=searchChanged)
    def search(self):
        return self._search

    # --------------------------------------------------------------- songs
    @Slot(str, str, result='QVariantList')
    def songs(self, which, sort):
        """Library songs for the Canciones tab: all / recent / favorites, in library order or sorted."""
        library = self.library
        keys = (library.collection(RECENT).keys if which == 'recent' else
                library.collection(FAVORITES).keys if which == 'favorites' else library.all_keys())
        sorters = {'title': lambda k: normalize(library.track(k).get('title', '')),
                   'artist': lambda k: normalize(library.track(k).get('artist', '')),
                   'album': lambda k: normalize(library.album(k)), 'duration': library.duration}
        return sorted(keys, key=sorters[sort]) if sort in sorters else list(keys)

    @Slot(result=QObject)
    def newTrackList(self):
        """A TrackListModel owned by the controller for a page that filters on its own (released by the page)."""
        model = TrackListModel(self.library, self.player, self.urls, self)
        return model

    @Slot(QObject)
    def releaseTrackList(self, model):
        if model is not None and model.parent() is self:
            model.deleteLater()

    # ------------------------------------------------------------ actions
    @Slot(str)
    def toggleFavorite(self, key):
        if key and self.library.track(key):
            self.library.toggle_favorite(key)

    @Slot('QVariantList', bool)
    def setFavorite(self, keys, favorite):
        for key in keys:
            if key and self.library.track(key) and (key in self.library.favorites) != favorite:
                self.library.toggle_favorite(key)

    @Slot('QVariantList', result=bool)
    def allFavorite(self, keys):
        return bool(keys) and all(k in self.library.favorites for k in keys)

    # ----------------------------------------------------------- playlists
    @Slot(result=str)
    def suggestedPlaylistName(self):
        return f'Mi playlist n.º {sum(c.editable for c in self.library.collections()) + 1}'

    @Slot(result='QVariantList')
    def editablePlaylists(self):
        return [{'id': c.id, 'title': c.title} for c in self.library.collections() if c.editable]

    @Slot(str, 'QVariantList', result=str)
    def createPlaylist(self, title, keys):
        return self.library.create_playlist(title, list(keys))

    @Slot(str, str)
    def renamePlaylist(self, collection_id, title):
        self.library.rename_playlist(collection_id, title)

    @Slot(str)
    def deletePlaylist(self, collection_id):
        self.library.delete_playlist(collection_id)

    @Slot(str, 'QVariantList')
    def addToPlaylist(self, collection_id, keys):
        self.library.add_to_playlist(collection_id, list(keys))
        self.player.message.emit('Añadido a la playlist')

    @Slot(str, 'QVariantList')
    def removeFromPlaylist(self, collection_id, keys):
        self.library.remove_from_playlist(collection_id, list(keys))

    @Slot(str, result='QVariantMap')
    def collectionSummary(self, collection_id):
        """What a collection menu needs: title, whether it is editable, its Spotify source, its songs."""
        collection = self.library.collection(collection_id)
        if collection is None:
            return {}
        return {'id': collection.id, 'title': collection.title, 'editable': collection.editable,
                'source': collection.source if collection.source.startswith('https://') else '',
                'keys': list(collection.keys)}

    # ------------------------------------------------------------- desktop
    @Slot(str)
    def showInFolder(self, key):
        """Select the song's file in the file manager (FileManager1.ShowItems), else open its folder."""
        from pathlib import Path
        path = self.library.playable(key).get('path')
        if not path:
            return
        uri = Path(path).as_uri()
        try:
            from gi.repository import Gio, GLib
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call_sync('org.freedesktop.FileManager1', '/org/freedesktop/FileManager1',
                          'org.freedesktop.FileManager1', 'ShowItems', GLib.Variant('(ass)', ([uri], '')),
                          None, Gio.DBusCallFlags.NONE, 3000, None)
        except Exception:                       # no file manager on the bus: just open the folder
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    @Slot(str)
    def openUrl(self, url):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if url.startswith('https://'):
            QDesktopServices.openUrl(QUrl(url))

    @Slot(str, result=str)
    def toneOf(self, collection_id):
        """The dominant colour of a collection's artwork (``#rrggbb``) or '' (user artwork, not a theme colour)."""
        collection = self.library.collection(collection_id)
        tone = self.covers.collection_tone(collection) if collection is not None else None
        return tone.name() if tone is not None else ''

    @Slot(str, result='QVariantList')
    def trackArtists(self, key):
        return artists(self.library.track(key))

    @Slot(str, result='QVariantList')
    def searchKeys(self, query):
        """Every match (the context a search result plays in)."""
        return self.library.search(query)

    @Slot(str, result=str)
    def collectionTitle(self, collection_id):
        collection = self.library.collection(collection_id)
        return collection.title if collection else ''
