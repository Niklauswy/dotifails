"""Native backend selection with synthetic widgets, no external WM or media."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication


class NativeUiBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        # QApplication is already offscreen; these variables exercise the actual
        # native guard even when an XWayland DISPLAY also exists.
        self.env=patch.dict(os.environ,dict(WAYLAND_DISPLAY='synthetic-wayland',XDG_SESSION_TYPE='wayland',DISPLAY=':synthetic-xwayland',QT_QPA_PLATFORM='wayland',XDG_CONFIG_HOME=self.temp.name))
        self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def test_native_player_embeds_without_winid_or_mpv_subprocess(self):
        import subprocess
        from PySide6.QtCore import QProcess
        from wysun_media import mpv
        from wysun_media.player import MediaPlayer
        from wysun_recorder.ui import media_host
        media_host.install()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=160x90:rate=10:duration=2','-pix_fmt','yuv420p',str(path)],check=True,timeout=60)
            with patch.dict(os.environ,{'WYSUN_MPV_OPTIONS':'ao=null'}),patch.object(QProcess,'start') as spawn:
                player=MediaPlayer(mode='embedded',renderer='software');player.resize(320,200);player.show()
                self.assertTrue(player.open(path))
                with patch.object(player._video,'winId',side_effect=AssertionError('native embedding needs no XID')):
                    end=__import__('time').monotonic()+10
                    while player.session.state!='playing' and __import__('time').monotonic()<end:self.app.processEvents()
                self.assertEqual(player.session.state,'playing');spawn.assert_not_called()
                self.assertEqual(player.renderer,'software')
                player.shutdown();player.deleteLater();self.app.processEvents();mpv.wait_closed()

if __name__=='__main__':unittest.main()
