"""Basic player and recorder settings pages."""
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel, QScrollArea, QSpinBox, QVBoxLayout,
                               QWidget)

from .app_kit import Button, IconButton, Panel, Switch, metric, section_label as _section_label


class PlayerPage(QWidget):
    """A finished recording in the shared Wysun player, under Recorder's own header."""

    closed = Signal()
    message = Signal(str)

    def __init__(self):
        super().__init__()
        from . import media_host
        media_host.install()
        from wysun_media.player import MediaPlayer
        column = QVBoxLayout(self)
        margin = metric('space_xl')
        column.setContentsMargins(margin, metric('space_l'), margin, metric('space_l'))
        column.setSpacing(metric('space_m'))
        head = QHBoxLayout()
        self.back = IconButton('arrow_back', 'Volver a la biblioteca · Esc', self.closed.emit, size=36)
        self.title = QLabel('')
        self.title.setObjectName('subheading')
        head.addWidget(self.back)
        head.addSpacing(metric('space_s'))
        head.addWidget(self.title, 1)
        self.external = IconButton('open_in_new', 'Abrir en Wysun Player', self._external, size=36)
        head.addWidget(self.external)
        column.addLayout(head)
        self.player = MediaPlayer(mode='embedded', backdrop='canvas')
        self.player.enable_integration()
        self.player.errorOccurred.connect(lambda error: self.message.emit(error.message))
        self.player.expandRequested.connect(self._external)
        column.addWidget(self.player, 1)
        self.setFocusProxy(self.player)             # keys reach the player when the page is focused
        self.path = None

    def load(self, item):
        self.path = item.video
        self.title.setText(item.title)
        self.player.open(item.video)                # the user asked to play it

    def stop(self):
        self.player.close_media()

    def _external(self):
        """Continue the recording in Wysun Player at the same place; the preview stays paused."""
        if not self.path:
            return
        session = self.player.session
        position, paused = session.position, session.paused
        session.set_paused(True)
        launcher = shutil.which('wysun-player') or str(Path.home() / '.local/bin/wysun-player')
        argv = [launcher, *(['--start', f'{position:.1f}'] if position else []), *(['--paused'] if paused else []), '--', str(self.path)]
        try:
            subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            subprocess.Popen(['xdg-open', str(self.path)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def shutdown(self):
        self.player.shutdown()


def section_label(text):
    label = _section_label(text)
    label.setContentsMargins(0, metric('space_l'), 0, metric('space_xs'))
    return label


class Row(QWidget):
    """Label with a hint on the left, the control on the right."""

    def __init__(self, title, hint, control):
        super().__init__()
        line = QHBoxLayout(self)
        line.setContentsMargins(0, metric('space_s'), 0, metric('space_s'))
        text = QVBoxLayout()
        text.setSpacing(0)
        label = QLabel(title)
        label.setObjectName('subheading')
        label.setStyleSheet('font-size:%dpx;' % metric('font_body'))
        note = QLabel(hint)
        note.setObjectName('muted')
        note.setWordWrap(True)
        text.addWidget(label)
        text.addWidget(note)
        line.addLayout(text, 1)
        line.addSpacing(metric('space_l'))
        line.addWidget(control, 0, Qt.AlignVCenter)


class SettingsPage(QScrollArea):
    """Recording defaults, saved as they change; the shell reads the same preferences."""

    message = Signal(str)
    folder_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        column = QVBoxLayout(body)
        margin = metric('space_xl')
        column.setContentsMargins(margin, margin, margin, margin)
        column.setSpacing(0)
        title = QLabel('Ajustes')
        title.setObjectName('heading')
        column.addWidget(title)
        from ..videolibrary import preferences, videos_root
        from .capture_feedback_prefs import load_countdown
        prefs = preferences()

        column.addWidget(section_label('Al grabar'))
        self.mic = Switch('Micrófono')
        self.mic.setChecked(bool(prefs.get('record_mic', False)))
        self.mic.toggledByUser.connect(lambda on: self.save(record_mic=on))
        column.addWidget(Row('Micrófono', 'Graba la entrada de audio predeterminada.', self.mic))
        from ..headless import devices
        found = devices()
        self.mic_device = QComboBox()
        self.mic_device.addItem('Predeterminado del sistema', '')
        for mic in found['mics']:
            self.mic_device.addItem(mic['name'], mic['id'])
        self.mic_device.setCurrentIndex(max(0, self.mic_device.findData(prefs.get('record_mic_device') or '')))
        self.mic_device.currentIndexChanged.connect(lambda _: self.save(record_mic_device=self.mic_device.currentData()))
        column.addWidget(Row('Dispositivo de micrófono', 'Cuál grabar cuando el micrófono está activo. También se elige en la barra al grabar.', self.mic_device))
        self.system = Switch('Audio del sistema')
        self.system.setChecked(bool(prefs.get('record_system', True)))
        self.system.toggledByUser.connect(lambda on: self.save(record_system=on))
        column.addWidget(Row('Audio del sistema', 'Incluye lo que suena en el equipo.', self.system))
        self.cursor = Switch('Cursor')
        self.cursor.setChecked(bool(prefs.get('record_cursor', True)))
        self.cursor.toggledByUser.connect(lambda on: self.save(record_cursor=on))
        column.addWidget(Row('Cursor', 'Muestra el puntero en el video.', self.cursor))
        self.countdown = QSpinBox()
        self.countdown.setRange(0, 30)
        self.countdown.setSuffix(' s')
        self.countdown.setValue(load_countdown())
        self.countdown.valueChanged.connect(self.save_countdown)
        column.addWidget(Row('Cuenta atrás', 'Tiempo antes de empezar a grabar. 0 empieza al instante.', self.countdown))

        column.addWidget(section_label('Cámara'))
        from ..schema import camera_style
        try:
            style = camera_style(prefs.get('camera_style'))
        except ValueError:
            style = camera_style({})
        self.camera = Switch('Cámara')
        self.camera.setChecked(bool(prefs.get('record_camera', False)))
        self.camera.toggledByUser.connect(lambda on: self.save(record_camera=on))
        column.addWidget(Row('Grabar con cámara', 'Se añade al video en una esquina, como una burbuja.', self.camera))
        self.camera_device = QComboBox()
        for camera in found['cameras']:
            self.camera_device.addItem(camera['name'], camera['id'])
        if not found['cameras']:
            self.camera_device.addItem('No se encontró ninguna cámara', '')
            self.camera_device.setEnabled(False)
            self.camera.setEnabled(False)
        self.camera_device.setCurrentIndex(max(0, self.camera_device.findData(prefs.get('camera_device') or '')))
        self.camera_device.currentIndexChanged.connect(lambda _: self.save(camera_device=self.camera_device.currentData()))
        column.addWidget(Row('Cámara', 'La que se usa al grabar.', self.camera_device))
        self.style_boxes = {}
        for key, title, hint, options in (
                ('corner', 'Esquina', 'Dónde queda la burbuja.', (('top-left', 'Arriba a la izquierda'), ('top-right', 'Arriba a la derecha'), ('bottom-left', 'Abajo a la izquierda'), ('bottom-right', 'Abajo a la derecha'))),
                ('shape', 'Forma', 'Círculo o rectángulo redondeado.', (('circle', 'Círculo'), ('rounded', 'Redondeada'))),
                ('size', 'Tamaño', 'Qué parte del video ocupa.', (('small', 'Pequeña'), ('medium', 'Mediana'), ('large', 'Grande')))):
            box = QComboBox()
            for value, name in options:
                box.addItem(name, value)
            box.setCurrentIndex(max(0, box.findData(style[key])))
            box.currentIndexChanged.connect(lambda _, key=key, box=box: self.save_camera_style(key, box.currentData()))
            self.style_boxes[key] = box
            column.addWidget(Row(title, hint, box))

        column.addWidget(section_label('Calidad'))
        self.fps = QComboBox()
        for value in (15, 24, 30, 60):
            self.fps.addItem(f'{value} fps', value)
        self.fps.setCurrentIndex(max(0, self.fps.findData(prefs.get('fps', 30))))
        self.fps.currentIndexChanged.connect(lambda _: self.save(fps=self.fps.currentData()))
        column.addWidget(Row('Fotogramas por segundo', '30 es lo habitual; 60 pesa el doble.', self.fps))
        self.quality = QComboBox()
        for key, name in (('compact', 'Compacta'), ('standard', 'Estándar'), ('high', 'Alta')):
            self.quality.addItem(name, key)
        self.quality.setCurrentIndex(max(0, self.quality.findData(prefs.get('quality', 'standard'))))
        self.quality.currentIndexChanged.connect(lambda _: self.save(quality=self.quality.currentData()))
        column.addWidget(Row('Calidad de video', 'Alta ocupa más espacio y exige más al equipo.', self.quality))

        column.addWidget(section_label('Archivos'))
        self.folder = QLabel(str(videos_root()))
        self.folder.setObjectName('muted')
        change = Button('Cambiar…', 'folder_open', 'tonal', self.choose_folder)
        holder = QWidget()
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.addWidget(self.folder)
        line.addWidget(change)
        column.addWidget(Row('Carpeta de videos', 'Dónde se guardan los MP4 al terminar.', holder))

        column.addWidget(section_label('Privacidad'))
        self.remember = Switch('Recordar pantalla autorizada')
        self.remember.setChecked(bool(prefs.get('remember_source', True)))
        self.remember.toggledByUser.connect(lambda on: self.save(remember_source=on))
        column.addWidget(Row('Recordar pantalla autorizada', 'Evita pedir permiso cada vez que grabas una pantalla.', self.remember))
        forget = Button('Olvidar', 'lock_reset', 'tonal', self.forget)
        column.addWidget(Row('Permisos de pantalla', 'Vuelve a pedir autorización en la próxima grabación.', forget))

        column.addWidget(section_label('Atajos'))
        for keys, what in (('Super+Shift+L', 'Elegir qué grabar (pantalla, ventana o área), o terminar'),
                           ('Ctrl+Shift+R', 'Pausar o reanudar'), ('Ctrl+Shift+S', 'Terminar'),
                           ('Ctrl+Shift+A', 'Dibujar sobre la pantalla mientras grabas')):
            note = QLabel(f'<b>{keys}</b> &nbsp; {what}')
            note.setContentsMargins(metric('space_m'), 2, 0, 2)
            column.addWidget(note)
        column.addStretch()
        self.setWidget(body)

    def save(self, **values):
        from ..videolibrary import save_preferences
        try:
            save_preferences(**values)
        except OSError as exc:
            self.message.emit(f'No se pudo guardar: {exc}')

    def save_camera_style(self, key, value):
        from ..schema import camera_style
        from ..videolibrary import preferences
        try:
            style = camera_style(preferences().get('camera_style'))
            style[key] = value
            self.save(camera_style=camera_style(style))
        except ValueError as exc:
            self.message.emit(str(exc))

    def save_countdown(self, value):
        from .capture_feedback_prefs import save_countdown
        try:
            save_countdown(value)
        except OSError as exc:
            self.message.emit(f'No se pudo guardar: {exc}')

    def choose_folder(self):
        from ..videolibrary import preferences, videos_root
        chosen = QFileDialog.getExistingDirectory(self, 'Carpeta de videos', str(videos_root()))
        if not chosen:
            return
        previous = [str(videos_root())] + [p for p in preferences().get('previous_video_folders', []) if p != chosen]
        self.save(videos_folder=chosen, previous_video_folders=previous[:5])
        self.folder.setText(chosen)
        self.folder_changed.emit()

    def forget(self):
        from .. import consent
        consent.clear()
        self.message.emit('Se volverá a pedir permiso para grabar pantallas')
