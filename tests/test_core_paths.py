"""wysun_core.paths resolves XDG locations on every call and keeps private directories private."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_core import paths


class PathsTests(unittest.TestCase):
    def test_xdg_variables_win_when_absolute(self):
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': '/x/cfg', 'XDG_STATE_HOME': 'relative'}):
            self.assertEqual(paths.config('wysun', 'theme.json'), Path('/x/cfg/wysun/theme.json'))
            self.assertEqual(paths.state_home(), Path.home() / '.local/state')

    def test_defaults_follow_home(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {'HOME': home}):
            for name in ('XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_STATE_HOME'):
                os.environ.pop(name, None)
            self.assertEqual(paths.data('wysun', 'colors.json'), Path(home) / '.local/share/wysun/colors.json')
            self.assertEqual(paths.cache('wysun'), Path(home) / '.cache/wysun')
            self.assertEqual(paths.bin_home(), Path(home) / '.local/bin')

    def test_runtime_dir_falls_back_to_a_private_directory(self):
        with tempfile.TemporaryDirectory() as shared, patch.dict(os.environ, {}), \
                patch('tempfile.gettempdir', return_value=shared):
            os.environ.pop('XDG_RUNTIME_DIR', None)
            fallback = paths.runtime_dir()
            self.assertEqual(fallback, Path(shared) / f'wysun-{os.getuid()}')
            self.assertEqual(fallback.stat().st_mode & 0o777, 0o700)
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': '/run/user/77'}):
            self.assertEqual(paths.runtime('wysun-player.sock'), Path('/run/user/77/wysun-player.sock'))

    def test_session_runtime_dir_is_none_outside_a_session(self):
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': ''}):
            self.assertIsNone(paths.session_runtime_dir())
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': '/run/user/77'}):
            self.assertEqual(paths.session_runtime_dir(), Path('/run/user/77'))

    def test_private_dir_rejects_open_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = paths.private_dir(Path(tmp) / 'new' / 'nested')
            self.assertEqual(created.stat().st_mode & 0o777, 0o700)
            shared = Path(tmp) / 'shared'
            shared.mkdir(mode=0o755)
            shared.chmod(0o755)
            with self.assertRaises(RuntimeError):
                paths.private_dir(shared)
            link = Path(tmp) / 'link'
            link.symlink_to(created)
            with self.assertRaises(RuntimeError):
                paths.private_dir(link)


if __name__ == '__main__':
    unittest.main()
