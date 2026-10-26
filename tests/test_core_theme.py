"""wysun_core.theme: the mode the user chose, the wallpaper's scheme and the tokens they give."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_core import theme  # noqa: E402

SCHEME = {'name': 'dynamic', 'flavour': 'tonalspot', 'mode': 'light', 'variant': 'tonalspot',
          'wallpaper_hash': 'a' * 64, 'colours': {'surface': 'abcdef', 'onSurface': '111111', 'primary': '334455'}}


class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        patcher = patch.dict(os.environ, {})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('WYSUN_THEME', None)
        theme.invalidate()
        self.addCleanup(theme.invalidate)

    def selection(self, text):
        path = theme.selection_path(self.home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        theme.invalidate()
        return path

    def test_paths_follow_the_injected_home(self):
        self.assertEqual(theme.selection_path(self.home), self.home / '.config/wysun/theme.json')
        self.assertEqual(theme.scheme_path(self.home), self.home / '.local/state/wysun/scheme.json')

    def test_old_or_broken_theme_file_reads_as_auto(self):
        self.assertEqual(theme.read_mode(self.home), 'auto')
        for text in ('{"style": "fluent", "variant": "tokyo"}', '{"id": "space-black"}', '[]', 'nope', '{"mode": "sepia"}'):
            self.selection(text)
            self.assertEqual(theme.read_mode(self.home), 'auto', text)

    def write_scheme(self, mode='light'):
        theme.write_scheme(dict(SCHEME, mode=mode), self.home)

    def test_active_scheme_is_the_wallpaper_scheme_when_it_exists(self):
        self.write_scheme('light')
        self.assertEqual(theme.active_scheme(self.home), {'mode': 'light', 'colours': SCHEME['colours']})

    def test_active_scheme_falls_back_to_the_base_palette_of_the_active_mode(self):
        self.selection('{"mode": "light"}')
        scheme = theme.active_scheme(self.home)
        self.assertEqual(scheme['mode'], 'light')
        self.assertEqual(scheme['colours'], theme.data()['palettes']['light']['scheme'])
        self.selection('{"mode": "auto"}')
        self.assertEqual(theme.active_scheme(self.home)['mode'], theme.DEFAULT_MODE)

    def test_active_scheme_ignores_a_broken_scheme_file(self):
        path = theme.scheme_path(self.home)
        path.parent.mkdir(parents=True)
        path.write_text('{"colours": 3')
        theme.invalidate()
        self.assertEqual(theme.active_scheme(self.home)['colours'], theme.data()['palettes'][theme.DEFAULT_MODE]['scheme'])

    def test_wysun_theme_forces_the_base_palette_over_the_scheme(self):
        self.write_scheme('light')
        scheme = theme.active_scheme(self.home, {'WYSUN_THEME': 'dark'})
        self.assertEqual(scheme, {'mode': 'dark', 'colours': theme.data()['palettes']['dark']['scheme']})

    def test_m3_roles_are_exposed_directly_for_both_base_palettes(self):
        for mode in ('light', 'dark'):
            values = theme.resolve(mode)
            base = theme.data()['palettes'][mode]['scheme']
            for role in ('primary', 'primaryContainer', 'secondaryContainer', 'onSecondaryContainer', 'tertiaryContainer',
                         'surfaceContainerLow', 'surfaceContainerHigh', 'outlineVariant', 'onSurface'):
                self.assertEqual(values['m3' + role], '#' + base[role].lower(), (mode, role))

    def test_m3_roles_cover_every_listed_role_and_nothing_else(self):
        roles = theme.m3_roles(theme.data()['palettes']['dark']['scheme'])
        self.assertEqual(set(roles), {'m3' + name for name in theme.MATERIAL_ROLE_NAMES})
        self.assertTrue(all(value.startswith('#') and len(value) == 7 and value == value.lower() for value in roles.values()))
        self.assertNotIn('m3term0', roles)
        self.assertEqual(theme.m3_roles({'primary': 'ABCDEF', 'junk': '000000'}), {'m3primary': '#abcdef'})

    def test_wallpaper_scheme_replaces_the_m3_roles_but_keeps_missing_ones_from_the_base(self):
        self.write_scheme('light')
        values = theme.resolve_active(self.home)
        self.assertEqual(values['m3primary'], '#334455')
        self.assertEqual(values['m3surface'], '#abcdef')
        self.assertEqual(values['m3tertiaryContainer'], '#' + theme.data()['palettes']['light']['scheme']['tertiaryContainer'].lower())

    def test_wysun_theme_override_keeps_the_base_m3_roles(self):
        self.write_scheme('light')
        values = theme.resolve_active(self.home, {'WYSUN_THEME': 'dark'})
        self.assertEqual(values['m3primary'], '#' + theme.data()['palettes']['dark']['scheme']['primary'].lower())

    def test_existing_tokens_keep_their_values(self):
        self.write_scheme('light')
        values = theme.resolve_active(self.home)
        self.assertEqual(values['accent'], '#334455')
        self.assertEqual(values['surface'], '#abcdef')

    def test_write_mode_keeps_other_keys_and_backs_up(self):
        path = self.selection('{"mode": "dark", "x": 1}')
        theme.write_mode('light', self.home)
        self.assertEqual(json.loads(path.read_text()), {'mode': 'light', 'x': 1})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(list((self.home / '.local/state/wysun/theme-backups').iterdir())), 1)
        self.assertEqual(theme.read_mode(self.home), 'light')

    def test_write_mode_replaces_a_broken_file_and_keeps_a_backup(self):
        for text in ('[]', 'nope'):
            path = self.selection(text)
            theme.write_mode('light', self.home)
            self.assertEqual(json.loads(path.read_text()), {'mode': 'light'})
        backups = sorted((self.home / '.local/state/wysun/theme-backups').iterdir())
        self.assertEqual([b.read_text() for b in backups], ['[]', 'nope'])
        with self.assertRaises(ValueError):
            theme.write_mode('sepia', self.home)

    def test_without_scheme_the_base_palette_of_the_mode_is_used(self):
        palettes = theme.data()['palettes']
        self.assertEqual(theme.active_mode(self.home), 'dark')
        self.assertEqual(theme.resolve_active(self.home)['canvas'], palettes['dark']['colors']['canvas'])
        theme.write_mode('light', self.home)
        self.assertEqual(theme.active_mode(self.home), 'light')
        self.assertEqual(theme.resolve_active(self.home)['canvas'], palettes['light']['colors']['canvas'])

    def test_scheme_mode_wins_and_roles_overlay(self):
        self.selection('{"mode": "dark"}')
        theme.write_scheme(SCHEME, self.home)
        self.assertEqual(theme.active_mode(self.home), 'light')
        values = theme.resolve_active(self.home)
        self.assertEqual((values['surface'], values['mode']), ('#abcdef', 'light'))

    def test_wysun_theme_overrides_and_skips_the_overlay(self):
        theme.write_scheme(SCHEME, self.home)
        environ = {'WYSUN_THEME': 'dark'}
        self.assertEqual(theme.active_mode(self.home, environ), 'dark')
        self.assertEqual(theme.resolve_active(self.home, environ)['canvas'], theme.data()['palettes']['dark']['colors']['canvas'])

    def test_invalid_scheme_is_ignored(self):
        path = theme.scheme_path(self.home)
        path.parent.mkdir(parents=True)
        for broken in (dict(SCHEME, colours={'surface': 'zzzzzz'}), dict(SCHEME, extra=1), 'text'):
            path.write_text(json.dumps(broken))
            theme.invalidate()
            self.assertIsNone(theme.read_scheme(self.home))
        with self.assertRaises(ValueError):
            theme.write_scheme(dict(SCHEME, mode='sepia'), self.home)

    def test_resolve_gives_shape_colours_and_metadata(self):
        values = theme.resolve('light')
        self.assertEqual(values['mode'], 'light')
        for key in ('rounding.medium', 'spacing.medium', 'font.family.sans', 'anim.durations.small', 'canvas', 'accent', 'external', 'wallpaper', 'translucent'):
            self.assertIn(key, values)
        with self.assertRaises(ValueError):
            theme.resolve('auto')

    def test_glass_belongs_to_dark_and_light_is_opaque(self):
        self.assertEqual((theme.resolve('dark')['material'], theme.resolve('dark')['translucent']), ('glass', True))
        self.assertEqual((theme.resolve('light')['material'], theme.resolve('light')['translucent']), ('pearl', False))

    def test_revision_changes_with_mode_and_scheme(self):
        first = theme.revision(self.home)
        theme.write_mode('light', self.home)
        second = theme.revision(self.home)
        theme.write_scheme(SCHEME, self.home)
        third = theme.revision(self.home)
        self.assertNotEqual(first, second)
        self.assertNotEqual(second, third)


if __name__ == '__main__':
    unittest.main()
