"""Material You producer and live Qt token contract tests."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
import theme_core  # noqa: E402
import theme_tokens  # noqa: E402
import wysun_scheme  # noqa: E402


TEXT_PAIRS = (
    ('text', 'canvas', 4.5), ('text', 'surface', 4.5), ('text', 'well', 4.5),
    ('muted', 'surface', 4.5), ('muted', 'canvas', 4.5), ('subtle', 'surface', 4.5),
    ('control_text', 'fill', 4.5), ('text', 'selection', 4.5),
    ('selection_text', 'selection', 4.5), ('text', 'hover', 4.5), ('text', 'menu', 4.5),
    ('text', 'menu_selected', 4.5), ('on_accent', 'accent', 4.5),
    ('on_accent', 'accent_hover', 4.5), ('on_accent', 'accent_pressed', 4.5),
    ('accent_ink', 'accent_alt', 4.5), ('danger', 'surface', 4.5),
    ('success', 'surface', 4.5), ('warning', 'surface', 4.5),
    ('on_tooltip', 'tooltip', 4.5), ('accent', 'surface', 3), ('accent', 'canvas', 3),
    ('focus', 'surface', 3), ('focus_input', 'well', 3),
    ('check_line', 'surface', 3), ('glyph', 'surface', 3),
)


def _linear(value):
    value = value / 255
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4


def _channels(value):
    text = value.lstrip('#')
    alpha = int(text[6:8], 16) / 255 if len(text) == 8 else 1
    rgb = [_linear(int(text[index:index + 2], 16)) for index in (0, 2, 4)]
    return rgb, alpha


def _contrast(foreground, background, base):
    fg, fa = _channels(foreground)
    bg, ba = _channels(background)
    under = [_linear(int(base.lstrip('#')[index:index + 2], 16)) for index in (0, 2, 4)]
    backdrop = [bg[index] * ba + under[index] * (1 - ba) for index in range(3)]
    shown = [fg[index] * fa + backdrop[index] * (1 - fa) for index in range(3)]
    luminance = lambda rgb: sum(channel * weight for channel, weight in zip(rgb, (.2126, .7152, .0722)))
    high, low = sorted((luminance(backdrop), luminance(shown)), reverse=True)
    return (high + .05) / (low + .05)


def _make_wallpaper(path, rgb):
    image = Image.new('RGB', (80, 64), rgb)
    image.save(path, format='PNG')
    return path


APP = QApplication.instance() or QApplication([])


class SchemeGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.red = _make_wallpaper(self.root / 'synthetic-red.png', (225, 36, 72))
        self.blue = _make_wallpaper(self.root / 'synthetic-blue.png', (25, 82, 224))

    def tearDown(self):
        theme_core.invalidate()
        theme_tokens.invalidate()
        self.folder.cleanup()

    def test_same_image_generates_identical_caelestia_scheme(self):
        first = wysun_scheme.generate_dynamic(self.red, 'dark', 'tonalspot')
        second = wysun_scheme.generate_dynamic(self.red, 'dark', 'tonalspot')
        self.assertEqual(first, second)
        self.assertEqual(first['name'], 'dynamic')
        self.assertEqual(first['mode'], 'dark')
        self.assertEqual(first['variant'], 'tonalspot')
        self.assertRegex(first['wallpaper_hash'], r'^[0-9a-f]{64}$')
        self.assertTrue(first['colours'])
        self.assertTrue(all(not value.startswith('#') for value in first['colours'].values()))

    def test_cli_reads_settings_wallpaper_and_two_images_produce_distinct_palettes(self):
        config = self.root / 'config'
        state = self.root / 'state'
        home = self.root / 'home'
        home.mkdir()
        orbit = config / 'orbit'
        orbit.mkdir(parents=True)
        theme_file = orbit / 'theme.json'
        legacy_selection = '{"style":"fluent","variant":"dark","private":"keep"}\n'
        theme_file.write_text(legacy_selection, encoding='utf-8')
        environment_file = orbit / 'environment.json'
        env = {**os.environ, 'HOME': str(home), 'XDG_CONFIG_HOME': str(config), 'XDG_STATE_HOME': str(state)}
        generated = []
        for wallpaper in (self.red, self.blue):
            environment_file.write_text(json.dumps({'wallpaper': {'default': str(wallpaper), 'mode': 'fill'}}))
            result = subprocess.run(
                [sys.executable, str(ROOT / 'bin/wysun'), 'scheme', 'set', '--dynamic', '--mode', 'dark', '--variant', 'tonalspot'],
                cwd=ROOT, env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            target = state / 'wysun/scheme.json'
            saved = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(saved['name'], 'dynamic')
            self.assertEqual(saved['wallpaper_hash'], wysun_scheme._file_hash(wallpaper))
            self.assertNotIn(str(wallpaper), target.read_text(encoding='utf-8'))
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            generated.append(saved)
        first = generated[0]['colours']['primary']
        second = generated[1]['colours']['primary']
        rgb = lambda value: tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
        self.assertGreaterEqual(sum((a - b) ** 2 for a, b in zip(rgb(first), rgb(second))) ** .5, 80)
        # Dynamic intent is stored additively; the fixed choice and unknown keys remain.
        stored = json.loads(theme_file.read_text(encoding='utf-8'))
        self.assertEqual({k: stored[k] for k in ('style', 'variant', 'private')}, {'style': 'fluent', 'variant': 'dark', 'private': 'keep'})
        self.assertEqual(stored['dynamic'], {'enabled': True, 'mode': 'dark', 'variant': 'tonalspot'})
        self.assertEqual(set(generated[0]), {'name', 'flavour', 'mode', 'variant', 'colours', 'wallpaper_hash'})
        for preset in ('space-black', 'tokyo', 'severance', 'fluent:light', 'fluent:dark'):
            result = subprocess.run([sys.executable, str(ROOT / 'bin/wysun'), 'scheme', 'set', preset],
                                    cwd=ROOT, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            fixed = json.loads((state / 'wysun/scheme.json').read_text(encoding='utf-8'))
            self.assertEqual(fixed['name'], theme_core.parse(preset)[1])
            self.assertIn(fixed['mode'], ('light', 'dark'))
            self.assertTrue(all(not value.startswith('#') for value in fixed['colours'].values()))
            selection = json.loads(theme_file.read_text(encoding='utf-8'))
            self.assertEqual(theme_core.key(selection['style'], selection['variant']), theme_core.key(*theme_core.parse(preset)))
            self.assertEqual(selection['private'], 'keep')

    def test_all_caelestia_variants_generate_for_light_and_dark(self):
        failures = []
        for wallpaper in (self.red, self.blue):
            for variant in wysun_scheme.VARIANTS:
                for mode in ('light', 'dark'):
                    scheme = wysun_scheme.generate_dynamic(wallpaper, mode, variant)
                    self.assertEqual((scheme['name'], scheme['mode'], scheme['variant']), ('dynamic', mode, variant))
                    self.assertTrue({'primary', 'onPrimary', 'surface', 'onSurface', 'error'} <= set(scheme['colours']))
                    self.assertTrue(all(not value.startswith('#') for value in scheme['colours'].values()))
                    tokens = theme_core.overlay_material_roles(theme_core.resolve('fluent', mode), scheme)
                    for foreground, background, minimum in TEXT_PAIRS:
                        actual = _contrast(tokens[foreground], tokens[background], tokens['canvas'])
                        if actual < minimum:
                            failures.append(f'{wallpaper.name} {variant}/{mode} {foreground}/{background}: {actual:.2f} < {minimum:.1f}')
        self.assertEqual(failures, [])

    def test_wallpaper_change_regenerates_only_an_explicit_dynamic_scheme(self):
        home = self.root / 'home'
        home.mkdir()
        dynamic = wysun_scheme.generate_dynamic(self.red, 'dark', 'content')
        path = theme_core.write_scheme(dynamic, home)
        before = json.loads(path.read_text())
        wysun_scheme.regenerate_if_dynamic(home, {'default': str(self.blue)})
        after = json.loads(path.read_text())
        self.assertEqual(after['wallpaper_hash'], wysun_scheme._file_hash(self.blue))
        self.assertNotEqual(before['colours']['primary'], after['colours']['primary'])
        fixed = wysun_scheme.fixed_scheme('fluent', 'dark')
        theme_core.write_scheme(fixed, home)
        fixed_before = path.read_bytes()
        wysun_scheme.regenerate_if_dynamic(home, {'default': str(self.red)})
        self.assertEqual(path.read_bytes(), fixed_before)

    def test_material_roles_map_to_live_wysun_tokens_and_pass_wcag(self):
        failures = []
        roles = theme_core.MATERIAL_TOKEN_ROLES
        self.assertEqual(roles['primary'], 'accent')
        self.assertEqual(roles['onPrimary'], 'on_accent')
        self.assertEqual(roles['onSecondary'], 'accent_ink')
        self.assertEqual(roles['success'], 'success')
        self.assertEqual(roles['error'], 'danger')
        for wallpaper in (self.red, self.blue):
            for mode in ('light', 'dark'):
                scheme = wysun_scheme.generate_dynamic(wallpaper, mode, 'tonalspot')
                preset = theme_core.resolve('fluent', mode)
                tokens = theme_core.overlay_material_roles(preset, scheme)
                self.assertEqual(tokens['accent'], '#' + scheme['colours']['primary'])
                self.assertEqual(tokens['on_accent'], '#' + scheme['colours']['onPrimary'])
                self.assertEqual(tokens['success'], '#' + scheme['colours']['success'].lower())
                for foreground, background, minimum in TEXT_PAIRS:
                    actual = _contrast(tokens[foreground], tokens[background], tokens['canvas'])
                    if actual < minimum:
                        failures.append(f'{mode} {foreground}/{background}: {actual:.2f} < {minimum:.1f}')
        self.assertEqual(failures, [])

    def test_qt_apps_recolour_when_scheme_json_is_replaced(self):
        home = self.root / 'home'
        config = home / 'config'
        state = home / 'state'
        (config / 'orbit').mkdir(parents=True)
        (state / 'wysun').mkdir(parents=True)
        (config / 'orbit/theme.json').write_text('{"style":"fluent","variant":"dark"}')
        previous = getattr(APP, 'orbitThemeWatcher', None)
        if previous is not None:
            del APP.orbitThemeWatcher
        environment = {'HOME': str(home), 'XDG_CONFIG_HOME': str(config),
                       'XDG_STATE_HOME': str(state), 'ORBIT_THEME': '', 'WYSUN_THEME': ''}

        def settle():
            # Other UI tests can leave lastWindowClosed/quit queued. Pump
            # events directly so their application quit cannot end this wait.
            deadline = time.monotonic() + .3
            while time.monotonic() < deadline:
                APP.processEvents()
                time.sleep(.005)

        with patch.dict(os.environ, environment), patch.object(theme_tokens, 'refresh_widgets') as refreshed:
            theme_tokens.invalidate()
            theme_tokens.watch_theme()
            watcher = APP.orbitThemeWatcher
            try:
                first = wysun_scheme.generate_dynamic(self.red, 'dark', 'tonalspot')
                theme_core.write_scheme(first)
                settle()
                expected_first = '#' + first['colours']['primary'].lower()
                self.assertEqual(theme_tokens.tokens()['accent'], expected_first)
                self.assertEqual(refreshed.call_count, 1)
                second = wysun_scheme.generate_dynamic(self.blue, 'dark', 'tonalspot')
                theme_core.write_scheme(second)
                settle()
                expected_second = '#' + second['colours']['primary'].lower()
                self.assertNotEqual(expected_first, expected_second)
                self.assertEqual(theme_tokens.tokens()['accent'], expected_second)
                self.assertEqual(refreshed.call_count, 2)
            finally:
                watcher.deleteLater()
                del APP.orbitThemeWatcher
                if previous is not None:
                    APP.orbitThemeWatcher = previous
                theme_tokens.invalidate()

    def test_scheme_write_is_atomic_private_and_rejects_sensitive_fields(self):
        path = theme_core.scheme_path(self.root)
        scheme = wysun_scheme.generate_dynamic(self.red, 'dark', 'vibrant')
        written = theme_core.write_scheme(scheme, self.root)
        original = written.read_bytes()
        self.assertEqual(path, written)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        invalid = dict(scheme, wallpaper_path='/private/background.png')
        with self.assertRaises(ValueError):
            theme_core.write_scheme(invalid, self.root)
        with patch.object(theme_core.os, 'replace', side_effect=OSError('simulated replace failure')):
            with self.assertRaises(OSError):
                theme_core.write_scheme(dict(scheme, variant='content'), self.root)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob('.scheme.json*')), [])


if __name__ == '__main__':
    unittest.main()
