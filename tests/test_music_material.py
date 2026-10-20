"""Run the native Music acceptance probe in an isolated Qt/data process."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class MusicMaterialTests(unittest.TestCase):
    def test_material_structure_live_scheme_and_session_contracts(self):
        with tempfile.TemporaryDirectory(prefix='wysun-music-material-') as folder:
            home = Path(folder)
            runtime = home / 'runtime'
            runtime.mkdir(mode=0o700)
            env = dict(os.environ, HOME=folder, XDG_CONFIG_HOME=str(home / '.config'),
                       XDG_STATE_HOME=str(home / '.local/state'),
                       XDG_CACHE_HOME=str(home / '.cache'), XDG_RUNTIME_DIR=str(runtime),
                       ORBIT_MUSIC_HOME=str(home / 'music'),
                       ORBIT_MUSIC_LIBRARY=str(home / 'audio'),
                       QT_QPA_PLATFORM='offscreen', ORBIT_REDUCED_MOTION='1')
            env.pop('ORBIT_THEME', None)
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('music_material_ui.py'))],
                                    env=env, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('MUSIC_MATERIAL_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
