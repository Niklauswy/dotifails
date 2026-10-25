"""Display bridge behind the Nexus pages, using temporary HOME data and fake compositor commands."""
import importlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
os.environ['WYSUN_APP_DIR'] = str(ROOT / 'apps/wysun')
sys.path.insert(0, str(ROOT / 'apps/wysun'))
sys.path.insert(0, str(ROOT / 'apps/shell/wysun'))
import display_bridge  # noqa: E402


class BridgeCase(unittest.TestCase):
    def setUp(self):
        self.bridge = display_bridge
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(display_bridge, 'HOME', self.home)
        patcher.start()
        self.addCleanup(patcher.stop)


class DisplayTests(BridgeCase):
    PLAN = [dict(name='A', enabled=True, primary=True, mode='1920x1080', rate='60.00', rotation='normal', x=0, y=0, scale=1.0),
            dict(name='B', enabled=True, primary=False, mode='1280x720', rate='60.00', rotation='left', x=5000, y=300, scale=2.0)]

    def test_widget_placement_preserves_profiles_and_other_preferences(self):
        backend = self.bridge.env()
        backend.save_section('displays', {'profiles': {'A|B': self.PLAN}})
        backend.save_section('wallpaper', {'default': 'keep.png'})
        self.assertEqual(self.bridge.displays_widgets({'mode': 'primary'}), {'mode': 'primary'})
        backend.reload()
        self.assertEqual(backend.section('displays')['profiles']['A|B'], self.PLAN)
        self.assertEqual(backend.section('displays')['widgetScreens'], 'primary')
        self.assertEqual(backend.section('wallpaper')['default'], 'keep.png')
        with self.assertRaises(ValueError):
            self.bridge.displays_widgets({'mode': 'invalid'})
        self.bridge.displays_widgets({'mode': 'all'})
        backend.reload()
        self.assertEqual(backend.section('displays')['widgetScreens'], 'all')

    def test_saved_primary_does_not_follow_keyboard_focus(self):
        backend = self.bridge.env()
        backend.save_section('displays', {'profiles': {'A|B': self.PLAN}})
        outputs = [dict(p, connected=True, primary=p['name'] == 'B',
                        modes=[dict(name=p['mode'], rates=[p['rate']])]) for p in self.PLAN]
        with patch.object(self.bridge, 'display_inventory', return_value=outputs):
            state = self.bridge.displays_state({})
        self.assertEqual([p['name'] for p in state['plan'] if p['primary']], ['A'])

    def test_layout_is_edge_to_edge_and_reports_logical_boxes(self):
        view = self.bridge.displays_normalize({'plan': self.PLAN})
        boxes = {b['name']: b for b in view['boxes']}
        self.assertEqual((boxes['A']['x'], boxes['A']['w']), (0, 1920))
        self.assertEqual((boxes['B']['x'], boxes['B']['y'], boxes['B']['w'], boxes['B']['h']), (1920, 0, 360, 640))
        self.assertEqual(view['order'], ['A', 'B'])
        moved = self.bridge.displays_normalize({'plan': view['plan'], 'move': {'name': 'B', 'direction': 'left'}})
        self.assertEqual(moved['order'], ['B', 'A'])
        below = self.bridge.displays_normalize({'plan': view['plan'], 'move': {'name': 'B', 'direction': 'below'}})
        self.assertGreater({b['name']: b for b in below['boxes']}['B']['y'], 0)

    def test_settling_only_resumes_trials_created_by_the_bridge(self):
        with self.assertRaisesRegex(ValueError, 'desconocida'):
            self.bridge.displays_settle({'folder': str(self.home / 'elsewhere'), 'accept': True})

    def test_expired_trial_cannot_be_reported_as_saved(self):
        folder = self.home / '.cache/orbit/display-trials/expired'
        folder.mkdir(parents=True)
        (folder / 'trial.json').write_text(json.dumps({'old': self.PLAN, 'deadline': 0}))
        (folder / 'meta.json').write_text(json.dumps({'plan': self.PLAN, 'key': 'A|B'}))
        (folder / 'reverted').write_text('ok')
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.bridge.displays_settle({'folder': str(folder), 'accept': True})
        self.assertFalse((folder / 'accepted').exists())

    def test_resumed_trial_rejects_and_restores_the_previous_layout(self):
        from environment_settings import DisplayTrial, EnvironmentSettings
        folder = self.home / '.cache/orbit/display-trials/t1'
        folder.mkdir(parents=True)
        (folder / 'trial.json').write_text(json.dumps({'old': self.PLAN, 'deadline': 0}))
        (folder / 'meta.json').write_text(json.dumps({'plan': self.PLAN, 'key': 'A|B'}))
        calls = []
        backend = EnvironmentSettings(self.home, lambda args: calls.append(list(args)) or 'ok')
        trial = DisplayTrial.resume(backend, folder)
        self.assertFalse(trial.done)
        with patch('environment_settings.display_inventory', return_value=[
                dict(name=p['name'], connected=True, enabled=True, primary=p['primary'], mode=p['mode'], rate=p['rate'],
                     rotation=p['rotation'], x=0, y=0, scale=p['scale'], modes=[dict(name=p['mode'], rates=[p['rate']])])
                for p in self.PLAN]), patch('environment_settings.after_display_change'):
            trial.reject()
        self.assertTrue((folder / 'reverted').exists())
        self.assertTrue(trial.done)
        self.assertTrue(calls)


class ProtocolTests(unittest.TestCase):
    def call(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = display_bridge.main(['bridge', *argv])
        return code, json.loads(out.getvalue())

    def test_unknown_action_and_errors_are_json(self):
        self.assertEqual(self.call(['nope'])[0], 2)
        code, reply = self.call(['workspaces.edit', '{"action": "missing"}'])
        self.assertEqual(code, 1)
        self.assertFalse(reply['ok'])
        self.assertTrue(reply['error'])

    def test_every_action_called_from_qml_exists(self):
        called = set()
        for path in (ROOT / 'apps/shell').rglob('*.qml'):
            called |= set(re.findall(r'DisplayBridge\.call\("([a-z]+\.[a-z]+)"', path.read_text()))
            called |= set(re.findall(r'streamCommand\("([a-z]+\.[a-z]+)"', path.read_text()))
        self.assertGreaterEqual(len(called), 6)
        self.assertLessEqual(called, set(display_bridge.ACTIONS))

    def test_bridge_does_not_import_qt(self):
        code = ('import os, sys; os.environ["WYSUN_APP_DIR"] = %r; sys.path.insert(0, %r); import display_bridge; '
                'sys.exit(1 if any(m.startswith(("PySide6", "PyQt")) for m in sys.modules) else 0)') % (
            str(ROOT / 'apps/wysun'), str(ROOT / 'apps/shell/wysun'))
        self.assertEqual(subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
