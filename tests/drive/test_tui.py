"""DriveApp: browsing, marking, uploading with links, Recientes, pasted paths and the login panel."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_nextcloud import PASSWORD, USER, FakeNextcloud  # noqa: E402
from wysun_core.tui.testing import VirtualTerminal  # noqa: E402
from wysun_drive.ui import app as ui  # noqa: E402


class DriveAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        runtime = self.base / 'run'
        runtime.mkdir(mode=0o700)
        patcher = mock.patch.dict(os.environ, {
            'HOME': str(self.base), 'XDG_DATA_HOME': str(self.base / 'data'),
            'XDG_CONFIG_HOME': str(self.base / 'config'), 'XDG_STATE_HOME': str(self.base / 'state'),
            'XDG_RUNTIME_DIR': str(runtime), 'WYSUN_REDUCED_MOTION': '1', 'WYSUN_THEME': ''})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cloud = FakeNextcloud().__enter__()
        self.addCleanup(self.cloud.__exit__)
        self.copied = []
        for target in ('wysun_drive.ui.app.copy',):
            p = mock.patch(target, side_effect=lambda text: self.copied.append(text) or True)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch('wysun_drive.ui.app.open_url', return_value=True)
        self.opened = p.start()
        self.addCleanup(p.stop)
        self.work = self.base / 'trabajo'
        (self.work / 'fotos').mkdir(parents=True)
        (self.work / 'fotos/a.jpg').write_bytes(b'a' * 100)
        (self.work / 'informe.pdf').write_bytes(b'pdf')
        (self.work / '.oculto').write_text('x')

    def login(self):
        account = self.base / 'data/wysun/drive/account.json'
        account.parent.mkdir(parents=True, mode=0o700)
        account.write_text(json.dumps({'server': self.cloud.url, 'user': USER, 'password': PASSWORD}))

    def make(self):
        term = VirtualTerminal(100, 30)
        self.addCleanup(term.close)
        app = ui.DriveApp(term=term, home=str(self.base), start=self.work)
        self.addCleanup(app.close)
        app.run_for(0.05)
        return app, term

    def press(self, app, data, wait=0.05):
        app.term.feed_input(data)
        app.step()
        app.run_for(wait)

    def text(self, term):
        return '\n'.join(term.canvas_text())

    def wait_for(self, app, predicate, seconds=5):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.run_for(0.05)
            if predicate():
                return True
        return False

    def test_lists_folder_dirs_first_hidden_off(self):
        self.login()
        app, term = self.make()
        screen = self.text(term)
        self.assertIn('Wysun Drive', screen)
        self.assertIn(f'{USER} · 127.0.0.1', screen)
        self.assertLess(screen.index('fotos/'), screen.index('informe.pdf'))
        self.assertNotIn('.oculto', screen)
        self.press(app, b'.')
        self.assertIn('.oculto', self.text(term))

    def test_mark_upload_with_link_and_recent(self):
        self.login()
        app, term = self.make()
        self.press(app, b' ')            # mark fotos/, cursor moves to informe.pdf
        self.press(app, b' ')            # mark informe.pdf
        self.press(app, b'l')
        self.assertIn('2 marcados', self.text(term))
        self.press(app, b'u')
        self.assertTrue(self.wait_for(app, lambda: app.finished))
        screen = self.text(term)
        self.assertIn('Listo', screen)
        self.assertIn('/s/tok', screen)
        self.assertEqual(self.cloud.state.files['Wysun/fotos/a.jpg'], b'a' * 100)
        self.assertEqual(len(self.copied[-1].splitlines()), 2)
        self.assertNotIn(PASSWORD, screen)
        self.press(app, b'\r')          # close the overlay
        self.press(app, b'\t')
        screen = self.text(term)
        self.assertIn('Subidos recientemente', screen)
        self.assertIn('informe.pdf', screen)
        self.press(app, b'c')
        self.assertIn('/s/tok', self.copied[-1])
        self.assertEqual(list((self.base / 'run/wysun-drive').glob('*.json')), [])

    def test_recent_without_link_makes_one(self):
        self.login()
        app, term = self.make()
        self.press(app, b'\x1b[B')      # informe.pdf
        self.press(app, b'u')
        self.assertTrue(self.wait_for(app, lambda: app.finished))
        self.assertEqual(self.copied, [])
        self.press(app, b'\r')
        self.press(app, b'2')
        self.assertIn('sin link', self.text(term))
        self.press(app, b'c')
        self.assertTrue(self.wait_for(app, lambda: bool(self.copied)))
        self.assertIn('/s/tok1', self.copied[-1])

    def test_pasted_paths_are_marked(self):
        self.login()
        app, term = self.make()
        pasted = f"file://{self.work / 'informe.pdf'}\n'{self.work / 'fotos'}'"
        app.on_paste(ui.Paste(pasted) if hasattr(ui, 'Paste') else type('P', (), {'text': pasted})())
        app.run_for(0.05)
        self.assertEqual(sorted(app.marked), sorted([str(self.work / 'informe.pdf'), str(self.work / 'fotos')]))

    def test_without_session_shows_login_and_logs_in(self):
        app, term = self.make()
        self.assertIn('aún no tiene sesión', self.text(term))
        with mock.patch('wysun_drive.account.settings', return_value={'server': self.cloud.url, 'folder': 'Wysun'}), \
                mock.patch('wysun_drive.login.INTERVAL', 0):
            self.press(app, b'\r')
            self.assertTrue(self.wait_for(app, lambda: app.account is not None, seconds=10))
        self.opened.assert_called()
        self.assertEqual(app.tab, 'browse')
        self.assertTrue((self.base / 'data/wysun/drive/account.json').exists())


if __name__ == '__main__':
    unittest.main()
