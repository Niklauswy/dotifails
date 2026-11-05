"""List models for the QML UI. Rows are library keys or collections; everything shown is read from the library
when asked (``data``), so a model only holds keys and refreshes the roles that can change in place."""
from PySide6.QtCore import Property, QAbstractListModel, QByteArray, QModelIndex, Qt, Signal, Slot

from wysun_music.store import artists
from .text import clock, songs


def _roles(names):
    return {Qt.UserRole + i: QByteArray(name.encode()) for i, name in enumerate(names)}


class _KeyedModel(QAbstractListModel):
    countChanged = Signal()
    NAMES = ()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._names = {Qt.UserRole + i: n for i, n in enumerate(self.NAMES)}

    def roleNames(self):
        return _roles(self.NAMES)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def _reset(self, rows):
        rows = list(rows)
        if self._same(rows):
            # Same rows: refresh their data in place, so views keep selection, current row and scroll.
            self._rows = rows
            if rows:
                self.dataChanged.emit(self.index(0), self.index(len(rows) - 1))
            return
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()
        self.countChanged.emit()

    def _changed(self, *names):
        if self._rows:
            roles = [r for r, n in self._names.items() if n in names]
            self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1), roles)

    def _same(self, rows):
        return rows == self._rows

    @Property(int, notify=countChanged)
    def count(self):
        return len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self.value(self._rows[index.row()], self._names.get(role), index.row())

    def value(self, row, name, number):
        raise NotImplementedError


class TrackListModel(_KeyedModel):
    """Songs by key. ``favorite``, ``current``/``playing`` and ``cover`` follow the library, player and covers."""
    NAMES = ('key', 'title', 'artist', 'artists', 'album', 'duration', 'durationText', 'favorite', 'cover',
             'current', 'playing', 'number', 'local')

    def __init__(self, library, player, urls, parent=None):
        super().__init__(parent)
        self.library, self.player, self.urls = library, player, urls
        # Bound slots (not lambdas): Qt drops these connections when a released model is deleted.
        library.favorites_changed.connect(self._favorites)
        player.track_changed.connect(self._track)
        player.state_changed.connect(self._state)
        urls.revisionChanged.connect(self._covers)

    @Slot()
    def _favorites(self):
        self._changed('favorite')

    @Slot(str)
    def _track(self, _key):
        self._changed('current', 'playing')

    @Slot()
    def _state(self):
        self._changed('playing')

    @Slot()
    def _covers(self):
        self._changed('cover')

    @Slot('QVariantList')
    def setKeys(self, keys):
        self._reset([k for k in keys if self.library.track(k)])

    def set_positions(self, keys):
        """Keys kept as they are (the queue: row N must stay position N of the queue for jump/remove)."""
        self._reset(list(keys))

    @Property('QVariantList', notify=_KeyedModel.countChanged)
    def keys(self):
        return list(self._rows)

    @Slot(int, result=str)
    def keyAt(self, row):
        return self._rows[row] if 0 <= row < len(self._rows) else ''

    def value(self, key, name, number):
        track = self.library.track(key)
        if name == 'key':
            return key
        if name in ('title', 'artist'):
            return track.get(name, '')
        if name == 'artists':
            return artists(track)
        if name == 'album':
            return self.library.album(key)
        if name == 'duration':
            return float(self.library.duration(key))
        if name == 'durationText':
            return clock(self.library.duration(key))
        if name == 'favorite':
            return key in self.library.favorites
        if name == 'cover':
            return self.urls.url(key)
        if name == 'current':
            return key == self.player.current
        if name == 'playing':
            return key == self.player.current and self.player.playing
        if name == 'number':
            return number + 1
        if name == 'local':
            return self.library.available(key)
        return None


class CardListModel(_KeyedModel):
    """Collections (albums, playlists, artists) as cards; ``subtitle`` comes from the function given to set()."""
    NAMES = ('id', 'title', 'subtitle', 'kind', 'label', 'count', 'covers', 'round', 'playing', 'editable')

    def __init__(self, library, player, urls, parent=None):
        super().__init__(parent)
        self.library, self.player, self.urls = library, player, urls
        self._subtitles = {}
        player.track_changed.connect(self._track)
        player.state_changed.connect(self._state)
        urls.revisionChanged.connect(self._covers)

    @Slot(str)
    def _track(self, _key):
        self._changed('playing')

    @Slot()
    def _state(self):
        self._changed('playing')

    @Slot()
    def _covers(self):
        self._changed('covers')

    def set(self, collections, subtitle=None):
        collections = [c for c in collections if c is not None]
        self._subtitles = {c.id: (subtitle(c) if subtitle else f'{c.label} · {songs(len(c.keys))}') for c in collections}
        self._reset(collections)

    def _same(self, rows):
        return [c.id for c in rows] == [c.id for c in self._rows]

    @Property('QVariantList', notify=_KeyedModel.countChanged)
    def ids(self):
        return [c.id for c in self._rows]

    def value(self, collection, name, number):
        if name in ('id', 'title', 'kind', 'label', 'editable'):
            return getattr(collection, name)
        if name == 'subtitle':
            return self._subtitles.get(collection.id, '')
        if name == 'count':
            return len(collection.keys)
        if name == 'covers':
            return self.urls.collection(collection.id)
        if name == 'round':
            return collection.kind == 'artist'
        if name == 'playing':
            return bool(self.player.current) and self.player.playing and self.player.queue.context == collection.id
        return None
