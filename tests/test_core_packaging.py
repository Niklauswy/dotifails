"""wysun_core reaches every place that runs Wysun Python code, and depends on no application."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'apps/wysun/wysun_core'
APPLICATION_MODULES = r'theme_tokens|theme_core|wysun_music|wysun_files|wysun_media|loomrec|orbit|music_material|ui_\w+'


class CorePackagingTests(unittest.TestCase):
    def test_capture_tree_links_wysun_core(self):
        link = ROOT / 'apps/capture/wysun_core'
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), CORE.resolve())

    def test_capture_release_ships_wysun_core(self):
        source = (ROOT / 'installer/capture_distribution.py').read_text()
        self.assertTrue("'wysun_core'" in source, 'capture releases must copy wysun_core')

    def test_installer_runtime_copies_wysun_core(self):
        sys.path.insert(0, str(ROOT / 'installer'))
        from ui_support import package_runtime
        with tempfile.TemporaryDirectory() as tmp:
            package_runtime(ROOT, tmp)
            self.assertTrue((Path(tmp) / 'wysun_core/jsonio.py').is_file())
            self.assertFalse(list(Path(tmp, 'wysun_core').rglob('__pycache__')))

    def test_core_imports_no_application_module(self):
        for module in CORE.glob('*.py'):
            imports = re.findall(r'^\s*(?:from|import)\s+([\w.]+)', module.read_text(), re.M)
            offending = [name for name in imports if re.fullmatch(APPLICATION_MODULES, name.split('.')[0])]
            self.assertEqual(offending, [], module.name)


    def test_one_theme_runtime(self):
        for gone in ('apps/wysun/theme_core.py', 'apps/wysun/theme_tokens.py', 'apps/wysun/ui_appearance.py',
                     'apps/wysun/wysun_theme.json', 'apps/capture/loomrec/ui/theme_core.py',
                     'apps/capture/loomrec/ui/wysun_theme.json', 'manifests/themes.json'):
            self.assertFalse((ROOT / gone).exists(), gone)
        hits = subprocess.run(['git', '-C', str(ROOT), 'grep', '-nE',
                               r'ORBIT_THEME|wysunThemeTemplate|wysunThemeStyle|RETIRED_BAR_COLORS|LOOMREC_REDUCED_MOTION',
                               '--', 'apps', 'installer', 'tests', 'bin', 'docs/themes.md', 'AGENTS.md',
                               ':!tests/test_core_packaging.py'], capture_output=True, text=True).stdout
        self.assertEqual(hits, '')


if __name__ == '__main__':
    unittest.main()
