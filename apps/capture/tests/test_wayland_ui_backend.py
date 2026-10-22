"""Native backend selection with synthetic widgets, no external WM or media."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from PySide6.QtCore import Qt,QRect,Signal
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QComboBox,QButtonGroup,QRadioButton


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
    def test_material_never_opens_xlib_or_passes_native_winid_to_x11(self):
        from loomrec.ui.materials import _x11_property,apply_material
        with patch('loomrec.ui.materials.ctypes.CDLL') as library,patch('subprocess.run') as run:
            self.assertFalse(_x11_property(123,True,20))
            widget=QWidget();widget.show();binding=apply_material(widget);binding.refresh()
            self.assertEqual(widget.property('materialMode'),'matte');library.assert_not_called();run.assert_not_called()
            widget.close();widget.deleteLater();self.app.processEvents()
        # Existing X11 branch remains callable, entirely mocked here.
        with patch.dict(os.environ,dict(WAYLAND_DISPLAY='',XDG_SESSION_TYPE='x11',QT_QPA_PLATFORM='xcb')),patch('loomrec.ui.materials.ctypes.CDLL') as library:
            library.return_value.XOpenDisplay.return_value=None
            self.assertFalse(_x11_property());library.assert_called_once()
    def test_native_player_embeds_without_winid_or_mpv_subprocess(self):
        from loomrec.ui.player import Player
        class Surface(QWidget):
            failed=Signal(str)
            def start(self,*args):self.started=args
            def stop(self):pass
        with patch('loomrec.ui.mpv_embed.MpvSurface',Surface),patch('loomrec.ui.player.QProcess.start') as spawn:
            player=Player()
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'synthetic-placeholder.mkv';path.write_bytes(b'not media; mocked engine')
                with patch.object(player.surface,'winId',side_effect=AssertionError('native embedding needs no XID')):player.load(path)
                self.assertEqual(player.surface.started[0],path);spawn.assert_not_called()
            player.shutdown();player.deleteLater();self.app.processEvents()

if __name__=='__main__':unittest.main()
