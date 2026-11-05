"""Read model of the music library: downloads manifest + private player store.

``library.json`` belongs to the download worker; this class only reads it,
reloading when the file is replaced. Favorites, user playlists and history
live in ``MusicStore`` (sqlite) and are changed through this facade so every
view hears about it from a single signal.
"""
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

from wysun_music import data as music_data
from wysun_music.store import MusicStore, artists, normalize

# Friendlier names for the curated lists that ship with the installer.
TITLES = {'nadie-sabe': 'Nadie sabe…', 'bad-bunny': 'Bad Bunny · éxitos',
          'top-global': 'Top 100 · Global', 'top-mexico': 'Top 100 · México'}
KIND_LABELS = {'favorites': 'Playlist', 'all': 'Biblioteca', 'album': 'Álbum', 'ranking': 'Ranking',
               'playlist': 'Playlist', 'user': 'Tu playlist', 'artist': 'Artista', 'recent': 'Historial',
               'search': 'Búsqueda', 'online': 'Playlist'}
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


CATALOG_FIELDS = ('id', 'title', 'artist', 'duration', 'youtube_url', 'album', 'cover_url')


def _identity(track):
    """Title and lead artist, the way two releases of one recording are matched."""
    return (music_data.canonical(music_data.song_title(track.get('title', ''))),
            music_data.canonical(track.get('artist', '').split(',')[0]))


