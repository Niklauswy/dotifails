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
sys.path.insert(0, str(ROOT / 'apps/python'))
from wysun_core import theme  # noqa: E402
from wysun_services import scheme as wysun_scheme  # noqa: E402
from PIL import Image  # noqa: E402


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
    def test_every_m3_property_is_fed_by_the_generated_scheme(self):
        props = {p for p in colours_property_names() if p.startswith(('m3', 'term'))}
        with tempfile.TemporaryDirectory() as folder:
            wallpaper = Path(folder, 'synthetic.png')
            Image.new('RGB', (64, 48), (25, 82, 224)).save(wallpaper)
            for mode in ('light', 'dark'):
                scheme = wysun_scheme.generate_dynamic(wallpaper, mode)
                self.assertEqual(set(scheme), {'name', 'flavour', 'mode', 'variant', 'colours', 'wallpaper_hash'})
                fed = {mapped(k) for k in scheme['colours']}
                self.assertEqual(sorted(props - fed), [], mode)
                for value in scheme['colours'].values():
                    self.assertRegex(value, r'^[0-9a-fA-F]{6}$')

    def test_colours_reads_the_single_scheme_file(self):
        source = (SHELL / 'services/Colours.qml').read_text()
        self.assertIn('${Paths.state}/scheme.json', source)
        self.assertIn('propertyKey(name)', source)
        self.assertIn('["wysun", "scheme", "set", mode]', source, 'the mode goes through the single producer')
        self.assertIn('wysun/theme.json', source, 'the page shows the stored mode, not only the one the wallpaper gave')
        self.assertEqual(theme.scheme_path(Path('/x')).as_posix(), '/x/.local/state/wysun/scheme.json')

    def test_scheme_changes_never_call_the_original_project_cli(self):
        for rel in ('services/Colours.qml', 'modules/nexus/pages/WallpaperAndStyle.qml', 'wysun/backend.py'):
            text = (SHELL / rel).read_text()
            self.assertNotIn('cae' + 'lestia', ' '.join(re.findall(r'execDetached\(\[[^\]]*\]', text)).lower(), rel)

    def test_colours_has_no_dead_hypr_rules_hook(self):
        hits = [str(p) for p in SHELL.rglob('*.qml') if 'reloadHyprRules' in p.read_text() or 'cooldownPending' in p.read_text()]
        self.assertEqual(hits, [])

    def test_no_fixed_theme_is_left_in_the_shell(self):
        for rel in ('modules/launcher/services/M3Variants.qml', 'modules/launcher/services/Schemes.qml',
                    'modules/nexus/pages/wallandstyle'):
            self.assertFalse((SHELL / rel).exists(), rel)
        page = (SHELL / 'modules/nexus/pages/WallpaperAndStyle.qml').read_text()
        for gone in ('wallpaperEnabled', 'openSubPage', 'Space Black', 'Tokyo', 'Severance', 'Fluent'):
            self.assertNotIn(gone, page)
        for mode in ('"auto"', '"light"', '"dark"'):
            self.assertIn('mode: ' + mode, page)
        self.assertIn('wysun", "shell", "wallpapers"', page, 'the carousel is the only wallpaper picker')

    def test_the_carousel_can_shuffle_and_add_an_image(self):
        picker = (SHELL / 'modules/wallpaperpicker/WallpaperPicker.qml').read_text()
        for needed in ('function random()', 'function add()', 'FileDialog', 'Qt.Key_R', 'icon: "shuffle"', 'icon: "add_photo_alternate"'):
            self.assertIn(needed, picker)

    def test_wallpaper_bridge_reads_environment_json_by_monitor(self):
        qml = (SHELL / 'wysun/WysunBridge.qml').read_text()
        self.assertIn("wysun/environment.json", qml)
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
        for relative in ('bin/wysun-session-services', 'apps/shell/wysun/backend.py', 'apps/python/wysun_settings/theme_runtime.py',
                         'config/.config/wysun/hyprland.lua'):
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
    def dispatch(self, *args, answer=None):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp, 'shell'); (config / 'wysun').mkdir(parents=True)
            (config / 'UPSTREAM.json').write_text('{}')
            runtime = config / 'wysun/runtime.sh'
            # The fake runtime echoes its arguments, or answers like the shell's IPC would.
            body = f'echo {answer}' if answer else 'printf "%s\\n" "$@"'
            runtime.write_text('#!/bin/sh\n' + body + '\n'); runtime.chmod(0o755)
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

    def surfaces(self):
        qml = (SHELL / 'wysun/WysunBridge.qml').read_text()
        body = re.search(r'property var surfaces: \((\{.*?\})\)', qml, re.S)[1]
        return re.findall(r'(\w+):', body)

    def test_unknown_surface_is_rejected_by_the_shell(self):
        for args in (('toggle', 'rm'), ('rm',)):
            code, out, err = self.dispatch(*args, answer='false')
            self.assertEqual(code, 2, args)
            self.assertIn('superficie desconocida', err)

    def test_every_surface_toggles_in_short_and_long_form(self):
        names = self.surfaces()
        for name in ('colors', 'processes', 'launcher', 'emoji', 'session', 'dashboard'):
            self.assertIn(name, names)
        self.assertNotIn('test', names)
        for name in names:
            for args in ((name,), ('toggle', name)):
                self.assertEqual(self.dispatch(*args)[:2], (0, ['ipc', 'call', 'wysunShell', 'toggle', name]), args)
            self.assertEqual(self.dispatch('open', name)[1], ['ipc', 'call', 'wysunShell', 'open', name])

    def test_the_launcher_script_does_not_repeat_the_surface_list(self):
        script = (ROOT / 'bin/wysun-shell').read_text()
        for name in self.surfaces():
            if name not in ('launcher', 'session'):   # launcher/session also name other words of the script
                self.assertNotRegex(script, rf'\b{name}\b', name)

    def test_start_and_quickshell_commands_still_reach_the_runtime(self):
        self.assertEqual(self.dispatch()[:2], (0, ['--no-duplicate']))
        self.assertEqual(self.dispatch('-d')[1], ['--no-duplicate', '-d'])
        self.assertEqual(self.dispatch('ipc', 'call', 'editor', 'open', '/x')[1], ['ipc', 'call', 'editor', 'open', '/x'])
        self.assertEqual(self.dispatch('surfaces')[1], ['ipc', 'call', 'wysunShell', 'surfaces'])

    def test_bridge_routes_own_modules_and_lists_its_surfaces(self):
        qml = (SHELL / 'wysun/WysunBridge.qml').read_text()
        for name in ('processes', 'colors'):
            self.assertIn(f'if (kind === "{name}")', qml)
            self.assertIn(f'return {name}.open(toggle)', qml)
        self.assertIn('function surfaces(): string', qml)

    def test_hyprland_shell_bindings_use_dispatcher_commands(self):
        lua = (ROOT / 'config/.config/wysun/hyprland.lua').read_text()
        for sub in re.findall(r'wysun shell (\S+?)"', lua):
            self.assertIn(sub, ('menu', 'launcher', 'reload-preferences', 'windows', 'session', 'overview', 'wallpapers', 'close', 'status'))


if __name__ == '__main__':
    unittest.main()
