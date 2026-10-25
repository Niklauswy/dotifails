"""Token source of truth: identical copies, contrast, mode selection and migration."""
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

COPIES = ['apps/capture/loomrec/ui/wysun_theme.json']
VARIANTS = [('material-you', 'light'), ('material-you', 'dark')]
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

    def test_one_style_with_a_light_and_a_dark_palette(self):
        styles = theme_core.styles()
        self.assertEqual({k: list(v['variants']) for k, v in styles.items()}, {'material-you': ['dark', 'light']})
        self.assertEqual(theme_core.default(), ('material-you', 'dark'))
        tokens = {pair: set(theme_core.resolve(*pair)) for pair in VARIANTS}
        self.assertEqual(len({frozenset(v) for v in tokens.values()}), 1, 'both palettes define the same tokens')
        for required in ('canvas', 'surface', 'well', 'line', 'text', 'muted', 'accent', 'accent_hover', 'selection', 'disabled', 'danger', 'success', 'warning', 'scrim',
                         'radius_s', 'radius_m', 'radius_l', 'motion_fast', 'font_family'):
            self.assertIn(required, tokens[VARIANTS[0]])

    IDENTITY = ('name', 'description', 'variant', 'external', 'key', 'material', 'translucent')

    def test_light_and_dark_share_the_shape_and_only_differ_by_palette_and_material(self):
        light, dark = theme_core.resolve('material-you', 'light'), theme_core.resolve('material-you', 'dark')
        for key, value in dark.items():
            if key in self.IDENTITY or isinstance(value, str) and value.startswith('#'):
                continue
            self.assertEqual(light[key], value, key)
        self.assertEqual((dark['material'], dark['translucent']), ('glass', True))
        self.assertEqual((light['material'], light['translucent']), ('pearl', False))

    def test_the_fallback_palette_belongs_to_the_shipped_wallpaper(self):
        wallpaper = theme_core.default_wallpaper()
        self.assertTrue((ROOT / 'assets/backgrounds' / wallpaper).is_file())
        self.assertEqual(json.loads((ROOT / 'manifests/themes.json').read_text())['material-you']['wallpaper'], wallpaper)
        self.assertEqual(theme_core.resolve()['wallpaper'], wallpaper)

    def test_wcag_contrast_in_every_variant(self):
        failures = []
        for pair in VARIANTS:
            colors = theme_core.resolve(*pair)
            base = colors['material_mid'] if colors['translucent'] else colors['canvas']
            for foreground, background, minimum in CONTRAST:
                value = ratio(colors[foreground], colors[background], base)
                if value < minimum:
                    failures.append(f'{pair} {foreground}/{background} {value:.2f} < {minimum}')
        self.assertEqual(failures, [])


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.environment = {key: os.environ.pop(key) for key in ('WYSUN_THEME', 'ORBIT_THEME') if key in os.environ}
        theme_core.invalidate()

    def tearDown(self):
        os.environ.update(self.environment)
        theme_core.invalidate()

    def test_parse_accepts_light_dark_and_the_retired_ids(self):
        for value, expected in (('dark', ('material-you', 'dark')), ('light', ('material-you', 'light')), ('material-you:light', ('material-you', 'light')),
                                ('material-you', ('material-you', 'dark')), ('Tokyo', ('material-you', 'dark')), ('severance', ('material-you', 'dark')),
                                ('fluent:dark', ('material-you', 'dark')), ('Fluent', ('material-you', 'light')), ('fluent/light', None)):
            self.assertEqual(theme_core.parse(value), expected, value)
        self.assertIsNone(theme_core.parse('nope'))
        self.assertIsNone(theme_core.parse('auto'), 'auto is a mode, not a palette')

    def test_mode_from_object_reads_the_new_and_the_old_formats(self):
        read = theme_core.mode_from_object
        self.assertEqual(read({'mode': 'light'}), ('light', False))
        self.assertEqual(read({'mode': 'auto'}), ('auto', False))
        self.assertEqual(read({}), ('auto', False))
        self.assertEqual(read({'mode': 'sepia'}), ('auto', False))
        self.assertEqual(read({'id': 'tokyo'}), ('auto', True))
        self.assertEqual(read({'style': 'fluent', 'variant': 'light'}), ('auto', True), 'a retired fixed theme becomes automatic')
        self.assertEqual(read({'style': 'space-black', 'variant': 'tokyo', 'dynamic': {'enabled': False, 'mode': 'dark'}}), ('auto', True))
        self.assertEqual(read({'dynamic': {'enabled': True, 'mode': 'light', 'variant': 'vibrant', 'seed': '#ff0000'}}), ('light', True))
        self.assertEqual(read({'mode': 'dark', 'style': 'fluent'}), ('dark', True))
        self.assertEqual(read([]), ('auto', False))

    def test_invalid_values_fall_back_to_the_defaults(self):
        self.assertEqual(theme_core.normalize('fluent', 'tokyo'), ('material-you', 'dark'))
        self.assertEqual(theme_core.normalize('material-you', 'nope'), ('material-you', 'dark'))
        self.assertEqual(theme_core.normalize(None, 'light'), ('material-you', 'light'))

    def test_environment_override_wins_and_wysun_theme_goes_first(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home) / '.config/orbit'
            config.mkdir(parents=True)
            (config / 'theme.json').write_text('{"mode":"dark"}')
            theme_core.invalidate()
            self.assertEqual(theme_core.selection(Path(home), {'ORBIT_THEME': 'light'}), ('material-you', 'light'))
            self.assertEqual(theme_core.selection(Path(home), {'ORBIT_THEME': 'light', 'WYSUN_THEME': 'dark'}), ('material-you', 'dark'))
            theme_core.invalidate()
            self.assertEqual(theme_core.selection(Path(home), {}), ('material-you', 'dark'))

    def test_auto_follows_the_published_scheme_and_explicit_modes_do_not(self):
        scheme = {'name': 'dynamic', 'flavour': 'default', 'mode': 'light', 'variant': 'tonalspot', 'wallpaper_hash': 'a' * 64,
                  'colours': {'primary': 'aabbcc'}}
        with tempfile.TemporaryDirectory() as home:
            home = Path(home)
            self.assertEqual(theme_core.selection(home, {}), ('material-you', 'dark'), 'no scheme yet: the default palette')
            theme_core.invalidate()
            theme_core.write_scheme(scheme, home)
            self.assertEqual(theme_core.selection(home, {}), ('material-you', 'light'), 'auto: the wallpaper decided light')
            theme_core.write_mode('dark', home)
            self.assertEqual(theme_core.selection(home, {}), ('material-you', 'dark'), 'dark overrides a light wallpaper')
            theme_core.write_mode('auto', home)
            self.assertEqual(theme_core.selection(home, {}), ('material-you', 'light'))

    def test_the_scheme_colours_are_laid_over_the_palette_of_its_mode(self):
        tokens = theme_core.resolve('material-you', 'dark')
        scheme = {'name': 'dynamic', 'flavour': 'default', 'mode': 'dark', 'variant': 'tonalspot', 'wallpaper_hash': 'a' * 64,
                  'colours': {'primary': 'aabbcc', 'term0': '111111', **{f'term{i}': '222222' for i in range(1, 16)}}}
        result = theme_core.overlay_material_roles(tokens, scheme)
        self.assertEqual(result['accent'], '#aabbcc')
        self.assertEqual(result['external']['palette'][0], '#111111', 'code colours follow the wallpaper too')
        self.assertEqual(tokens['external']['palette'][0], theme_core.resolve('material-you', 'dark')['external']['palette'][0])
        self.assertIs(theme_core.overlay_material_roles(tokens, dict(scheme, name='tokyo')), tokens, 'only dynamic schemes are laid over')

    def test_write_mode_keeps_unknown_keys_and_drops_the_old_ones(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / '.config/orbit/theme.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'style': 'fluent', 'variant': 'dark', 'dynamic': {'enabled': True}, 'future': [1, 2]}))
            theme_core.write_mode('light', Path(home))
            self.assertEqual(json.loads(path.read_text()), {'future': [1, 2], 'mode': 'light'})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(ValueError):
                theme_core.write_mode('sepia', Path(home))
            path.write_text('[1]')
            with self.assertRaises(ValueError):
                theme_core.write_mode('dark', Path(home))
            self.assertEqual(path.read_text(), '[1]', 'a file that is not an object is never replaced')

    def test_legacy_file_migrates_with_backup_atomic_write_and_private_mode(self):
        for legacy, expected in (({'id': 'tokyo', 'name': 'Tokyo'}, 'auto'),
                                 ({'style': 'space-black', 'variant': 'severance', 'dynamic': {'enabled': False, 'mode': 'dark', 'variant': 'tonalspot'}}, 'auto'),
                                 ({'style': 'fluent', 'variant': 'dark', 'dynamic': {'enabled': True, 'mode': 'light', 'seed': '#112233'}}, 'light')):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as home:
                path = Path(home) / '.config/orbit/theme.json'
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(legacy))
                self.assertTrue(theme_core.migrate(Path(home)))
                self.assertEqual(json.loads(path.read_text()), {'mode': expected})
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                backups = list((Path(home) / '.local/state/orbit/theme-backups').glob('theme-*.json'))
                self.assertTrue(any(json.loads(p.read_text()) == legacy for p in backups), 'the old file is kept as a backup')
                self.assertFalse(theme_core.migrate(Path(home)), 'a migrated file is left alone')
                self.assertEqual([p.name for p in path.parent.iterdir()], ['theme.json'])

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
