"""Read model of the music library: downloads manifest + private player store.

``library.json`` belongs to the download worker; this class only reads it,
reloading when the file is replaced. Favorites, user playlists and history
live in ``MusicStore`` (sqlite) and are changed through this facade so every
view hears about it from a single signal.
"""
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

import music_data
from music_library import MusicStore, artists, normalize

# Friendlier names for the curated lists that ship with the installer.
TITLES = {'nadie-sabe': 'Nadie sabe…', 'bad-bunny': 'Bad Bunny · éxitos',
          'top-global': 'Top 100 · Global', 'top-mexico': 'Top 100 · México'}
KIND_LABELS = {'favorites': 'Playlist', 'all': 'Biblioteca', 'album': 'Álbum', 'ranking': 'Ranking',
               'playlist': 'Playlist', 'user': 'Tu playlist', 'artist': 'Artista', 'recent': 'Historial',
               'search': 'Búsqueda'}
HIDDEN = {'audio-versions'}
FAVORITES, ALL, RECENT = 'favorites', 'all', 'recent'


@dataclass
class Collection:
    id: str
    title: str
    kind: str
    keys: list = field(default_factory=list)
    source: str = ''
    date: str = ''
    cover_url: str = ''

    @property
    def label(self):
        return KIND_LABELS.get(self.kind, 'Playlist')

    @property
    def editable(self):
        return self.kind == 'user'


