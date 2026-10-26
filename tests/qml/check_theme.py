"""WysunM3.Theme: direct M3 roles from scheme.json + tokens.json, live; ThemeBridge feeding it."""
import json
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

THEME_QML = (support.LIBRARY / 'Theme.qml').read_text()
ROLES = re.findall(r'readonly property color m3(\w+):', THEME_QML)


def tearDownModule():
    support.Harness.get().close_views()


class RoleTests(unittest.TestCase):
    def setUp(self):
        self.h = support.Harness.get()
        self.h.bridge.setPreview(None)

    def test_the_role_list_is_complete(self):
        for required in ('background', 'surface', 'surfaceContainerLow', 'surfaceContainer', 'surfaceContainerHigh',
                         'surfaceContainerHighest', 'onSurface', 'onSurfaceVariant', 'outline', 'outlineVariant',
                         'primary', 'onPrimary', 'primaryContainer', 'onPrimaryContainer', 'secondaryContainer',
                         'onSecondaryContainer', 'tertiaryContainer', 'onTertiaryContainer', 'error', 'errorContainer',
                         'inverseSurface', 'inverseOnSurface', 'inversePrimary', 'scrim', 'shadow', 'surfaceTint',
                         'success', 'onSuccess', 'successContainer', 'onSuccessContainer'):
            self.assertIn(required, ROLES)

    def test_role_list_matches_wysun_core_theme(self):
        from wysun_core import theme
        self.assertEqual(sorted(ROLES), sorted(theme.MATERIAL_ROLE_NAMES))

    def test_roles_use_the_m3_prefix_and_never_a_bare_handler_name(self):
        self.assertFalse(re.search(r'property\s+color\s+on[A-Z]', THEME_QML), 'a bare onSurface is a signal handler in QML')
        self.assertIn('onSurface', ROLES)

    def test_every_role_is_exposed_and_equals_the_scheme_for_every_palette(self):
        for name, palette in support.palettes().items():
            with self.subTest(palette=name):
                self.h.use(name)
                got = self.h.roles(ROLES)
                for role in ROLES:
                    self.assertEqual(got[role].lower(), '#' + palette['colours'][role].lower(), f'{name}:{role}')

    def test_live_switch_light_dark_repaints(self):
        body = 'Rectangle { anchors.fill: parent; color: Theme.m3surfaceContainerHigh }'
        palettes = support.palettes()
        for first, second in (('default-dark', 'default-light'), ('green-light', 'orange-dark')):
            self.h.use(first)
            view, image = self.h.render(body)
            support.close_to(self, self.h.pixel(image, 10, 10), palettes[first]['colours']['surfaceContainerHigh'], msg=first)
            self.h.use(second)
            support.close_to(self, self.h.pixel(self.h.grab(view), 10, 10),
                             palettes[second]['colours']['surfaceContainerHigh'], msg=second)

    def test_live_wallpaper_change_from_scheme_file(self):
        from wysun_qml import theme_bridge
        palettes = support.palettes()
        home = Path(self.h.dir.name) / 'live-home'
        bridge = theme_bridge.ThemeBridge(home=home)
        self.addCleanup(bridge.deleteLater)
        seen = []
        bridge.schemeChanged.connect(lambda: seen.append(bridge.scheme['colours']['primary']))
        scheme_path = home / '.local/state/wysun/scheme.json'
        support.write_atomic(scheme_path, support.scheme_file(palettes['orange-dark']))
        self.assertTrue(self.h.wait_for(lambda: bridge.scheme['colours']['primary'] == palettes['orange-dark']['colours']['primary']))
        support.write_atomic(scheme_path, support.scheme_file(palettes['green-light']))
        self.assertTrue(self.h.wait_for(lambda: bridge.scheme['colours']['primary'] == palettes['green-light']['colours']['primary']),
                        'the watcher missed the atomic replacement')
        self.assertEqual(bridge.scheme['mode'], 'light')

    def test_mode_file_change_switches_the_base_palette_when_there_is_no_scheme(self):
        from wysun_qml import theme_bridge
        home = Path(self.h.dir.name) / 'mode-home'
        bridge = theme_bridge.ThemeBridge(home=home)
        self.addCleanup(bridge.deleteLater)
        support.write_atomic(home / '.config/wysun/theme.json', {'mode': 'light'})
        self.assertTrue(self.h.wait_for(lambda: bridge.scheme['mode'] == 'light'))
        support.write_atomic(home / '.config/wysun/theme.json', {'mode': 'dark'})
        self.assertTrue(self.h.wait_for(lambda: bridge.scheme['mode'] == 'dark'))

    def test_broken_scheme_file_never_leaves_transparent_roles(self):
        from wysun_qml import theme_bridge
        home = Path(self.h.dir.name) / 'broken-home'
        bridge = theme_bridge.ThemeBridge(home=home)
        self.addCleanup(bridge.deleteLater)
        path = home / '.local/state/wysun/scheme.json'
        support.write_atomic(path, support.scheme_file(support.palettes()['blue-dark']))
        self.assertTrue(self.h.wait_for(lambda: bridge.scheme['colours']['primary'] == support.palettes()['blue-dark']['colours']['primary']))
        path.write_text('{"colours": {"primary": "zz"')
        self.h.pump(300)
        self.assertTrue(all(bridge.scheme['colours'].get(role) for role in ROLES), 'colours must stay complete')

    def test_theme_ignores_an_invalid_scheme_and_keeps_the_last_good_one(self):
        self.h.use('green-dark')
        view = self.h.view('function poke(v) { Theme.scheme = v }', 10, 10)
        for bad in (None, 42, {}, {'mode': 'dark'}, {'mode': 'dark', 'colours': {}}):
            self.h.call(view.rootObject(), 'poke', bad)
            self.h.pump()
            got = self.h.roles(['primary', 'surface'])
            for role, value in got.items():
                self.assertEqual(value.lower(), '#' + support.palettes()['green-dark']['colours'][role].lower(), repr(bad))

    def test_a_role_missing_from_the_scheme_falls_back_to_the_base_palette(self):
        palette = support.palettes()['orange-light']
        partial = {'mode': 'light', 'colours': {k: v for k, v in palette['colours'].items() if k not in ('success', 'tertiaryContainer')}}
        self.h.bridge.setPreview(partial)
        self.h.pump()
        base = support.palettes()['default-light']['colours']
        got = self.h.roles(['success', 'tertiaryContainer', 'primary'])
        self.assertEqual(got['success'].lower(), '#' + base['success'].lower())
        self.assertEqual(got['tertiaryContainer'].lower(), '#' + base['tertiaryContainer'].lower())
        self.assertEqual(got['primary'].lower(), '#' + palette['colours']['primary'].lower())


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.h = support.Harness.get()
        self.h.bridge.setPreview(None)
        self.tokens = json.loads((ROOT / 'apps/python/wysun_core/tokens.json').read_text())

    def test_shape_and_motion_tokens_are_exposed(self):
        h = self.h
        self.assertEqual(h.theme('rounding')['extraLarge'], self.tokens['rounding']['extraLarge'])
        self.assertEqual(h.theme('spacing')['medium'], self.tokens['spacing']['medium'])
        self.assertEqual(h.theme('anim')['durations']['expressiveFastSpatial'], 350)
        self.assertEqual(list(h.theme('anim')['curves']['expressiveFastSpatial']),
                         self.tokens['anim']['curves']['expressiveFastSpatial'])

    def test_curve_and_duration_helpers(self):
        view = self.h.view('function c(n) { return Theme.curve(n) }\nfunction d(n) { return Theme.duration(n) }', 10, 10)
        root = view.rootObject()
        self.assertEqual(self.h.call(root, 'd', 'expressiveSlowEffects'), self.tokens['anim']['durations']['expressiveSlowEffects'])
        self.assertEqual(list(self.h.call(root, 'c', 'expressiveDefaultSpatial')), self.tokens['anim']['curves']['expressiveDefaultSpatial'])

    def test_type_scale_resolves_family_size_and_weight(self):
        view = self.h.view('function f(r) { return Theme.typeFont(r) }', 10, 10)
        body = self.h.call(view.rootObject(), 'f', 'body.medium')
        self.assertEqual((body['family'], body['pointSize'], body['weight']), ('Google Sans Flex', 14, 400))
        title = self.h.call(view.rootObject(), 'f', 'title.large')
        self.assertEqual((title['pointSize'], title['weight']), (22, 500))
        unknown = self.h.call(view.rootObject(), 'f', 'nonsense.role')
        self.assertEqual(unknown['pointSize'], 14, 'an unknown role is body.medium')

    def test_state_layer_opacities(self):
        view = self.h.view('function o(k) { return Theme.stateOpacity(k) }', 10, 10)
        got = {k: self.h.call(view.rootObject(), 'o', k) for k in ('hover', 'focus', 'pressed', 'dragged')}
        self.assertEqual(got, {'hover': 0.08, 'focus': 0.12, 'pressed': 0.12, 'dragged': 0.16})

    def test_style_and_dark_flags(self):
        self.h.use('green-dark')
        self.assertEqual(self.h.theme('style'), 'material3')
        self.assertTrue(self.h.theme('dark'))
        self.h.use('green-light')
        self.assertFalse(self.h.theme('dark'))

    def test_full_radius_is_half_the_height(self):
        view = self.h.view('function r(h) { return Theme.fullRadius(h) }', 10, 10)
        self.assertEqual(self.h.call(view.rootObject(), 'r', 56), 28)


