"""The colour mode (auto, light, dark) and the wallpaper entry point of the single colour producer."""
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
import wysun_scheme  # noqa: E402

MONITORS = [dict(name='DP-1', width=64, height=48, x=0, y=0, scale=1, refreshRate=60,
                 availableModes=['64x48@60.00Hz'], focused=True)]


def fake_runner(calls):
    def runner(args):
        calls.append(list(args))
        return json.dumps(MONITORS) if list(args[:3]) == ['hyprctl', '-j', 'monitors'] else 'ok'
    return runner


class ModeTests(unittest.TestCase):
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

    # -- the stored mode ---------------------------------------------------
    def test_a_new_profile_is_automatic_and_the_mode_survives_unknown_keys(self):
        self.assertEqual(theme_core.read_mode(self.home), 'auto')
        self.theme.write_text('{"unrelated": 1}')
        self.assertEqual(theme_core.read_mode(self.home), 'auto')
        self.theme.write_text('{"mode": "light", "unrelated": 1}')
        self.assertEqual(theme_core.read_mode(self.home), 'light')

    def test_unreadable_theme_json_is_never_overwritten(self):
        self.theme.write_text('{broken')
        self.assertEqual(theme_core.read_mode(self.home), 'auto')
        with self.assertRaises(ValueError):
            wysun_scheme.set_scheme('dark', self.home)
        self.assertEqual(self.theme.read_text(), '{broken')
        self.assertFalse(self.state_file.exists())

    def test_set_persists_the_mode_and_publishes_the_scheme_from_the_wallpaper(self):
        self.theme.write_text('{"style":"fluent","variant":"dark","private":"keep"}\n')
        self.config.joinpath('environment.json').write_text(json.dumps({'wallpaper': {'default': str(self.red)}}))
        run = lambda *args: wysun_scheme.main(['set', *args])
        run('light')
        self.assertEqual(json.loads(self.theme.read_text()), {'private': 'keep', 'mode': 'light'})
        scheme = json.loads(self.state_file.read_text())
        self.assertEqual((scheme['name'], scheme['mode']), ('dynamic', 'light'))
        self.assertEqual(scheme['wallpaper_hash'], wysun_scheme._file_hash(self.red))
        run('--mode', 'dark')
        self.assertEqual(json.loads(self.theme.read_text())['mode'], 'dark')
        self.assertEqual(json.loads(self.state_file.read_text())['mode'], 'dark')
        run()
        self.assertEqual(json.loads(self.theme.read_text())['mode'], 'dark', 'without a mode the stored one is kept')
        run('--dynamic', 'auto')  # the flag of the older CLI is accepted and does nothing
        self.assertEqual(json.loads(self.theme.read_text())['mode'], 'auto')

    def test_failed_publication_restores_theme_and_scheme_bytes(self):
        original = '{"mode":"dark","private":"keep"}\r\n'
        self.theme.write_bytes(original.encode())
        self.config.joinpath('environment.json').write_text(json.dumps({'wallpaper': {'default': str(self.red)}}))
        theme_core.write_scheme(wysun_scheme.generate_dynamic(self.blue, 'dark'), self.home)
        before = self.state_file.read_bytes()
        with patch.object(theme_core, 'write_scheme', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                wysun_scheme.set_scheme('light', self.home)
        self.assertEqual(self.theme.read_bytes(), original.encode())
        self.assertEqual(self.state_file.read_bytes(), before)

    # -- wallpaper ---------------------------------------------------------
    def test_wallpaper_set_regenerates_the_scheme(self):
        environment, calls = self.environment()
        wysun_scheme.set_wallpaper(self.red, self.home, environment.runner)
        first = json.loads(self.state_file.read_text())
        self.assertEqual(first['name'], 'dynamic')
        self.assertEqual(first['wallpaper_hash'], wysun_scheme._file_hash(self.red))
        self.assertEqual(json.loads((self.config / 'environment.json').read_text())['wallpaper']['default'], str(self.red))
        self.assertIn(['wysun', 'shell', 'reload-preferences'], calls)
        wysun_scheme.set_wallpaper(self.blue, self.home, environment.runner)
        second = json.loads(self.state_file.read_text())
        self.assertEqual(second['wallpaper_hash'], wysun_scheme._file_hash(self.blue))
        self.assertNotEqual(first['colours']['primary'], second['colours']['primary'])

    def test_refresh_is_idempotent_and_does_not_rewrite_unchanged_scheme(self):
        environment, _ = self.environment()
        wysun_scheme.set_wallpaper(self.red, self.home, environment.runner)
        stat = self.state_file.stat()
        environment.reload()
        self.assertTrue(wysun_scheme.regenerate_scheme(self.home, environment.wallpaper_values()))
        self.assertEqual(self.state_file.stat().st_mtime_ns, stat.st_mtime_ns)
        wysun_scheme.main(['set', 'light'])
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
        self.config.joinpath('environment.json').write_text(json.dumps({'wallpaper': {'default': str(self.blue)}}))
        mode = subprocess.run([sys.executable, str(ROOT / 'bin/wysun'), 'scheme', 'set', 'light'],
                              env=env, capture_output=True, text=True)
        self.assertEqual(mode.returncode, 0, mode.stderr)
        scheme = json.loads((self.home / '.local/state/wysun/scheme.json').read_text())
        self.assertEqual((scheme['mode'], scheme['wallpaper_hash']), ('light', wysun_scheme._file_hash(self.blue)))


if __name__ == '__main__':
    unittest.main()
