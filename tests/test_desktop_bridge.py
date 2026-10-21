"""Desktop bridge behind the Nexus pages, using temporary HOME data and fake compositor commands."""
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
import desktop_bridge  # noqa: E402
from hypr_settings import HyprShortcutFile, HyprDesktopSettings  # noqa: E402


def runner(args):
    if list(args[:3]) == ['hyprctl', '-j', 'binds']:
        return '[]'
    if len(args) > 2 and args[2] == 'getoption':
        return '{"int": 1}'
    return 'ok'


def process(pid, name, cpu=0, memory=1024, ppid=1, uid=None, state='S'):
    return dict(pid=pid, name=name, cpu=cpu, memory=memory, ppid=ppid, uid=os.getuid() if uid is None else uid,
                state=state, user='demo', start='1')


class BridgeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        env = {'HOME': self.tmp.name, 'XDG_CONFIG_HOME': str(self.home / '.config'), 'XDG_CONFIG_DIRS': str(self.home / 'etc')}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        importlib.reload(desktop_bridge)
        self.bridge = desktop_bridge
        self.bridge.HOME = self.home
        self.bridge.BACKUPS = self.home / '.local/share/orbit/settings-backups'
        for name, factory in (('ShortcutFile', lambda h: HyprShortcutFile(h, runner)),
                              ('DesktopSettings', lambda h: HyprDesktopSettings(h, runner))):
            patcher = patch.object(self.bridge, name, side_effect=factory)
            patcher.start()
            self.addCleanup(patcher.stop)


class ProcessViewTests(unittest.TestCase):
    def test_owner_state_query_and_sort(self):
        rows = [process(10, 'terminal', cpu=9), process(20, 'python', cpu=80, ppid=10), process(30, 'node', cpu=100),
                process(40, 'daemon', cpu=1, uid=os.getuid() + 1), process(50, 'editor', cpu=2, state='T')]
        view = desktop_bridge.process_view
        shown, total = view(rows, dict(owner='mine', sort='cpu'), os.getuid())
        self.assertEqual([r['pid'] for r in shown], [30, 20, 10, 50])
        self.assertEqual(total, 4)
        shown, _ = view(rows, dict(owner='all', sort='name'), os.getuid())
        self.assertEqual([r['name'] for r in shown], ['daemon', 'editor', 'node', 'python', 'terminal'])
        shown, _ = view(rows, dict(owner='mine', state='paused'), os.getuid())
        self.assertEqual([r['pid'] for r in shown], [50])
        shown, _ = view(rows, dict(owner='mine', query='cpu>50'), os.getuid())
        self.assertEqual([r['pid'] for r in shown], [30, 20])

    def test_tree_shows_ancestors_with_depth_and_survives_cycles(self):
        rows = [process(10, 'terminal'), process(20, 'python', ppid=10), process(30, 'child', ppid=20), process(40, 'a', ppid=50), process(50, 'b', ppid=40)]
        shown, matched = desktop_bridge.process_view(rows, dict(owner='mine', tree=True, query='child', sort='pid'), os.getuid())
        self.assertEqual([(r['pid'], r['depth']) for r in shown], [(10, 0), (20, 1), (30, 2)])
        self.assertEqual(matched, 1)
        shown, _ = desktop_bridge.process_view(rows, dict(owner='mine', tree=True, sort='pid'), os.getuid())
        self.assertEqual({r['pid'] for r in shown}, {10, 20, 30, 40, 50})

    def test_row_cap(self):
        rows = [process(100 + i, 'p%d' % i) for i in range(500)]
        shown, total = desktop_bridge.process_view(rows, dict(owner='mine'), os.getuid())
        self.assertEqual((len(shown), total), (400, 500))


class ShortcutTests(BridgeCase):
    def test_create_edit_duplicate_and_delete_keep_a_backup(self):
        state = self.bridge.shortcuts_save({'key': 'super + alt + t', 'command': 'true', 'title': 'Prueba'})
        self.assertEqual([r['key'] for r in state['rows']], ['super + alt + t'])
        self.assertEqual(state['conflicts'], 0)
        row = state['rows'][0]
        state = self.bridge.shortcuts_save({'key': 'super + alt + u', 'command': 'false', 'title': 'Otra',
                                            'source_index': row['source_index'], 'part': row['part']})
        self.assertEqual(state['rows'][0]['key'], 'super + alt + u')
        with self.assertRaisesRegex(ValueError, 'ya existe'):
            self.bridge.shortcuts_save({'key': 'super + alt + u', 'command': 'true', 'title': 'Repetida'})
        with self.assertRaisesRegex(ValueError, 'sintaxis'):
            self.bridge.shortcuts_save({'key': 'super + alt + v', 'command': 'if then', 'title': 'Rota'})
        self.assertEqual(self.bridge.shortcuts_delete({'source_index': 0, 'part': state['rows'][0]['part']})['rows'], [])
        kinds = {b['kind'] for b in self.bridge.backups_state({})['backups']}
        self.assertIn('atajos', kinds)

    def test_restoring_a_shortcut_backup_reapplies_it(self):
        self.bridge.shortcuts_save({'key': 'super + alt + t', 'command': 'true', 'title': 'Uno'})
        self.bridge.shortcuts_save({'key': 'super + alt + y', 'command': 'true', 'title': 'Dos'})
        backups = [b for b in self.bridge.backups_state({})['backups'] if b['kind'] == 'atajos']
        oldest = backups[-1]
        self.bridge.backups_restore({'name': oldest['name']})
        keys = [r['key'] for r in self.bridge.shortcuts_state({})['rows']]
        self.assertEqual(keys, ['super + alt + t'])
        with self.assertRaisesRegex(ValueError, 'ya no existe'):
            self.bridge.backups_restore({'name': '../../etc/passwd'})


