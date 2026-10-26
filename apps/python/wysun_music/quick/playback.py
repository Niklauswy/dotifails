"""The player as QML sees it: state as properties, intents as slots (PlayerBridge); the queue as models; the lyrics
of the current song with their timing (LyricsBridge)."""
import bisect

from PySide6.QtCore import Property, QObject, Signal, Slot

from wysun_music.store import artists, parse_lrc
from .models import TrackListModel
from .text import clock

MESSAGES = {'idle': 'Reproduce una canción para ver su letra.', 'loading': 'Buscando letra…',
            'instrumental': 'Instrumental · no hay letra',
            'missing': 'La letra no está disponible para esta versión.'}

REPEAT_LABELS = {'off': 'Repetir', 'all': 'Repetir lista', 'one': 'Repetir canción'}


class PlayerBridge(QObject):
    trackChanged = Signal()
    stateChanged = Signal()
    positionChanged = Signal()
    queueChanged = Signal()
    message = Signal(str)

    def __init__(self, library, player, urls, parent=None):
        super().__init__(parent)
        self.library, self.player, self.urls = library, player, urls
        player.track_changed.connect(lambda _: self.trackChanged.emit())
        player.state_changed.connect(self.stateChanged)
        player.position_changed.connect(lambda _: self.positionChanged.emit())
        player.duration_changed.connect(lambda _: self.positionChanged.emit())
        player.queue_changed.connect(self.queueChanged)
        player.queue_changed.connect(self.stateChanged)        # canNext follows the queue
        player.message.connect(self.message)
        library.favorites_changed.connect(self.trackChanged)
        urls.revisionChanged.connect(self.trackChanged)
        self.upcoming = TrackListModel(library, player, urls, self)
        self.nowModel = TrackListModel(library, player, urls, self)
        player.queue_changed.connect(self._queue)
        player.track_changed.connect(lambda _: self._queue())
        self._queue()

    def _queue(self):
        self.upcoming.setKeys(self.player.queue.upcoming())
        self.nowModel.setKeys([self.player.current] if self.player.current else [])
        self.queueChanged.emit()

    @Property(QObject, constant=True)
    def upcomingModel(self):
        return self.upcoming

    @Property(QObject, constant=True)
    def currentModel(self):
        return self.nowModel

    @Property(str, notify=queueChanged)
    def contextTitle(self):
        context = self.player.queue.context
        collection = self.library.collection(context) if context else None
        return ('De ' + collection.title) if collection and self.player.queue.upcoming() else ''

    # ------------------------------------------------------------- the song
    def _track(self):
        return self.library.track(self.player.current) if self.player.current else {}

    @Property(str, notify=trackChanged)
    def currentKey(self):
        return self.player.current or ''

    @Property(str, notify=trackChanged)
    def title(self):
        return self._track().get('title', '')

    @Property(str, notify=trackChanged)
    def artist(self):
        return self._track().get('artist', '')

    @Property('QVariantList', notify=trackChanged)
    def artists(self):
        return artists(self._track()) if self.player.current else []

    @Property(str, notify=trackChanged)
    def album(self):
        return self.library.album(self.player.current) if self.player.current else ''

    @Property(str, notify=trackChanged)
    def coverUrl(self):
        return self.urls.url(self.player.current) if self.player.current else ''

    @Property(bool, notify=trackChanged)
    def favorite(self):
        return bool(self.player.current) and self.player.current in self.library.favorites

    @Property(str, notify=trackChanged)
    def quality(self):
        audio = self.library.playable(self.player.current) if self.player.current else {}
        codec = audio.get('codec', '').upper()
        bitrate = round(audio.get('bitrate', 0) / 1000)
        return f'{codec} · {bitrate} kb/s' if codec and bitrate else codec

    # ------------------------------------------------------------ the state
    @Property(bool, notify=stateChanged)
    def paused(self):
        return self.player.paused or self.player.ended or not self.player.current

    @Property(bool, notify=stateChanged)
    def playing(self):
        return self.player.playing and not self.player.ended

    @Property(int, notify=stateChanged)
    def volume(self):
        return int(self.player.volume)

    @Property(bool, notify=stateChanged)
    def muted(self):
        return bool(self.player.muted)

    @Property(str, notify=stateChanged)
    def volumeIcon(self):
        muted = self.player.muted or not self.player.volume
        return 'volume_off' if muted else 'volume_down' if self.player.volume < 50 else 'volume_up'

    @Property(bool, notify=stateChanged)
    def shuffle(self):
        return bool(self.player.shuffle)

    @Property(str, notify=stateChanged)
    def repeat(self):
        return self.player.repeat

    @Property(str, notify=stateChanged)
    def repeatLabel(self):
        return REPEAT_LABELS[self.player.repeat]

    @Property(bool, notify=stateChanged)
    def canNext(self):
        return self.player.can_next()

    @Property(bool, notify=stateChanged)
    def canPrevious(self):
        return self.player.can_previous()

    @Property(str, notify=stateChanged)
    def contextId(self):
        return self.player.queue.context or '' if self.player.current else ''

    @Property(float, notify=positionChanged)
    def position(self):
        return float(self.player.position)

    @Property(float, notify=positionChanged)
    def duration(self):
        return float(self.player.duration)

    @Property(str, notify=positionChanged)
    def positionText(self):
        return clock(self.player.position)

    @Property(str, notify=positionChanged)
    def durationText(self):
        return clock(self.player.duration)

    # -------------------------------------------------------------- intents
    @Slot()
    def toggle(self):
        self.player.toggle()

    @Slot()
    def next(self):
        self.player.next()

    @Slot()
    def previous(self):
        self.player.previous()

    @Slot(float)
    def seek(self, seconds):
        self.player.seek(seconds)

    @Slot(float)
    def seekBy(self, delta):
        if self.player.current:
            self.player.seek(max(0.0, self.player.position + delta))

    @Slot(int)
    def setVolume(self, value):
        self.player.set_volume(max(0, min(100, int(value))))

    @Slot(int)
    def changeVolume(self, delta):
        self.setVolume(self.player.volume + delta)

    @Slot()
    def toggleMute(self):
        self.player.toggle_mute()

    @Slot(bool)
    def setShuffle(self, enabled):
        self.player.set_shuffle(enabled)

    @Slot()
    def cycleRepeat(self):
        self.player.cycle_repeat()

    @Slot()
    def toggleFavorite(self):
        if self.player.current:
            self.library.toggle_favorite(self.player.current)

    @Slot(str, 'QVariantList', str)
    def play(self, key, context_keys, context_id):
        """``key`` within ``context_keys`` (the list it was picked from); the same key again toggles."""
        if key == self.player.current and self.player.queue.context == (context_id or None):
            self.player.toggle()
        else:
            self.player.play(key, list(context_keys) or [key], context_id or None)

    @Slot(str, str, bool)
    def playCollection(self, collection_id, start_key, shuffle):
        collection = self.library.collection(collection_id)
        if collection is not None:
            self.player.play_collection(collection.keys, start_key or None, collection.id,
                                        True if shuffle else None)

    @Slot(str)
    def toggleCollection(self, collection_id):
        """The big play button: pause/resume its own context, or start it."""
        if self.player.current and self.player.queue.context == collection_id:
            self.player.toggle()
        else:
            self.playCollection(collection_id, '', False)

    @Slot()
    def shuffleLibrary(self):
        self.player.play_collection(self.library.all_keys(), context='all', shuffle=True)

    @Slot('QVariantList')
    def addToQueue(self, keys):
        self.player.add_to_queue(list(keys))

    @Slot('QVariantList')
    def playNext(self, keys):
        self.player.play_next(list(keys))

    @Slot(int)
    def removeUpcoming(self, index):
        self.player.remove_upcoming(index)

    @Slot(int)
    def jumpTo(self, index):
        self.player.jump_to_upcoming(index)


