"""Wysun bridge contracts: scheme/Colours keys, single Dunst, dispatcher. Synthetic data only."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
SHELL = ROOT / 'apps/shell'
spec = importlib.util.spec_from_file_location('wysun_cael_backend_b', SHELL / 'wysun/backend.py')
backend = importlib.util.module_from_spec(spec); spec.loader.exec_module(backend)
sys.path.insert(0, str(ROOT / 'apps/wysun'))
import theme_core  # noqa: E402
import wysun_scheme  # noqa: E402

STYLES = [('space-black', 'space-black'), ('space-black', 'tokyo'), ('space-black', 'severance'),
          ('fluent', 'light'), ('fluent', 'dark')]


def colours_property_names():
    source = (SHELL / 'services/Colours.qml').read_text()
    return set(re.findall(r'property color (\w+)', source))


def mapped(name):
    """Python mirror of Colours.load/propertyKey."""
    if name.startswith('term'):
        return name
    match = re.fullmatch(r'(neutralVariant|neutral|primary|secondary|tertiary|error)PaletteKeyColor', name)
    if match:
        key = 'neutral_variant' if match[1] == 'neutralVariant' else match[1]
        return 'm3' + key + '_paletteKeyColor'
    return 'm3' + name


class SchemeBridgeTests(unittest.TestCase):
    def test_every_m3_property_is_fed_by_every_fixed_scheme(self):
        props = {p for p in colours_property_names() if p.startswith(('m3', 'term'))}
        for style, variant in STYLES:
            scheme = wysun_scheme.fixed_scheme(style, variant)
            self.assertEqual(set(scheme) - {'wallpaper_hash'}, {'name', 'flavour', 'mode', 'variant', 'colours'})
            fed = {mapped(k) for k in scheme['colours']}
            self.assertEqual(sorted(props - fed), [], (style, variant))
            for value in scheme['colours'].values():
                self.assertRegex(value, r'^[0-9a-fA-F]{6}$')

    def test_colours_reads_the_single_scheme_file(self):
        source = (SHELL / 'services/Colours.qml').read_text()
        self.assertIn('${Paths.state}/scheme.json', source)
        self.assertIn('propertyKey(name)', source)
        self.assertEqual(theme_core.scheme_path(Path('/x')).as_posix(), '/x/.local/state/wysun/scheme.json')

    def test_scheme_changes_never_call_the_original_project_cli(self):
        for rel in ('services/Colours.qml', 'modules/launcher/services/M3Variants.qml', 'modules/launcher/services/Schemes.qml'):
            text = (SHELL / rel).read_text()
            self.assertNotIn('cae' + 'lestia', ' '.join(re.findall(r'execDetached\(\[[^\]]*\]', text)).lower(), rel)

    def test_current_reports_name_flavour_variant(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home + '/c', XDG_STATE_HOME=home + '/s')
            for key in ('WYSUN_THEME', 'ORBIT_THEME'):
                env.pop(key, None)
            out = subprocess.run([sys.executable, str(SHELL / 'wysun/backend.py'), 'current'], env=env,
                                 capture_output=True, text=True, check=True).stdout.split()
            self.assertEqual(len(out), 3)

    def test_wallpaper_bridge_reads_environment_json_by_monitor(self):
        qml = (SHELL / 'wysun/WysunBridge.qml').read_text()
        self.assertIn("orbit/environment.json", qml)
        wall = (SHELL / 'services/Wallpapers.qml').read_text()
        self.assertIn('wysunWallpaper.monitors?.[name]?.path', wall)
        self.assertIn('"wysun", "wallpaper", "set"', wall)


class DunstTests(unittest.TestCase):
    def run_dnd(self, state_home, answers):
        calls = []
        def fake(argv):
            calls.append(argv); return answers.pop(0)
        with patch.dict(os.environ, {'XDG_STATE_HOME': state_home}), patch.object(backend, 'run', fake), \
                patch.object(sys, 'argv', ['backend', 'dnd']):
            import io, contextlib
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                backend.main()
        return calls, json.loads(out.getvalue())

    def test_dnd_toggles_the_single_dunst(self):
        with tempfile.TemporaryDirectory() as state:
            calls, result = self.run_dnd(state, ['', 'true\n'])
            self.assertEqual(calls, [['dunstctl', 'set-paused', 'toggle'], ['dunstctl', 'is-paused']])
            self.assertEqual(result, {'paused': True})

    def test_dnd_yields_to_recorder_concentration(self):
        with tempfile.TemporaryDirectory() as state:
            Path(state, 'loomrec').mkdir()
            Path(state, 'loomrec/concentration.json').write_text('{}')
            with self.assertRaises(RuntimeError):
                self.run_dnd(state, [])

    def test_wysun_never_owns_the_notification_bus(self):
        for path in SHELL.rglob('*.qml'):
            if 'plugin' in path.relative_to(SHELL).parts:
                continue
            self.assertNotIn('NotificationServer', path.read_text(), path)
        notifs = (SHELL / 'services/Notifs.qml').read_text()
        self.assertIn('shouldShowPopup(): bool { return false; }', notifs)
        self.assertIn('readonly property list<NotifData> popups: []', notifs)
        self.assertFalse(list(SHELL.glob('plugin/**/*notificationserver*')))


class DispatcherTests(unittest.TestCase):
    def dispatch(self, *args):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp, 'shell'); (config / 'wysun').mkdir(parents=True)
            (config / 'UPSTREAM.json').write_text('{}')
            runtime = config / 'wysun/runtime.sh'
            runtime.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n'); runtime.chmod(0o755)
            env = dict(os.environ, WYSUN_SHELL_CONFIG=str(config))
            result = subprocess.run([str(ROOT / 'bin/wysun-shell'), *args], env=env, capture_output=True, text=True)
        return result.returncode, result.stdout.split(), result.stderr

    def test_launcher_and_menu_map_to_ipc(self):
        self.assertEqual(self.dispatch('launcher')[:2], (0, ['ipc', 'call', 'wysunShell', 'toggle', 'launcher']))
        self.assertEqual(self.dispatch('menu')[1], ['ipc', 'call', 'wysunShell', 'toggle', 'menu'])
        self.assertEqual(self.dispatch('reload-preferences')[1], ['ipc', 'call', 'wysunShell', 'reloadPreferences'])
        self.assertEqual(self.dispatch('open', 'notifications')[1], ['ipc', 'call', 'wysunShell', 'open', 'notifications'])

    def test_unknown_surface_is_rejected(self):
        code, out, err = self.dispatch('toggle', 'rm')
        self.assertEqual(code, 2); self.assertEqual(out, [])

    def test_every_dispatched_surface_exists_in_bridge(self):
        qml = (SHELL / 'wysun/WysunBridge.qml').read_text()
        script = (ROOT / 'bin/wysun-shell').read_text()
        names = re.search(r'test\|([\w|]+)\) ;;', script)[1].split('|') + ['test']
        for name in set(names):
            self.assertRegex(qml, rf'\b{name}:')

    def test_hyprland_shell_bindings_use_dispatcher_commands(self):
        lua = (ROOT / 'config/.config/wysun/hyprland.lua').read_text()
        for sub in re.findall(r'wysun shell (\S+?)"', lua):
            self.assertIn(sub, ('menu', 'launcher', 'reload-preferences', 'windows', 'session', 'close', 'status'))


if __name__ == '__main__':
    unittest.main()