class RulesTests(BridgeCase):
    def test_rules_round_trip_and_validation(self):
        rules = [{'class': 'Gimp', 'state': 'floating', 'desktop': '', 'center': True, 'border': False}]
        state = self.bridge.desktop_apply({'rules': rules})
        self.assertEqual(state['rules'], rules)
        self.assertIn('window_gap', state['values'])
        self.assertEqual(self.bridge.desktop_state({})['rules'], rules)
        with self.assertRaises(ValueError):
            self.bridge.desktop_apply({'rules': rules + [dict(rules[0])]})
        with self.assertRaises(ValueError):
            self.bridge.desktop_apply({'rules': [{'class': 'bad class', 'state': 'tiled'}]})


class StartupAndSshTests(BridgeCase):
    def test_startup_entries_can_be_added_and_toggled(self):
        state = self.bridge.startup_add({'name': 'Prueba', 'command': 'true'})
        entry = next(e for e in state['entries'] if e['name'] == 'Prueba')
        self.assertTrue(entry['enabled'])
        state = self.bridge.startup_toggle({'id': entry['id'], 'enabled': False})
        self.assertFalse(next(e for e in state['entries'] if e['id'] == entry['id'])['enabled'])
        with self.assertRaisesRegex(ValueError, 'ya no existe'):
            self.bridge.startup_toggle({'id': 'missing.desktop', 'enabled': True})
        with self.assertRaises(ValueError):
            self.bridge.startup_add({'name': 'Mal', 'command': 'no-such-program-xyz'})

    def test_ssh_profiles_save_edit_delete_and_validate(self):
        state = self.bridge.ssh_save({'name': 'Local', 'host': 'localhost', 'user': 'nico', 'port': '2222'})
        row = state['rows'][0]
        self.assertEqual((row['name'], row['port'], row['index'], row['imported']), ('Local', 2222, 0, False))
        state = self.bridge.ssh_save({'name': 'Local2', 'host': 'localhost', 'port': 22, 'index': 0})
        self.assertEqual(state['rows'][0]['name'], 'Local2')
        with self.assertRaises(ValueError):
            self.bridge.ssh_save({'name': 'Mal', 'host': '-oProxyCommand=x'})
        self.assertEqual(self.bridge.ssh_delete({'index': 0})['rows'], [])
        with self.assertRaisesRegex(ValueError, 'ya no existe'):
            self.bridge.ssh_connect({'name': 'Local2'})

    def test_open_file_only_inside_user_configuration(self):
        with patch.object(self.bridge.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'Ruta no permitida'):
                self.bridge.open_file({'path': '/etc/passwd'})
            with patch.object(self.bridge, 'vim_args', return_value=['editor']):
                self.bridge.open_file({'path': str(self.home / '.config/ghostty/config')})
            popen.assert_called_once()


class ComponentTests(BridgeCase):
    def test_every_component_schema_is_typed_clamped_and_complete(self):
        values = {'duration': 0, 'corner-radius': 10, 'font-size': '12', 'background': 'abcdef', 'timeout': '99'}
        with patch.object(self.bridge.EnvironmentSettings, 'component_values', return_value=values):
            for kind, (title, note, schema) in self.bridge.COMPONENTS.items():
                data = self.bridge.component_state({'kind': kind})
                self.assertEqual([r['key'] for r in data['rows']], [r[0] for r in schema])
                for row in data['rows']:
                    if row['type'] in ('int', 'float'):
                        self.assertTrue(row['low'] <= row['value'] <= row['high'], row['key'])
            effects = {r['key']: r for r in self.bridge.component_state({'kind': 'effects'})['rows']}
            self.assertEqual(effects['duration']['value'], 50)
            terminal = {r['key']: r for r in self.bridge.component_state({'kind': 'terminal'})['rows']}
            self.assertEqual(terminal['background']['value'], '#abcdef')


class DisplayTests(BridgeCase):
    PLAN = [dict(name='A', enabled=True, primary=True, mode='1920x1080', rate='60.00', rotation='normal', x=0, y=0, scale=1.0),
            dict(name='B', enabled=True, primary=False, mode='1280x720', rate='60.00', rotation='left', x=5000, y=300, scale=2.0)]

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
            code = desktop_bridge.main(['bridge', *argv])
        return code, json.loads(out.getvalue())

    def test_unknown_action_and_errors_are_json(self):
        self.assertEqual(self.call(['nope'])[0], 2)
        code, reply = self.call(['component.state', '{"kind": "missing"}'])
        self.assertEqual(code, 1)
        self.assertFalse(reply['ok'])
        self.assertTrue(reply['error'])

    def test_every_action_called_from_qml_exists(self):
        called = set()
        for path in (ROOT / 'apps/shell').rglob('*.qml'):
            called |= set(re.findall(r'DesktopBridge\.call\("([a-z]+\.[a-z]+)"', path.read_text()))
            called |= set(re.findall(r'streamCommand\("([a-z]+\.[a-z]+)"', path.read_text()))
        self.assertGreaterEqual(len(called), 20)
        self.assertLessEqual(called, set(desktop_bridge.ACTIONS))

    def test_bridge_does_not_import_qt(self):
        code = ('import os, sys; os.environ["WYSUN_APP_DIR"] = %r; sys.path.insert(0, %r); import desktop_bridge; '
                'sys.exit(1 if any(m.startswith(("PySide6", "PyQt")) for m in sys.modules) else 0)') % (
            str(ROOT / 'apps/wysun'), str(ROOT / 'apps/shell/wysun'))
        self.assertEqual(subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
