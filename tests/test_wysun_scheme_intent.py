"""Dynamic intent, seed and wallpaper entry point of the single colour producer."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
import theme_core  # noqa: E402
import theme_intent  # noqa: E402
import wysun_scheme  # noqa: E402

MONITORS = [dict(name='DP-1', width=64, height=48, x=0, y=0, scale=1, refreshRate=60,
                 availableModes=['64x48@60.00Hz'], focused=True)]


def fake_runner(calls):
    def runner(args):
        calls.append(list(args))
        return json.dumps(MONITORS) if list(args[:3]) == ['hyprctl', '-j', 'monitors'] else 'ok'
    return runner


class IntentTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.home = Path(self.folder.name)
        self.config = self.home / '.config/orbit'
        self.config.mkdir(parents=True)
        self.theme = self.config / 'theme.json'
        self.red = self.home / 'red.png'
        self.blue = self.home / 'blue.png'
        Image.new('RGB', (64, 48), (225, 36, 72)).save(self.red)
        Image.new('RGB', (64, 48), (25, 82, 224)).save(self.blue)
        self.patch = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.home / '.config'),
                                             'XDG_STATE_HOME': str(self.home / '.local/state')})
        self.patch.start()
        theme_core.invalidate()
        self.state_file = theme_core.scheme_path(self.home)

    def tearDown(self):
        self.patch.stop()
        theme_core.invalidate()
        self.folder.cleanup()

    def environment(self):
        from environment_settings import EnvironmentSettings
        calls = []
        return EnvironmentSettings(self.home, runner=fake_runner(calls)), calls

    # -- intent defaults ---------------------------------------------------
    def test_new_profile_is_dynamic_and_explicit_choices_stay_fixed(self):
        self.assertEqual(theme_intent.dynamic_intent(self.home), {'enabled': True})
        self.theme.write_text('{"unrelated": 1}')
        self.assertEqual(theme_intent.dynamic_intent(self.home), {'enabled': True})
        for explicit in ('{"style":"fluent","variant":"dark"}', '{"id":"tokyo"}'):
            self.theme.write_text(explicit)
            self.assertEqual(theme_intent.dynamic_intent(self.home), {'enabled': False}, explicit)
        self.theme.unlink()
        theme_core.write_scheme(wysun_scheme.fixed_scheme('space-black', 'tokyo'), self.home)
        self.assertEqual(theme_intent.dynamic_intent(self.home), {'enabled': False})

    def test_unreadable_theme_json_is_never_dynamic_nor_overwritten(self):
        self.theme.write_text('{broken')
        self.assertEqual(theme_intent.dynamic_intent(self.home), {'enabled': False})
        with self.assertRaises(ValueError):
            theme_intent.write_dynamic({'enabled': True}, self.home)
        args = type('A', (), dict(dynamic=True, theme=None, mode='dark', variant=None, seed='#336699'))
        with self.assertRaises(ValueError):
            wysun_scheme.set_scheme(args, self.home)
        self.assertEqual(self.theme.read_text(), '{broken')
        self.assertFalse(self.state_file.exists())

    # -- seed --------------------------------------------------------------
    def test_seed_is_reproducible_validated_and_keeps_the_contract_shape(self):
        first = wysun_scheme.generate_from_seed('#3366CC', 'dark', 'tonalspot')
        self.assertEqual(first, wysun_scheme.generate_from_seed('3366cc', 'dark', 'tonalspot'))
        self.assertNotEqual(first['colours']['primary'],
                            wysun_scheme.generate_from_seed('#cc3333', 'dark', 'tonalspot')['colours']['primary'])
        self.assertEqual(set(first), {'name', 'flavour', 'mode', 'variant', 'colours', 'wallpaper_hash'})
        self.assertTrue(theme_core._valid_scheme(first))
        for bad in ('', '#12', 'zzzzzz', '#12345678'):
            with self.assertRaises(ValueError):
                wysun_scheme.normalize_seed(bad)

    def test_set_persists_intent_and_seed_overrides_wallpaper(self):
        self.theme.write_text('{"style":"fluent","variant":"dark","private":"keep"}\n')
        self.home.joinpath('.config/orbit/environment.json').write_text(
            json.dumps({'wallpaper': {'default': str(self.red)}}))
        run = lambda *args: wysun_scheme.main(['set', *args])
        run('--dynamic', '--mode', 'light', '--variant', 'vibrant', '--seed', '#336699')
        stored = json.loads(self.theme.read_text())
        self.assertEqual(stored['dynamic'], {'enabled': True, 'mode': 'light', 'variant': 'vibrant', 'seed': '#336699'})
        self.assertEqual((stored['style'], stored['variant'], stored['private']), ('fluent', 'dark', 'keep'))
        scheme = json.loads(self.state_file.read_text())
        self.assertEqual(scheme, wysun_scheme.generate_from_seed('#336699', 'light', 'vibrant'))
        # Mode/variant/seed persist across later calls that do not repeat them.
        run('--dynamic', '--mode', 'dark')
        again = json.loads(self.theme.read_text())['dynamic']
        self.assertEqual(again, {'enabled': True, 'mode': 'dark', 'variant': 'vibrant', 'seed': '#336699'})
        run('--dynamic', '--seed', 'none', '--variant', 'auto')
        self.assertEqual(json.loads(self.theme.read_text())['dynamic'], {'enabled': True, 'mode': 'dark'})
        self.assertEqual(json.loads(self.state_file.read_text())['wallpaper_hash'], wysun_scheme._file_hash(self.red))
        # A fixed preset ends the intent but remembers its details, and nothing is lost.
        run('tokyo')
        final = json.loads(self.theme.read_text())
        self.assertEqual((final['style'], final['variant'], final['private']), ('space-black', 'tokyo', 'keep'))
        self.assertEqual(final['dynamic']['enabled'], False)
        self.assertEqual(theme_intent.dynamic_intent(self.home)['enabled'], False)

    def test_failed_publication_restores_theme_and_scheme_bytes(self):
        original = '{"style":"fluent","variant":"dark","private":"keep"}\r\n'
        self.theme.write_bytes(original.encode())
        theme_core.write_scheme(wysun_scheme.fixed_scheme('fluent', 'dark'), self.home)
        before = self.state_file.read_bytes()
        args = type('A', (), dict(dynamic=True, theme=None, mode='dark', variant=None, seed='#336699'))
        with patch.object(theme_core, 'write_scheme', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                wysun_scheme.set_scheme(args, self.home)
        self.assertEqual(self.theme.read_bytes(), original.encode())
        self.assertEqual(self.state_file.read_bytes(), before)

    # -- wallpaper ---------------------------------------------------------
    def test_wallpaper_set_regenerates_dynamic_and_leaves_fixed_alone(self):
        environment, calls = self.environment()
        wysun_scheme.set_wallpaper(self.red, self.home, environment.runner)
        first = json.loads(self.state_file.read_text())  # new profile: dynamic by default
        self.assertEqual(first['name'], 'dynamic')
        self.assertEqual(first['wallpaper_hash'], wysun_scheme._file_hash(self.red))
        self.assertEqual(json.loads((self.config / 'environment.json').read_text())['wallpaper']['default'], str(self.red))
        self.assertIn(['wysun', 'shell', 'reload-preferences'], calls)
        wysun_scheme.set_wallpaper(self.blue, self.home, environment.runner)
        second = json.loads(self.state_file.read_text())
        self.assertEqual(second['wallpaper_hash'], wysun_scheme._file_hash(self.blue))
        self.assertNotEqual(first['colours']['primary'], second['colours']['primary'])
        wysun_scheme.main(['set', 'severance'])
        fixed = self.state_file.read_bytes()
        wysun_scheme.set_wallpaper(self.red, self.home, environment.runner)
        self.assertEqual(self.state_file.read_bytes(), fixed)

    def test_refresh_is_idempotent_and_does_not_rewrite_unchanged_scheme(self):
        environment, _ = self.environment()
        wysun_scheme.set_wallpaper(self.red, self.home, environment.runner)
        stat = self.state_file.stat()
        environment.reload()
        self.assertTrue(wysun_scheme.regenerate_if_dynamic(self.home, environment.wallpaper_values()))
        self.assertEqual(self.state_file.stat().st_mtime_ns, stat.st_mtime_ns)
        wysun_scheme.main(['set', '--dynamic', '--mode', 'light'])
        self.assertEqual(json.loads(self.state_file.read_text())['mode'], 'light')

    def test_wallpaper_rejects_missing_and_non_image_without_changes(self):
        environment, _ = self.environment()
        junk = self.home / 'not-image.png'
        junk.write_text('nope')
        for target in (self.home / 'missing.png', junk):
            with self.assertRaises(ValueError):
                wysun_scheme.set_wallpaper(target, self.home, environment.runner)
        self.assertFalse((self.config / 'environment.json').exists())

    def test_public_command_dispatches_wallpaper_and_scheme(self):
        env = {**os.environ, 'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home / '.config'),
               'XDG_STATE_HOME': str(self.home / '.local/state'), 'PATH': '/nonexistent:' + os.environ['PATH']}
        bad = subprocess.run([sys.executable, str(ROOT / 'bin/wysun'), 'wallpaper', 'set', str(self.home / 'missing.png')],
                             env=env, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertIn('no existe', bad.stderr)
        seed = subprocess.run([sys.executable, str(ROOT / 'bin/wysun'), 'scheme', 'set', '--seed', '#aa5500'],
                              env=env, capture_output=True, text=True)
        self.assertEqual(seed.returncode, 0, seed.stderr)
        self.assertEqual(json.loads((self.home / '.local/state/wysun/scheme.json').read_text())['wallpaper_hash'],
                         wysun_scheme.seed_hash('#aa5500'))


if __name__ == '__main__':
    unittest.main()
