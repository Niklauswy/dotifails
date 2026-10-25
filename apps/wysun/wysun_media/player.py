"""MediaPlayer: one reusable widget that shows video, audio and images, in a window or embedded in another app.

It owns a :class:`MediaSession` (audio/video), an :class:`ImageView`, an audio stage, the floating
control bar and the collection of neighbouring files. Hosts supply theme and symbols through
:mod:`wysun_media.host` and drive it with ``open()``.
"""
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget
from shiboken6 import isValid

from . import host
from .audio import AudioStage
from .bar import ControlBar
from .collection import Collection
from .controls import Rounding, Toast, clock, unit
from .cover import CoverJob
from .errors import MediaError
from .image import ImageView
from .resume import Positions
from .session import MediaSession
from .source import open_source
from .video import gl_available, make_view

HIDE_AFTER_MS = 2500
SUBTITLES = ('.srt', '.ass', '.ssa', '.vtt', '.sub')
SPEEDS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0)
INTEGRATION_PROPERTIES = ('duration', 'metadata', 'volume', 'mute', 'speed', 'loop-file', 'seeking', 'track-list')
ENV_OPTIONS = ('ao', 'hwdec', 'audio-device', 'volume')      # the only mpv options WYSUN_MPV_OPTIONS may set


def environment_options():
    """``WYSUN_MPV_OPTIONS='ao=null,hwdec=no'``: diagnostics and tests; everything outside ENV_OPTIONS is ignored."""
    found = {}
    for pair in os.environ.get('WYSUN_MPV_OPTIONS', '').split(','):
        key, _, value = pair.partition('=')
        if key.strip() in ENV_OPTIONS and value:
            found[key.strip()] = value.strip()
    return found


