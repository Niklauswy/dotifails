"""DriveApp (layout B): panes, preview, chips, uploads through a child process, background, Recientes,
filter, narrow terminals, transparency and the login panels. The child gets fake wl-copy/notify-send."""
import json
import os
import shutil
import signal
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
from wysun_drive.ui import app as ui, preview  # noqa: E402


class Paste:
    def __init__(self, text):
        self.text = text


class DriveAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        runtime = self.base / 'run'
        runtime.mkdir(mode=0o700)
        bindir = self.base / 'bin'
        bindir.mkdir()
        for name in ('wl-copy', 'notify-send', 'xdg-open'):
            tool = bindir / name
            tool.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{self.base}/{name}.log"\n')
            tool.chmod(0o755)
        patcher = mock.patch.dict(os.environ, {
            'HOME': str(self.base), 'XDG_DATA_HOME': str(self.base / 'data'),
            'XDG_CONFIG_HOME': str(self.base / 'config'), 'XDG_STATE_HOME': str(self.base / 'state'),
            'XDG_RUNTIME_DIR': str(runtime), 'WYSUN_REDUCED_MOTION': '1', 'WYSUN_THEME': '',
            'PATH': f'{bindir}:{os.environ.get("PATH", "/usr/bin:/bin")}'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cloud = FakeNextcloud().__enter__()
        self.addCleanup(self.cloud.__exit__)
        self.work = self.base / 'trabajo'
        (self.work / 'fotos').mkdir(parents=True)
        (self.work / 'fotos/a.jpg').write_bytes(b'a' * 100)
        (self.work / 'informe.pdf').write_bytes(b'pdf')
        (self.work / 'notas.md').write_text('# Título\nprimera línea\n')
        (self.work / '.oculto').write_text('x')

    def login(self):
        account = self.base / 'data/wysun/drive/account.json'
        account.parent.mkdir(parents=True, mode=0o700)
        account.write_text(json.dumps({'server': self.cloud.url, 'user': USER, 'password': PASSWORD}))
        config = self.base / 'config/wysun/drive.json'
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({'server': self.cloud.url}))

    def make(self, width=120, height=34):
        term = VirtualTerminal(width, height)
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

    def wait_for(self, app, predicate, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.run_for(0.05)
            if predicate():
                return True
        return False

    def log(self, name):
        path = self.base / f'{name}.log'
        return path.read_text() if path.exists() else ''

    # -- browse -------------------------------------------------------------
    def test_two_panes_icons_quota_and_detail(self):
        self.login()
        app, term = self.make()
        self.assertTrue(self.wait_for(app, lambda: 'libres' in self.text(term)))
        screen = self.text(term)
        self.assertIn('Archivos', screen)
        self.assertIn('Detalle', screen)
        self.assertIn(preview.ICON['dir'], screen)
        self.assertLess(screen.index('fotos/'), screen.index('informe.pdf'))
        self.assertNotIn('.oculto', screen)
        self.assertIn('41,2 GB libres de 49,4 GB', screen)
        self.assertIn('1 carpeta · 2 archivos', screen)
        self.assertIn('Irá a', screen)
        self.press(app, b'\x1b[B\x1b[B')       # notas.md: its first lines are the preview
        self.assertTrue(self.wait_for(app, lambda: 'primera línea' in self.text(term)))
        self.press(app, b'.')
        self.assertIn('.oculto', self.text(term))

    def test_remote_existence_warning(self):
        self.login()
        self.cloud.state.dirs.add('Wysun')
        self.cloud.state.files['Wysun/informe.pdf'] = b'old'
        app, term = self.make()
        self.press(app, b'\x1b[B')             # informe.pdf
        self.assertTrue(self.wait_for(app, lambda: 'Ya existe en la nube' in self.text(term)))

    def test_chips_filter_and_mark_all(self):
        self.login()
        app, term = self.make()
        self.press(app, b'l')
        self.press(app, b'p')
        self.press(app, b'd')
        app.run_for(3.2)                        # let the toasts go so the tray is fully visible
        screen = self.text(term)
        self.assertIn('con link', screen)
        self.assertIn('contraseña', screen)
        self.assertIn('caduca 1 d', screen)
        self.press(app, b'/')
        for ch in b'not':
            self.press(app, bytes([ch]), wait=0.01)
        self.press(app, b'\r')
        self.assertEqual([e[0] for e in app.visible_entries()], ['notas.md'])
        self.press(app, b'a')
        self.assertEqual(app.marked, [str(self.work / 'notas.md')])
        self.press(app, b'\x1b')
        app.run_for(0.1)
        self.assertEqual(len(app.visible_entries()), 3)

    def test_help_overlay(self):
        self.login()
        app, term = self.make()
        self.press(app, b'?')
        self.assertIn('Teclas', self.text(term))
        self.press(app, b'x')
        self.assertNotIn('Teclas', self.text(term))

    def test_transparent_background(self):
        self.login()
        app, term = self.make()
        self.assertTrue(app.transparent)
        surface = app.palette['surface']
        rendered = app.screen.render(None, app._prev, transparent_bg=surface)
        self.assertNotIn(('48;2;%d;%d;%d' % surface).encode(), rendered)

    def test_narrow_terminal_hides_the_detail(self):
        self.login()
        app, term = self.make(width=80, height=24)
        screen = self.text(term)
        self.assertIn('Archivos', screen)
        self.assertNotIn('Detalle', screen)

    # -- upload ---------------------------------------------------------------
    def test_upload_with_link_through_a_child(self):
        self.login()
        app, term = self.make()
        self.press(app, b' ')              # fotos/
        self.press(app, b' ')              # informe.pdf
        self.press(app, b'l')
        app.run_for(3.2)
        self.assertIn('2 marcados', self.text(term))
        self.press(app, b'u')
        self.assertEqual(app.mode, 'uploading')
        self.assertTrue(self.wait_for(app, lambda: app.mode == 'done', seconds=20))
        screen = self.text(term)
        self.assertIn('Listo', screen)
        self.assertIn('/s/tok', screen)
        self.assertIn('2 links copiados', screen)
        self.assertEqual(self.cloud.state.files['Wysun/fotos/a.jpg'], b'a' * 100)
        self.assertIn('/s/tok', self.log('wl-copy'))
        self.assertEqual(self.log('notify-send'), '', 'no notification while the selector is open')
        self.assertNotIn(PASSWORD, screen)
        self.assertEqual(app.marked, [])
        self.assertEqual(list((self.base / 'run/wysun-drive').glob('*.json')), [])
        self.press(app, b'\r')
        self.assertEqual(app.mode, 'idle')

    def test_leaving_keeps_the_upload_running_and_it_notifies(self):
        self.login()
        app, term = self.make()
        self.press(app, b'\x1b[B')         # informe.pdf
        with mock.patch.object(ui.DriveApp, '_poll_child', lambda self: None):
            self.press(app, b'u')
            child = app.child
            child.send_signal(signal.SIGSTOP)   # still running when the selector closes
            self.press(app, b'b')
            child.send_signal(signal.SIGCONT)
        self.assertTrue(app._quitting)
        self.assertEqual(getattr(app, 'left_running', None), 'informe.pdf')
        child.wait(timeout=20)
        self.assertEqual(child.returncode, 0)
        self.assertIn('Wysun/informe.pdf', self.cloud.state.files)
        self.assertIn('Subido a Wysun Drive', self.log('notify-send'))

    # -- Recientes ---------------------------------------------------------------
    def test_recent_groups_link_remove_and_new(self):
        self.login()
        app, term = self.make()
        self.press(app, b'\x1b[B')         # informe.pdf, no link
        self.press(app, b'u')
        self.assertTrue(self.wait_for(app, lambda: app.mode == 'done', seconds=20))
        self.press(app, b'\r')
        self.press(app, b'2')
        screen = self.text(term)
        self.assertIn('Recientes', screen)
        self.assertIn('Hoy', screen)
        self.assertIn('desde la terminal', screen)
        self.assertIn('Sin link', screen)
        with mock.patch.object(ui, 'copy', return_value=True) as copied:
            self.press(app, b'c')
            self.assertTrue(self.wait_for(app, lambda: copied.called))
        self.assertIn('/s/tok1', copied.call_args.args[0])
        self.assertTrue(self.wait_for(app, lambda: '/s/tok1' in self.text(term)))
        self.press(app, b'k')
        self.assertTrue(self.wait_for(app, lambda: 'Link quitado' in self.text(term)))
        self.assertEqual(self.cloud.state.shares, {})

    def test_pasted_paths_are_marked(self):
        self.login()
        app, term = self.make()
        app.on_paste(Paste(f"file://{self.work / 'informe.pdf'}\n'{self.work / 'fotos'}'"))
        app.run_for(0.05)
        self.assertEqual(sorted(app.marked), sorted([str(self.work / 'informe.pdf'), str(self.work / 'fotos')]))

    # -- login ----------------------------------------------------------------------
    def test_login_panel_edits_the_server(self):
        app, term = self.make()
        self.assertIn('Servidor: https://cloud.wysun.store', self.text(term))
        self.press(app, b's')
        for _ in range(len('https://cloud.wysun.store')):
            self.press(app, b'\x7f', wait=0)
        with mock.patch('wysun_drive.login.INTERVAL', 0), mock.patch.object(ui, 'open_url', return_value=True):
            app.on_paste(Paste(self.cloud.url))
            self.press(app, b'\r')
            self.assertTrue(self.wait_for(app, lambda: app.account is not None))
        settings = json.loads((self.base / 'config/wysun/drive.json').read_text())
        self.assertEqual(settings['server'], self.cloud.url)

    def test_manual_app_password_from_the_login_panel(self):
        config = self.base / 'config/wysun/drive.json'
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({'server': self.cloud.url}))
        app, term = self.make()
        self.press(app, b'p')
        for chunk in (USER.encode(), b'\r', PASSWORD.encode()):
            self.press(app, chunk)
        screen = self.text(term)
        self.assertIn('•' * len(PASSWORD), screen)
        self.assertNotIn(PASSWORD, screen)
        self.press(app, b'\r')
        self.assertTrue(self.wait_for(app, lambda: app.account is not None))
        self.assertEqual(app.tab, 'browse')
        self.assertNotIn(PASSWORD, self.text(term))


class PreviewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg not installed')
    def test_image_becomes_half_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'p.png'
            import subprocess
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=8x8', '-frames:v', '1', str(path)],
                           check=True)
            item = preview.build(str(path), 4, 2)
        self.assertEqual(item['kind'], 'image')
        self.assertEqual((len(item['pixels']), len(item['pixels'][0])), (2, 4))
        top, _bottom = item['pixels'][0][0]
        self.assertGreater(top[0], 200)

    def test_when_and_groups(self):
        now = time.mktime((2026, 11, 5, 15, 0, 0, 0, 0, -1))
        self.assertTrue(preview.when(now - 60, now).startswith('hoy '))
        self.assertEqual(preview.when(now - 86400, now), 'ayer')
        self.assertEqual(preview.group_of(now - 3 * 86400, now), 'Esta semana')
        self.assertEqual(preview.when(now - 40 * 86400, now), '26 sep')
        self.assertEqual(preview.kind_of('Informe.PDF'), 'pdf')


if __name__ == '__main__':
    unittest.main()
