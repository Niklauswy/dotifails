"""One Wysun Player window's logic, without widgets: what MediaPlayer did, exposed to QML.

It owns the MediaSession (video and audio), the collection of neighbouring files, the remembered positions, the
desktop integration (MPRIS, screen awake, pausing Music) and the cover job. Images are drawn by QML (zoom, rotation
and animation live there); QML reports what it loaded through ``setImageInfo``. Short feedback goes out as
``toast(text, icon)``; a file that cannot be shown sets ``error``.
"""
import json
import os
from pathlib import Path
import subprocess

from PySide6.QtCore import Property, QObject, QProcess, QProcessEnvironment, QStandardPaths, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImageReader

from wysun_core import launch
from wysun_media.collection import Collection
from wysun_media.cover import CoverJob
from wysun_media.errors import MediaError
from wysun_media.resume import Positions
from wysun_media.session import MediaSession
from wysun_media.source import open_source

SUBTITLES = ('.srt', '.ass', '.ssa', '.vtt', '.sub')
SPEEDS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0)
INTEGRATION_PROPERTIES = ('duration', 'metadata', 'volume', 'mute', 'speed', 'loop-file', 'seeking', 'track-list')
PLAYBACK_PROPERTIES = ('duration', 'volume', 'mute', 'speed', 'loop-file', 'ab-loop-a', 'ab-loop-b', 'track-list',
                       'chapter-list', 'sub-delay')
INFO_PROPERTIES = ('duration', 'video-params', 'video-codec', 'audio-codec-name', 'hwdec-current', 'container-fps',
                   'metadata')
ENV_OPTIONS = ('ao', 'hwdec', 'audio-device', 'volume')      # the only mpv options WYSUN_MPV_OPTIONS may set


def environment_options():
    """``WYSUN_MPV_OPTIONS='ao=null,hwdec=no'``: diagnostics and tests; everything outside ENV_OPTIONS is ignored."""
    found = {}
    for pair in os.environ.get('WYSUN_MPV_OPTIONS', '').split(','):
        key, _, value = pair.partition('=')
        if key.strip() in ENV_OPTIONS and value:
            found[key.strip()] = value.strip()
    return found


def clock(seconds):
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f'{hours}:{minutes:02d}:{secs:02d}' if hours else f'{minutes}:{secs:02d}'


def size_text(count):
    value = float(count)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'.replace('.', ',')
        value /= 1024


def track_label(track):
    text = ' · '.join(part for part in (track.get('title'), track.get('lang')) if part)
    return text or f"Pista {track['id']}"


def system_python():
    import sys
    return str(Path(sys.base_prefix) / 'bin/python3')


class CoverStore:
    """Cover pictures served to QML as image://cover/<key> (one store per process)."""

    def __init__(self):
        self.images = {}

    def put(self, key, image):
        self.images[key] = image

    def drop(self, prefix):
        for key in [k for k in self.images if k.startswith(prefix)]:
            del self.images[key]


