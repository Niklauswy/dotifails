"""Embedded media player in the Music language: wavy progress, morphing play button, cookie art.

Playback is the same isolated libmpv/IPC used before; only the skin is new.
"""
import json
import os
from pathlib import Path
import socket
import tempfile

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QShortcut
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from file_media import FilePreviewJob, duration_label
from theme_tokens import color, tokens
from ui_motion import reduced_motion
from wysun_music.ui.shapes import artwork, clip_pixmap, cookie
from .kit import IconButton, Slider, metric, paint_symbol, text_font

VOLUME = 65
_JOBS = set()   # preview jobs outlive a closed player instead of being destroyed while running


class PlayerCore:
    """mpv process/IPC with observed properties; no widgets."""

    def __init__(self, path, surface):
        self.path, self.surface = str(path), surface
        self.sock, self.buffer, self.props = None, b'', {}
        self.root, self.stopped, self.error = None, False, ''
        self.socket_path = ''

    def start(self):
        from desktop_backend import wayland
        if QApplication.platformName() == 'offscreen':
            self.error = 'La reproducción está disponible en la sesión gráfica.'
            return False
        if not wayland():
            self.error = 'La reproducción incrustada requiere la sesión Wayland.'
            return False
        self.root = tempfile.TemporaryDirectory(prefix='orbit-video-', dir=os.environ.get('XDG_RUNTIME_DIR', '/tmp'))
        self.socket_path = str(Path(self.root.name) / 'mpv.sock')
        try:
            self.surface.start(self.path, self.socket_path, {'volume': str(VOLUME)})
        except Exception as exc:  # libmpv missing or refused the file
            self.error = str(exc)
            return False
        return True

    def send(self, command):
        if not self.sock:
            return
        try:
            self.sock.sendall((json.dumps({'command': command}) + '\n').encode())
        except OSError:
            pass

    def poll(self):
        """Read pending IPC; returns True once connected."""
        if not self.sock:
            if not self.socket_path or not Path(self.socket_path).exists():
                return False
            try:
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client.settimeout(.025)
                client.connect(self.socket_path)
                client.setblocking(False)
                self.sock = client
                for number, name in enumerate(('time-pos', 'duration', 'pause', 'mute', 'eof-reached', 'volume')):
                    self.send(['observe_property', number, name])
            except OSError:
                return False
        try:
            while True:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                self.buffer += chunk
        except BlockingIOError:
            pass
        except OSError:
            return True
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                data = json.loads(line)
                if data.get('event') == 'property-change':
                    self.props[data['name']] = data.get('data')
            except (ValueError, KeyError):
                continue
        return True

    @property
    def position(self):
        return self.props.get('time-pos') or 0

    @property
    def duration(self):
        return self.props.get('duration') or 0

    @property
    def paused(self):
        return self.props.get('pause', True)

    def toggle(self):
        if self.props.get('eof-reached'):
            self.send(['seek', 0, 'absolute'])
        self.send(['cycle', 'pause'])

    def stop(self):
        self.stopped = True
        self.send(['quit'])
        if hasattr(self.surface, 'stop'):
            self.surface.stop()
        if self.sock:
            self.sock.close()
            self.sock = None
        if self.root:
            self.root.cleanup()
            self.root = None


def _stage_surface():
    from mpv_embed import MpvSurface

    class RoundedSurface(MpvSurface):
        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            outline = QPainterPath()
            radius = tokens()['radius_m']
            outline.addRoundedRect(QRectF(self.rect()), radius, radius)
            painter.setClipPath(outline)
            painter.fillRect(self.rect(), QColor('#000'))  # theme-exception: lienzo negro de vídeo
            if not self.image.isNull():
                painter.drawImage(self.rect(), self.image)
    return RoundedSurface()


