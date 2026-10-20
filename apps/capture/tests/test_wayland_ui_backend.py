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
    def test_indicator_and_controller_do_not_run_x11_commands_with_display(self):
        from loomrec.ui.capture_feedback import RecordingIndicator
        from loomrec.ui.activation import RecordingController,focus_window
        with patch('subprocess.run') as run,patch('subprocess.check_output') as output:
            indicator=RecordingIndicator();widget=QWidget();indicator._show(widget,QRect(0,0,40,20),False)
            self.assertFalse(widget.windowFlags()&Qt.X11BypassWindowManagerHint)
            controller=QWidget();RecordingController.dock(controller)
            self.assertFalse(focus_window(123));run.assert_not_called();output.assert_not_called()
            indicator.hide();controller.close();controller.deleteLater();self.app.processEvents()
    def test_compact_native_window_mode_and_present_do_not_query_bspwm(self):
        from loomrec.ui.quick import QuickBar
        owner=QWidget();owner.camera=QComboBox();owner.mic=QComboBox();owner.system=QComboBox()
        owner.window_target=None;owner.capture_pending=False;owner.session=owner.job=owner.analysis=None
        owner.control_hint=QLabel('synthetic');owner.selection_feedback=Mock();owner.capture_modes=QButtonGroup(owner)
        buttons=[]
        for i in range(3):
            button=QRadioButton(owner);owner.capture_modes.addButton(button);buttons.append(button)
        buttons[2].setChecked(True)
        with patch('subprocess.run') as run,patch('subprocess.check_output') as output,patch('loomrec.ui.quick.QTimer.singleShot'):
            quick=QuickBar(owner);quick.timer.stop();quick.resize(720,88);quick.sync()
            self.assertIn('Ventana',quick.mode.accessibleName());quick.present();owner.selection_feedback.assert_called_once()
            run.assert_not_called();output.assert_not_called()
            quick.hide_all();quick.close();quick.deleteLater();owner.close();owner.deleteLater();self.app.processEvents()
    def test_legacy_controls_never_hide_native_window_using_xid(self):
        from loomrec.ui.activation import RecordingController
        session=Mock();session.status.return_value={'state':'paused'}
        owner=Mock();owner.request.return_value={'window':123}
        controller=SimpleNamespace(session=session,owner=owner,warning=Mock())
        with patch('subprocess.run') as run,patch('subprocess.check_output') as output:
            RecordingController.pause_requested(controller)
            run.assert_not_called();output.assert_not_called();session.resume.assert_not_called()
            self.assertIn('controles antiguos',controller.warning.setText.call_args.args[0])
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
