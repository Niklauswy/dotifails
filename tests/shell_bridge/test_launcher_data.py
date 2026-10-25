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
        self.env = dict(os.environ, HOME=self.home.name, XDG_DATA_HOME=str(Path(self.home.name) / '.local/share'), XDG_CONFIG_HOME=str(Path(self.home.name) / '.config'), XDG_STATE_HOME=str(Path(self.home.name) / '.local/state'), XDG_CACHE_HOME=str(Path(self.home.name) / '.cache'))
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

    def test_tree_index_lists_nested_files_and_folders_without_hidden_or_noise(self):
        home = Path(self.home.name)
        (home / 'Documents/Facturas/2024').mkdir(parents=True)
        (home / 'Documents/Facturas/2024/marzo.pdf').write_text('x')
        (home / '.cache').mkdir()
        (home / '.cache/oculto.txt').write_text('x')
        (home / 'proyecto/node_modules/dep').mkdir(parents=True)
        (home / 'proyecto/node_modules/dep/index.js').write_text('x')
        self.run_cli('files-index')
        lines = (home / '.local/share/orbit/launcher-files.idx').read_text().split('\n')
        self.assertIn('dDocuments/Facturas/2024', lines)
        self.assertIn('fDocuments/Facturas/2024/marzo.pdf', lines)
        self.assertIn('dproyecto', lines)
        self.assertFalse([x for x in lines if 'node_modules' in x or '.cache/' in x])

    def seed_image(self, text):
        code = ('import sys; sys.path.insert(0, %r); from data_v2 import StoreV2; from core import STATE; s = StoreV2(STATE);'
                'i = s.clip("image", "", b"\\x89PNG"); s.db.execute("UPDATE clips SET ocr=?, ocr_done=1 WHERE id=?", (%r, i)); s.db.commit()') % (str(ROOT / 'apps/wysun'), text)
        subprocess.run([sys.executable, '-I', '-c', code], env=self.env, check=True, timeout=30)

    def test_images_are_found_by_their_recognized_text(self):
        self.seed()
        self.seed_image('Factura\n\nTotal a pagar: 1,250 pesos\n\nCafetería Ñandú')
        rows = self.run_cli('query', 'clip', 'total pagar')
        self.assertEqual([r['clip_kind'] for r in rows], ['image'])
        self.assertEqual(rows[0]['ocr'], 'Factura\nTotal a pagar: 1,250 pesos\nCafetería Ñandú')
        self.assertEqual(len(self.run_cli('query', 'clip', 'cafeteria nandu')), 1)  # accent-insensitive
        self.assertEqual(self.run_cli('query', 'clip', 'texto total'), [])  # kind prefix still filters
        self.assertEqual(len(self.run_cli('query', 'clip', 'imagen total')), 1)

    def test_code_preview_uses_the_neovim_theme(self):
        home = Path(self.home.name)
        nvim = home / '.config/nvim/lua'
        nvim.mkdir(parents=True)
        (nvim / 'chadrc.lua').write_text('''local M = {}
M.base46 = { theme = "demo", transparency = true, changed_themes = { demo = { base_16 = { base0E = "#112233" } } },
  hl_override = { Comment = { fg = "#445566", italic = true }, LineNr = { fg = "#778899" } } }
return M''')
        themes = home / '.local/share/nvim/lazy/base46/lua/base46/themes'
        themes.mkdir(parents=True)
        base = {f'base{i:02X}': f'#{i:02x}{i:02x}{i:02x}' for i in range(16)}
        base['base00'] = '#0a0b0c'
        (themes / 'demo.lua').write_text('M.base_16 = {' + ','.join(f'{k} = "{v}"' for k, v in base.items()) + '}')
        source = home / 'Downloads/sample.py'
        source.write_text('def f():\n    return "x"  # note\n')
        result = subprocess.run([sys.executable, '-I', str(SCRIPT), 'code-preview', str(source)], env=self.env, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        self.assertEqual((data['bg'], data['lineNr'], data['lexer'], data['transparent']), ('#0a0b0c', '#778899', 'Python', True))
        self.assertIn('<font color="#112233">def&nbsp;</font>', data['html'])  # keyword colour from changed_themes
        self.assertIn('<font color="#445566"><i>#&nbsp;note', data['html'])  # Comment override
        self.assertNotIn('<span', data['html'])  # StyledText subset, not RichText
        self.assertEqual(data['lines'], 2)
        # A second preview of the unchanged file comes from the cache; editing the file refreshes it.
        cached = subprocess.run([sys.executable, '-I', str(SCRIPT), 'code-preview', str(source)], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(json.loads(cached.stdout), data)
        self.assertTrue(any((home / '.cache/wysun/code-preview').glob('*.json')))
        source.write_text('x = 1\n' * 500)
        long = json.loads(subprocess.run([sys.executable, '-I', str(SCRIPT), 'code-preview', str(source)], env=self.env, capture_output=True, text=True, timeout=30).stdout)
        self.assertEqual((long['lines'], long['text'].count('\n') + 1), (500, 120))  # whole count, first lines shown
        source.write_text('def f():\n    return "x"  # note\n')
        # Without an Neovim setup the text still comes back and the launcher keeps its own colours.
        plain = subprocess.run([sys.executable, '-I', str(SCRIPT), 'code-preview', str(source)], env=dict(self.env, XDG_CONFIG_HOME=str(home / 'none')), capture_output=True, text=True, timeout=30)
        self.assertNotIn('html', json.loads(plain.stdout))
        self.assertIn('def f()', json.loads(plain.stdout)['text'])

    def test_hidden_files_are_indexed_and_config_is_entered(self):
        home = Path(self.home.name)
        (home / '.zshrc').write_text('x')
        (home / '.config/nvim').mkdir(parents=True)
        (home / '.config/nvim/init.lua').write_text('x')
        (home / '.config/Brave/Local Storage').mkdir(parents=True)
        (home / '.config/Brave/Cache').mkdir()
        (home / '.config/Brave/Cache/blob').write_text('x')
        (home / '.local/share/junk').mkdir(parents=True)
        (home / '.local/share/junk/a').write_text('x')
        self.run_cli('files-index')
        lines = (home / '.local/share/orbit/launcher-files.idx').read_text().split('\n')
        self.assertIn('f.zshrc', lines)
        self.assertIn('f.config/nvim/init.lua', lines)
        self.assertFalse([x for x in lines if 'Brave/Cache' in x or '.local/share/junk/' in x])

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

    def test_editor_morph_and_window_rule_are_wired(self):
        self.assertTrue((LAUNCHER / 'EditMorph.qml').is_file() and (LAUNCHER / 'services/Editor.qml').is_file())
        self.assertIn('EditMorph {}', (LAUNCHER / 'Launcher.qml').read_text())
        self.assertIn('Editor.open(', (LAUNCHER / 'LauncherPanel.qml').read_text())
        # The editor is an ordinary tiled window: its only rule maps it unseen (no float), the card flies onto its
        # real tile and the shell makes it visible on landing.
        rules = [l for l in (ROOT / 'config/.config/wysun/hyprland.lua').read_text().splitlines() if 'wysun\\\\.edit' in l]
        self.assertEqual(len(rules), 1)
        self.assertIn('no_anim = true', rules[0])
        self.assertIn('opacity = "0 override"', rules[0])
        self.assertNotIn('float', rules[0])
        editor = (LAUNCHER / 'services/Editor.qml').read_text()
        self.assertIn('function followWindow()', editor)
        self.assertIn('prop = "${prop}", value = "1 override"', editor)
        # Every state the rule hid comes back, or the editor vanishes again when it loses focus.
        self.assertIn('["opacity", "opacity_inactive", "opacity_fullscreen"]', editor)
        self.assertIn('Component.onCompleted', editor)  # a restarted shell never leaves an editor invisible
        self.assertIn('stage.mapToItem', (LAUNCHER / 'LauncherPanel.qml').read_text())  # the card starts on the preview
        self.assertNotIn('float', editor)

    def test_no_synchronous_process_per_keystroke(self):
        index = (LAUNCHER / 'services/LauncherIndex.qml').read_text()
        self.assertIn('source: "FileSearchWorker.mjs"', index)  # in-memory index, no process per query
        worker = (LAUNCHER / 'services/FileSearchWorker.mjs').read_text()
        self.assertIn('FileSearch.search', worker)  # searched off the GUI thread
        self.assertNotIn('"find", home', index.split('function searchFiles')[1].split('function decorateClips')[0])
        panel = (LAUNCHER / 'LauncherPanel.qml').read_text()
        self.assertIn('interval: 30', panel)  # debounce
        self.assertNotIn('python3', panel)
        self.assertIn('reuseItems: true', panel)


if __name__ == '__main__':
    unittest.main()
