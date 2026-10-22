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
        self.env = dict(os.environ, HOME=self.home.name, XDG_DATA_HOME=str(Path(self.home.name) / '.local/share'), XDG_CONFIG_HOME=str(Path(self.home.name) / '.config'), XDG_STATE_HOME=str(Path(self.home.name) / '.local/state'))
        sys.path.insert(0, str(ROOT / 'apps/wysun'))

    def run_cli(self, *args):
        result = subprocess.run([sys.executable, '-I', str(SCRIPT), *args], env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if args[0] == 'query' else result.stdout

    def seed(self):
        code = ('import sys; sys.path.insert(0, %r); from core import Store; s = Store();'
                's.clip("text", "hola mundo"); s.clip("color", "#ff8800"); s.clip("url", "https://example.org")') % str(ROOT / 'apps/wysun')
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

    def test_removed_snippet_and_window_modes_are_rejected(self):
        for mode in ('snippets', 'windows'):
            self.assertEqual(self.run_cli('query', mode, '')[0]['kind'], 'error', mode)

    def test_discover_includes_math_conversions_and_files_without_prefix(self):
        result = self.run_cli('query', 'all', '15% of 80')
        self.assertEqual((result[0]['kind'], result[0]['value'], result[0]['section']), ('calc', '12', 'Calculator'))
        result = self.run_cli('query', 'all', '10 km to mi')
        self.assertEqual(result[0]['value'], '6.21371192237 mi')
        self.assertEqual(self.run_cli('query', 'all', 'informe')[0]['kind'], 'file')

    def test_recent_documents_use_xdg_history_and_ignore_remote_and_missing_files(self):
        data = Path(self.home.name) / 'xdg-data'
        data.mkdir()
        doc = Path(self.home.name) / 'Downloads/informe-final.txt'
        (data / 'recently-used.xbel').write_text(f'''<xbel>
          <bookmark href="{doc.as_uri()}" visited="2026-10-21T12:00:00Z"/>
          <bookmark href="file://remote/private.txt" visited="2026-10-21T13:00:00Z"/>
          <bookmark href="file:///missing.txt" visited="2026-10-21T14:00:00Z"/>
        </xbel>''')
        self.env['XDG_DATA_HOME'] = str(data)
        self.assertEqual([r['path'] for r in self.run_cli('query', 'files', '')], [str(doc)])

    def test_emoji_has_categories_and_supports_english_and_spanish_search(self):
        for query in ('rocket', 'cohete', '🚀'):
            rows = self.run_cli('query', 'emoji', query)
            self.assertEqual(rows[0]['value'], '🚀')
            self.assertEqual(rows[0]['category'], 'Travel')
        self.assertGreater(len(self.run_cli('query', 'emoji', '')), 1000)

    def test_unknown_mode_and_action_fail_safely(self):
        self.assertEqual(self.run_cli('query', 'nope', '')[0]['kind'], 'error')
        result = subprocess.run([sys.executable, '-I', str(SCRIPT), 'act', 'rm-rf'], env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)


class WiringTests(unittest.TestCase):
    def test_single_floating_panel_without_tabs_or_prefixes(self):
        panel = (LAUNCHER / 'LauncherPanel.qml').read_text()
        self.assertIn('Search apps, files, commands...', panel)
        for gone in ('actionPrefix', 'specialPrefix', 'Catalog.categories'):
            self.assertNotIn(gone, panel)
        self.assertFalse((LAUNCHER / 'Content.qml').exists())
        self.assertFalse((LAUNCHER / 'Wrapper.qml').exists())
        window = (LAUNCHER / 'Launcher.qml').read_text()
        self.assertIn('anchors.top: true', window)
        self.assertIn('WlrLayer.Overlay', window)
        emoji = (LAUNCHER / 'EmojiPicker.qml').read_text()
        self.assertIn('anchors.bottom: true', emoji)
        self.assertIn('mode: "emoji"', emoji)
        self.assertIn('GridView', emoji)

    def test_provider_runs_argv_without_a_shell_and_has_no_qt_fallback(self):
        service = (LAUNCHER / 'services/LauncherData.qml').read_text()
        self.assertNotIn('"sh", "-c", script', service)
        self.assertIn('"python3", "-I", script', service)
        wysun = (ROOT / 'bin/wysun').read_text()
        self.assertNotIn("WYSUN_LAUNCHER", wysun)

    def test_keyboard_actions_and_views_exist(self):
        panel = (LAUNCHER / 'LauncherPanel.qml').read_text()
        for needle in ('Qt.Key_K', 'Qt.Key_Delete', 'Qt.Key_Backspace', 'Qt.Key_Tab', 'Qt.Key_1', 'Qt.Key_Escape',
                       'function push', 'function pop', 'LauncherData.paste'):
            self.assertIn(needle, panel)
        actions = (LAUNCHER / 'services/Actions.js').read_text()
        for needle in ('Show in Folder', 'Copy Path', 'Open With', 'Pin to Favorites', 'Paste to Previous Window'):
            self.assertIn(needle, actions)
        for gone in ('Close Window', 'Snippet'):
            self.assertNotIn(gone, actions)

    def test_no_synchronous_process_per_keystroke(self):
        index = (LAUNCHER / 'services/LauncherIndex.qml').read_text()
        self.assertIn('SplitParser', index)  # streaming file search
        panel = (LAUNCHER / 'LauncherPanel.qml').read_text()
        self.assertIn('interval: 120', panel)  # debounce
        self.assertNotIn('python3', panel)
        self.assertIn('reuseItems: true', panel)


if __name__ == '__main__':
    unittest.main()
