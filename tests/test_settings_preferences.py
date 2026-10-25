"""shell.json migration, single-authority preferences and exact undo (temporary HOME)."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
import settings_data  # noqa: E402
import theme_core  # noqa: E402
from environment_settings import EnvironmentSettings  # noqa: E402
from settings_data import PreferenceBackup, ShellPreferences  # noqa: E402

MONITORS = [dict(name='DP-1', width=64, height=48, x=0, y=0, scale=1, refreshRate=60,
                 availableModes=['64x48@60.00Hz'], focused=True)]
LEGACY = {'height': 40, 'opacity': 70, 'background': '#101118', 'left': ['orbit', 'workspaces'],
          'center': ['title'], 'right': ['date', 'tray'], 'monitors': {'DP-1': True, 'eDP-1': False},
          'tray_monitor': 'DP-1', 'future_key': {'keep': True}}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None


class PreferenceCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.home = Path(self.folder.name)
        self.orbit = self.home / '.config/orbit'
        self.orbit.mkdir(parents=True)
        self.calls = []
        self.shell_alive = True

        def runner(args):
            self.calls.append(list(args))
            if list(args[:3]) == ['hyprctl', '-j', 'monitors']:
                return json.dumps(MONITORS)
            if list(args[:3]) == ['wysun', 'shell', 'reload-preferences'] and not self.shell_alive:
                raise RuntimeError('quickshell no está en ejecución')
            return 'ok'
        self.env = EnvironmentSettings(self.home, runner=runner)
        self.patch = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.home / '.config'),
                                             'XDG_STATE_HOME': str(self.home / '.local/state')})
        self.patch.start()
        theme_core.invalidate()

    def tearDown(self):
        self.patch.stop()
        theme_core.invalidate()
        self.folder.cleanup()

    def write(self, name, text):
        path = self.orbit / name
        path.write_bytes(text.encode() if isinstance(text, str) else text)
        return path

    def state(self):
        names = ('shell.json', 'hypr-bar.json', 'appearance.json', 'environment.json', 'theme.json')
        return {n: digest(self.orbit / n) for n in names} | {'scheme.json': digest(theme_core.scheme_path(self.home))}


class MigrationTests(PreferenceCase):
    def test_migrates_once_keeps_legacy_bytes_and_is_idempotent(self):
        legacy = self.write('hypr-bar.json', json.dumps(LEGACY, indent=1) + '\r\n')
        before = digest(legacy)
        shell = ShellPreferences(self.home)
        self.assertTrue(shell.migrate())
        written = digest(self.orbit / 'shell.json')
        values = json.loads((self.orbit / 'shell.json').read_text())
        self.assertEqual((values['schema_version'], values['anchor']), (1, 'left'))
        self.assertEqual(values['monitors'], {'DP-1': True, 'eDP-1': False})
        self.assertEqual(values['tray_monitor'], 'DP-1')
        self.assertEqual(values['rail_modules'], {'left': ['orbit', 'workspaces'], 'center': ['title'], 'right': ['date', 'tray']})
        self.assertNotIn('height', values)
        self.assertEqual(digest(legacy), before)
        self.assertEqual(oct((self.orbit / 'shell.json').stat().st_mode & 0o777), '0o600')
        self.assertFalse(ShellPreferences(self.home).migrate())  # second run: no-op
        self.assertEqual(digest(self.orbit / 'shell.json'), written)
        self.assertEqual(shell.migration_backup.before['hypr-bar.json'], (self.orbit / 'hypr-bar.json').read_bytes())
        # Undo of the migration removes shell.json and leaves hypr-bar.json exact.
        shell.migration_backup.restore()
        self.assertFalse((self.orbit / 'shell.json').exists())
        self.assertEqual(digest(legacy), before)

    def test_new_profile_gets_defaults_without_files_or_legacy(self):
        values = ShellPreferences(self.home).values()
        self.assertEqual(values['rail_enabled'], True)
        self.assertEqual(values['monitors'], {})
        self.assertFalse((self.orbit / 'shell.json').exists())

    def test_disabled_tray_and_all_off_legacy_never_leave_the_desktop_empty(self):
        self.write('hypr-bar.json', json.dumps({'monitors': {'A': False, 'B': False}, 'tray_monitor': 'A'}))
        values = ShellPreferences(self.home).values()
        self.assertEqual((values['monitors'], values['tray_monitor']), ({}, 'A'))
        (self.orbit / 'shell.json').unlink()
        self.write('hypr-bar.json', json.dumps({'monitors': {'A': False, 'B': True}, 'tray_monitor': 'A'}))
        self.assertEqual(ShellPreferences(self.home).values()['tray_monitor'], '')

    def test_invalid_legacy_json_is_reported_and_nothing_is_created(self):
        legacy = self.write('hypr-bar.json', '{"height": ')
        before = digest(legacy)
        with self.assertRaisesRegex(ValueError, 'JSON inválido'):
            ShellPreferences(self.home).values()
        with self.assertRaises(ValueError):
            self.env.apply_shell({'low_power': True})
        self.assertFalse((self.orbit / 'shell.json').exists())
        self.assertEqual(digest(legacy), before)

    def test_unknown_version_blocks_reads_and_writes_without_touching_the_file(self):
        shell = self.write('shell.json', json.dumps({'schema_version': 2, 'future': 1}))
        before = digest(shell)
        for action in (ShellPreferences(self.home).values, lambda: self.env.apply_shell({'low_power': True}),
                       lambda: self.env.apply_panels({'low_power': True}, {'opacity': 80, 'reduced_motion': False})):
            with self.assertRaisesRegex(ValueError, 'Versión'):
                action()
        self.assertEqual(digest(shell), before)
        self.assertFalse((self.orbit / 'appearance.json').exists())

    def test_write_failure_during_migration_leaves_no_partial_state(self):
        legacy = self.write('hypr-bar.json', json.dumps(LEGACY))
        before = digest(legacy)
        real = settings_data.atomic_write

        def failing(path, text, mode=None):
            if Path(path).name == 'shell.json':
                raise OSError(28, 'No space left on device')
            return real(path, text, mode)
        with patch.object(settings_data, 'atomic_write', failing):
            with self.assertRaises(OSError):
                ShellPreferences(self.home).migrate()
        self.assertFalse((self.orbit / 'shell.json').exists())
        self.assertEqual(digest(legacy), before)
        self.assertTrue(ShellPreferences(self.home).migrate())  # recovers on the next attempt


class SaveAndUndoTests(PreferenceCase):
    def test_panels_save_keeps_unknown_keys_and_undo_is_byte_for_byte(self):
        self.write('hypr-bar.json', json.dumps(LEGACY))
        appearance = self.write('appearance.json', '{"opacity": 80,\r\n "reduced_motion": false, "futuro": "ñ"}\r\n')
        ShellPreferences(self.home).migrate()
        shell = self.write('shell.json', json.dumps(dict(json.loads((self.orbit / 'shell.json').read_text()), extra={'x': 1}), indent=4) + '\n')
        before = self.state()
        backup = self.env.apply_panels({'frame_enabled': False, 'low_power': True, 'monitors': {'DP-1': True, 'eDP-1': True}},
                                       {'opacity': 90, 'reduced_motion': True},
                                       self.env.shell_values(), self.env.appearance_values())
        saved = json.loads(shell.read_text())
        self.assertEqual((saved['frame_enabled'], saved['low_power'], saved['extra']), (False, True, {'x': 1}))
        kept = json.loads(appearance.read_text())
        self.assertEqual((kept['opacity'], kept['reduced_motion'], kept['futuro']), (90, True, 'ñ'))
        self.assertEqual(self.state()['hypr-bar.json'], before['hypr-bar.json'])
        self.env.undo_preferences(backup)
        self.assertEqual(self.state(), before)
        self.assertEqual(appearance.read_bytes(), b'{"opacity": 80,\r\n "reduced_motion": false, "futuro": "\xc3\xb1"}\r\n')

    def test_undo_refuses_to_discard_another_writers_change(self):
        self.write('appearance.json', '{"opacity": 80}\n')
        backup = self.env.apply_appearance({'opacity': 70, 'reduced_motion': False})
        (self.orbit / 'appearance.json').write_text('{"opacity": 99}\n')
        with self.assertRaisesRegex(ValueError, 'otra ventana'):
            self.env.undo_preferences(backup)
        self.assertEqual(json.loads((self.orbit / 'appearance.json').read_text())['opacity'], 99)

    def test_sealed_receipt_can_be_reopened_for_undo_after_restart(self):
        self.write('appearance.json', '{"opacity": 80}\n')
        before = self.state()
        backup = self.env.apply_appearance({'opacity': 70, 'reduced_motion': True})
        paths = self.env.preference_paths()
        reopened = PreferenceBackup.open(self.home, paths, backup.folder)
        reopened.restore()
        self.assertEqual(self.state(), before)
        with self.assertRaises(ValueError):  # a folder outside Settings' backups is refused
            PreferenceBackup.open(self.home, paths, self.orbit)

    def test_stale_form_and_invalid_values_are_rejected_before_writing(self):
        self.write('hypr-bar.json', json.dumps(LEGACY))
        baseline = self.env.shell_values()
        self.env.apply_shell({'low_power': True}, baseline)
        before = self.state()
        for bad in ({'rail_enabled': 'yes'}, {'anchor': 'top'}, {'monitors': {'DP-1': 1}},
                    {'monitors': {'A': False, 'B': False}}, {'tray_monitor': 'eDP-1'}, {'rail_modules': {'up': []}}):
            with self.assertRaises(ValueError, msg=str(bad)):
                self.env.apply_shell(bad)
        with self.assertRaisesRegex(ValueError, 'otra ventana'):
            self.env.apply_shell({'low_power': False}, baseline)  # baseline predates the save above
        self.assertEqual(self.state(), before)

    def test_write_failure_rolls_back_every_file_of_the_combined_save(self):
        self.write('hypr-bar.json', json.dumps(LEGACY))
        appearance = self.write('appearance.json', '{"opacity": 80, "k": 1}\n')
        ShellPreferences(self.home).migrate()
        before = self.state()
        real = settings_data.atomic_write

        def failing(path, text, mode=None):
            if Path(path).name == 'appearance.json' and 'opacity": 90' in text:
                raise OSError(28, 'No space left on device')
            return real(path, text, mode)
        with patch.object(settings_data, 'atomic_write', failing), patch('environment_settings.atomic_write', failing):
            with self.assertRaises(OSError):
                self.env.apply_panels({'low_power': True}, {'opacity': 90, 'reduced_motion': False})
        self.assertEqual(self.state(), before)  # shell.json written first, then rolled back
        self.assertEqual(appearance.read_text(), '{"opacity": 80, "k": 1}\n')

    def test_missing_shell_process_does_not_fail_the_save(self):
        self.shell_alive = False
        backup = self.env.apply_shell({'low_power': True})
        self.assertIn('quickshell', backup.warning)
        self.assertTrue(json.loads((self.orbit / 'shell.json').read_text())['low_power'])


class ColourPreferenceTests(PreferenceCase):
    def setUp(self):
        super().setUp()
        self.red = self.home / 'red.png'
        self.blue = self.home / 'blue.png'
        Image.new('RGB', (64, 48), (225, 36, 72)).save(self.red)
        Image.new('RGB', (64, 48), (25, 82, 224)).save(self.blue)

    def test_new_profile_reads_as_automatic_and_the_old_formats_are_read(self):
        self.assertEqual(self.env.colour_values(), {'mode': 'auto'})
        self.write('theme.json', '{"mode":"light","privado":[1,2]}')
        self.assertEqual(self.env.colour_values(), {'mode': 'light'})
        self.write('theme.json', '{"style":"fluent","variant":"light","privado":[1,2]}')
        self.assertEqual(self.env.colour_values(), {'mode': 'auto'}, 'a retired fixed theme reads as automatic')

    def test_mode_save_with_wallpaper_and_exact_undo(self):
        theme = self.write('theme.json', '{"style":"fluent","variant":"dark","privado":{"a":[1,2]}}\r\n')
        environment = self.write('environment.json', json.dumps({'wallpaper': {'default': str(self.red), 'mode': 'fit', 'folders': ['/x']},
                                                                  'other': {'k': 1}}, indent=3) + '\n')
        self.env.reload()
        before = self.state()
        baseline = self.env.colour_values()
        result = self.env.apply_colour(dict(mode='light'), str(self.blue), baseline)
        theme_json = json.loads(theme.read_text())
        self.assertEqual(theme_json, {'privado': {'a': [1, 2]}, 'mode': 'light'})
        saved = json.loads(environment.read_text())
        self.assertEqual((saved['wallpaper']['default'], saved['wallpaper']['mode'], saved['wallpaper']['folders'], saved['other']),
                         (str(self.blue), 'fit', ['/x'], {'k': 1}))
        scheme = json.loads(theme_core.scheme_path(self.home).read_text())
        self.assertEqual((scheme['name'], scheme['mode']), ('dynamic', 'light'))
        self.assertEqual(set(scheme), {'name', 'flavour', 'mode', 'variant', 'colours', 'wallpaper_hash'})
        self.assertEqual(self.env.colour_values()['mode'], 'light')
        self.env.undo_preferences(result['backup'])
        self.assertEqual(self.state(), before)

    def test_automatic_mode_follows_the_wallpaper_and_an_explicit_one_does_not(self):
        bright = self.home / 'bright.png'
        Image.new('RGB', (64, 48), (245, 240, 225)).save(bright)
        self.write('environment.json', json.dumps({'wallpaper': {'default': str(bright)}}))
        self.env.reload()
        self.env.apply_colour(dict(mode='auto'), None, self.env.colour_values())
        self.assertEqual(json.loads(theme_core.scheme_path(self.home).read_text())['mode'], 'light')
        self.env.apply_colour(dict(mode='dark'), None, self.env.colour_values())
        self.assertEqual(json.loads(theme_core.scheme_path(self.home).read_text())['mode'], 'dark')
        self.assertEqual(json.loads((self.orbit / 'theme.json').read_text()), {'mode': 'dark'})

    def test_invalid_theme_json_or_mode_blocks_the_save(self):
        theme = self.write('theme.json', '{oops')
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'JSON inválido'):
            self.env.apply_colour(dict(mode='dark'), None)
        theme.write_text('{}')
        for bad in ('nope', 'sepia', ''):
            with self.assertRaises(ValueError):
                self.env.apply_colour(dict(mode=bad), None)
        with self.assertRaises(ValueError):
            self.env.apply_colour(dict(mode='dark'), None, dict(mode='light'))
        theme.write_text('{oops')
        self.assertEqual(self.state()['theme.json'], before['theme.json'])
        self.assertFalse(theme_core.scheme_path(self.home).exists())

    def test_unreadable_wallpaper_restores_environment_and_scheme(self):
        junk = self.home / 'not-image.png'
        junk.write_text('nope')
        environment = self.write('environment.json', json.dumps({'wallpaper': {'default': str(self.red)}, 'k': 2}))
        self.env.reload()
        before = self.state()
        base = self.env.colour_values()
        with self.assertRaises(Exception):
            self.env.apply_colour(dict(mode='dark'), str(junk), base)
        self.assertEqual(self.state(), before)
        self.assertEqual(json.loads(environment.read_text())['k'], 2)


if __name__ == '__main__':
    unittest.main()
