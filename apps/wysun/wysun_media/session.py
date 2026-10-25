"""Playback of one file at a time on a single, reused mpv core.

The session never blocks: every command is queued with ``mpv_command_async`` and
every answer arrives as an event drained on the GUI thread when mpv wakes the
pipe. Each ``open`` starts a new generation; events that belong to the file it
replaced are recognised by mpv's playlist entry id and dropped, so a late
end-of-file or error can never be shown for the file that is on screen now.
"""
import itertools

from PySide6.QtCore import QObject, QSocketNotifier, QTimer, Signal

from . import mpv
from .errors import MediaError
from .source import argument

STATES = ('idle', 'loading', 'playing', 'paused', 'ended', 'error', 'closing')

OBSERVED = {
    'time-pos': mpv.FMT_DOUBLE, 'duration': mpv.FMT_DOUBLE, 'pause': mpv.FMT_FLAG, 'mute': mpv.FMT_FLAG,
    'volume': mpv.FMT_DOUBLE, 'speed': mpv.FMT_DOUBLE, 'eof-reached': mpv.FMT_FLAG, 'idle-active': mpv.FMT_FLAG,
    'seeking': mpv.FMT_FLAG, 'paused-for-cache': mpv.FMT_FLAG, 'track-list': mpv.FMT_NODE,
    'chapter-list': mpv.FMT_NODE, 'loop-file': mpv.FMT_STRING, 'ab-loop-a': mpv.FMT_STRING, 'ab-loop-b': mpv.FMT_STRING,
    'sub-delay': mpv.FMT_DOUBLE, 'hwdec-current': mpv.FMT_STRING, 'video-codec': mpv.FMT_STRING,
    'audio-codec-name': mpv.FMT_STRING, 'video-params': mpv.FMT_NODE, 'container-fps': mpv.FMT_DOUBLE,
    'frame-drop-count': mpv.FMT_INT64, 'vo-drop-frame-count': mpv.FMT_INT64,
    'decoder-frame-drop-count': mpv.FMT_INT64, 'file-format': mpv.FMT_STRING, 'metadata': mpv.FMT_NODE,
}
SCRUB_INTERVAL_MS = 33


