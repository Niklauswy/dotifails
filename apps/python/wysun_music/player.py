"""The single playback controller shared by the window, mini player and MPRIS."""
import random

from PySide6.QtCore import QObject, QTimer, Signal

from .engine import MpvEngine
from .queue import PlayQueue

RESTART_THRESHOLD = 3.0  # seconds: "previous" restarts the song after this point.
HISTORY_AFTER = 10.0     # seconds listened before a song counts as played.


class Player(QObject):
    track_changed = Signal(str)
    state_changed = Signal()        # paused / shuffle / repeat / volume / mute
    position_changed = Signal(float)
    duration_changed = Signal(float)
    queue_changed = Signal()
    seeked = Signal(float)
    message = Signal(str)

    def __init__(self, library, persist=True, parent=None):
        super().__init__(parent)
        self.library = library
        self.persist = persist
        self.queue = PlayQueue()
        self.current = None
        self.position = 0.0
        self.duration = 0.0
        self.ended = False
        self.muted = False
        self._counted = False
        session = library.store.get('session', {}) if persist else {}
        self.engine = MpvEngine(volume=session.get('volume', 60), parent=self)
        self.engine.position_changed.connect(self._position)
        self.engine.duration_changed.connect(self._duration)
        self.engine.pause_changed.connect(lambda _: self.state_changed.emit())
        self.engine.volume_changed.connect(lambda _: self.state_changed.emit())
        self.engine.mute_changed.connect(self._mute)
        self.engine.ended.connect(self._ended)
        self.engine.failed.connect(self.message)
        self._restore(session)
        self._save_timer = QTimer(self, interval=5000)
        self._save_timer.timeout.connect(self.save)
        if persist:
            self._save_timer.start()

    # ----------------------------------------------------------------- state
    @property
    def paused(self):
        return self.engine.paused

    @property
    def playing(self):
        return bool(self.current) and not self.engine.paused

    @property
    def volume(self):
        return self.engine.volume

    @property
    def shuffle(self):
        return self.queue.shuffle

    @property
    def repeat(self):
        return self.queue.repeat

    def can_next(self):
        return bool(self.current) and self.queue.has_next()

    def can_previous(self):
        return bool(self.current)

    # -------------------------------------------------------------- playback
    def play_collection(self, keys, start=None, context=None, shuffle=None):
        """Start ``keys`` as the playing context, from ``start`` or the beginning."""
        keys = [k for k in keys if self.library.available(k)]
        if not keys:
            return
        if shuffle is not None:
            self.queue.order.shuffle = shuffle
        if start is None:
            start = random.choice(keys) if self.queue.shuffle else keys[0]
        self.queue.start(keys, start, self.queue.shuffle, context)
        self._load(start)
        self.queue_changed.emit()

    def play(self, key, context_keys=None, context=None):
        self.play_collection(context_keys or [key], key, context)

    def toggle(self):
        if not self.current:
            keys = self.library.all_keys()
            if keys:
                self.play_collection(keys, context='all')
            return
        if self.ended or not self.engine.running:
            self._load(self.current, 0.0 if self.ended else self.position)
        else:
            self.engine.set_paused(not self.engine.paused)

    def set_paused(self, paused):
        if paused:
            if self.engine.running:
                self.engine.set_paused(True)
        elif self.paused:
            self.toggle()

    def next(self, automatic=False):
        if automatic and self.queue.repeat == 'one' and self.current:
            self._load(self.current)
            return
        key = self.queue.next(self.library.available)
        if key:
            self._load(key)
            self.queue_changed.emit()
        elif automatic:
            self.ended = True
            self.engine.set_paused(True)
            self.message.emit('Terminó la lista · pulsa reproducir para escucharla de nuevo')
            self.state_changed.emit()

    def previous(self):
        if self.position > RESTART_THRESHOLD or not self.queue.has_previous():
            self.seek(0)
            return
        key = self.queue.previous(self.library.available)
        if key:
            self._load(key)
            self.queue_changed.emit()

    def seek(self, seconds):
        if not self.current:
            return
        seconds = max(0.0, min(float(seconds), self.duration or float(seconds)))
        if self.ended or not self.engine.running:
            self._load(self.current, seconds, paused=self.paused and not self.ended)
        else:
            self.engine.seek(seconds)
        self.position = seconds
        self.position_changed.emit(seconds)
        self.seeked.emit(seconds)

    def set_volume(self, value):
        self.engine.set_volume(value)
        if self.muted and value:
            self.toggle_mute()
        self.state_changed.emit()

    def toggle_mute(self):
        self.muted = not self.muted
        self.engine.set_mute(self.muted)
        self.state_changed.emit()

    def set_shuffle(self, enabled):
        self.queue.set_shuffle(bool(enabled))
        self.state_changed.emit()
        self.queue_changed.emit()

    def set_repeat(self, mode):
        self.queue.set_repeat(mode)
        self.state_changed.emit()
        self.queue_changed.emit()

    def cycle_repeat(self):
        self.set_repeat({'off': 'all', 'all': 'one', 'one': 'off'}[self.queue.repeat])

    # ------------------------------------------------------------------ queue
    def add_to_queue(self, keys):
        self.queue.add([k for k in keys if self.library.available(k)])
        self.queue_changed.emit()
        self.message.emit('Añadido a la cola')

    def play_next(self, keys):
        self.queue.add_next([k for k in keys if self.library.available(k)])
        self.queue_changed.emit()
        self.message.emit('Sonará a continuación')

    def remove_upcoming(self, index):
        self.queue.remove_upcoming(index)
        self.queue_changed.emit()

    def jump_to_upcoming(self, index):
        """Play the n-th upcoming song, skipping everything before it."""
        for _ in range(index):
            self.queue.next(self.library.available)
        self.next()

    # -------------------------------------------------------------- internals
    def _load(self, key, start=0.0, paused=False):
        track = self.library.playable(key)
        if not track.get('path'):
            self.message.emit('Esta canción todavía no está descargada.')
            return
        changed = key != self.current
        self.current = key
        self.ended = False
        self.position = start
        self.duration = track.get('duration', 0) or self.library.duration(key)
        self._counted = start > 0 and not changed
        self.engine.load(track['path'], start, paused)
        if changed:
            self.track_changed.emit(key)
        self.duration_changed.emit(self.duration)
        self.position_changed.emit(start)
        self.state_changed.emit()

    def _position(self, value):
        self.position = value
        if not self._counted and value >= HISTORY_AFTER and self.current:
            self._counted = True
            self.library.record_play(self.current)
        self.position_changed.emit(value)

    def _duration(self, value):
        if value and abs(value - self.duration) > .05:
            self.duration = value
            self.duration_changed.emit(value)

    def _mute(self, muted):
        self.muted = muted
        self.state_changed.emit()

    def _ended(self):
        self.next(automatic=True)

    # ------------------------------------------------------------ persistence
    def _restore(self, session):
        self.queue.restore(session.get('queue') or session.get('order'))
        key = session.get('track')
        if key and self.library.available(key):
            self.current = key
            self.ended = session.get('ended', False)
            self.position = 0.0 if self.ended else session.get('position', 0.0)
            self.duration = self.library.duration(key)
        self.muted = False

    def save(self):
        if not self.persist:
            return
        session = dict(self.library.store.get('session', {}))
        session.update(track=self.current, position=self.position, ended=self.ended,
                       volume=self.engine.volume, queue=self.queue.export())
        self.library.store.put('session', session)

    def shutdown(self):
        self.save()
        self._save_timer.stop()
        self.engine.quit()
