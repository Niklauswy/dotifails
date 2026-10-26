"""apps/python is a root of packages run as modules with PYTHONPATH; nothing goes looking for the app."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'apps/python'
PACKAGES = {'wysun_core', 'wysun_music', 'wysun_files', 'wysun_media', 'wysun_player', 'wysun_pdf',
            'wysun_settings', 'wysun_services', 'wysun_qml'}
# The vendored materialyoucolor is the only sys.path entry production code adds: next to the packages, never the app.
SYS_PATH_ALLOWED = {'apps/python/wysun_services/scheme.py'}


class LayoutTests(unittest.TestCase):
    def test_root_holds_only_packages(self):
        tracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files', 'apps/python'], capture_output=True, text=True,
                                 check=True).stdout.split()
        top = {Path(name).relative_to('apps/python').parts[0] for name in tracked}
        self.assertEqual(top - PACKAGES, {'vendor', 'README.md'})
        for package in PACKAGES:
            self.assertTrue((APP / package / '__init__.py').is_file(), package)

    def test_apps_have_module_entry_points(self):
        for package in ('wysun_music', 'wysun_files', 'wysun_player', 'wysun_pdf'):
            self.assertTrue((APP / package / '__main__.py').is_file(), package)

    def test_no_production_code_inserts_paths(self):
        offenders = []
        for base in ('apps/python', 'apps/shell', 'apps/recorder/wysun_recorder', 'bin', 'config/.local/bin'):
            for path in sorted((ROOT / base).rglob('*')):
                relative = str(path.relative_to(ROOT))
                if not path.is_file() or path.is_symlink() or 'vendor' in path.parts or 'plugin' in path.parts:
                    continue
                if path.suffix not in ('.py', '') or relative in SYS_PATH_ALLOWED:
                    continue
                text = path.read_text(errors='ignore')
                if re.search(r'sys\.path\.(insert|append)', text):
                    offenders.append(relative)
        self.assertEqual(offenders, [])

    def test_shell_runs_python_with_pythonpath_and_without_the_current_directory(self):
        paths = (ROOT / 'apps/shell/utils/Paths.qml').read_text()
        self.assertIn('readonly property string app: Quickshell.env("WYSUN_APP_DIR") || `${data}/app`', paths)
        self.assertIn('return ["/usr/bin/env", `PYTHONPATH=${app}`, "/usr/bin/python3", "-s", "-P", ...entry, ...(args ?? [])];',
                      paths)
        qml = '\n'.join(p.read_text() for p in (ROOT / 'apps/shell').rglob('*.qml') if 'plugin' not in p.parts)
        self.assertNotRegex(qml, r'"-I", [^\]]*(launcher_data|code_preview)')
        with tempfile.TemporaryDirectory() as cwd:
            # A decoy package in the current directory must not shadow the real one.
            decoy = Path(cwd, 'wysun_services'); decoy.mkdir()
            (decoy / '__init__.py').write_text('raise SystemExit("decoy imported")\n')
            argv = ['/usr/bin/env', f'PYTHONPATH={APP}', sys.executable, '-s', '-P', '-m', 'wysun_services.launcher_data',
                    'query', 'calc', '2+2']
            home = Path(cwd, 'home'); home.mkdir()
            env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / 'data'), XDG_CONFIG_HOME=str(home / 'config'),
                       XDG_STATE_HOME=str(home / 'state'), XDG_CACHE_HOME=str(home / 'cache'))
            result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"4"', result.stdout)

    def test_launch_helper_runs_a_module_from_the_same_root(self):
        sys.path.insert(0, str(APP))
        from wysun_core import launch
        self.assertEqual(launch.ROOT, APP)
        self.assertEqual(launch.argv('wysun_music', '--background', python='py'), ['py', '-P', '-m', 'wysun_music', '--background'])
        self.assertEqual(launch.environment({'A': '1'}), {'A': '1', 'PYTHONPATH': str(APP)})


if __name__ == '__main__':
    unittest.main()
