"""wysun_core reaches every place that runs Wysun Python code, and depends on no application."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'apps/python/wysun_core'
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
        for gone in ('apps/python/theme_core.py', 'apps/python/theme_tokens.py', 'apps/python/ui_appearance.py',
                     'apps/python/wysun_theme.json', 'apps/capture/loomrec/ui/theme_core.py',
                     'apps/capture/loomrec/ui/wysun_theme.json', 'manifests/themes.json'):
            self.assertFalse((ROOT / gone).exists(), gone)
        hits = subprocess.run(['git', '-C', str(ROOT), 'grep', '-nE',
                               r'ORBIT_THEME|orbitOriginalStyle|wysunThemeStyle|RETIRED_BAR_COLORS|LOOMREC_REDUCED_MOTION',
                               '--', 'apps', 'installer', 'tests', 'bin', 'docs/themes.md', 'AGENTS.md',
                               ':!tests/test_core_packaging.py'], capture_output=True, text=True).stdout
        self.assertEqual(hits, '')


    def test_capture_release_ships_theme_data(self):
        self.assertTrue((ROOT / 'apps/capture/wysun_core/tokens.json').is_file())
        source = (ROOT / 'apps/capture/loomrec/ui/tokens.py').read_text()
        self.assertIn('from wysun_core.qt_theme import', source)
        self.assertNotIn('theme_core', source)


    def test_capture_release_ships_the_fonts(self):
        for name in ('MaterialSymbolsRounded.ttf', 'GoogleSansFlex.ttf', 'CaskaydiaCoveNerdFont-Regular.ttf'):
            self.assertTrue((ROOT / 'apps/capture/wysun_core/fonts' / name).is_file(), name)
        self.assertFalse((ROOT / 'apps/python/wysun_core/fonts/Rubik-Variable.ttf').exists())

    def test_shell_and_core_fonts_are_identical(self):
        import hashlib
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        core, shell = ROOT / 'apps/python/wysun_core/fonts', ROOT / 'apps/shell/assets'
        for ours, theirs in (('MaterialSymbolsRounded.ttf', 'fonts/MaterialSymbolsRounded.ttf'),
                             ('GoogleSansFlex.ttf', 'google-sans-flex/GoogleSansFlex-VariableFont_GRAD,ROND,opsz,slnt,wdth,wght.ttf'),
                             ('CaskaydiaCoveNerdFont-Regular.ttf', 'fonts/CaskaydiaCoveNerdFont-Regular.ttf')):
            self.assertEqual(digest(core / ours), digest(shell / theirs), ours)

    def test_bundled_fonts_have_their_licences(self):
        for name in ('OFL-GoogleSansFlex.txt', 'OFL-CascadiaCode.txt', 'MIT-NerdFonts.txt'):
            self.assertTrue((ROOT / 'LICENSES' / name).is_file(), name)
        self.assertFalse((ROOT / 'LICENSES/OFL-Rubik.txt').exists())
        notes = (ROOT / 'THIRD_PARTY.md').read_text()
        for needle in ('Google Sans Flex', 'CaskaydiaCove', 'Nerd Fonts v3.4.0'):
            self.assertIn(needle, notes)
        self.assertFalse((ROOT / 'apps/capture/loomrec/ui/assets/fonts').exists())
        self.assertFalse((ROOT / 'apps/python/assets/fonts').exists())


if __name__ == '__main__':
    unittest.main()