class AudioStage(QWidget):
    """Cookie artwork (embedded cover or note symbol) that turns slowly while playing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.rotation = 0.0
        self.playing = False
        self.timer = QTimer(self, interval=50)
        self.timer.timeout.connect(self._turn)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_cover(self, image):
        self.pixmap = QPixmap_from(image) if image is not None and not image.isNull() else None
        self.update()

    def set_playing(self, playing):
        self.playing = playing
        self._sync()

    def _sync(self):
        if self.playing and self.isVisible() and not reduced_motion(self.window()):
            self.timer.start()
        else:
            self.timer.stop()

    def _turn(self):
        self.rotation = (self.rotation - 360 * .05 / 23.5) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 44
        box = QRectF(0, 0, side, side)
        box.moveCenter(QRectF(self.rect()).center())
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('accent', 20))
        painter.drawPath(cookie(box.adjusted(-10, -10, 10, 10), 12, -self.rotation * .6))
        outline = cookie(box, 12, self.rotation)
        if self.pixmap is not None:
            clip_pixmap(self.pixmap, outline, painter, box)
            return
        painter.setBrush(color('tile'))
        painter.drawPath(outline)
        painter.setBrush(color('accent', 38))
        painter.drawPath(outline)
        paint_symbol(painter, box, 'music_note', 'accent', side * .36, filled=True)


def QPixmap_from(image):
    from PySide6.QtGui import QPixmap
    return QPixmap.fromImage(image)


class MediaPlayer(QWidget):
    fullscreen_requested = Signal(bool)

    def __init__(self, path, audio=False, parent=None):
        super().__init__(parent)
        self.path, self.audio, self.fullscreen = str(path), audio, False
        self.job = None
        self.setObjectName('mediaPlayer')
        self.setFocusPolicy(Qt.StrongFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metric('space_m'))
        if audio:
            self.surface = _stage_surface()      # hidden: libmpv still needs a render target
            self.surface.hide()
            self.stage = AudioStage()
            layout.addWidget(self.stage, 1)
        else:
            self.surface = _stage_surface()
            self.surface.setMinimumHeight(120)
            self.surface.setCursor(Qt.PointingHandCursor)
            self.surface.installEventFilter(self)
            self.stage = None
            layout.addWidget(self.surface, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setFont(text_font('small'))
        self.status.setStyleSheet(f'color:{color("muted").name()};')
        self.status.hide()
        layout.addWidget(self.status)
        layout.addWidget(self._controls())
        self.core = PlayerCore(path, self.surface)
        self.timer = QTimer(self, interval=120)
        self.timer.timeout.connect(self._tick)
        for key, callback in (('Space', self.toggle), ('M', self.toggle_mute), ('F', self._toggle_fullscreen),
                              ('Left', lambda: self.skip(-5)), ('Right', lambda: self.skip(5)),
                              ('Up', lambda: self.nudge_volume(5)), ('Down', lambda: self.nudge_volume(-5))):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
        QTimer.singleShot(0, self._start)
        if audio:
            self.job = FilePreviewJob(self.path)
            job = self.job
            _JOBS.add(job)
            job.finished.connect(lambda: _JOBS.discard(job))
            job.ready.connect(lambda _p, data: self._cover(data.get('image')))
            job.start()

    # ----------------------------------------------------------------- build
    def _controls(self):
        capsule = _Capsule()
        column = QVBoxLayout(capsule)
        column.setContentsMargins(metric('space_l'), metric('space_m'), metric('space_l'), metric('space_m'))
        column.setSpacing(2)
        self.progress = Slider('Posición de reproducción', wavy=True, step=.02)
        self.progress.released.connect(lambda ratio: self.core.send(['seek', ratio * 100, 'absolute-percent+exact']))
        self.progress.moved.connect(lambda ratio: self.elapsed.setText(duration_label(ratio * self.core.duration)))
        column.addWidget(self.progress)
        times = QHBoxLayout()
        times.setContentsMargins(0, 0, 0, 0)
        self.elapsed, self.total = QLabel('0:00'), QLabel('0:00')
        for label in (self.elapsed, self.total):
            label.setFont(text_font('caption', 500))
            label.setStyleSheet(f'color:{color("muted").name()};')
        times.addWidget(self.elapsed)
        times.addStretch()
        times.addWidget(self.total)
        column.addLayout(times)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(metric('space_s'))
        self.back = IconButton('replay_10', 'Retroceder 10 s', lambda: self.skip(-10), size=40)
        self.play = IconButton('play_arrow', 'Reproducir · Espacio', self.toggle, variant='filled', size=56)
        self.ahead = IconButton('forward_10', 'Avanzar 10 s', lambda: self.skip(10), size=40)
        self.full = IconButton('fullscreen', 'Pantalla completa · F', self._toggle_fullscreen, size=34)
        self.full.setVisible(not self.audio)
        ghost = QWidget()
        ghost.setFixedSize(34, 34)
        row.addWidget(ghost)           # balances the fullscreen button so the transport stays centred
        row.addStretch()
        for button in (self.back, self.play, self.ahead):
            row.addWidget(button)
        row.addStretch()
        row.addWidget(self.full if not self.audio else _blank(34))
        column.addLayout(row)
        level = QHBoxLayout()
        level.setContentsMargins(0, 0, 0, 0)
        level.setSpacing(metric('space_s'))
        self.mute = IconButton('volume_up', 'Silenciar · M', self.toggle_mute, size=34)
        self.volume = Slider('Volumen', step=.05)
        self.volume.set_value(VOLUME / 100)
        self.volume.released.connect(self._set_volume)
        self.volume.moved.connect(self._set_volume)
        level.addWidget(self.mute)
        level.addWidget(self.volume, 1)
        column.addLayout(level)
        return capsule

    # ------------------------------------------------------------------ flow
    def _start(self):
        if self.core.stopped:
            return
        if self.core.start():
            self.timer.start()
        else:
            self._say(self.core.error)

    def _cover(self, image):
        try:
            self.stage.set_cover(image)
        except RuntimeError:        # player closed before the cover arrived
            pass

    def _say(self, text):
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _tick(self):
        if not self.core.poll():
            return
        duration, position = self.core.duration, self.core.position
        self.progress.set_value(position / duration if duration else 0)
        if not self.progress.dragging:
            self.elapsed.setText(duration_label(position))
        self.total.setText(duration_label(duration))
        paused = self.core.paused
        self.play.set_symbol('play_arrow' if paused else 'pause')
        self.play.set_label(('Reproducir' if paused else 'Pausar') + ' · Espacio')
        self.progress.set_playing(not paused)
        if self.stage is not None:
            self.stage.set_playing(not paused)
        muted = bool(self.core.props.get('mute'))
        self.mute.set_symbol('volume_off' if muted else 'volume_up')

    def toggle(self):
        self.core.toggle()

    def toggle_mute(self):
        self.core.send(['cycle', 'mute'])

    def skip(self, seconds):
        self.core.send(['seek', seconds, 'relative+exact'])

    def nudge_volume(self, step):
        value = max(0, min(100, round((self.core.props.get('volume') or VOLUME) + step)))
        self.volume.set_value(value / 100)
        self._set_volume(value / 100)

    def _set_volume(self, ratio):
        self.core.send(['set_property', 'volume', round(ratio * 100)])

    def _toggle_fullscreen(self):
        if not self.audio:
            self.set_fullscreen(not self.fullscreen)

    def set_fullscreen(self, enabled):
        if enabled == self.fullscreen or self.audio:
            return
        self.fullscreen = enabled
        self.full.set_symbol('fullscreen_exit' if enabled else 'fullscreen')
        self.full.set_label('Salir de pantalla completa · Esc' if enabled else 'Pantalla completa · F')
        self.fullscreen_requested.emit(enabled)

    def eventFilter(self, watched, event):
        if watched is self.surface and event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self.toggle()
            return True
        return super().eventFilter(watched, event)

    def stop(self):
        self.timer.stop()
        self.set_fullscreen(False)
        self.core.stop()


def _blank(side):
    spacer = QWidget()
    spacer.setFixedSize(side, side)
    return spacer


class _Capsule(QWidget):
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('surface_raised'))
        radius = tokens()['radius_l']
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
