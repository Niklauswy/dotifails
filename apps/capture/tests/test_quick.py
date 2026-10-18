"""Quick UI contracts: no capture, device probes or real user data."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from loomrec.ui.main import Window,apply_theme
from loomrec.library import Library
from loomrec.devices import visible_window_rect,list_windows

class QuickTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);apply_theme(cls.app)
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'XDG_STATE_HOME':self.tmp.name});self.env.start()
  self.w=Window(Library(self.tmp.name),False);self.w.monitor.addItem('Synthetic',[0,0,600,400])
 def tearDown(self):
  self.w.session=None;self.w.job=None;self.w.analysis=None;self.w.capture_pending=False
  self.w.timer.stop();self.w.quick.timer.stop();self.w.quick.hide_all();self.w.close();self.w.deleteLater();self.app.processEvents();self.env.stop();self.tmp.cleanup()
 def test_quick_activation_never_shows_main_and_focus_restores_full(self):
  result=self.w.activate_instance('quick');self.app.processEvents()
  self.assertTrue(result['quick']);self.assertTrue(self.w.quick.isVisible());self.assertFalse(self.w.isVisible())
  with patch.object(self.w,'ensure_keys'):
   self.w.activate_instance('focus')
  self.assertFalse(self.w.quick.isVisible());self.assertTrue(self.w.isVisible())
 def test_device_popup_shares_actual_selection(self):
  w=self.w;w.mic.addItem('Synthetic mic','null-device');w.quick.present();w.quick.device(w.quick.mode,w.mic,'Mic')
  from loomrec.ui.components import DeviceChoices
  choices=w.quick.popup.findChild(DeviceChoices);choices.view.activated.emit(w.mic.model().index(1,0))
  self.assertEqual(w.mic.currentData(),'null-device');w.mic.setCurrentIndex(0);self.assertEqual(choices.view.currentIndex().row(),0)
 def test_quick_does_not_mutate_active_session(self):
  w=self.w;w.session=Mock();result=w.activate_instance('quick')
  self.assertEqual(result['result'],'quick_unavailable');w.session.pause.assert_not_called();w.session.stop.assert_not_called();self.assertFalse(w.quick.isVisible())
 def test_duplicate_quick_routes_active_capture_to_explicit_controller(self):
  from loomrec.ui.main import main
  for state in ('paused','recording','starting','stopping'):
   owner=Mock();owner.claim.return_value=False
   owner.request.side_effect=[{'state':'busy','result':'quick_unavailable'},{'state':state,'project_path':'/synthetic/project.json'}]
   with patch.dict(os.environ,{'LOOMREC_QUICK_RECORD':'1'}),patch('loomrec.ui.instance.Instance',return_value=owner),patch('loomrec.ui.activation.activate_response',return_value=0) as activate:
    self.assertEqual(main(),0)
    self.assertEqual([call.args[0] for call in owner.request.call_args_list],['quick','status'])
    self.assertEqual(activate.call_args.args[0]['state'],state)
    self.assertIs(activate.call_args.args[1],owner)
 def test_countdown_hides_all_before_deferred_start_and_escape_cancels(self):
  w=self.w;w.quick.present();w.capture_pending=True;w.remaining=0
  callbacks=[]
  with patch.object(w.camera_preview,'stop',side_effect=lambda callback=None:callback() if callback else None),patch('loomrec.ui.main.QTimer.singleShot',side_effect=lambda delay,fn:callbacks.append(fn)):
   w.countdown_tick()
  self.assertFalse(w.quick.isVisible());self.assertFalse(w.isVisible());self.assertEqual(len(callbacks),1)
  w.quick.escape();self.assertFalse(w.capture_pending)
  with patch.object(w,'start_capture') as start:callbacks[0]();start.assert_not_called()
 def test_window_rechecked_after_countdown_before_engine(self):
  w=self.w;w.window_target='0x123';w.pending_config=Mock(rect=[0,0,100,100]);w.capture_pending=True
  with patch('loomrec.ui.main.visible_window_rect',return_value=[1,0,100,100]),patch('loomrec.ui.main.CaptureSession') as engine:
   with self.assertRaises(ValueError):w.start_capture()
   engine.assert_not_called();self.assertFalse(w.capture_pending)
 def test_hidden_window_rejected_and_live_geometry_even(self):
  text='Map State: IsUnMapped\nAbsolute upper-left X: 1\nAbsolute upper-left Y: 2\nWidth: 101\nHeight: 99'
  with patch('loomrec.devices.run',return_value=text):
   with self.assertRaises(ValueError):visible_window_rect('0x123')
  with patch('loomrec.devices.run',return_value=text.replace('IsUnMapped','IsViewable')):
   self.assertEqual(visible_window_rect('0x123'),[1,2,100,98])

 def test_quick_controls_fit_native_surface_at_compact_widths(self):
  from PySide6.QtCore import QRect
  from PySide6.QtWidgets import QScrollArea
  for available in (752,652,532,352):
   screen=Mock();screen.availableGeometry.return_value=QRect(-200,0,available,900)
   with patch('loomrec.ui.quick.QApplication.screenAt',return_value=screen):self.w.quick.present()
   self.app.processEvents();bar=self.w.quick
   self.assertEqual(bar.height(),88);self.assertEqual(bar.width(),available-32)
   previous=0
   for control in [bar.mode,*bar.source_buttons,bar.options,bar.start,bar.dismiss]:
    if not control.isVisible():continue
    self.assertGreaterEqual(control.width(),44)
    self.assertGreaterEqual(control.x(),previous)
    self.assertLessEqual(control.geometry().right(),bar.width())
    previous=control.geometry().right()+1
   self.assertFalse(bar.findChildren(QScrollArea))
