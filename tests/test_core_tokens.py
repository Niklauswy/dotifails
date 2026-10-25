"""tokens.json: both base palettes define the same tokens, share the shape and meet WCAG contrast."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
from wysun_core import theme  # noqa: E402

MODES = ('light', 'dark')
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
    def test_both_palettes_define_the_same_tokens(self):
        self.assertEqual(sorted(theme.data()['palettes']), ['dark', 'light'])
        light, dark = (set(theme.resolve(mode)) for mode in MODES)
        self.assertEqual(light, dark)
        for required in ('canvas', 'surface', 'well', 'line', 'text', 'muted', 'accent', 'accent_hover', 'selection', 'disabled',
                         'danger', 'success', 'warning', 'scrim', 'rounding.small', 'rounding.medium', 'spacing.large',
                         'anim.durations.normal', 'font.family.sans', 'font.body.medium.size'):
            self.assertIn(required, light)

    def test_light_and_dark_share_the_shape_and_only_differ_by_palette_and_material(self):
        light, dark = theme.resolve('light'), theme.resolve('dark')
        for key, value in dark.items():
            if key in ('mode', 'external', 'material', 'translucent') or isinstance(value, str) and value.startswith('#'):
                continue
            self.assertEqual(light[key], value, key)

    def test_the_fallback_palette_belongs_to_the_shipped_wallpaper(self):
        wallpaper = theme.default_wallpaper()
        self.assertTrue((ROOT / 'assets/backgrounds' / wallpaper).is_file())
        self.assertEqual(theme.resolve('dark')['wallpaper'], wallpaper)

    def test_schema_3_follows_the_shell_names(self):
        data = theme.data()
        self.assertEqual(data['schema'], 3)
        for group in ('rounding', 'spacing', 'padding', 'font', 'anim', 'border', 'icon', 'palettes'):
            self.assertIn(group, data)
        self.assertNotIn('shape', data)
        self.assertEqual(data['rounding']['full'], 2147483647)
        self.assertEqual(data['font']['family'], {'sans': 'Google Sans Flex', 'mono': 'CaskaydiaCove NF',
                                                  'icon': 'Material Symbols Rounded'})
        values = theme.resolve('dark')
        self.assertEqual(values['rounding.medium'], 12)
        self.assertEqual(values['font.body.medium.size'], 14)
        self.assertEqual(values['anim.curves.standard'], [0.2, 0, 0, 1, 1, 1])
        old = [key for key in values if key.startswith(('radius_', 'corner_', 'space_', 'font_', 'motion_', 'shadow_', 'lock_'))
               or key in ('border', 'focus_width', 'icon_size', 'icon_stroke')]
        self.assertEqual(old, [])

    def test_base_scheme_is_the_default_wallpaper_scheme(self):
        import wysun_scheme
        wallpaper = ROOT / 'assets/backgrounds' / theme.default_wallpaper()
        for mode in MODES:
            self.assertEqual(theme.data()['palettes'][mode]['scheme'],
                             wysun_scheme.generate_dynamic(wallpaper, mode=mode)['colours'], mode)

    def test_wcag_contrast_in_every_palette(self):
        failures = []
        for mode in MODES:
            colors = theme.resolve(mode)
            base = colors['material_mid'] if colors['translucent'] else colors['canvas']
            for foreground, background, minimum in CONTRAST:
                value = ratio(colors[foreground], colors[background], base)
                if value < minimum:
                    failures.append(f'{mode} {foreground}/{background} {value:.2f} < {minimum}')
        self.assertEqual(failures, [])


if __name__ == '__main__':
    unittest.main()
