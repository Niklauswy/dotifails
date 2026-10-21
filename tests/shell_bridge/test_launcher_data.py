"""Native launcher parity: data provider (isolated HOME) and QML wiring."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'apps/wysun/launcher_data.py'
LAUNCHER = ROOT / 'apps/shell/modules/launcher'


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        (Path(self.home.name) / 'Downloads').mkdir()
        (Path(self.home.name) / 'Downloads/informe-final.txt').write_text('x')
        self.env = dict(os.environ, HOME=self.home.name)
        sys.path.insert(0, str(ROOT / 'apps/wysun'))

    def run_cli(self, *args):
        result = subprocess.run([sys.executable, '-I', str(SCRIPT), *args], env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if args[0] == 'query' else result.stdout

    def seed(self):
        code = ('import sys; sys.path.insert(0, %r); from core import Store; s = Store();'
                's.clip("text", "hola mundo"); s.clip("color", "#ff8800"); s.clip("url", "https://example.org");'
                's.save_snippet("Saludo", "hola", "Hola {date}")') % str(ROOT / 'apps/wysun')
        subprocess.run([sys.executable, '-I', '-c', code], env=self.env, check=True, timeout=30)

    def test_calculator_emoji_and_files(self):
        calc = self.run_cli('query', 'calc', '2+3*4')
        self.assertEqual((calc[0]['kind'], calc[0]['value']), ('calc', '14'))
        self.assertEqual(self.run_cli('query', 'calc', 'no es una cuenta'), [])
        self.assertIn('🚀', self.run_cli('query', 'emoji', 'cohete')[0]['value'])
        files = self.run_cli('query', 'files', 'informe')
        self.assertEqual(files[0]['title'], 'informe-final.txt')
        self.assertTrue(files[0]['path'].startswith(self.home.name))

    def test_history_records_and_clipboard_filters_and_deletes(self):
        self.assertEqual(self.run_cli('query', 'calc', ''), [])
        self.run_cli('act', 'record-calc', '1+1', '2')
        self.assertEqual(self.run_cli('query', 'calc', '')[0]['query'], '1+1')
        self.seed()
        kinds = {r['clip_kind'] for r in self.run_cli('query', 'clip', '')}
        self.assertEqual(kinds, {'text', 'color', 'url'})
        colour = self.run_cli('query', 'clip', 'color')
        self.assertEqual([r['swatch'] for r in colour], ['#ff8800'])
        text = self.run_cli('query', 'clip', 'texto hola')
        self.assertEqual([r['value'] for r in text], ['hola mundo'])
        self.run_cli('act', 'delete-clip', str(text[0]['id']))
        self.assertEqual(self.run_cli('query', 'clip', 'texto'), [])
        snippet = self.run_cli('query', 'snippets', 'hola')[0]
        self.assertNotIn('{date}', snippet['value'])
        self.run_cli('act', 'delete-snippet', str(snippet['id']))
        self.assertEqual(self.run_cli('query', 'snippets', ''), [])

    def test_unknown_mode_and_action_fail_safely(self):
        self.assertEqual(self.run_cli('query', 'nope', '')[0]['kind'], 'error')
        result = subprocess.run([sys.executable, '-I', str(SCRIPT), 'act', 'rm-rf'], env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)


class WiringTests(unittest.TestCase):
    def test_every_mode_is_reachable_from_the_launcher(self):
        service = (LAUNCHER / 'services/LauncherData.qml').read_text()
        actions = (LAUNCHER / 'services/WysunActions.js').read_text()
        for mode, alias in [('clip', 'clip'), ('files', 'files'), ('snippets', 'snip'),
                            ('windows', 'win'), ('emoji', 'emoji'), ('calc', 'hist')]:
            self.assertRegex(service, rf'\b{mode}: \[[^\]]*"{alias}"')
            self.assertIn(f'["autocomplete", "{alias}"]', actions)
        self.assertIn('["autocomplete", "run"]', actions)
        applist = (LAUNCHER / 'AppList.qml').read_text()
        for needle in ('name: "data"', 'name: "run"', 'return "calc"', 'LauncherData.parse'):
            self.assertIn(needle, applist)

    def test_provider_runs_argv_without_a_shell_and_keeps_qt_fallback(self):
        service = (LAUNCHER / 'services/LauncherData.qml').read_text()
        self.assertNotIn('"sh", "-c", script', service)
        self.assertIn('"python3", "-I", script', service)
        wysun = (ROOT / 'bin/wysun').read_text()
        self.assertIn("WYSUN_LAUNCHER=qt", wysun)
        self.assertIn("os.execv(str(executable)", wysun)

    def test_shortcuts_row_actions_exist(self):
        content = (LAUNCHER / 'Content.qml').read_text()
        for needle in ('Qt.Key_Delete', 'openFolder', 'copyPath', 'webRow'):
            self.assertIn(needle, content)


if __name__ == '__main__':
    unittest.main()
