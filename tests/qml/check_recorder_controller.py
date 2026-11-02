"""Wysun Recorder's SettingsController (venv Python, temporary HOME/XDG): the defaults of the old Widgets page, the
same preference files, other keys kept, damaged files tolerated, devices, the folder chooser and the permissions."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.append(str(ROOT / 'apps/recorder'))      # after apps/python: wysun_core there is the same code (a link)
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()

NO_DEVICES = {'mics': [], 'cameras': []}


def defaults():
    return {'record_mic': False, 'record_mic_device': '', 'record_system': True, 'record_cursor': True, 'countdown': 3,
            'record_camera': False, 'camera_device': '', 'camera_corner': 'bottom-right', 'camera_shape': 'circle',
            'camera_size': 'medium', 'cursor_preset': 'presentation', 'cursor_size': 32, 'fps': 30, 'quality': 'standard',
            'videos_folder': str(Path.home() / 'Videos'), 'remember_source': True}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wysun-recorder-ctl-')
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.home = root / 'home'
        self.home.mkdir()
        env = {'HOME': str(self.home), 'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_DATA_HOME': str(root / 'data'),
               'XDG_STATE_HOME': str(root / 'state')}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        devices = mock.patch('wysun_recorder.headless.devices', return_value=NO_DEVICES)
        self.devices = devices.start()
        self.addCleanup(devices.stop)
        self.config = root / 'config/wysun/recorder'
        self.config.mkdir(parents=True)
        self.messages = []

    def controller(self, **kwargs):
        from wysun_recorder.ui.controller import SettingsController
        ctl = SettingsController(**kwargs)
        ctl.message.connect(self.messages.append)
        return ctl

    def prefs(self):
        return json.loads((self.config / 'preferences.json').read_text())

    def test_defaults_match_the_widgets_page(self):
        self.assertEqual(self.controller().values, defaults())

    def test_existing_files_are_read(self):
        (self.config / 'preferences.json').write_text(json.dumps(
            {'record_mic': True, 'record_system': False, 'fps': 60, 'quality': 'high', 'videos_folder': '/srv/videos',
             'remember_source': False, 'camera_device': '/dev/video2',
             'camera_style': {'shape': 'rounded', 'size': 'large', 'corner': 'top-left'}}))
        (self.config / 'capture-ui.json').write_text(json.dumps({'countdown': 9}))
        values = self.controller().values
        self.assertEqual(values, dict(defaults(), record_mic=True, record_system=False, fps=60, quality='high',
                                      videos_folder='/srv/videos', remember_source=False, camera_device='/dev/video2',
                                      camera_shape='rounded', camera_size='large', camera_corner='top-left', countdown=9))

    def test_set_pref_writes_the_same_files(self):
        ctl = self.controller()
        changed = []
        ctl.valuesChanged.connect(lambda: changed.append(1))
        for key, value in (('record_mic', True), ('camera_corner', 'top-left'), ('fps', 60), ('quality', 'high'),
                           ('remember_source', False), ('cursor_preset', 'trail'), ('cursor_size', 44)):
            ctl.setPref(key, value)
        self.assertEqual(len(changed), 7)
        prefs = self.prefs()
        self.assertEqual((prefs['record_mic'], prefs['camera_style']['corner'], prefs['fps'], prefs['quality'],
                          prefs['remember_source'], prefs['cursor_preset'], prefs['cursor_size']),
                         (True, 'top-left', 60, 'high', False, 'trail', 44))
        self.assertEqual((ctl.values['cursor_preset'], ctl.values['cursor_size']), ('trail', 44))
        ctl.setPref('countdown', 5)
        self.assertEqual(json.loads((self.config / 'capture-ui.json').read_text())['countdown'], 5)
        self.assertEqual((ctl.values['record_mic'], ctl.values['camera_corner'], ctl.values['countdown']), (True, 'top-left', 5))
        self.assertEqual(self.messages, [])

    def test_saving_one_pref_keeps_the_unknown_ones(self):
        kept = {'previous_video_folders': ['/a', '/b'], 'camera_style': {'shape': 'circle', 'size': 'large', 'corner': 'top-left'},
                'invented': {'x': 1}}
        (self.config / 'preferences.json').write_text(json.dumps(kept))
        self.controller().setPref('fps', 24)
        self.assertEqual(self.prefs(), dict(kept, fps=24))

    def test_invalid_values_emit_a_message_and_change_nothing(self):
        ctl = self.controller()
        for key, value in (('fps', 45), ('quality', 'x'), ('camera_shape', 'x'), ('nope', 1), ('cursor_preset', 'disco'),
                           ('cursor_size', 5)):
            ctl.setPref(key, value)
        self.assertEqual(len(self.messages), 6)
        self.assertFalse((self.config / 'preferences.json').exists())
        self.assertEqual(ctl.values, defaults())

    def test_damaged_preferences_fall_back_to_defaults(self):
        for text in ('not json', '[]', '{"camera_style": {"shape": "x"}}'):
            (self.config / 'preferences.json').write_text(text)
            self.assertEqual(self.controller().values, defaults(), text)

    def test_a_preferences_file_that_is_not_an_object_can_still_be_saved_over(self):
        (self.config / 'preferences.json').write_text('[]')
        ctl = self.controller()
        ctl.setPref('fps', 24)
        self.assertEqual((self.prefs(), ctl.values['fps'], self.messages), ({'fps': 24}, 24, []))

    def test_devices_are_listed_and_failures_are_empty(self):
        self.devices.return_value = {'mics': [{'id': 'm1', 'name': 'Mic 1', 'default': True}],
                                     'cameras': [{'id': '/dev/video0', 'name': 'Cam'}]}
        ctl = self.controller()
        self.assertEqual(([m['id'] for m in ctl.mics], [c['name'] for c in ctl.cameras]), (['m1'], ['Cam']))
        self.devices.side_effect = OSError('no pactl')
        ctl.reload()
        self.assertEqual((ctl.mics, ctl.cameras), ([], []))

    def test_reload_sees_changes_made_elsewhere(self):
        ctl = self.controller()
        from wysun_recorder import headless
        headless.set_shell_pref('record_cursor', 'false')
        ctl.reload()
        self.assertFalse(ctl.values['record_cursor'])

    def test_choose_folder_saves_it_and_keeps_five_previous(self):
        (self.config / 'preferences.json').write_text(json.dumps(
            {'previous_video_folders': ['/p1', '/p2', '/p3', '/p4', '/p5', '/p6']}))
        calls = []
        ctl = self.controller(picker=lambda initial, done: calls.append((initial, done)))
        ctl.chooseFolder()
        ctl.chooseFolder()                         # already choosing: asks once
        self.assertEqual(len(calls), 1)
        self.assertTrue(ctl.picking)
        initial, done = calls[0]
        self.assertEqual(initial, str(self.home / 'Videos'))
        done(['/tmp/a'])
        self.assertFalse(ctl.picking)
        self.assertEqual(ctl.values['videos_folder'], '/tmp/a')
        previous = self.prefs()['previous_video_folders']
        self.assertEqual((previous[0], len(previous)), (str(self.home / 'Videos'), 5))

    def test_cancelling_the_folder_chooser_changes_nothing(self):
        calls = []
        ctl = self.controller(picker=lambda initial, done: calls.append(done))
        ctl.chooseFolder()
        calls[0]([])
        self.assertFalse(ctl.picking)
        self.assertEqual(ctl.values['videos_folder'], str(self.home / 'Videos'))
        self.assertFalse((self.config / 'preferences.json').exists())

    def test_picker_answers_are_parsed_defensively(self):
        from wysun_recorder.ui.controller import picked_paths
        good = json.dumps({'code': 0, 'uris': ['file:///tmp/a%20b', 'file:///tmp/c']}).encode()
        self.assertEqual(picked_paths(good, 0), ['/tmp/a b', '/tmp/c'])
        self.assertEqual(picked_paths(json.dumps({'code': 1, 'uris': []}).encode(), 0), [])
        self.assertEqual(picked_paths(good, 1), [])
        self.assertEqual(picked_paths(b'garbage', 0), [])
        self.assertEqual(picked_paths(b'x' * (1 << 21), 0), [])

    def test_a_picker_that_cannot_start_says_so(self):
        calls = []
        ctl = self.controller(picker=lambda initial, done: calls.append(done))
        ctl.chooseFolder()
        calls[0](None)
        self.assertFalse(ctl.picking)
        self.assertEqual(self.messages, ['No se pudo abrir el selector de Wysun Files'])

    def test_the_picker_process_runs_on_the_apps_code_and_not_the_releases_qml(self):
        from wysun_recorder.ui.controller import picker_environment
        env = picker_environment({'HOME': '/h', 'WYSUN_QML_LIB': '/release/qml', 'WAYLAND_DISPLAY': 'wayland-1'})
        self.assertEqual(env['PYTHONPATH'], str(Path(os.environ['XDG_DATA_HOME']) / 'wysun/app'))
        self.assertNotIn('WYSUN_QML_LIB', env)
        self.assertEqual((env['HOME'], env['WAYLAND_DISPLAY']), ('/h', 'wayland-1'))

    def test_forget_permissions_clears_consent_and_says_so(self):
        ctl = self.controller()
        with mock.patch('wysun_recorder.consent.clear') as clear:
            ctl.forgetPermissions()
        clear.assert_called_once_with()
        self.assertEqual(self.messages, ['Se volverá a pedir permiso para grabar pantallas'])


if __name__ == '__main__':
    unittest.main()
