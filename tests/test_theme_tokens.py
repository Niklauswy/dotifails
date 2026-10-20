"""Token source of truth: identical copies, contrast, selection rules and migration."""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
import theme_core  # noqa: E402

COPIES = ['apps/capture/loomrec/ui/wysun_theme.json', 'apps/shell/wysun_theme.json']
VARIANTS = [('space-black', 'space-black'), ('space-black', 'tokyo'), ('space-black', 'severance'), ('fluent', 'light'), ('fluent', 'dark')]
# (foreground, background, minimum WCAG ratio): text 4.5:1, UI components and focus 3:1.
CONTRAST = [('text', 'canvas', 4.5), ('text', 'surface', 4.5), ('text', 'well', 4.5), ('muted', 'surface', 4.5), ('muted', 'canvas', 4.5), ('subtle', 'surface', 4.5),
            ('control_text', 'fill', 4.5), ('text', 'selection', 4.5), ('selection_text', 'selection', 4.5), ('text', 'hover', 4.5), ('text', 'menu', 4.5),
            ('text', 'menu_selected', 4.5), ('on_accent', 'accent', 4.5), ('on_accent', 'accent_hover', 4.5), ('danger', 'surface', 4.5), ('success', 'surface', 4.5),
            ('warning', 'surface', 4.5), ('on_tooltip', 'tooltip', 4.5), ('accent', 'surface', 3), ('accent', 'canvas', 3), ('focus', 'surface', 3),
            ('focus_input', 'well', 3), ('check_line', 'surface', 3), ('glyph', 'surface', 3)]


def channels(value):
    text = value.lstrip('#')
    alpha = int(text[6:8], 16) / 255 if len(text) == 8 else 1
    return [int(text[i:i + 2], 16) / 255 for i in (0, 2, 4)], alpha


def over(foreground, background):
    (fg, alpha), (bg, _) = channels(foreground), channels(background)
    return [fg[i] * alpha + bg[i] * (1 - alpha) for i in range(3)]


def luminance(rgb):
    lin = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
    return .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2]


def ratio(foreground, background, base):
    backdrop = over(background, base)
    shown = over(foreground, '#' + ''.join(f'{round(c * 255):02x}' for c in backdrop))
    high, low = sorted([luminance(shown), luminance(backdrop)], reverse=True)
    return (high + .05) / (low + .05)


class TokenSourceTests(unittest.TestCase):
    def test_runtime_copies_are_byte_identical(self):
        source = (ROOT / 'apps/wysun/wysun_theme.json').read_bytes()
        for copy in COPIES:
            self.assertEqual((ROOT / copy).read_bytes(), source, copy)
        self.assertEqual((ROOT / 'apps/capture/loomrec/ui/theme_core.py').read_bytes(), (ROOT / 'apps/wysun/theme_core.py').read_bytes())

    def test_two_styles_five_variants_with_matching_structure(self):
        styles = theme_core.styles()
        self.assertEqual({k: list(v['variants']) for k, v in styles.items()}, {'space-black': ['space-black', 'tokyo', 'severance'], 'fluent': ['light', 'dark']})
        tokens = {pair: set(theme_core.resolve(*pair)) for pair in VARIANTS}
        self.assertEqual(len({frozenset(v) for v in tokens.values()}), 1, 'every variant defines the same tokens')
        for required in ('canvas', 'surface', 'well', 'line', 'text', 'muted', 'accent', 'accent_hover', 'selection', 'disabled', 'danger', 'success', 'warning', 'scrim',
                         'radius_s', 'radius_m', 'radius_l', 'motion_fast', 'font_family'):
            self.assertIn(required, tokens[VARIANTS[0]])

    IDENTITY = ('name', 'description', 'wallpaper', 'variant', 'external', 'key')

    def test_space_black_variants_share_structure_and_only_differ_by_palette(self):
        base = theme_core.resolve('space-black', 'space-black')
        for variant in ('tokyo', 'severance'):
            other = theme_core.resolve('space-black', variant)
            for key, value in base.items():
                if key in self.IDENTITY or isinstance(value, str) and value.startswith('#'):
                    continue
                self.assertEqual(other[key], value, (variant, key))

    def test_fluent_light_matches_recorder_look_and_dark_shares_its_structure(self):
        light, dark = theme_core.resolve('fluent', 'light'), theme_core.resolve('fluent', 'dark')
        self.assertEqual((light['accent'], light['canvas'], light['surface']), ('#2165D5', '#F3F6FB', '#FCFDFF'))
        self.assertEqual((light['radius_s'], light['radius_m'], light['radius_l'], light['motion_fast']), (8, 12, 20, 150))
        self.assertEqual(light['font_family'][:2], ['Segoe UI Variable', 'Inter'])
        for key in light:
            if not (isinstance(light[key], str) and light[key].startswith('#')) and key not in self.IDENTITY + ('material',):  # pearl/mica: only the name of the palette's surface
                self.assertEqual(dark[key], light[key], key)

    def test_wcag_contrast_in_every_variant(self):
        failures = []
        for pair in VARIANTS:
            colors = theme_core.resolve(*pair)
            base = colors['material_mid'] if pair[0] == 'space-black' else colors['canvas']
            for foreground, background, minimum in CONTRAST:
                value = ratio(colors[foreground], colors[background], base)
                if value < minimum:
                    failures.append(f'{pair} {foreground}/{background} {value:.2f} < {minimum}')
        self.assertEqual(failures, [])


