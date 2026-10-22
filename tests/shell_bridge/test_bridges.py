"""Wysun bridge contracts: scheme/Colours keys, shell-owned notifications, dispatcher. Synthetic data only."""
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

ROOT = Path(__file__).resolve().parents[2]
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


class NotificationOwnershipTests(unittest.TestCase):
    """The shell is the only notification server: no dunst anywhere, Do Not Disturb lives in the shell."""

    def test_shell_owns_the_notification_bus(self):
        notifs = (SHELL / 'services/Notifs.qml').read_text()
        self.assertIn('NotificationServer', notifs)
        self.assertIn('toggleDnd', notifs)
        self.assertIn('target: "notifs"', notifs)
        servers = [p for p in SHELL.rglob('*.qml') if 'plugin' not in p.relative_to(SHELL).parts
                   and 'NotificationServer {' in p.read_text()]
        self.assertEqual(servers, [SHELL / 'services/Notifs.qml'])

    def test_no_dunst_is_started_or_called(self):
        root = SHELL.parents[1]
        for relative in ('bin/wysun-session-services', 'apps/shell/wysun/backend.py', 'apps/wysun/theme_runtime.py',
                         'apps/capture/loomrec/integration.py', 'config/.config/wysun/hyprland.lua'):
            self.assertNotIn('dunst', (root / relative).read_text().lower(), relative)

    def test_dnd_command_reaches_the_shell_ipc(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp, 'shell'); (config / 'wysun').mkdir(parents=True)
            runtime = config / 'wysun/runtime.sh'
            runtime.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n'); runtime.chmod(0o755)
            env = dict(os.environ, WYSUN_SHELL_CONFIG=str(config))
            for action, expected in (('on', ['ipc', 'call', 'notifs', 'setDnd', 'true']), ('off', ['ipc', 'call', 'notifs', 'setDnd', 'false']),
                                     ('toggle', ['ipc', 'call', 'notifs', 'toggleDnd']), ('status', ['ipc', 'call', 'notifs', 'status'])):
                out = subprocess.run([str(SHELL.parents[1] / 'bin/wysun-shell'), 'dnd', action], env=env, capture_output=True, text=True)
                self.assertEqual(out.stdout.split(), expected, action)


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

    def test_session_toggle_repeats(self):
        for _ in range(3):
            self.assertEqual(self.dispatch('session')[:2],
                             (0, ['ipc', 'call', 'wysunShell', 'toggle', 'session']))

    def test_search_and_brightness_reach_the_shell_ipc(self):
        self.assertEqual(self.dispatch('search', '>clip')[1], ['ipc', 'call', 'wysunShell', 'search', '>clip'])
        self.assertEqual(self.dispatch('brightness', 'up')[1], ['ipc', 'call', 'wysunShell', 'brightness', 'up'])

    def test_media_key_helper_covers_every_bound_key(self):
        helper = (ROOT / 'bin/wysun-control').read_text()
        lua = (ROOT / 'config/.config/wysun/hyprland.lua').read_text()
        for action in re.findall(r'wysun-control (\S+?)"', lua):
            self.assertIn(f'{action})', helper, action)
        for key in ('XF86AudioMicMute', 'XF86MonBrightnessUp', 'XF86AudioRaiseVolume'):
            self.assertIn(f'"{key}"', lua)

    def test_unknown_surface_is_rejected(self):
        code, out, err = self.dispatch('toggle', 'rm')
        self.assertEqual(code, 2); self.assertEqual(out, [])

    def test_every_dispatched_surface_exists_in_bridge(self):
        qml = (SHELL / 'wysun/WysunBridge.qml').read_text()
        script = (ROOT / 'bin/wysun-shell').read_text()
        names = re.search(r'test\|([\w|]+)\) ;;', script)[1].split('|') + ['test']
        for name in set(names):
            if name in ('processes', 'colors'):
                self.assertIn(f'if (kind === "{name}")', qml)
                self.assertIn(f'return {name}.open(toggle)', qml)
            else:
                self.assertRegex(qml, rf'\b{name}:')

    def test_hyprland_shell_bindings_use_dispatcher_commands(self):
        lua = (ROOT / 'config/.config/wysun/hyprland.lua').read_text()
        for sub in re.findall(r'wysun shell (\S+?)"', lua):
            self.assertIn(sub, ('menu', 'launcher', 'reload-preferences', 'windows', 'session', 'overview', 'wallpapers', 'close', 'status'))


if __name__ == '__main__':
    unittest.main()