class Note(QWidget):
    """Full-size message for a file that could not be shown."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = ''
        self.hide()

    def say(self, text):
        self.text = text
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, _event):
        h = host.get()
        painter = QPainter(self)
        painter.fillRect(self.rect(), h.color('well'))
        box = QRectF(self.rect())
        h.symbol(painter, QRectF(box.center().x() - 28, box.center().y() - 56, 56, 56), 'error', 'muted', 44)
        painter.setFont(h.font('body', 500))
        painter.setPen(h.color('muted'))
        margin = float(h.token('space_xl'))
        painter.drawText(QRectF(margin, box.center().y() + 8, box.width() - 2 * margin, 80),
                         Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.text)


class MediaPlayer(QWidget):
    expandRequested = Signal()           # embedded hosts: open this file in the full player
    fullscreenRequested = Signal(bool)
    titleChanged = Signal(str)
    stateChanged = Signal(str)
    opened = Signal(object)              # MediaSource
    infoChanged = Signal()               # what is known about the open file changed: duration, codecs, picture size…
    errorOccurred = Signal(object)       # MediaError
    filesDropped = Signal(list)
    revealRequested = Signal(str)

    def __init__(self, parent=None, *, mode='embedded', backdrop='surface', remember=False, renderer='auto', options=None):
        super().__init__(parent)
        self.mode, self.remember, self.backdrop = mode, remember, backdrop
        self.source, self.kind = None, ''
        self.extra_actions = []          # host-supplied (label, callback) entries for the "more" menu
        self.integrations = []           # objects with sync(player), told about every state change
        self._switching = False          # a file is being replaced: integrations hear about it once, when the new one is on screen
        self.activated = False           # the user has pressed play on the current file (embedded hosts publish MPRIS from then on)
        self._fullscreen = False
        self._menu = None
        self._click = QTimer(self, singleShot=True)
        self._click.timeout.connect(self.toggle)
        self._idle = QTimer(self, singleShot=True, interval=HIDE_AFTER_MS)
        self._idle.timeout.connect(self._maybe_hide_bar)
        self._cover = None
        self._video = self._images = self._audio = None
        renderer = os.environ.get('WYSUN_PLAYER_RENDERER', renderer) if renderer == 'auto' else renderer
        self._renderer = 'software' if renderer == 'software' or not gl_available() else 'opengl'
        self.positions = Positions() if remember else None

        settings = {'hwdec': 'auto-copy' if self._renderer == 'opengl' else 'no', **(options or {}), **environment_options()}
        self.session = MediaSession(self, settings)
        self.collection = Collection(self)
        self.collection.changed.connect(self._collection_changed)
        self.note = Note(self)
        self.rounding = Rounding(self)
        self.bar = ControlBar(self)
        self.toast = Toast(self)
        self._wire_session()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAcceptDrops(mode == 'full')
        self.rounding.set_corner('xl' if mode == 'embedded' else 'none', backdrop)
        self.bar.configure('video', mode)
        self.bar.hide()
        host.get().on_theme_changed(self._theme_changed)

    # ------------------------------------------------------------------ wiring
    def _wire_session(self):
        session = self.session
        session.stateChanged.connect(self._state_changed)
        session.positionChanged.connect(self._position_changed)
        session.propertyChanged.connect(self._property_changed)
        session.errorOccurred.connect(self._fail)
        session.commandFailed.connect(lambda error: self.toast.say(error.message, 'error'))
        session.frameSaved.connect(lambda path: self.toast.say('Fotograma guardado', 'photo_camera'))

    def _ensure_video(self):
        if self._video is None:
            self._video = make_view(self, 'software' if self._renderer == 'software' else 'auto')
            self._connect_video(self._video)
        return self._video

    def _connect_video(self, view):
        view.ready.connect(lambda: self.session.set_surface_ready(True))
        view.failed.connect(self._render_failed)
        view.setMouseTracking(True)
        view.installEventFilter(self)
        view.attach(self.session)

    def _render_failed(self, reason):
        """OpenGL could not start: continue with the software surface, once."""
        if self._renderer == 'software':
            self._fail(MediaError('render', detail=reason))
            return
        self._renderer = 'software'
        failed, self._video = self._video, None
        if failed is not None:
            failed.release()
            failed.hide()
            failed.deleteLater()
        self.session.set_surface_ready(False)
        self.session.set_hwdec('no')
        self._ensure_video()
        self._layout()
        self._video.show()

    def _ensure_images(self):
        if self._images is None:
            self._images = ImageView(self)
            self._images.setMouseTracking(True)
            self._images.installEventFilter(self)
            self._images.loaded.connect(self._image_loaded)
            self._images.failed.connect(self._image_failed)
            self._images.zoomChanged.connect(self._zoom_changed)
            self._images.animationChanged.connect(lambda _: self._sync_animation())
        return self._images

    def _ensure_audio(self):
        if self._audio is None:
            self._audio = AudioStage(self)
            self._audio.setMouseTracking(True)
            self._audio.installEventFilter(self)
        return self._audio

    @property
    def renderer(self):
        return self._renderer

    # ------------------------------------------------------------------ opening
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
        self.source, self.kind = source, source.kind
        if isinstance(browse, (list, tuple)):
            paths = [str(Path(p).absolute()) for p in browse]
            self.collection.set_explicit(paths, paths.index(str(source.path)) if str(source.path) in paths else 0)
        elif browse == 'folder':
            self.collection.follow_folder(source.path, source.group)
        else:
            self.collection.set_explicit([source.path], 0)
        self.note.hide()
        self._present(source, start, paused)
        self._switching = False
        self._sync_integrations()
        self.titleChanged.emit(source.name)
        self.opened.emit(source)
        self.infoChanged.emit()
        return True

    def open_many(self, paths, current=0, **options):
        paths = [str(p) for p in paths]
        if paths:
            self.open(paths[current], browse=paths, **options)

    def enable_integration(self, identity='Wysun Player', desktop_entry='wysun-player'):
        """Publish MPRIS for this player, keep the screen awake while a video plays, and pause Wysun Music on sound."""
        from .integration import Integration
        integration = Integration(identity, desktop_entry)
        self.integrations.append(integration)
        return integration

    def _sync_integrations(self):
        if self._switching:
            return
        for integration in self.integrations:
            integration.sync(self)

    def _present(self, source, start, paused):
        self.activated = False
        kind = source.kind
        if kind == 'image':
            self.session.stop()
            view = self._ensure_images()
            self._show_only(view)
            view.show_source(source)
            self._prefetch()
        else:
            if self.remember and self.positions and start is None:
                start = self.positions.get(source)
            if kind == 'video':
                self._show_only(self._ensure_video())
            else:
                stage = self._ensure_audio()
                stage.set_text(source.name, '')
                stage.set_cover(None)
                self._show_only(stage)
                self._cover = CoverJob(source.path, self)
                self._cover.ready.connect(stage.set_cover)
                self._cover.start()
            try:
                self.session.open(source, start or 0.0, paused)
            except MediaError as error:
                self._fail(error)
        self.bar.configure(kind, self.mode, len(self.collection), self.width())
        self._sync_all()
        self._layout()
        self._activity()

    def _show_only(self, widget):
        for stage in (self._video, self._images, self._audio):
            if stage is not None and stage is not widget:
                stage.hide()
        widget.show()
        self._layout()

    def _leave(self):
        """Save where the current file stopped and release what belongs to it."""
        self._save_position()
        self._click.stop()
        self.activated = False
        if self._cover is not None:
            self._cover.cancel()
            self._cover = None
        self.session.stop()
        if self._images is not None:
            self._images.clear()
        self._sync_integrations()

    def close_media(self):
        self._leave()
        self.source, self.kind = None, ''
        self.collection.set_explicit([], 0)
        self.note.hide()
        for stage in (self._video, self._images, self._audio):
            if stage is not None:
                stage.hide()
        self.bar.hide()
        self.titleChanged.emit('')

    def shutdown(self):
        """Release video surface and core. Idempotent; call before the window is destroyed."""
        self._save_position()
        self._idle.stop()
        self._click.stop()
        if self._cover is not None:
            self._cover.cancel()
        if self._video is not None:
            self._video.release()
        self.session.close()
        for integration in self.integrations:
            integration.close()
        self.integrations.clear()

    # ------------------------------------------------------------------ collection
    def _collection_changed(self):
        self.bar.configure(self.kind or 'video', self.mode, len(self.collection), self.width())
        self._prefetch()

    def step_collection(self, step):
        """Open the next (+1) or previous (-1) file of the collection; False at either end."""
        path = self.collection.move(step)
        if path is None:
            self.toast.say('No hay más archivos', 'info')
            return False
        try:
            source = open_source(path)
        except MediaError as error:
            self._fail(error)
            return False
        self._save_position()
        if self._cover is not None:
            self._cover.cancel()
        self.source, self.kind = source, source.kind
        self.note.hide()
        self._present(source, None, False)
        self.titleChanged.emit(source.name)
        self.opened.emit(source)
        self.infoChanged.emit()
        return True

    def _prefetch(self):
        if self.kind != 'image' or self._images is None:
            return
        around = []
        for step in (1, -1):
            index = self.collection.neighbour(step)
            if index is not None:
                try:
                    around.append(open_source(self.collection.paths[index]))
                except MediaError:
                    continue
        self._images.prefetch(around)

    # ------------------------------------------------------------------ session events
    def _state_changed(self, state):
        if state == 'playing':
            self.activated = True
        self.bar.sync_state(state)
        if self._audio is not None:
            self._audio.set_playing(state == 'playing')
        if state in ('paused', 'ended', 'idle'):
            self._save_position(ended=state == 'ended')
        self._activity()
        self.stateChanged.emit(state)
        self._sync_integrations()

    def _position_changed(self, position):
        self.bar.sync_progress(position, self.session.duration)

    def _property_changed(self, name):
        session = self.session
        if name == 'duration':
            self.bar.sync_progress(session.position, session.duration)
        elif name in ('volume', 'mute'):
            self.bar.sync_volume(session.volume, session.muted)
        elif name == 'speed':
            self.bar.sync_speed(session.speed)
        elif name == 'chapter-list':
            self.bar.seek.set_chapters(session.chapters)
        elif name in ('ab-loop-a', 'ab-loop-b'):
            self.bar.seek.set_loop(*session.ab_loop)
        elif name == 'track-list':
            self.bar.configure(self.kind or 'video', self.mode, len(self.collection), self.width())
        elif name == 'metadata' and self._audio is not None:
            tags = {str(k).lower(): v for k, v in (session.props.get('metadata') or {}).items()}
            self._audio.set_text(tags.get('title') or (self.source.name if self.source else ''),
                                 ' · '.join(v for v in (tags.get('artist'), tags.get('album')) if v))
        if name in ('duration', 'video-params', 'video-codec', 'audio-codec-name', 'hwdec-current', 'container-fps', 'metadata'):
            self.infoChanged.emit()
        if name in INTEGRATION_PROPERTIES:
            self._sync_integrations()

    def _fail(self, error):
        self.note.setGeometry(self.rect())
        self.note.say(error.message + (f'\n{self.source.name}' if self.source else ''))
        self.bar.hide()
        self.errorOccurred.emit(error)

    def _image_failed(self, error):
        self.bar.configure('image', self.mode, len(self.collection), self.width())
        self.errorOccurred.emit(error)

    def _image_loaded(self, _frame):
        self.infoChanged.emit()
        self._zoom_changed()
        self._sync_animation()
        self._activity()

    def _zoom_changed(self):
        view = self._images
        if view is not None and view.frame is not None:
            self.bar.sync_zoom(view.zoom_percent, view.mode == 'fit')

    def _sync_animation(self):
        view = self._images
        self.bar.show_animation(bool(view and view.animated), bool(view and view.animating))

    def _sync_all(self):
        session = self.session
        self.bar.sync_state(session.state)
        self.bar.sync_progress(session.position, session.duration)
        self.bar.sync_volume(session.volume, session.muted)
        self.bar.sync_speed(session.speed)
        self.bar.sync_fullscreen(self._fullscreen)

    def _save_position(self, ended=False):
        if self.positions is None or self.source is None or self.kind == 'image':
            return
        duration = self.session.duration
        self.positions.put(self.source, 0.0 if ended else self.session.position, duration)

    # ------------------------------------------------------------------ commands
    def toggle(self):
        if self.kind == 'image':
            if self._images is not None and self._images.animated:
                self._images.toggle_animation()
            else:
                self.step_collection(1)
            return
        self.session.toggle()

    def skip(self, seconds):
        self.session.seek_relative(seconds)
        self.toast.say(f'{seconds:+g} s', 'forward_10' if seconds > 0 else 'replay_10')

    def seek_fraction(self, fraction):
        if self.session.duration:
            self.session.seek(self.session.duration * fraction)

    def toggle_mute(self):
        self.session.set_muted(not self.session.muted)

    def set_volume(self, percent):
        percent = max(0.0, min(150.0, percent))
        self.session.set_volume(percent)
        if self.session.muted and percent > 0:
            self.session.set_muted(False)

    def nudge_volume(self, delta):
        volume = max(0.0, min(150.0, self.session.volume + delta))
        self.set_volume(volume)
        self.toast.say(f'Volumen {volume:.0f} %', 'volume_up' if volume else 'volume_off')

    def set_speed(self, speed):
        self.session.set_speed(speed)
        self.toast.say(f'{speed:g}×', 'speed')

    def nudge_speed(self, direction):
        speeds = list(SPEEDS)
        current = min(range(len(speeds)), key=lambda i: abs(speeds[i] - self.session.speed))
        self.set_speed(speeds[max(0, min(len(speeds) - 1, current + direction))])

    def zoom(self, factor):
        if self._images is not None:
            self._images.zoom_by(factor)

    def toggle_fit(self):
        if self._images is not None:
            self._images.toggle_fit()

    def rotate(self, steps=1):
        if self._images is not None:
            self._images.rotate(steps)

    def toggle_fullscreen(self):
        self.set_fullscreen(not self._fullscreen)

    def set_fullscreen(self, active, notify=True):
        if active == self._fullscreen or self.kind == 'audio' and active:
            return
        self._fullscreen = active
        self.rounding.set_corner('none' if active or self.mode == 'full' else 'xl', self.backdrop)
        self.bar.sync_fullscreen(active)
        if notify:
            self.fullscreenRequested.emit(active)
        self._activity()

    @property
    def fullscreen(self):
        return self._fullscreen

    def cycle_subtitles(self):
        tracks = self.session.tracks('sub')
        if not tracks:
            self.toast.say('Sin subtítulos', 'closed_caption_disabled')
            return
        ids = [t['id'] for t in tracks]
        current = next((t['id'] for t in tracks if t.get('selected')), None)
        following = None if current == ids[-1] else ids[ids.index(current) + 1] if current in ids else ids[0]
        self.session.select_subtitle(following)
        label = 'Subtítulos desactivados' if following is None else next(t.get('title') or t.get('lang') or f'Pista {following}' for t in tracks if t['id'] == following)
        self.toast.say(label, 'closed_caption')

    def cycle_audio(self):
        tracks = self.session.tracks('audio')
        if len(tracks) < 2:
            return
        ids = [t['id'] for t in tracks]
        current = next((t['id'] for t in tracks if t.get('selected')), ids[0])
        following = ids[(ids.index(current) + 1) % len(ids)] if current in ids else ids[0]
        self.session.select_audio(following)
        self.toast.say(next(t.get('title') or t.get('lang') or f'Pista {following}' for t in tracks if t['id'] == following), 'audiotrack')

    def load_subtitle_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Cargar subtítulos', str(self.source.path.parent) if self.source else '',
                                              'Subtítulos (*.srt *.ass *.ssa *.vtt *.sub)')
        if path:
            self.session.add_subtitle(path)

    def save_frame(self):
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

    def copy_path(self):
        if self.source is not None:
            QGuiApplication.clipboard().setText(str(self.source.path))
            self.toast.say('Ruta copiada', 'content_copy')

    def copy_image(self):
        view = self._images
        if view is None or view.frame is None:
            return
        from .image import decode
        try:
            frame = decode(self.source.path, self.source.fingerprint, view.frame.size)
        except MediaError as error:
            self.toast.say(error.message, 'error')
            return
        QGuiApplication.clipboard().setImage(frame.image)
        self.toast.say('Imagen copiada', 'content_copy')

    def reveal(self):
        if self.source is None:
            return
        self.revealRequested.emit(str(self.source.path))
        uri = QUrl.fromLocalFile(str(self.source.path)).toString()
        subprocess.Popen(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.FileManager1', '--object-path',
                          '/org/freedesktop/FileManager1', '--method', 'org.freedesktop.FileManager1.ShowItems', f"['{uri}']", ''],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def trash(self):
        """Move the file to the trash (recoverable) and show its neighbour."""
        if self.source is None or self.mode != 'full':
            return
        path = str(self.source.path)
        try:
            moved = subprocess.run(['gio', 'trash', '--', path], capture_output=True, timeout=10).returncode == 0
        except (OSError, subprocess.SubprocessError):
            moved = False
        if not moved:
            self.toast.say('No se pudo mover a la papelera', 'error')
            return
        neighbour = self.collection.neighbour(1)
        if neighbour is None:
            neighbour = self.collection.neighbour(-1)
        following = self.collection.paths[neighbour] if neighbour is not None else None
        remaining = [p for p in self.collection.paths if p != path]
        if following is None:
            self.close_media()
            self._fail(MediaError('missing'))
        else:
            self.open(following, browse=remaining)
        self.toast.say('Movido a la papelera', 'delete')

    # ------------------------------------------------------------------ menus
    def show_speed_menu(self, anchor):
        from .menus import speed_menu
        self._popup(speed_menu(self), anchor)

    def show_subtitle_menu(self, anchor):
        from .menus import subtitle_menu
        self._popup(subtitle_menu(self), anchor)

    def show_audio_menu(self, anchor):
        from .menus import audio_menu
        self._popup(audio_menu(self), anchor)

    def show_more_menu(self, anchor):
        from .menus import more_menu
        self._popup(more_menu(self), anchor)

    def show_info(self, anchor=None):
        from .menus import info_menu
        self._popup(info_menu(self), anchor or self.bar.more)

    def _popup(self, menu, anchor):
        if self._menu is not None:
            self._menu.close()
        self._menu = menu
        menu.dismissed.connect(self._menu_closed)
        menu.popup_above(anchor if anchor.isVisible() else self)
        self._idle.stop()

    def _menu_closed(self):
        self._menu = None
        self._activity()

    # ------------------------------------------------------------------ layout and bar
    def _theme_changed(self):
        """Sizes derive from tokens: let every control measure itself again."""
        if not isValid(self):               # the window closed and Qt freed it; the listener list still names us
            return
        for widget in self.bar.findChildren(QWidget):
            widget.updateGeometry()
        self.bar.configure(self.kind or 'video', self.mode, len(self.collection), self.width())
        self._layout()
        self.rounding.update()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout()

    def _layout(self):
        area = self.rect()
        for stage in (self._video, self._images, self._audio):
            if stage is not None:
                stage.setGeometry(area)
        self.note.setGeometry(area)
        self.rounding.setGeometry(area)
        margin = round(float(host.get().token('space_m')))
        width = min(area.width() - 2 * margin, round(unit() * 46)) if self.mode == 'full' else area.width() - 2 * margin
        compact = width < unit() * 26
        if compact != self.bar.compact and self.kind:
            self.bar.configure(self.kind, self.mode, len(self.collection), width)
        height = self.bar.preferred_height()
        self.bar.setGeometry((area.width() - width) // 2, area.height() - height - margin, max(1, width), height)
        if self._audio is not None:
            self._audio.reserve = height + margin
        for overlay in (self.rounding, self.bar, self.toast):
            overlay.raise_()
        self.toast.reposition()

    def _bar_wanted(self):
        if not self.kind:
            return False
        return not (self.kind == 'image' and self.mode == 'embedded') and self.note.isHidden()

    def _activity(self):
        """Show the bar and restart the countdown to hide it."""
        if not self._bar_wanted():
            self.bar.hide()
            return
        if not self.bar.isVisible():
            self.bar.show()
            self._layout()
        self.unsetCursor()
        for stage in (self._video, self._images, self._audio):
            if stage is not None:
                stage.unsetCursor()
        self._idle.start()

    def _hides_bar(self):
        playing_video = self.kind == 'video' and self.session.state == 'playing'
        return (playing_video or self.kind == 'image' and self.mode == 'full') and self._menu is None \
            and not self.bar.underMouse()

    def _maybe_hide_bar(self):
        if self._hides_bar():
            self.bar.hide()
            if self.kind == 'video' and self._video is not None and self.underMouse():
                self._video.setCursor(Qt.BlankCursor)
        else:
            self._idle.start()

    # ------------------------------------------------------------------ input
    def eventFilter(self, watched, event):
        kind = event.type()
        if kind in (QEvent.MouseMove, QEvent.Wheel, QEvent.MouseButtonPress):
            self._activity()
        if kind == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason)
        if watched is self._video or watched is self._audio:
            if kind == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and watched is self._video:
                if self.mode == 'full':
                    self._click.start(QApplication.doubleClickInterval())
                else:
                    self.toggle()
                return True
            if kind == QEvent.MouseButtonDblClick and self.mode == 'full' and watched is self._video:
                self._click.stop()
                self.toggle_fullscreen()
                return True
            if kind == QEvent.Wheel:
                self.nudge_volume(5 if event.angleDelta().y() > 0 else -5)
                return True
        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event):
        self._activity()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        self._activity()
        key, mods = event.key(), event.modifiers()
        shift, ctrl = bool(mods & Qt.ShiftModifier), bool(mods & Qt.ControlModifier)
        timed = self.kind in ('video', 'audio')
        text = event.text().lower()
        if key == Qt.Key_Escape and self._fullscreen:
            self.set_fullscreen(False)
        elif key in (Qt.Key_F, Qt.Key_F11) and self.kind != 'audio':
            self.toggle_fullscreen()
        elif ctrl and key == Qt.Key_C:
            self.copy_image() if self.kind == 'image' else self.copy_path()
        elif key == Qt.Key_Delete and self.mode == 'full':
            self.trash()
        elif key == Qt.Key_I:
            self.show_info()
        elif timed and self._timed_key(key, text, shift, ctrl):
            pass
        elif self.kind == 'image' and self._image_key(key, text, shift):
            pass
        elif key in (Qt.Key_PageDown, Qt.Key_N) or key == Qt.Key_Right and self.kind == 'image':
            self.step_collection(1)
        elif key in (Qt.Key_PageUp, Qt.Key_P) or key == Qt.Key_Left and self.kind == 'image':
            self.step_collection(-1)
        else:
            return super().keyPressEvent(event)
        event.accept()

    def _timed_key(self, key, text, shift, ctrl):
        session = self.session
        step = 60 if ctrl else 1 if shift else 5
        if key in (Qt.Key_Space, Qt.Key_K):
            self.toggle()
        elif key == Qt.Key_Left:
            self.skip(-step)
        elif key == Qt.Key_Right:
            self.skip(step)
        elif key == Qt.Key_Up:
            self.nudge_volume(5)
        elif key == Qt.Key_Down:
            self.nudge_volume(-5)
        elif key == Qt.Key_Home:
            session.seek(0)
        elif key == Qt.Key_End:
            session.seek(max(0.0, session.duration - 1))
        elif text.isdigit() and not shift:
            self.seek_fraction(int(text) / 10)
        elif key == Qt.Key_Period and session.paused:
            session.step(1)
        elif key == Qt.Key_Comma and session.paused:
            session.step(-1)
        elif key == Qt.Key_BracketRight:
            self.nudge_speed(1)
        elif key == Qt.Key_BracketLeft:
            self.nudge_speed(-1)
        elif key == Qt.Key_Backspace:
            self.set_speed(1.0)
        elif text == 'm':
            self.toggle_mute()
        elif text == 'l' and not shift:
            session.mark_loop()
        elif text == 'l' and shift:
            session.set_loop(not session.looping)
            self.toast.say('Bucle activado' if session.looping else 'Bucle desactivado', 'repeat')
        elif text == 'c' and self.kind == 'video':
            self.cycle_subtitles()
        elif text == 'a':
            self.cycle_audio()
        elif text == 's' and self.kind == 'video':
            self.save_frame()
        else:
            return False
        return True

    def _image_key(self, key, text, shift):
        if key == Qt.Key_Space:
            self.toggle()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom(1.25)
        elif key == Qt.Key_Minus:
            self.zoom(1 / 1.25)
        elif text == '0':
            self._images.set_mode('fit')
        elif text == '1':
            self._images.set_mode('actual')
        elif text == 'r':
            self.rotate(-1 if shift else 1)
        else:
            return False
        return True

    # ------------------------------------------------------------------ drag and drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        subtitles = [p for p in paths if Path(p).suffix.lower() in SUBTITLES]
        media = [p for p in paths if p not in subtitles]
        if subtitles and self.kind == 'video':
            for path in subtitles:
                self.session.add_subtitle(path)
        if media:
            self.filesDropped.emit(media)
            event.acceptProposedAction()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_integrations()              # visibility is part of what keeps the screen awake

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_integrations()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