class Library(QObject):
    changed = Signal()            # tracks or collections changed
    favorites_changed = Signal()
    history_changed = Signal()

    def __init__(self, store=None, watch=True, parent=None):
        super().__init__(parent)
        self.store = store or MusicStore(music_data.DATA)
        self.state = music_data.empty()
        self.favorites = set()
        self._references = {}
        self._variants = {}
        self._keys = []
        self._haystack = {}
        self._artists = {}
        self._mtime = None
        self._reload_timer = QTimer(self, singleShot=True, interval=150)
        self._reload_timer.timeout.connect(self.reload)
        self._watcher = None
        if watch:
            music_data.DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Watch the directory: the worker replaces library.json atomically.
            self._watcher = QFileSystemWatcher([str(music_data.DATA)], self)
            self._watcher.directoryChanged.connect(lambda _: self._reload_timer.start())
        self.reload(force=True)

    # --------------------------------------------------------------- loading
    def reload(self, force=False):
        path = Path(music_data.DATA) / 'library.json'
        try:
            mtime = path.stat().st_mtime_ns
        except FileNotFoundError:
            mtime = 0
        if mtime == self._mtime and not force:
            return
        try:
            self.state = music_data.read_state()
        except (OSError, ValueError):
            return
        self._mtime = mtime
        self.favorites = self.store.favorites()
        self._references = self.store.references()
        self._variants = self.store.variants()
        self._index()
        self.changed.emit()

    def _index(self):
        tracks = self.state['tracks']
        self._keys = [k for k, t in tracks.items() if not t.get('album_audio_of') and self.available(k)]
        self._haystack = {k: normalize(' '.join((tracks[k]['title'], tracks[k]['artist'], self.album(k))))
                          for k in self._keys}
        self._artists = {}
        for key in self._keys:
            for name in artists(tracks[key]):
                self._artists.setdefault(name, []).append(key)

    # ---------------------------------------------------------------- tracks
    def track(self, key):
        return self.state['tracks'].get(key, {})

    def available(self, key):
        track = self.state['tracks'].get(key, {})
        return track.get('status') == 'ready' and bool(track.get('path')) and Path(track['path']).is_file()

    def playable(self, key):
        """The audio file to play for ``key``: the album cut when it matches the reference."""
        tracks = self.state['tracks']
        preferred = self._variants.get(key, key)
        variant = tracks.get('album-audio-' + key, {})
        reference = self._references.get(key, {})
        if variant.get('status') == 'ready' and abs(variant.get('duration', 0) - (reference.get('duration') or 0)) <= 2:
            preferred = 'album-audio-' + key
        return tracks[preferred] if self.available(preferred) else tracks.get(key, {})

    def all_keys(self):
        return list(self._keys)

    def album(self, key):
        return self._references.get(key, {}).get('album') or self.state['tracks'].get(key, {}).get('album', '')

    def duration(self, key):
        return self.playable(key).get('duration', 0) or self.track(key).get('duration', 0)

    def spotify_url(self, key):
        reference = self._references.get(key, {})
        if reference.get('spotify'):
            return reference['spotify']
        return 'https://open.spotify.com/track/' + key if len(key) == 22 and key.isalnum() else ''

    def search(self, query):
        words = normalize(query).split()
        if not words:
            return []
        return [k for k in self._keys if all(word in self._haystack[k] for word in words)]

    # ------------------------------------------------------------ collections
    def collections(self):
        """Library sidebar order: favorites, user playlists, then imported lists."""
        result = [self.collection(FAVORITES)]
        result += [Collection(p['id'], p['title'], 'user', [k for k in p['tracks'] if k in self._haystack])
                   for p in self.store.playlists()]
        for key in self.state['collections']:
            if key not in HIDDEN:
                result.append(self.collection(key))
        return result

    def collection(self, key):
        if key == FAVORITES:
            return Collection(FAVORITES, 'Tus me gusta', 'favorites', [k for k in self._keys if k in self.favorites])
        if key == ALL:
            return Collection(ALL, 'Todas las canciones', 'all', self.all_keys())
        if key == RECENT:
            return Collection(RECENT, 'Escuchado recientemente', 'recent',
                              [k for k in self.store.recent(50) if k in self._haystack])
        if key.startswith('user-'):
            playlist = next((p for p in self.store.playlists() if p['id'] == key), None)
            if playlist:
                return Collection(key, playlist['title'], 'user', [k for k in playlist['tracks'] if k in self._haystack])
            return None
        if key.startswith('artist:'):
            name = key.split(':', 1)[1]
            return Collection(key, name, 'artist', list(self._artists.get(name, [])))
        if key.startswith('search:'):
            query = key.split(':', 1)[1]
            return Collection(key, f'«{query}»', 'search', self.search(query))
        raw = self.state['collections'].get(key)
        if raw is None:
            return None
        source = raw.get('source', '')
        kind = 'ranking' if raw.get('date') else 'album' if '/album/' in source else 'playlist'
        keys = [k for k in raw.get('tracks', []) if k in self._haystack]
        return Collection(key, TITLES.get(key, raw.get('title', 'Playlist')), kind, keys, source,
                          raw.get('date', ''), raw.get('cover_url', ''))

    def artists(self):
        """Artist name -> keys, featured credits included."""
        return self._artists

    def artist_albums(self, name):
        wanted = normalize(name)
        return [c for c in self.collections() if c.kind == 'album'
                and any(wanted in map(normalize, artists(self.track(k))) for k in c.keys)]

    # -------------------------------------------------------------- mutations
    def toggle_favorite(self, key):
        self.store.toggle(key)
        self.favorites = self.store.favorites()
        self.favorites_changed.emit()

    def create_playlist(self, title, keys=()):
        key = self.store.create_playlist(title.strip() or 'Mi playlist')
        if keys:
            self.store.add_to_playlist(key, list(keys))
        self.changed.emit()
        return key

    def rename_playlist(self, key, title):
        self.store.rename_playlist(key, title.strip() or 'Mi playlist')
        self.changed.emit()

    def delete_playlist(self, key):
        self.store.delete_playlist(key)
        self.changed.emit()

    def add_to_playlist(self, key, keys):
        self.store.add_to_playlist(key, list(keys))
        self.changed.emit()

    def remove_from_playlist(self, key, keys):
        self.store.remove_from_playlist(key, list(keys))
        self.changed.emit()

    def record_play(self, key):
        self.store.record_play(key)
        self.history_changed.emit()

    def refresh_references(self):
        self._references = self.store.references()
        self._index()
        self.changed.emit()

    # ------------------------------------------------------------- downloads
    def download_counts(self):
        counts = dict(ready=0, pending=0, downloading=0, error=0, review=0)
        for track in self.state['tracks'].values():
            counts[track.get('status')] = counts.get(track.get('status'), 0) + 1
        return counts

    def unfinished(self):
        return [(k, t) for k, t in self.state['tracks'].items() if t.get('status') != 'ready']
