"""Wysun Player's libmpv items in a QML scene (venv Python): the software item shows the frames of a synthetic clip
and stops its thread on release; the OpenGL item draws them and frees mpv's context before the core closes (only with
a real GL session: WYSUN_TEST_GL=1 under Wayland); the renderer choice follows WYSUN_PLAYER_RENDERER."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
os.environ.setdefault('QSG_RENDER_LOOP', 'basic')
os.environ['WYSUN_MPV_OPTIONS'] = 'ao=null'
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402


def make_clip(folder, name='clip.mp4', seconds=2):
    path = Path(folder) / name
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc=size=320x180:rate=30:duration={seconds}',
                    '-pix_fmt', 'yuv420p', str(path)], check=True, timeout=60)
    return path


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg needed for the synthetic clip')
class VideoItemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()
        from wysun_player.quick import video
        video.register()
        cls.video = video
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(prefix='player-video-', dir=scratch)
        cls.clip = make_clip(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def scene(self, element):
        from PySide6.QtCore import QUrl
        from PySide6.QtQuick import QQuickView
        from wysun_media.session import MediaSession
        session = MediaSession(options={'ao': 'null', 'hwdec': 'no'})
        view = QQuickView()
        view.rootContext().setContextProperty('mediaSession', session)
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        qml = Path(self.tmp.name) / f'{element}.qml'
        qml.write_text(f'import QtQuick\nimport Wysun.Player\n{element} {{ width: 320; height: 180; session: mediaSession }}\n')
        view.setSource(QUrl.fromLocalFile(str(qml)))
        self.assertEqual(view.status(), QQuickView.Ready, [e.toString() for e in view.errors()])
        view.resize(320, 180)
        view.show()
        return session, view

    def bright(self, image):
        return max(image.pixelColor(x, y).lightness() for x in range(0, image.width(), 16) for y in range(0, image.height(), 16))

    def test_software_item_shows_frames_and_stops_its_thread(self):
        from wysun_media.source import open_source
        session, view = self.scene('MpvSoftwareVideo')
        item = view.rootObject()
        session.open(open_source(self.clip))
        self.assertTrue(self.h.wait_for(lambda: item.property('frames') > 3, 8000), 'no frames arrived')
        self.assertGreater(self.bright(view.grabWindow()), 40)
        thread = item._thread
        item.release()
        self.assertFalse(thread.is_alive())
        session.close()
        view.close()
        view.deleteLater()
        self.h.pump(50)

    def test_renderer_choice(self):
        os.environ['WYSUN_PLAYER_RENDERER'] = 'software'
        try:
            self.assertEqual(self.video.renderer_name(), 'software')
        finally:
            del os.environ['WYSUN_PLAYER_RENDERER']
        self.assertIn(self.video.renderer_name(), ('opengl', 'software'))

    @unittest.skipUnless(os.environ.get('WYSUN_TEST_GL') == '1', 'needs a real GL session (WYSUN_TEST_GL=1, Wayland)')
    def test_gl_item_draws_and_frees_its_context_before_the_core(self):
        from wysun_media.source import open_source
        session, view = self.scene('MpvVideo')
        item = view.rootObject()
        session.open(open_source(self.clip))
        self.assertTrue(self.h.wait_for(lambda: item._context is not None and session.position > .3, 8000))
        self.assertGreater(self.bright(view.grabWindow()), 40)
        item.release()
        self.assertIsNone(item._context)
        session.close()
        view.close()
        view.deleteLater()
        self.h.pump(50)


if __name__ == '__main__':
    unittest.main()