class Library(QObject):
    changed = Signal()            # tracks or collections changed
    favorites_changed = Signal()
    history_changed = Signal()
    online_changed = Signal()

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
        # Songs that are not on disk (Spotify lists, YouTube results, mixes): key -> track. Played ones persist.
        self.catalog = self.store.catalog()
        self.online = False
        self._online = {}
        self._aliases = {}
        self.start_downloads = music_data.start_worker
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
        # What a streamed song may already be on disk as: Spotify id, YouTube video, or title + artist + duration.
        self._aliases = {}
        for key, track in tracks.items():
            if track.get('album_audio_of'):
                continue
            for alias in track.get('spotify_ids', []):
                self._aliases[alias] = key
            if track.get('youtube_url'):
                self._aliases[track['youtube_url']] = key
            self._aliases[_identity(track)] = key

    # ---------------------------------------------------------------- tracks
    def track(self, key):
        return self.state['tracks'].get(key) or self.catalog.get(key, {})

    def available(self, key):
        track = self.state['tracks'].get(key, {})
        return track.get('status') == 'ready' and bool(track.get('path')) and Path(track['path']).is_file()

    local = available

    def known(self, key):
        return key in self.state['tracks'] or key in self.catalog

    def listenable(self, key):
        """On disk, or (with a connection) any song we know enough about to find on YouTube."""
        if self.available(key):
            return True
        return self.online and self.known(key) and not self.track(key).get('album_audio_of')

    def set_online(self, online):
        if bool(online) != self.online:
            self.online = bool(online)
            self.online_changed.emit()

    # --------------------------------------------------------------- catalog
    def _equivalent(self, track):
        key = track['id']
        if key in self.state['tracks']:
            return key
        for alias in (key, track.get('youtube_url')):
            if alias and alias in self._aliases:
                return self._aliases[alias]
        other = self._aliases.get(_identity(track))
        if other:
            expected = track.get('duration') or 0
            actual = self.state['tracks'][other].get('reference_duration') or self.state['tracks'][other].get('duration', 0)
            if not expected or not actual or abs(expected - actual) <= 3:
                return other
        return key

    def register(self, tracks):
        """Make streamed songs known; returns each one's key (its library copy's key when we already have it)."""
        keys = []
        for source in tracks:
            if not source.get('id') or not source.get('title'):
                continue
            key = self._equivalent(source)
            keys.append(key)
            if key in self.state['tracks']:
                continue
            row = {name: source[name] for name in CATALOG_FIELDS if source.get(name)}
            known = self.catalog.get(key, {})
            self.catalog[key] = {**row, **{k: v for k, v in known.items() if k == 'youtube_url'}} | {'id': key}
        return keys

    def remember_video(self, key, url):
        """The YouTube video a streamed song resolved to, so playing or downloading it again skips the search."""
        if key in self.catalog and self.catalog[key].get('youtube_url') != url:
            self.catalog[key]['youtube_url'] = url
            self.store.remember(key, self.catalog[key])

    def set_online_collections(self, collections):
        self._online = {}
        for raw in collections:
            keys = list(dict.fromkeys(self.register(raw.get('tracks', []))))
            self._online['online:' + raw['id']] = dict(title=raw.get('title', 'Playlist'), source=raw.get('source', ''),
                                                       cover_url=raw.get('cover_url') or '', tracks=keys,
                                                       note=raw.get('note', ''))
        self.changed.emit()

    def online_collections(self):
        return [self.collection(key) for key in self._online]

    def raw_collection(self, key):
        """Stored description of a list (cover URL, source), for artwork."""
        return self.state['collections'].get(key) or self._online.get(key)

    def ensure_downloaded(self, keys):
        """Liked or saved streamed songs download into «Tus descargas»."""
        tracks = []
        for key in dict.fromkeys(keys):
            if key in self.state['tracks'] or key not in self.catalog:
                continue
            track = dict(self.catalog[key], id=key)
            if len(key) == 22 and key.isalnum():
                track['prefer_audio'] = True
            tracks.append(track)
        if not tracks:
            return
        music_data.enqueue({'collections': [{'id': 'personal', 'title': 'Tus descargas', 'append': True,
                                             'source': 'Wysun', 'tracks': tracks}]})
        self.reload(force=True)
        self.start_downloads()

    def playable(self, key):
        """The audio file to play for ``key``: the album cut when it matches the reference."""
        tracks = self.state['tracks']
        preferred = self._variants.get(key, key)
        variant = tracks.get('album-audio-' + key, {})
        reference = self._references.get(key, {})
        if variant.get('status') == 'ready' and abs(variant.get('duration', 0) - (reference.get('duration') or 0)) <= 2:
            preferred = 'album-audio-' + key
        return tracks[preferred] if self.available(preferred) else self.track(key)

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
        result += [Collection(p['id'], p['title'], 'user', [k for k in p['tracks'] if self._listed(k)])
                   for p in self.store.playlists()]
        for key in self.state['collections']:
            if key not in HIDDEN:
                result.append(self.collection(key))
        return result

    def collection(self, key):
        if key == FAVORITES:
            waiting = sorted(k for k in self.favorites if k not in self._haystack and self.known(k))
            return Collection(FAVORITES, 'Tus me gusta', 'favorites',
                              [k for k in self._keys if k in self.favorites] + waiting)
        if key == ALL:
            return Collection(ALL, 'Todas las canciones', 'all', self.all_keys())
        if key == RECENT:
            return Collection(RECENT, 'Escuchado recientemente', 'recent',
                              [k for k in self.store.recent(50) if k in self._haystack or k in self.catalog])
        if key.startswith('user-'):
            playlist = next((p for p in self.store.playlists() if p['id'] == key), None)
            if playlist:
                return Collection(key, playlist['title'], 'user', [k for k in playlist['tracks'] if self._listed(k)])
            return None
        if key.startswith('artist:'):
            name = key.split(':', 1)[1]
            return Collection(key, name, 'artist', list(self._artists.get(name, [])))
        if key in self._online:
            raw = self._online[key]
            return Collection(key, raw['title'], 'online', list(raw['tracks']), raw['source'], '', raw['cover_url'])
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

    def _listed(self, key):
        """Songs a user list shows: on disk, or still downloading / waiting (they stream meanwhile)."""
        return key in self._haystack or (self.known(key) and not self.track(key).get('album_audio_of'))

    def artists(self):
        """Artist name -> keys, featured credits included."""
        return self._artists

    def artist_albums(self, name):
        wanted = normalize(name)
        return [c for c in self.collections() if c.kind == 'album'
                and any(wanted in map(normalize, artists(self.track(k))) for k in c.keys)]

    # -------------------------------------------------------------- mutations
    def toggle_favorite(self, key):
        if self.store.toggle(key):
            self.ensure_downloaded([key])
        self.favorites = self.store.favorites()
        self.favorites_changed.emit()

    def create_playlist(self, title, keys=()):
        key = self.store.create_playlist(title.strip() or 'Mi playlist')
        if keys:
            self.store.add_to_playlist(key, list(keys))
            self.ensure_downloaded(keys)
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
        self.ensure_downloaded(keys)
        self.changed.emit()

    def remove_from_playlist(self, key, keys):
        self.store.remove_from_playlist(key, list(keys))
        self.changed.emit()

    def record_play(self, key):
        if key in self.catalog and key not in self.state['tracks']:
            self.store.remember(key, self.catalog[key])
        self.store.record_play(key)
        self.history_changed.emit()

    def refresh_references(self):
        self._references = self.store.references()
        self._index()
        self.changed.emit()

    # ------------------------------------------------------------- downloads
    def download_counts(self):
        counts = dict(ready=0, pending=0, downloading=0, error=0, missing=0)
        for track in self.state['tracks'].values():
            counts[track.get('status')] = counts.get(track.get('status'), 0) + 1
        return counts

    def unfinished(self):
        return [(k, t) for k, t in self.state['tracks'].items() if t.get('status') != 'ready']