class MediaSession(QObject):
    stateChanged = Signal(str)
    propertyChanged = Signal(str)
    positionChanged = Signal(float)
    errorOccurred = Signal(object)          # MediaError
    commandFailed = Signal(object)          # MediaError of a seek or track change; playback continues
    frameSaved = Signal(str)

    def __init__(self, parent=None, options=None):
        super().__init__(parent)
        self.options = dict(options or {})
        self.props = {}
        self.source = None
        self.error = None
        self.generation = 0
        self._core = None
        self._notifier = None
        self._state = 'idle'
        self._loading = False
        self._awaiting = False          # an open() whose START_FILE has not arrived: older END_FILEs are stale
        self._entry = 0
        self._surface_ready = False
        self._relink = False             # the render context was lost and recreated: the video track must be re-selected
        self._deferred = None
        self._expect = None             # pause state requested by open(); shown until mpv confirms it
        self._requests = {}
        self._ids = itertools.count(1)
        self._scrub_to = None
        self._scrub = QTimer(self, singleShot=True, interval=SCRUB_INTERVAL_MS)
        self._scrub.timeout.connect(self._send_scrub)
        self.render_hook = None         # set by the video surface: called with the raw wakeup bytes

    # ------------------------------------------------------------------ core
    @property
    def core(self):
        return self._core

    def ensure_core(self):
        if self._core is not None:
            return self._core
        try:
            core = mpv.Mpv(self.options)
        except RuntimeError as error:
            raise MediaError('backend', detail=str(error)) from None
        self._core = core
        self._notifier = QSocketNotifier(core.wake_fd, QSocketNotifier.Read, self)
        self._notifier.activated.connect(self._wake)
        for name, fmt in OBSERVED.items():
            core.observe(name, fmt)
        return core

    def set_surface_ready(self, ready):
        """The video surface (GL context or software thread) can now take frames, or has just lost its target."""
        if not ready and self._surface_ready and self._core is not None and self.source is not None:
            self._relink = True
        self._surface_ready = ready
        if not ready or self._core is None:
            return
        if self._deferred is not None:
            deferred, self._deferred = self._deferred, None
            self._relink = False
            self._load(*deferred)
        elif self._relink:
            self._relink = False
            if self.source.kind == 'video':
                # mpv drops the video track when its render context is freed; selecting it again
                # attaches the decoder to the new context (video-reload does not).
                self._command('set', 'vid', 'no')
                self._command('set', 'vid', 'auto')

    # ----------------------------------------------------------------- state
    @property
    def state(self):
        return self._state

    def _derive(self):
        if self._state == 'closing':
            return 'closing'
        if self.error is not None:
            return 'error'
        if self.source is None:
            return 'idle'
        if self._loading:
            return 'loading'
        if self.props.get('eof-reached'):
            return 'ended'
        paused = self._expect if self._expect is not None else self.props.get('pause', True)
        return 'paused' if paused else 'playing'

    def _refresh(self):
        state = self._derive()
        if state != self._state:
            self._state = state
            self.stateChanged.emit(state)

    # ------------------------------------------------------------ properties
    @property
    def position(self):
        return self.props.get('time-pos') or 0.0

    @property
    def duration(self):
        return self.props.get('duration') or 0.0

    @property
    def paused(self):
        return bool(self.props.get('pause', True))

    @property
    def volume(self):
        return self.props.get('volume') or 0.0

    @property
    def muted(self):
        return bool(self.props.get('mute'))

    @property
    def speed(self):
        return self.props.get('speed') or 1.0

    @property
    def seeking(self):
        return bool(self.props.get('seeking'))

    @property
    def buffering(self):
        return bool(self.props.get('paused-for-cache'))

    @property
    def seekable(self):
        return self.duration > 0

    @property
    def chapters(self):
        return self.props.get('chapter-list') or []

    def tracks(self, kind):
        return [t for t in self.props.get('track-list') or [] if t.get('type') == kind and not t.get('albumart')]

    @property
    def has_video(self):
        return any(not t.get('image') for t in self.tracks('video'))

    @property
    def has_audio(self):
        return bool(self.tracks('audio'))

    @property
    def audible(self):
        """Sound is actually being produced: playing, not muted, with an audio track."""
        return self._state == 'playing' and not self.muted and self.has_audio and self.volume > 0

    @property
    def looping(self):
        return self.props.get('loop-file') not in (None, 'no')

    @property
    def ab_loop(self):
        a, b = self.props.get('ab-loop-a'), self.props.get('ab-loop-b')
        return (None if a in (None, 'no') else float(a)), (None if b in (None, 'no') else float(b))

    # ----------------------------------------------------------------- open
    def open(self, source, start=0.0, paused=False):
        """Start ``source`` (a MediaSource of kind video or audio). Raises MediaError if mpv is missing."""
        self.ensure_core()
        self.generation += 1
        self.source, self.error = source, None
        self._loading = self._awaiting = True
        self._scrub.stop()
        self._scrub_to = None
        self.props['time-pos'] = float(start or 0.0)
        self.props['duration'] = 0.0
        self.props['eof-reached'] = False
        self._expect = bool(paused) if self.props.get('pause', True) != bool(paused) else None
        self._refresh()
        job = (source, float(start or 0.0), bool(paused), self.generation)
        if source.kind == 'video' and not self._surface_ready:
            self._deferred = job
        else:
            self._deferred = None
            self._load(*job)

    def _load(self, source, start, paused, generation):
        if self._core is None:
            return
        request = next(self._ids)
        self._requests[request] = ('open', generation)
        options = f'start={start:.3f},pause={"yes" if paused else "no"},vid={"auto" if source.kind == "video" else "no"}'
        self._core.command('loadfile', argument(source.path), 'replace', '-1', options, userdata=request)

    def stop(self):
        """Back to idle: no file, no error."""
        self._deferred = None
        self._scrub.stop()
        self.source, self.error, self._loading, self._awaiting, self._expect = None, None, False, False, None
        if self._core:
            self._core.command('stop')
        self._refresh()

    def close(self):
        """Release the core without waiting for the audio and video threads."""
        if self._state == 'closing':
            return
        self._state = 'closing'
        self._scrub.stop()
        if self._notifier:
            self._notifier.setEnabled(False)
            self._notifier = None
        core, self._core = self._core, None
        if core:
            core.close()
        self.stateChanged.emit('closing')

    # --------------------------------------------------------------- control
    def _command(self, *args, operation=''):
        if self._core is None:
            return
        request = 0
        if operation:
            request = next(self._ids)
            self._requests[request] = (operation, self.generation)
        self._core.command(*args, userdata=request)

    def set_paused(self, paused):
        if self.props.get('eof-reached') and not paused:
            self._command('seek', 0, 'absolute+exact')
        self._command('set', 'pause', 'yes' if paused else 'no')

    def toggle(self):
        self.set_paused(False if self._state == 'ended' else not self.paused)

    def seek(self, seconds, exact=True):
        """Absolute seek; replaces any scrub still waiting for its turn."""
        self._scrub.stop()
        self._scrub_to = None
        seconds = max(0.0, min(float(seconds), self.duration or float(seconds)))
        self._command('seek', f'{seconds:.3f}', 'absolute+exact' if exact else 'absolute+keyframes', operation='seek')

    def seek_relative(self, delta, exact=True):
        self._scrub.stop()
        self._scrub_to = None
        self._command('seek', f'{delta:+.3f}', 'relative+exact' if exact else 'relative+keyframes', operation='seek')

    def scrub(self, seconds):
        """Coalesced keyframe seeks while a slider is dragged; release with :meth:`seek`."""
        self._scrub_to = max(0.0, min(float(seconds), self.duration or float(seconds)))
        if not self._scrub.isActive():
            self._send_scrub()
            self._scrub.start()

    def _send_scrub(self):
        if self._scrub_to is not None:
            target, self._scrub_to = self._scrub_to, None
            self._command('seek', f'{target:.3f}', 'absolute+keyframes', operation='seek')
            self._scrub.start()

    def step(self, frames):
        self._command('frame-step' if frames > 0 else 'frame-back-step')

    def set_volume(self, volume):
        self._command('set', 'volume', f'{max(0.0, min(150.0, float(volume))):.0f}')

    def set_muted(self, muted):
        self._command('set', 'mute', 'yes' if muted else 'no')

    def set_speed(self, speed):
        self._command('set', 'speed', f'{max(0.25, min(4.0, float(speed))):.3f}')

    def set_hwdec(self, mode):
        self._command('set', 'hwdec', mode)

    def set_loop(self, loop):
        self._command('set', 'loop-file', 'inf' if loop else 'no')

    def mark_loop(self):
        """Cycle the A-B loop: set A, set B, clear."""
        self._command('ab-loop')

    def add_chapter(self, step):
        self._command('add', 'chapter', step, operation='seek')

    def select_audio(self, track_id):
        self._command('set', 'aid', track_id if track_id else 'no', operation='track')

    def select_subtitle(self, track_id):
        self._command('set', 'sid', track_id if track_id else 'no', operation='track')

    def add_subtitle(self, path):
        self._command('sub-add', argument(path), 'select', operation='track')

    def shift_subtitles(self, seconds):
        self._command('add', 'sub-delay', f'{seconds:+.2f}')

    def save_frame(self, path):
        self._command('screenshot-to-file', argument(path), 'video', operation='frame:' + argument(path))

    # ---------------------------------------------------------------- events
    def _wake(self, *_):
        core = self._core
        if core is None:
            return
        wakeups = core.take_wakeups()
        if self.render_hook is not None and b'r' in wakeups:
            self.render_hook()
        if b'e' in wakeups or not wakeups:
            for event in core.events():
                if self._core is None:
                    return
                self._handle(event)

    def _handle(self, event):
        kind = event.kind
        if kind == mpv.EV_PROPERTY_CHANGE:
            self._property(event.name, event.value)
        elif kind == mpv.EV_COMMAND_REPLY:
            self._reply(event)
        elif kind == mpv.EV_START_FILE:
            self._entry, self._awaiting = event.entry, False
        elif kind == mpv.EV_FILE_LOADED:
            self._loading = False
            self._refresh()
        elif kind == mpv.EV_END_FILE:
            self._ended(event)
        elif kind == mpv.EV_SHUTDOWN:
            self._state = 'closing'

    def _property(self, name, value):
        self.props[name] = value
        if name == 'pause' and self._expect is not None and bool(value) == self._expect:
            self._expect = None             # mpv caught up with what open() asked for
        if name == 'time-pos':
            if value is not None:
                self.positionChanged.emit(value)
            return
        if name in ('pause', 'eof-reached', 'idle-active'):
            self._refresh()
        self.propertyChanged.emit(name)

    def _ended(self, event):
        if self._awaiting or event.entry != self._entry:
            return                                    # belongs to the file that was replaced
        if event.reason == mpv.END_ERROR:
            category = mpv.ERROR_CATEGORY.get(event.error, 'decode')
            self._fail(MediaError(category, 'open', mpv.error_text(event.error)))
        elif event.reason in (mpv.END_STOP, mpv.END_QUIT):
            self._loading = False
            self._refresh()

    def _reply(self, event):
        request = self._requests.pop(event.userdata, None)
        if request is None:
            return
        operation, generation = request
        if event.error >= 0:
            if operation.startswith('frame:'):
                self.frameSaved.emit(operation[6:])
            return
        if generation != self.generation:
            return                                     # the file it was meant for is gone
        if operation == 'open':
            category = mpv.ERROR_CATEGORY.get(event.error, 'unreadable')
            self._fail(MediaError(category, 'open', mpv.error_text(event.error)))
        else:
            name = 'unsupported' if operation == 'track' else 'decode'
            self.commandFailed.emit(MediaError(name, operation.split(':')[0], mpv.error_text(event.error), recoverable=True))

    def _fail(self, error):
        self.error, self._loading, self._expect = error, False, None
        self._refresh()
        self.errorOccurred.emit(error)
