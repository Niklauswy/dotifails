"""The player as QML sees it: state as properties, intents as slots (PlayerBridge)."""
from PySide6.QtCore import Property, QObject, Signal, Slot

from wysun_music.store import artists
from .text import clock

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