class SelectionTests(unittest.TestCase):
    def test_parse_aliases_and_both_formats(self):
        for value, expected in (('Tokyo', ('space-black', 'tokyo')), ('azul', ('space-black', 'severance')), ('morado', ('space-black', 'tokyo')), ('Severance', ('space-black', 'severance')),
                                ('fluent:dark', ('fluent', 'dark')), ('fluent/light', ('fluent', 'light')), ('dark', ('fluent', 'dark')), ('fluent', ('fluent', 'light'))):
            self.assertEqual(theme_core.parse(value), expected, value)
        self.assertIsNone(theme_core.parse('nope'))
        self.assertEqual(theme_core.from_object({'id': 'tokyo'}), ('space-black', 'tokyo', True))
        self.assertEqual(theme_core.from_object({'style': 'fluent', 'variant': 'dark'}), ('fluent', 'dark', False))

    def test_invalid_variant_falls_back_to_the_style_default(self):
        self.assertEqual(theme_core.normalize('fluent', 'tokyo'), ('fluent', 'light'))
        self.assertEqual(theme_core.normalize('space-black', 'nope'), ('space-black', 'space-black'))
        self.assertEqual(theme_core.from_object({'style': 'fluent', 'variant': 'nope'}), ('fluent', 'light', False))

    def test_environment_override_wins_and_wysun_theme_goes_first(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home) / '.config/orbit'
            config.mkdir(parents=True)
            (config / 'theme.json').write_text('{"style":"fluent","variant":"dark"}')
            theme_core.invalidate()
            self.assertEqual(theme_core.selection(Path(home), {'ORBIT_THEME': 'tokyo'}), ('space-black', 'tokyo'))
            self.assertEqual(theme_core.selection(Path(home), {'ORBIT_THEME': 'tokyo', 'WYSUN_THEME': 'fluent:light'}), ('fluent', 'light'))
            theme_core.invalidate()
            self.assertEqual(theme_core.selection(Path(home), {}), ('fluent', 'dark'))

    def test_legacy_file_migrates_with_backup_atomic_write_and_private_mode(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / '.config/orbit/theme.json'
            path.parent.mkdir(parents=True)
            path.write_text('{"id": "tokyo", "name": "Tokyo"}')
            environment = {key: os.environ.pop(key) for key in ('WYSUN_THEME', 'ORBIT_THEME') if key in os.environ}
            try:
                self.assertTrue(theme_core.migrate(Path(home)))
                self.assertEqual(json.loads(path.read_text()), {'style': 'space-black', 'variant': 'tokyo'})
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                backups = list((Path(home) / '.local/state/orbit/theme-backups').glob('theme-*.json'))
                self.assertTrue(any('tokyo' in p.read_text() for p in backups), 'the old file is kept as a backup')
                self.assertFalse(theme_core.migrate(Path(home)), 'a migrated file is left alone')
                self.assertEqual([p.name for p in path.parent.iterdir()], ['theme.json'])
            finally:
                os.environ.update(environment)

    def test_corrupt_file_never_raises_and_uses_the_default(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / '.config/orbit/theme.json'
            path.parent.mkdir(parents=True)
            path.write_text('{not json')
            theme_core.invalidate()
            self.assertEqual(theme_core.selection(Path(home), {}), theme_core.default())
            self.assertFalse(theme_core.migrate(Path(home)))


if __name__ == '__main__':
    unittest.main()