class TextAndIconTests(unittest.TestCase):
    def setUp(self):
        self.h = support.Harness.get()
        self.h.bridge.setPreview(None)

    def test_label_takes_its_font_from_the_type_scale(self):
        view = self.h.view('Label { id: l; objectName: "l"; role: "title.large"; text: "Hola" }', 100, 40)
        from PySide6.QtCore import QObject
        label = view.rootObject().findChild(QObject, 'l')
        font = label.property('font')
        self.assertEqual(font.family(), 'Google Sans Flex')
        self.assertEqual(font.pointSize(), 22)
        self.assertEqual(font.weight(), 500)

    def test_icon_draws_a_glyph_not_the_ligature_name(self):
        _, image = self.h.render('Icon { name: "search"; size: 24; x: 4; y: 4 }', 40, 40)
        w, h = image.width(), image.height()
        lit = sum(1 for x in range(w) for y in range(h) if image.pixelColor(x, y).alpha() > 0 and image.pixelColor(x, y) != image.pixelColor(0, 0))
        self.assertGreater(lit, 20)
        self.assertLess(lit, 24 * 24, 'a 24 px glyph, not the word "search" in plain text')

    def test_icon_size_is_a_token_default(self):
        view = self.h.view('Icon { id: i; name: "home" }', 40, 40)
        icon = view.rootObject().children()[-1]
        self.assertEqual(icon.property('size'), 24)
        self.assertEqual(icon.property('width'), 24)

    def test_icon_without_its_font_renders_nothing(self):
        tokens = json.loads(json.dumps(self.h.bridge.tokens))
        tokens['font']['family']['icon'] = 'No Such Icon Font'
        self.h.bridge.setPreviewTokens(tokens)
        self.h.pump()
        try:
            _, image = self.h.render('Icon { name: "search"; size: 24; x: 4; y: 4 }', 40, 40)
            background = image.pixelColor(0, 0)
            self.assertTrue(all(image.pixelColor(x, y) == background for x in range(40) for y in range(40)),
                            'a missing icon font must not print the ligature name')
        finally:
            self.h.bridge.setPreviewTokens(None)


if __name__ == '__main__':
    unittest.main()
