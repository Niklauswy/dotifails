"""The quick bar opens again after a capture and defaults to the focused monitor."""
import json,os,subprocess,tempfile,unittest
from unittest.mock import patch,Mock
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from loomrec.ui.main import Window,apply_theme,focused_monitor
from loomrec.library import Library

MONITORS=[{'name':'eDP-1','focused':False},{'name':'DP-1','focused':True}]

class QuickAfterCaptureTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);apply_theme(cls.app)
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'XDG_STATE_HOME':self.tmp.name});self.env.start()
  self.w=Window(Library(self.tmp.name),False);self.w.timer.stop()
  self.w.monitor.addItem('eDP-1',[0,0,1920,1080]);self.w.monitor.addItem('DP-1',[1920,0,1920,1080])
 def tearDown(self):
  self.w.session=None;self.w.job=None;self.w.analysis=None;self.w.capture_pending=False
  self.w.quick.timer.stop();self.w.quick.hide_all();self.w.close();self.w.deleteLater();self.app.processEvents();self.env.stop();self.tmp.cleanup()
 def hypr(self):
  done=subprocess.CompletedProcess([],0,json.dumps(MONITORS),'')
  return patch.dict(os.environ,{'HYPRLAND_INSTANCE_SIGNATURE':'fixture'}),patch('subprocess.run',return_value=done)
 def test_finished_session_is_reaped_and_quick_bar_opens_without_library(self):
  w=self.w;session=Mock();session.status.return_value={'state':'stopped','project_path':os.path.join(self.tmp.name,'missing/project.json')}
  w.session=session
  result=w.activate_instance('quick');self.app.processEvents()
  self.assertTrue(result.get('quick'));self.assertIsNone(w.session)
  self.assertTrue(w.quick.isVisible());self.assertFalse(w.isVisible())
  session.stop.assert_not_called()
 def test_quick_bar_defaults_to_focused_monitor(self):
  w=self.w;env,run=self.hypr()
  with env,run:
   self.assertEqual(focused_monitor(),'DP-1')
   w.activate_instance('quick')
  self.assertEqual(w.monitor.currentText(),'DP-1')
  self.assertEqual([s.value() for s in w.rect],[1920,0,1920,1080])
 def test_focused_monitor_applies_once_devices_load(self):
  w=self.w;w.monitor.clear();env,run=self.hypr()
  with env,run:w.select_focused_monitor()
  self.assertEqual(getattr(w,'_wanted_monitor',None),'DP-1')
 def test_failing_shortcut_helper_does_not_keep_session(self):
  w=self.w;w.keys=Mock();w.keys.poll.side_effect=RuntimeError('portal restarted');w.keys.error=''
  session=Mock();session.status.return_value={'state':'stopped','project_path':os.path.join(self.tmp.name,'missing/project.json')}
  w.session=session;w._quiet_reap=True
  try:w.poll()
  finally:w._quiet_reap=False;w.keys=None
  self.assertIsNone(w.session)

class ControllerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_hidden_controller_closes_when_capture_ended_elsewhere(self):
  from loomrec.ui.activation import RecordingController
  session=Mock();session.status.return_value={'state':'recording','duration':3}
  with patch.object(RecordingController,'prepare_show'):
   controller=RecordingController(session,Mock(),'Synthetic')
  controller.hide();session.status.return_value={'state':'stopped','duration':3}
  with patch('loomrec.ui.activation.QApplication.quit') as quit:
   controller.poll()
  quit.assert_called_once()
  controller.timer.stop();controller.deleteLater()

if __name__=='__main__':unittest.main()
