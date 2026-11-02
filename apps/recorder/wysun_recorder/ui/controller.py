"""The settings of Wysun Recorder for its QML window.

Same preferences as the Widgets page it replaces, read and written through the same files
(``preferences.json`` and ``capture-ui.json``) and the same functions the shell's CLI uses, so a value
saved here is the one the recording bar and the worker see.
"""
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QProcessEnvironment, QUrl, Signal, Slot

from wysun_core import paths
from .. import consent, headless, videolibrary
from ..schema import camera_style
from .capture_feedback_prefs import load_countdown

SHELL_KEYS = ('record_mic', 'record_system', 'record_cursor', 'record_camera', 'record_mic_device', 'camera_device',
              'camera_corner', 'camera_shape', 'camera_size', 'countdown', 'cursor_preset', 'cursor_size')
FPS = (15, 24, 30, 60)
QUALITY = ('compact', 'standard', 'high')
MAX_ANSWER = 1 << 20
PREVIOUS_FOLDERS = 5
PICKER_FAILED = 'No se pudo abrir el selector de Wysun Files'


def picked_paths(raw, code):
    """Local paths of the one-shot picker's answer (``{"code": 0, "uris": [...]}``); empty for anything else."""
    if code != 0 or len(raw) > MAX_ANSWER:
        return []
    try:
        result = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(result, dict) or result.get('code') != 0 or not isinstance(result.get('uris'), list):
        return []
    found = (QUrl(uri).toLocalFile() for uri in result['uris'] if isinstance(uri, str))
    return [path for path in found if path]


def picker_environment(base=None):
    """The picker runs Wysun's installed code, as its own process; the release's QML folder is not its library."""
    env = dict(os.environ if base is None else base)
    env['PYTHONPATH'] = str(paths.data('wysun', 'app'))
    env.pop('WYSUN_QML_LIB', None)
    return env


def process_picker(parent):
    """A picker that runs ``python -m wysun_files.picker`` and calls ``done(paths)``; ``done(None)`` if it cannot start."""
    def pick(initial, done):
        process = QProcess(parent)
        env = QProcessEnvironment()
        for key, value in picker_environment().items():
            env.insert(key, value)
        process.setProcessEnvironment(env)

        def finished(code, _status):
            raw = bytes(process.readAllStandardOutput())
            process.deleteLater()
            done(picked_paths(raw, code))

        def failed(error):
            if error == QProcess.FailedToStart:
                process.deleteLater()
                done(None)

        process.finished.connect(finished)
        process.errorOccurred.connect(failed)
        process.start(str(Path(sys.base_prefix) / 'bin/python3'), ['-P', '-m', 'wysun_files.picker'])
        process.write(json.dumps({'kind': 'folder', 'initial': initial, 'title': 'Carpeta de videos'}).encode() + b'\n')
        process.closeWriteChannel()
    return pick


class SettingsController(QObject):
    valuesChanged = Signal()
    devicesChanged = Signal()
    pickingChanged = Signal()
    message = Signal(str)

    def __init__(self, picker=None, parent=None):
        super().__init__(parent)
        self._picker = picker or process_picker(self)
        self._picking = False
        self._values = self._read()
        self._mics, self._cameras = self._devices()

    values = Property('QVariantMap', lambda self: self._values, notify=valuesChanged)
    mics = Property('QVariantList', lambda self: self._mics, notify=devicesChanged)
    cameras = Property('QVariantList', lambda self: self._cameras, notify=devicesChanged)
    picking = Property(bool, lambda self: self._picking, notify=pickingChanged)

    @staticmethod
    def _read():
        prefs = videolibrary.preferences()
        try:
            style = camera_style(prefs.get('camera_style'))
        except ValueError:
            style = camera_style({})
        fps, quality = prefs.get('fps', 30), prefs.get('quality', 'standard')
        preset, size = prefs.get('cursor_preset'), prefs.get('cursor_size')
        return {'record_mic': bool(prefs.get('record_mic', False)), 'record_mic_device': str(prefs.get('record_mic_device') or ''),
                'record_system': bool(prefs.get('record_system', True)), 'record_cursor': bool(prefs.get('record_cursor', True)),
                'countdown': load_countdown(), 'record_camera': bool(prefs.get('record_camera', False)),
                'camera_device': str(prefs.get('camera_device') or ''), 'camera_corner': style['corner'],
                'camera_shape': style['shape'], 'camera_size': style['size'],
                'cursor_preset': preset if preset in headless.CURSOR_PRESETS else headless.DEFAULT_CURSOR_PRESET,
                'cursor_size': size if type(size) is int and 16 <= size <= 64 else headless.DEFAULT_CURSOR_SIZE,
                'fps': fps if fps in FPS else 30, 'quality': quality if quality in QUALITY else 'standard',
                'videos_folder': str(videolibrary.videos_root()), 'remember_source': bool(prefs.get('remember_source', True))}

    @staticmethod
    def _devices():
        try:
            found = headless.devices()
            return ([{'id': str(m['id']), 'name': str(m['name'])} for m in found.get('mics', [])],
                    [{'id': str(c['id']), 'name': str(c['name'])} for c in found.get('cameras', [])])
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return [], []

    def _refresh(self):
        values = self._read()
        if values != self._values:
            self._values = values
            self.valuesChanged.emit()

    @Slot()
    def reload(self):
        self._refresh()
        mics, cameras = self._devices()
        if (mics, cameras) != (self._mics, self._cameras):
            self._mics, self._cameras = mics, cameras
            self.devicesChanged.emit()

    @Slot(str, 'QVariant')
    def setPref(self, key, value):
        try:
            if key in SHELL_KEYS:
                headless.set_shell_pref(key, value)
            elif key == 'fps':
                if int(value) not in FPS:
                    raise ValueError(f'Fotogramas no admitidos: {value}')
                videolibrary.save_preferences(fps=int(value))
            elif key == 'quality':
                if value not in QUALITY:
                    raise ValueError(f'Calidad no admitida: {value}')
                videolibrary.save_preferences(quality=value)
            elif key == 'remember_source':
                videolibrary.save_preferences(remember_source=bool(value))
            else:
                raise ValueError(f'Preferencia desconocida: {key}')
        except (ValueError, TypeError) as exc:
            self.message.emit(str(exc))
            return
        except OSError as exc:
            self.message.emit(f'No se pudo guardar: {exc}')
            return
        self._refresh()

    def _set_picking(self, picking):
        if picking != self._picking:
            self._picking = picking
            self.pickingChanged.emit()

    @Slot()
    def chooseFolder(self):
        if self._picking:
            return
        self._set_picking(True)
        self._picker(self._values['videos_folder'], self._chosen)

    def _chosen(self, found):
        self._set_picking(False)
        if found is None:
            self.message.emit(PICKER_FAILED)
            return
        if not found:
            return
        chosen, current = found[0], self._values['videos_folder']
        saved = videolibrary.preferences().get('previous_video_folders', [])
        previous = [current] + [p for p in (saved if isinstance(saved, list) else []) if p not in (chosen, current)]
        try:
            videolibrary.save_preferences(videos_folder=chosen, previous_video_folders=previous[:PREVIOUS_FOLDERS])
        except OSError as exc:
            self.message.emit(f'No se pudo guardar: {exc}')
            return
        self._refresh()

    @Slot()
    def forgetPermissions(self):
        try:
            consent.clear()
        except OSError as exc:
            self.message.emit(f'No se pudo olvidar: {exc}')
            return
        self.message.emit('Se volverá a pedir permiso para grabar pantallas')
