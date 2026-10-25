"""Recorder plays recordings through the shared Wysun player, under its own theme and header."""
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['WYSUN_MPV_OPTIONS'] = 'ao=null'
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication


def pump(predicate, timeout=10):
    app = QApplication.instance()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(.01)
    return False


class PlayerComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.folder = tempfile.TemporaryDirectory()
        cls.video = Path(cls.folder.name) / 'recording.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10:duration=4', '-f', 'lavfi', '-i',
                        'sine=frequency=440:duration=4', '-pix_fmt', 'yuv420p', '-shortest', str(cls.video)], check=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def page(self):
        from loomrec.ui.app_pages import PlayerPage
        with patch.dict(os.environ, {'WYSUN_PLAYER_RENDERER': 'software'}):
            page = PlayerPage()
        page.resize(640, 420)
        page.show()
        self.addCleanup(self.finish, page)
        page.messages = []
        page.message.connect(page.messages.append)
        return page

    def finish(self, page):
        page.shutdown()
        page.close()
        page.deleteLater()
        from wysun_media import mpv
        self.app.processEvents()
        mpv.wait_closed()

    def item(self):
        return SimpleNamespace(video=self.video, title='Mi grabación')

    def test_a_recording_plays_directly_and_creates_nothing(self):
        before = sorted(p.name for p in self.video.parent.iterdir())
        page = self.page()
        page.load(self.item())
        self.assertTrue(pump(lambda: page.player.session.state == 'playing'))
        self.assertEqual(page.title.text(), 'Mi grabación')
        self.assertEqual(page.player.kind, 'video')
        self.assertEqual(sorted(p.name for p in self.video.parent.iterdir()), before, 'watching must not export another file')

    def test_the_player_uses_recorders_theme_tokens(self):
        from loomrec.ui import tokens
        from wysun_media import host
        page = self.page()
        values = tokens.tokens()
        self.assertEqual(host.get().token('corner_xl'), values['corner_xl'])
        self.assertEqual(host.get().color('hud').name(), tokens.color('hud').name())
        self.assertEqual(page.player.mode, 'embedded')
        self.assertEqual(page.player.rounding.corner, 'xl')

    def test_keys_reach_the_player_when_the_page_has_focus(self):
        page = self.page()
        self.assertIs(page.focusProxy(), page.player)

    def test_stop_returns_to_idle_and_shutdown_releases_the_core(self):
        page = self.page()
        page.load(self.item())
        pump(lambda: page.player.session.state == 'playing')
        page.stop()
        self.assertEqual(page.player.session.state, 'idle')
        page.shutdown()
        self.assertIsNone(page.player.session.core)

    def test_a_missing_recording_reports_instead_of_raising(self):
        page = self.page()
        page.load(SimpleNamespace(video=self.video.with_name('gone.mp4'), title='Perdida'))
        self.assertTrue(page.player.note.isVisible())
        self.assertTrue(pump(lambda: page.messages))
        self.assertIn('archivo', page.messages[0].lower())

    def test_opening_in_wysun_player_continues_at_the_same_place_and_pauses_the_preview(self):
        page = self.page()
        page.load(self.item())
        pump(lambda: page.player.session.state == 'playing')
        page.player.session.seek(2.0)
        pump(lambda: abs(page.player.session.position - 2.0) < .4)
        with patch('subprocess.Popen') as popen:
            page.external.click()
        argv = popen.call_args.args[0]
        self.assertTrue(argv[0].endswith('wysun-player'))
        self.assertEqual(argv[argv.index('--') + 1], str(self.video))
        self.assertAlmostEqual(float(argv[argv.index('--start') + 1]), 2.0, delta=.5)
        self.assertTrue(pump(lambda: page.player.session.state == 'paused'))

    def test_software_frames_are_opaque_over_any_desktop(self):
        page = self.page()
        page.load(self.item())
        view = None
        pump(lambda: page.player._video is not None)
        view = page.player._video
        self.assertTrue(pump(lambda: not view._image.isNull(), 10))
        rendered = QImage(view.size(), QImage.Format_ARGB32_Premultiplied)
        rendered.fill(0)
        view.render(rendered)
        for x in range(0, rendered.width(), 31):
            for y in range(0, rendered.height(), 23):
                self.assertEqual(rendered.pixelColor(x, y).alpha(), 255)


if __name__ == '__main__':
    unittest.main()
