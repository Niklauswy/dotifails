"""Wysun Recorder's settings window (venv Python, offscreen, temporary HOME/XDG): it loads without warnings, every
control reads and writes the preference files, a machine without cameras still opens, a second launch focuses the
first, light and dark follow the theme live, and the Wayland app id is wysun-recorder."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.append(str(ROOT / 'apps/recorder'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

CONTROLS = ('record_mic', 'record_mic_device', 'record_system', 'record_cursor', 'countdown', 'cursor_preset', 'cursor_size',
            'record_camera',
            'camera_device', 'camera_corner', 'camera_shape', 'camera_size', 'fps', 'quality', 'chooseFolder',
            'remember_source', 'forgetPermissions')
CAMERA = {'mics': [], 'cameras': [{'id': '/dev/video0', 'name': 'Cámara de prueba'}]}
NOTHING = {'mics': [], 'cameras': []}


class SettingsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import Qt
        cls.Qt = Qt
        cls.h = support.Harness.get()
        from wysun_qml import engine as qml_engine
        # Its own engine: the window sets its own `bridge` on the root context, which must not replace the Harness's.
        _, cls.engine = qml_engine.create_engine('wysun-recorder-tests')
        cls.warnings = []
        cls.engine.warnings.connect(lambda found: cls.warnings.extend(w.toString() for w in found))

    def setUp(self):
        self.warnings.clear()
        self.tmp = tempfile.TemporaryDirectory(prefix='wysun-recorder-ui-', dir=Path.home() / '.cache/wysun-fase1/tmp')
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        env = {'HOME': str(root / 'home'), 'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_DATA_HOME': str(root / 'data'),
               'XDG_STATE_HOME': str(root / 'state'), 'XDG_RUNTIME_DIR': str(root / 'run')}
        (root / 'home').mkdir()
        (root / 'run').mkdir(mode=0o700)
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = root / 'config/wysun/recorder'
        self.config.mkdir(parents=True)
        self.devices = mock.patch('wysun_recorder.headless.devices', return_value=NOTHING)
        self.devices.start()
        self.addCleanup(self.devices.stop)

    def open(self, devices=None):
        from wysun_recorder.ui.window import RecorderSettingsWindow
        if devices is not None:
            self.devices.stop()
            self.devices = mock.patch('wysun_recorder.headless.devices', return_value=devices)
            self.devices.start()
            self.addCleanup(self.devices.stop)
        self.win = RecorderSettingsWindow(engine=self.engine)
        self.win.bridge.setReducedMotion(True)
        self.window = self.win.window
        self.window.resize(640, 720)
        self.win.present()
        self.h.pump(100)
        self.addCleanup(self.dispose, self.window)
        return self.win

    def dispose(self, window):
        try:
            window.close()
            window.deleteLater()
        except RuntimeError:            # already deleted
            pass
        self.h.pump(30)

    def item(self, name):
        return self.h.find_in(self.window.contentItem(), name)

    def reveal(self, name):
        """Scroll the control into view; returns its centre in window coordinates."""
        from PySide6.QtCore import QPointF
        item = self.item(name)
        flick = self.item('scroll')
        top = item.mapToItem(flick.property('contentItem'), QPointF(0, 0)).y()
        flick.setProperty('contentY', max(0, top - flick.height() / 2))
        self.h.pump(30)
        return item.mapToScene(QPointF(item.width() / 2, item.height() / 2))

    def click(self, name):
        point = self.reveal(name)
        self.h.click(self.window, point.x(), point.y())

    def prefs(self):
        return json.loads((self.config / 'preferences.json').read_text())

    def test_loads_without_warnings_and_lists_every_setting(self):
        self.open()
        self.assertEqual(self.warnings, [])
        for name in CONTROLS:
            self.assertIsNotNone(self.item(name), name)
        self.assertEqual(self.item('record_system').property('checked'), True)
        self.assertEqual(self.item('record_mic').property('checked'), False)
        self.assertEqual(self.item('fps').property('displayText'), '30 fps')

    def test_switch_writes_the_preference_file(self):
        self.open()
        self.click('record_mic')
        self.assertTrue(self.prefs()['record_mic'])
        self.assertEqual((self.win.settings.values['record_mic'], self.item('record_mic').property('checked')), (True, True))

    def test_dropdown_and_slider_write(self):
        self.open()
        self.click('fps')
        self.click_item(self.h.find_in(self.window.contentItem(), 'menuitem-60'))
        self.assertEqual(self.prefs()['fps'], 60)
        self.assertEqual(self.item('fps').property('displayText'), '60 fps')
        slider = self.item('countdown')
        self.reveal('countdown')
        slider.forceActiveFocus(self.Qt.TabFocusReason)
        for _ in range(4):
            self.h.key(self.window, self.Qt.Key_Right)
        self.assertEqual(json.loads((self.config / 'capture-ui.json').read_text())['countdown'], 7)

    def test_the_pointer_style_and_size_are_chosen_here_and_follow_the_cursor_switch(self):
        self.open()
        self.assertEqual((self.item('cursor_preset').property('displayText'), self.item('cursor_size').property('value')),
                         ('Resaltado', 32))
        self.click('cursor_preset')
        self.click_item(self.h.find_in(self.window.contentItem(), 'menuitem-trail'))
        self.assertEqual(self.prefs()['cursor_preset'], 'trail')
        slider = self.item('cursor_size')
        self.reveal('cursor_size')
        slider.forceActiveFocus(self.Qt.TabFocusReason)
        for _ in range(2):
            self.h.key(self.window, self.Qt.Key_Right)
        self.assertEqual(self.prefs()['cursor_size'], 40)
        self.assertFalse(self.item('cursor_preset').property('disabled'))
        self.click('record_cursor')                                  # the cursor off: nothing to dress up
        self.assertTrue(self.h.wait_for(lambda: self.item('cursor_preset').property('disabled'), 2000))
        self.assertTrue(self.item('cursor_size').property('disabled'))

    def click_item(self, item):
        from PySide6.QtCore import QPointF
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        self.h.click(self.window, point.x(), point.y())

    def test_without_devices_the_camera_rows_are_disabled_and_say_so(self):
        self.open()
        self.assertEqual(self.warnings, [])
        camera, device = self.item('record_camera'), self.item('camera_device')
        self.assertEqual((camera.property('disabled'), device.property('disabled')), (True, True))
        self.assertEqual(device.property('displayText'), 'No se encontró ninguna cámara')
        self.assertEqual(self.item('record_mic_device').property('displayText'), 'Predeterminado del sistema')

    def test_with_a_camera_the_rows_are_enabled(self):
        (self.config / 'preferences.json').write_text(json.dumps({'camera_device': '/dev/video0'}))
        self.open(CAMERA)
        device = self.item('camera_device')
        self.assertEqual((self.item('record_camera').property('disabled'), device.property('disabled')), (False, False))
        self.assertEqual(device.property('displayText'), 'Cámara de prueba')

    def test_the_first_camera_is_shown_when_none_is_saved_or_it_is_gone(self):
        for saved in ({}, {'camera_device': '/dev/video9'}):
            with self.subTest(saved=saved):
                (self.config / 'preferences.json').write_text(json.dumps(saved))
                self.open(CAMERA)
                self.assertEqual(self.item('camera_device').property('displayText'), 'Cámara de prueba')
                self.dispose(self.window)

    def test_second_launch_focuses_the_open_window(self):
        from wysun_recorder.ui import window as module
        from wysun_recorder.ui.instance import Instance
        directory = Path(self.tmp.name) / 'instance'
        owner = Instance(str(directory))
        self.assertTrue(owner.claim())
        self.addCleanup(owner.close)
        seen, results = [], []
        thread = threading.Thread(target=lambda: results.append(module.run([], instance=Instance(str(directory)))))
        with mock.patch.object(bootstrap, 'ensure_runtime_python'):
            thread.start()
            deadline = time.monotonic() + 5
            while thread.is_alive() and time.monotonic() < deadline:
                owner.poll(lambda action: seen.append(action) or {'state': 'focused'})
                time.sleep(0.01)
            thread.join(1)
        self.assertEqual((results, seen), ([0], ['focus']))

    def test_presenting_a_visible_window_only_raises_and_activates_it(self):
        """A second launch must not re-show the window: on Hyprland that left it maximized (found live)."""
        self.open()
        calls = []
        self.window.show = lambda: calls.append('show')
        self.window.showNormal = lambda: calls.append('showNormal')
        self.window.setPosition = lambda *args: calls.append('setPosition')
        self.window.resize = lambda *args: calls.append('resize')
        self.win.present()
        self.assertEqual(calls, [])

    def test_light_and_dark_follow_the_theme_live(self):
        self.open()
        for name in ('green-light', 'green-dark', 'orange-light', 'blue-dark'):
            with self.subTest(palette=name):
                self.win.bridge.setPreview(support.palettes()[name])
                self.h.pump(60)
                image = self.window.grabWindow()
                support.close_to(self, self.h.pixel(image, image.width() - 4, 30), support.palettes()[name]['colours']['surface'],
                                 msg=name)

    def test_the_wayland_app_id_is_wysun_recorder(self):
        from PySide6.QtGui import QGuiApplication
        self.open()
        self.assertEqual(QGuiApplication.desktopFileName(), 'wysun-recorder')

    def test_escape_closes_and_reactivating_reloads_values(self):
        from PySide6.QtGui import QWindow
        from wysun_recorder import headless
        self.open()
        other = QWindow()                       # offscreen never deactivates a hidden window: take the focus away instead
        other.resize(50, 50)
        other.show()
        other.requestActivate()
        self.addCleanup(other.close)
        self.assertTrue(self.h.wait_for(lambda: not self.window.isActive(), 2000))
        headless.set_shell_pref('record_cursor', 'false')
        self.assertTrue(self.win.settings.values['record_cursor'])       # not read yet
        self.win.present()
        self.assertTrue(self.h.wait_for(lambda: self.win.settings.values['record_cursor'] is False, 2000))
        self.h.key(self.window, self.Qt.Key_Escape)
        self.assertFalse(self.window.isVisible())


if __name__ == '__main__':
    unittest.main()