class PlayerController(QObject):
    mediaChanged = Signal()
    playbackChanged = Signal()
    positionChanged = Signal()
    fullscreenChanged = Signal()
    infoChanged = Signal()
    toast = Signal(str, str)
    fullscreenRequested = Signal(bool)
    closeRequested = Signal()

    mode = 'full'

    def __init__(self, parent=None, *, renderer='opengl', covers=None, positions=None, options=None, trash=None,
                 reveal=None):
        super().__init__(parent)
        self.renderer = renderer
        self.source, self.kind = None, ''
        self.activated = False
        self.integrations = []
        self._switching = False
        self._fullscreen = False
        self._error = ''
        self._window = None
        self._cover = None
        self._cover_url = ''
        self._audio_title = self._audio_detail = ''
        self._image = {}
        self._picker = None
        self._covers = covers or CoverStore()
        self._trash = trash or self._gio_trash
        self._reveal = reveal or self._file_manager
        self.positions = positions if positions is not None else Positions()
        settings = {'hwdec': 'auto-copy' if renderer == 'opengl' else 'no', **(options or {}), **environment_options()}
        self.session = MediaSession(self, settings)
        self.collection = Collection(self)
        self.collection.changed.connect(self._collection_changed)
        session = self.session
        session.stateChanged.connect(self._state_changed)
        session.positionChanged.connect(lambda _: self.positionChanged.emit())
        session.propertyChanged.connect(self._property_changed)
        session.errorOccurred.connect(self._fail)
        session.commandFailed.connect(lambda error: self.toast.emit(error.message, 'error'))
        session.frameSaved.connect(lambda _path: self.toast.emit('Fotograma guardado', 'photo_camera'))

    # ------------------------------------------------------------------ what QML reads
    def _media_session(self):
        return self.session

    mediaSession = Property(QObject, _media_session, constant=True)
    kindName = Property(str, lambda self: self.kind, notify=mediaChanged)
    title = Property(str, lambda self: self.source.name if self.source else '', notify=mediaChanged)
    url = Property(str, lambda self: QUrl.fromLocalFile(str(self.source.path)).toString() if self.source else '',
                   notify=mediaChanged)
    error = Property(str, lambda self: self._error, notify=mediaChanged)
    count = Property(int, lambda self: len(self.collection), notify=mediaChanged)
    hasNext = Property(bool, lambda self: self.collection.neighbour(1) is not None, notify=mediaChanged)
    hasPrevious = Property(bool, lambda self: self.collection.neighbour(-1) is not None, notify=mediaChanged)
    coverUrl = Property(str, lambda self: self._cover_url, notify=mediaChanged)
    audioTitle = Property(str, lambda self: self._audio_title, notify=mediaChanged)
    audioDetail = Property(str, lambda self: self._audio_detail, notify=mediaChanged)
    rendererName = Property(str, lambda self: self.renderer, constant=True)

    state = Property(str, lambda self: self.session.state, notify=playbackChanged)
    duration = Property(float, lambda self: self.session.duration, notify=playbackChanged)
    position = Property(float, lambda self: self.session.position, notify=positionChanged)
    volume = Property(float, lambda self: self.session.volume, notify=playbackChanged)
    muted = Property(bool, lambda self: self.session.muted, notify=playbackChanged)
    speed = Property(float, lambda self: self.session.speed, notify=playbackChanged)
    looping = Property(bool, lambda self: self.session.looping, notify=playbackChanged)
    subDelay = Property(float, lambda self: float(self.session.props.get('sub-delay') or 0.0), notify=playbackChanged)

    def _ab(self):
        a, b = self.session.ab_loop
        return [x for x in (a, b) if x is not None]

    abLoop = Property('QVariantList', _ab, notify=playbackChanged)
    chapters = Property('QVariantList', lambda self: [float(c) for c in self.session.chapters], notify=playbackChanged)

    def _tracks(self, kind):
        return [{'id': int(t['id']), 'label': track_label(t), 'selected': bool(t.get('selected')),
                 'detail': str(t.get('codec') or '').upper()} for t in self.session.tracks(kind)]

    audioTracks = Property('QVariantList', lambda self: self._tracks('audio'), notify=playbackChanged)
    subtitleTracks = Property('QVariantList', lambda self: self._tracks('sub'), notify=playbackChanged)
    fullscreen = Property(bool, lambda self: self._fullscreen, notify=fullscreenChanged)

    def _info(self):
        source, session = self.source, self.session
        if source is None:
            return []
        rows = [('Archivo', source.name), ('Tamaño', size_text(source.size))]
        if self.kind == 'image':
            if self._image:
                rows += [('Formato', self._image.get('format', '').upper() or '—'),
                         ('Dimensiones', f"{self._image['width']} × {self._image['height']}")]
                if self._image.get('frames', 1) > 1:
                    rows.append(('Fotogramas', str(self._image['frames'])))
        else:
            props = session.props
            params = props.get('video-params') or {}
            rows.append(('Duración', clock(session.duration)))
            if self.kind == 'video':
                hw = props.get('hwdec-current')
                dropped = sum(props.get(name) or 0 for name in ('frame-drop-count', 'vo-drop-frame-count',
                                                                 'decoder-frame-drop-count'))
                rows += [('Resolución', f"{params.get('w', '—')} × {params.get('h', '—')}"),
                         ('Códec de video', props.get('video-codec') or '—'),
                         ('Decodificador', 'Software' if hw in (None, 'no', '') else 'Hardware · ' + hw),
                         ('Renderizador', {'opengl': 'OpenGL', 'software': 'Software'}[self.renderer]),
                         ('Fotogramas perdidos', str(dropped))]
            rows.append(('Códec de audio', props.get('audio-codec-name') or '—'))
        return [{'label': label, 'value': value} for label, value in rows]

    info = Property('QVariantList', _info, notify=infoChanged)

    # ------------------------------------------------------------------ for the window and the integrations
    def attach_window(self, window):
        self._window = window

    def window(self):
        return self._window

    def isVisible(self):
        return self._window is not None and self._window.isVisible()

    def enable_integration(self, identity='Wysun Player', desktop_entry='wysun-player'):
        from wysun_media.integration import Integration
        integration = Integration(identity, desktop_entry)
        self.integrations.append(integration)
        return integration

    def _sync_integrations(self):
        if self._switching:
            return
        for integration in self.integrations:
            integration.sync(self)

    @Slot()
    def visibilityChanged(self):
        """The window was shown, hidden or minimized: part of what keeps the screen awake."""
        self._sync_integrations()

    # ------------------------------------------------------------------ opening
    @Slot(str)
    def openPath(self, path):
        self.open(path, browse='folder')

    def open(self, path, *, start=None, paused=False, browse=None):
        """Show ``path``. ``browse``: None, ``'folder'`` (its neighbours) or a list of paths (given order)."""
        try:
            source = open_source(path)
        except MediaError as error:
            self._leave()
            self._fail(error)
            return False
        self._switching = True
        self._leave()
        if isinstance(browse, (list, tuple)):
            paths = [str(Path(p).absolute()) for p in browse]
            self.collection.set_explicit(paths, paths.index(str(source.path)) if str(source.path) in paths else 0)
        elif browse == 'folder':
            self.collection.follow_folder(source.path, source.group)
        else:
            self.collection.set_explicit([source.path], 0)
        self._present(source, start, paused)
        self._switching = False
        self._sync_integrations()
        return True

    def open_many(self, paths, current=0, **options):
        paths = [str(p) for p in paths]
        if paths:
            self.open(paths[current], browse=paths, **options)

    def show_files(self, files, paused=False, start=None):
        if len(files) == 1:
            self.open(files[0], paused=paused, start=start, browse='folder')
        else:
            self.open_many(files, paused=paused, start=start)

    def _present(self, source, start, paused):
        self.source, self.kind, self._error = source, source.kind, ''
        self.activated = False
        self._image = {}
        if source.kind == 'image':
            self.session.stop()
        else:
            if start is None:
                start = self.positions.get(source)
            if source.kind == 'audio':
                self._audio_title, self._audio_detail = source.name, ''
                self._start_cover(source)
            try:
                self.session.open(source, start or 0.0, paused)
            except MediaError as error:
                self._fail(error)
                return
        self.mediaChanged.emit()
        self.playbackChanged.emit()
        self.infoChanged.emit()

    def _start_cover(self, source):
        self._cover_url = ''
        self._covers.drop(f'{id(self)}-')
        job = self._cover = CoverJob(source.path, self)
        generation = self.session.generation + 1

        def ready(image):
            if job is not self._cover:
                return
            self._cover = None
            if image is not None and not image.isNull():
                key = f'{id(self)}-{generation}'
                self._covers.put(key, image)
                self._cover_url = f'image://cover/{key}'
                self.mediaChanged.emit()

        job.ready.connect(ready)
        job.start()

    def _leave(self):
        """Save where the current file stopped and release what belongs to it."""
        self._save_position()
        self.activated = False
        if self._cover is not None:
            self._cover.cancel()
            self._cover = None
        self._cover_url = ''
        self.session.stop()
        self._sync_integrations()

    def close_media(self):
        self._leave()
        self.source, self.kind, self._error = None, '', ''
        self.collection.set_explicit([], 0)
        self.mediaChanged.emit()
        self.closeRequested.emit()

    @Slot()
    def shutdown(self):
        """Release the core and the integrations. Idempotent; the video item frees its context first."""
        self._save_position()
        if self._cover is not None:
            self._cover.cancel()
            self._cover = None
        self._covers.drop(f'{id(self)}-')
        if self._picker is not None:
            self._picker.kill()
        self.session.close()
        for integration in self.integrations:
            integration.close()
        self.integrations.clear()

    # ------------------------------------------------------------------ collection
    def _collection_changed(self):
        self.mediaChanged.emit()

    @Slot(int, result=bool)
    def stepCollection(self, step):
        return self.step_collection(step)

    def step_collection(self, step):
        """Open the next (+1) or previous (-1) file of the collection; False at either end."""
        path = self.collection.move(step)
        if path is None:
            self.toast.emit('No hay más archivos', 'info')
            return False
        try:
            source = open_source(path)
        except MediaError as error:
            self._fail(error)
            return False
        self._switching = True
        self._leave()
        self._present(source, None, False)
        self._switching = False
        self._sync_integrations()
        return True

    def _neighbours(self):
        """Paths next to the current image, for QML to decode ahead."""
        found = []
        for step in (1, -1):
            index = self.collection.neighbour(step)
            if index is not None:
                found.append(QUrl.fromLocalFile(self.collection.paths[index]).toString())
        return found

    neighbours = Property('QVariantList', _neighbours, notify=mediaChanged)

    # ------------------------------------------------------------------ session events
    def _state_changed(self, state):
        if state == 'playing':
            self.activated = True
        if state in ('paused', 'ended', 'idle'):
            self._save_position(ended=state == 'ended')
        self.playbackChanged.emit()
        self._sync_integrations()

    def _property_changed(self, name):
        if name in PLAYBACK_PROPERTIES:
            self.playbackChanged.emit()
        if name == 'metadata' and self.kind == 'audio':
            tags = {str(k).lower(): v for k, v in (self.session.props.get('metadata') or {}).items()}
            self._audio_title = str(tags.get('title') or (self.source.name if self.source else ''))
            self._audio_detail = ' · '.join(str(v) for v in (tags.get('artist'), tags.get('album')) if v)
            self.mediaChanged.emit()
        if name in INFO_PROPERTIES:
            self.infoChanged.emit()
        if name in INTEGRATION_PROPERTIES:
            self._sync_integrations()

    def _fail(self, error):
        self._error = error.message + (f'\n{self.source.name}' if self.source else '')
        self.mediaChanged.emit()

    def _save_position(self, ended=False):
        if self.positions is None or self.source is None or self.kind == 'image':
            return
        self.positions.put(self.source, 0.0 if ended else self.session.position, self.session.duration)

    # ------------------------------------------------------------------ images (drawn by QML)
    @Slot(int, int, int)
    def setImageInfo(self, width, height, frames):
        if self.source is None or self.kind != 'image':
            return
        fmt = bytes(QImageReader.imageFormat(str(self.source.path))).decode() or self.source.path.suffix.lstrip('.')
        self._image = {'width': width, 'height': height, 'frames': frames, 'format': fmt}
        self.infoChanged.emit()

    @Slot(str)
    def imageFailed(self, message):
        self._fail(MediaError('decode', detail=message))

    @Slot()
    def copyImage(self):
        if self.source is None or self.kind != 'image':
            return
        reader = QImageReader(str(self.source.path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            self.toast.emit('No se pudo copiar la imagen', 'error')
            return
        QGuiApplication.clipboard().setImage(image)
        self.toast.emit('Imagen copiada', 'content_copy')

    # ------------------------------------------------------------------ playback commands
    @Slot()
    def toggle(self):
        if self.kind in ('video', 'audio'):
            self.session.toggle()

    @Slot(float)
    def skip(self, seconds):
        self.session.seek_relative(seconds)
        self.toast.emit(f'{seconds:+g} s', 'forward_10' if seconds > 0 else 'replay_10')

    @Slot(float)
    def seek(self, seconds):
        self.session.seek(seconds)

    @Slot(float)
    def scrub(self, seconds):
        self.session.scrub(seconds)

    @Slot(float)
    def seekFraction(self, fraction):
        if self.session.duration:
            self.session.seek(self.session.duration * fraction)

    @Slot()
    def seekEnd(self):
        self.session.seek(max(0.0, self.session.duration - 1))

    @Slot()
    def toggleMute(self):
        self.session.set_muted(not self.session.muted)

    @Slot(float)
    def setVolume(self, percent):
        self.set_volume(percent)

    def set_volume(self, percent):
        percent = max(0.0, min(150.0, percent))
        self.session.set_volume(percent)
        if self.session.muted and percent > 0:
            self.session.set_muted(False)

    @Slot(float)
    def nudgeVolume(self, delta):
        volume = max(0.0, min(150.0, self.session.volume + delta))
        self.set_volume(volume)
        self.toast.emit(f'Volumen {volume:.0f} %', 'volume_up' if volume else 'volume_off')

    @Slot(float)
    def setSpeed(self, speed):
        self.session.set_speed(speed)
        self.toast.emit(f'{speed:g}×', 'speed')

    @Slot(int)
    def nudgeSpeed(self, direction):
        current = min(range(len(SPEEDS)), key=lambda i: abs(SPEEDS[i] - self.session.speed))
        self.setSpeed(SPEEDS[max(0, min(len(SPEEDS) - 1, current + direction))])

    @Slot(int)
    def step(self, frames):
        if self.session.paused:
            self.session.step(frames)

    @Slot()
    def markLoop(self):
        self.session.mark_loop()

    @Slot()
    def toggleLoop(self):
        self.session.set_loop(not self.session.looping)
        self.toast.emit('Bucle activado' if self.session.looping else 'Bucle desactivado', 'repeat')

    @Slot()
    def cycleSubtitles(self):
        tracks = self.session.tracks('sub')
        if not tracks:
            self.toast.emit('Sin subtítulos', 'closed_caption_disabled')
            return
        ids = [t['id'] for t in tracks]
        current = next((t['id'] for t in tracks if t.get('selected')), None)
        following = None if current == ids[-1] else ids[ids.index(current) + 1] if current in ids else ids[0]
        self.session.select_subtitle(following)
        label = 'Subtítulos desactivados' if following is None else \
            next(track_label(t) for t in tracks if t['id'] == following)
        self.toast.emit(label, 'closed_caption')

    @Slot()
    def cycleAudio(self):
        tracks = self.session.tracks('audio')
        if len(tracks) < 2:
            return
        ids = [t['id'] for t in tracks]
        current = next((t['id'] for t in tracks if t.get('selected')), ids[0])
        following = ids[(ids.index(current) + 1) % len(ids)] if current in ids else ids[0]
        self.session.select_audio(following)
        self.toast.emit(next(track_label(t) for t in tracks if t['id'] == following), 'audiotrack')

    @Slot(int)
    def selectSubtitle(self, track):
        self.session.select_subtitle(None if track < 0 else track)

    @Slot(int)
    def selectAudio(self, track):
        self.session.select_audio(track)

    @Slot(float)
    def shiftSubtitles(self, seconds):
        self.session.shift_subtitles(seconds)

    @Slot(str)
    def addSubtitle(self, path):
        self.session.add_subtitle(path)

    @Slot()
    def saveFrame(self):
        if self.kind != 'video' or self.source is None:
            return
        folder = Path(QStandardPaths.writableLocation(QStandardPaths.PicturesLocation) or Path.home())
        folder.mkdir(parents=True, exist_ok=True)
        stamp = clock(self.session.position).replace(':', '.')
        target = folder / f'{self.source.path.stem} {stamp}.png'
        number = 1
        while target.exists():
            number += 1
            target = folder / f'{self.source.path.stem} {stamp} ({number}).png'
        self.session.save_frame(target)

    # ------------------------------------------------------------------ file actions
    @Slot()
    def copyPath(self):
        if self.source is not None:
            QGuiApplication.clipboard().setText(str(self.source.path))
            self.toast.emit('Ruta copiada', 'content_copy')

    @Slot()
    def reveal(self):
        if self.source is not None:
            self._reveal(str(self.source.path))

    @staticmethod
    def _file_manager(path):
        uri = QUrl.fromLocalFile(path).toString()
        subprocess.Popen(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.FileManager1', '--object-path',
                          '/org/freedesktop/FileManager1', '--method', 'org.freedesktop.FileManager1.ShowItems',
                          f"['{uri}']", ''], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)

    @staticmethod
    def _gio_trash(path):
        try:
            return subprocess.run(['gio', 'trash', '--', path], capture_output=True, timeout=10).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    @Slot()
    def trash(self):
        """Move the file to the trash (recoverable) and show its neighbour."""
        if self.source is None:
            return
        path = str(self.source.path)
        if not self._trash(path):
            self.toast.emit('No se pudo mover a la papelera', 'error')
            return
        neighbour = self.collection.neighbour(1)
        if neighbour is None:
            neighbour = self.collection.neighbour(-1)
        following = self.collection.paths[neighbour] if neighbour is not None else None
        remaining = [p for p in self.collection.paths if p != path]
        if following is None:
            self._leave()
            self.source, self.kind = None, ''
            self.collection.set_explicit([], 0)
            self._fail(MediaError('missing'))
        else:
            self.open(following, browse=remaining)
        self.toast.emit('Movido a la papelera', 'delete')

    # ------------------------------------------------------------------ window state
    @Slot(bool)
    def setFullscreen(self, active):
        self.set_fullscreen(active)

    def set_fullscreen(self, active, notify=True):
        if active == self._fullscreen or self.kind == 'audio' and active:
            return
        self._fullscreen = active
        self.fullscreenChanged.emit()
        if notify:
            self.fullscreenRequested.emit(active)

    @Slot()
    def toggleFullscreen(self):
        self.set_fullscreen(not self._fullscreen)

    # ------------------------------------------------------------------ drag and drop, choosing files
    @Slot('QVariantList')
    def drop(self, urls):
        paths = [QUrl(str(u)).toLocalFile() for u in urls]
        paths = [p for p in paths if p]
        subtitles = [p for p in paths if Path(p).suffix.lower() in SUBTITLES]
        media = [p for p in paths if p not in subtitles]
        if subtitles and self.kind == 'video':
            for path in subtitles:
                self.session.add_subtitle(path)
        if media:
            self.show_files(media)

    @Slot()
    def chooseFiles(self):
        self._pick('media')

    @Slot()
    def chooseSubtitles(self):
        self._pick('subtitles')

    def _pick(self, kind):
        if self._picker is not None:
            return
        process = self._picker = QProcess(self)
        env = QProcessEnvironment()
        for key, value in launch.environment().items():
            env.insert(key, value)
        process.setProcessEnvironment(env)
        command = launch.argv('wysun_files.picker', python=system_python())
        process.finished.connect(lambda code, *_: self._picked(kind, code))
        process.errorOccurred.connect(lambda error: self._picker_failed(error))
        process.start(command[0], command[1:])
        folder = str(self.source.path.parent) if self.source else str(Path.home())
        request = {'kind': kind, 'initial': folder}
        process.write(json.dumps(request).encode() + b'\n')
        process.closeWriteChannel()

    def _picker_failed(self, error):
        if error == QProcess.FailedToStart and self._picker is not None:
            self._picker.deleteLater()
            self._picker = None
            self.toast.emit('No se pudo abrir el selector de Wysun Files', 'error')

    def _picked(self, kind, code):
        process, self._picker = self._picker, None
        if process is None:
            return
        raw = bytes(process.readAllStandardOutput())
        process.deleteLater()
        try:
            result = json.loads(raw) if code == 0 and len(raw) <= 1 << 20 else {}
        except ValueError:
            result = {}
        paths = [QUrl(u).toLocalFile() for u in result.get('uris', [])] if result.get('code') == 0 else []
        paths = [p for p in paths if p]
        if not paths:
            if self.source is None and kind == 'media':
                self.closeRequested.emit()          # an empty window asked for files and got none
            return
        if kind == 'subtitles':
            for path in paths:
                self.session.add_subtitle(path)
        else:
            self.show_files(paths)

    # ------------------------------------------------------------------ cover provider
    def covers(self):
        return self._covers


def cover_provider(store):
    """The QQuickImageProvider for image://cover/<key>, reading ``store``."""
    from PySide6.QtGui import QImage
    from PySide6.QtQuick import QQuickImageProvider

    class Provider(QQuickImageProvider):
        def __init__(self):
            super().__init__(QQuickImageProvider.Image)

        def requestImage(self, ident, size, requested):
            image = store.images.get(ident.split('?')[0])
            if image is None:
                return QImage()
            if requested.width() > 0 and requested.height() > 0:
                from PySide6.QtCore import Qt
                image = image.scaled(requested, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            size.setWidth(image.width())
            size.setHeight(image.height())
            return image

    return Provider()