class LyricsBridge(QObject):
    """Lyrics of the current song from LRCLIB (via Metadata), fetched while the lyrics are wanted (``active``).
    Synced lines follow the position plus the song's own offset (``offset:<key>`` in the store)."""
    changed = Signal()
    currentChanged = Signal()

    def __init__(self, library, metadata, player, parent=None):
        super().__init__(parent)
        self.library, self.metadata, self.player = library, metadata, player
        self._active = False
        self._key = ''
        self._state = 'idle'
        self._lines = []
        self._times = []
        self._current = -1
        metadata.ready.connect(self._ready)
        player.track_changed.connect(lambda _: self._request())
        player.position_changed.connect(self._position)
        player.seeked.connect(self._position)

    # -------------------------------------------------------------- fetching
    @Property(bool, notify=changed)
    def active(self):
        return self._active

    @active.setter
    def active(self, value):
        if value != self._active:
            self._active = bool(value)
            self.changed.emit()
            self._request()

    def _request(self):
        key = self.player.current
        if not key:
            self._set('idle', [])
            self._key = ''
            return
        if not self._active:
            return
        audio = self.library.playable(key)
        lyric_key = f"{key}:{round(audio.get('duration', 0), 2)}"
        if lyric_key == self._key:
            return
        self._key = lyric_key
        self._set('loading', [])
        track = self.library.track(key)
        self.metadata.lyrics(lyric_key, dict(audio, title=track.get('title', ''), artist=track.get('artist', '')),
                             self.library.store.reference(key))

    def _ready(self, kind, key, data):
        if kind != 'lyrics' or key != self._key:
            return
        synced = parse_lrc(data.get('synced'))
        if synced:
            self._set('synced', [{'time': t, 'text': text} for t, text in synced])
        elif data.get('plain'):
            self._set('plain', [{'time': -1, 'text': line or ' '} for line in data['plain'].splitlines()])
        else:
            self._set('instrumental' if data.get('instrumental') else 'missing', [])
        self._position(self.player.position)

    def _set(self, state, lines):
        self._state, self._lines = state, lines
        self._times = [line['time'] for line in lines] if state == 'synced' else []
        self._current = -1
        self.changed.emit()
        self.currentChanged.emit()

    # ---------------------------------------------------------------- timing
    def _offset(self):
        return float(self.library.store.get('offset:' + str(self.player.current), 0) or 0)

    def _position(self, seconds):
        if not self._times:
            return
        index = bisect.bisect_right(self._times, seconds + self._offset()) - 1
        if index != self._current:
            self._current = index
            self.currentChanged.emit()

    @Property(str, notify=changed)
    def state(self):
        return self._state

    @Property(str, notify=changed)
    def message(self):
        return MESSAGES.get(self._state, '')

    @Property('QVariantList', notify=changed)
    def lines(self):
        return self._lines

    @Property(bool, notify=changed)
    def hasLyrics(self):
        return bool(self._lines)

    @Property(int, notify=currentChanged)
    def currentIndex(self):
        return self._current

    @Property(str, notify=changed)
    def source(self):
        if not self._lines:
            return ''
        return ('Sincronizada' if self._state == 'synced' else 'Sin sincronizar') + ' · LRCLIB'

    @Property(float, notify=changed)
    def offset(self):
        return self._offset()

    @Property(str, notify=changed)
    def offsetText(self):
        return f'{self._offset():+.1f} s'

    @Slot(int)
    def seekLine(self, index):
        if self._state == 'synced' and 0 <= index < len(self._times):
            self.player.seek(max(0.0, self._times[index] - self._offset()))

    @Slot(float)
    def nudge(self, amount):
        """±0.5 s: lyrics earlier (−) or later (+) for this song, kept in the store."""
        if not self.player.current or self._state != 'synced':
            return
        value = round(self._offset() + amount, 1)
        self.library.store.put('offset:' + self.player.current, value)
        self.changed.emit()
        self._position(self.player.position)
