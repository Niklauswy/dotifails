import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile,unittest
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from loomrec.ui.activation import RecordingController,owned_capture,focus_window

class ActivationFocusTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_bspwm_focus_targets_only_requested_node(self):
  with patch.dict(os.environ,{'QT_QPA_PLATFORM':'xcb'}),patch('loomrec.ui.activation.shutil.which',return_value='/usr/bin/bspc'),patch('loomrec.ui.activation.subprocess.run',return_value=Mock(returncode=0)) as run:
   self.assertTrue(focus_window(123))
   self.assertEqual([c.args[0] for c in run.call_args_list],[['bspc','query','-N','-n','0x7b'],['bspc','node','0x7b','-g','hidden=off'],['bspc','node','0x7b','-f']])
 def test_paused_controls_dock_in_negative_origin_workarea(self):
  from PySide6.QtCore import QRect
  session=Mock();session.status.return_value={'state':'paused','duration':62}
  controller=RecordingController(session,Mock());controller.timer.stop()
  try:
   area=QRect(-1280,0,1280,800);screen=Mock();screen.availableGeometry.return_value=area
   with patch.object(QApplication,'screenAt',return_value=screen):controller.dock()
   self.assertTrue(area.contains(controller.geometry()));self.assertLess(abs(controller.geometry().bottom()-(area.bottom()-28)),2)
   controller.poll();self.assertEqual(controller.timer_label.text(),'01:02 · En pausa');session.pause.assert_not_called()
  finally:controller.close();controller.deleteLater();self.app.processEvents()
 def test_capture_owner_excludes_other_sessions(self):
  with tempfile.TemporaryDirectory() as d:
   proc=Path(d);children=proc/'20/task/20/children';children.parent.mkdir(parents=True);children.write_text('21')
   child=proc/'21';child.mkdir();(child/'cmdline').write_bytes(b'python\0-m\0loomrec.worker\0/owned\0')
   other=proc/'99';other.mkdir();(other/'cmdline').write_bytes(b'python\0-m\0loomrec.worker\0/unrelated\0')
   self.assertEqual(owned_capture(20,proc),Path('/owned'))
   children.write_text('21 99')
   with self.assertRaises(RuntimeError):owned_capture(20,proc)
 def test_controls_wait_for_finalized_pause_ack_before_mapping(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);session=Mock(root=root);session.status.return_value={'state':'recording'};owner=Mock()
   controller=RecordingController(session,owner);controller.timer.stop()
   try:
    session.pause.assert_not_called();session.stop.assert_not_called()
    with patch('loomrec.ui.activation.show_and_focus') as show:
     controller.prepare_show();controller.prepare_show();controller.poll()
     session.pause.assert_called_once();show.assert_not_called();self.assertFalse(controller.isVisible())
     session.status.return_value={'state':'paused','duration':62};controller.poll()
     show.assert_called_once_with(controller);self.assertEqual(controller.timer_label.text(),'01:02 · En pausa')
    owner.request.assert_not_called();session.resume.assert_not_called();session.stop.assert_not_called()
   finally:controller.close();controller.deleteLater();self.app.processEvents()
 def test_pause_timeout_never_reveals_controls(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_STATE_HOME':d}):
   session=Mock(root=Path(d));session.status.return_value={'state':'recording'}
   controller=RecordingController(session,Mock());controller.timer.stop()
   try:
    with patch('loomrec.ui.activation.show_and_focus') as show:
     controller.prepare_show();controller.deadline=0;controller.poll()
     show.assert_not_called();self.assertFalse(controller.isVisible());self.assertIsNotNone(controller.failure)
    session.resume.assert_not_called();session.stop.assert_not_called()
   finally:controller.close();controller.deleteLater();self.app.processEvents()
 def test_modern_resume_hides_owner_before_delayed_command(self):
  from PySide6.QtCore import QEventLoop,QTimer
  with tempfile.TemporaryDirectory() as d:
   session=Mock(root=Path(d));session.status.return_value={'state':'paused'};owner=Mock()
   owner.request.side_effect=[{'controls_protocol':1},{'hidden':True}]
   controller=RecordingController(session,owner);controller.timer.stop()
   try:
    controller.show();controller.pause_requested()
    self.assertEqual([c.args[0] for c in owner.request.call_args_list],['status','hide_controls'])
    self.assertFalse(controller.isVisible());session.resume.assert_not_called()
    loop=QEventLoop();QTimer.singleShot(550,loop.quit);loop.exec();session.resume.assert_called_once()
   finally:controller.close();controller.deleteLater();self.app.processEvents()
 def test_legacy_discovery_requires_fresh_matching_process_identity(self):
  import json,time
  from loomrec.ui.activation import live_recordings
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);proc=base/'proc';proc.mkdir();root=base/'project';root.mkdir();child=proc/'21';child.mkdir()
   (child/'cmdline').write_bytes(b'python\0-m\0loomrec.worker\0'+os.fsencode(root)+b'\0')
   status=root/'status.json';status.write_text(json.dumps({'pid':21,'state':'recording','heartbeat':time.time()}))
   self.assertEqual(live_recordings(proc),[root])
   status.write_text(json.dumps({'pid':99,'state':'recording','heartbeat':time.time()}));self.assertEqual(live_recordings(proc),[])
   status.write_text(json.dumps({'pid':21,'state':'recording','heartbeat':time.time()-30}));self.assertEqual(live_recordings(proc),[])

 def test_paused_controller_never_resumes_on_open_and_hides_before_explicit_resume(self):
  from PySide6.QtCore import QEventLoop,QTimer
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'capture.json').write_text('{}');session=Mock(root=root);session.status.return_value={'state':'paused'};owner=Mock();owner.request.return_value={'window':123,'project_path':str(root/'project.json')}
   controller=RecordingController(session,owner);controller.timer.stop()
   try:
    self.assertEqual(controller.pause_button.text(),'Reanudar');session.resume.assert_not_called();session.stop.assert_not_called()
    with patch('loomrec.ui.activation.subprocess.check_output',return_value='Map State: IsUnMapped'):
     controller.pause_button.click();session.resume.assert_not_called();self.assertFalse(controller.isVisible())
     loop=QEventLoop();QTimer.singleShot(550,loop.quit);loop.exec();session.resume.assert_called_once()
    session.stop.assert_not_called()
   finally:controller.close();controller.deleteLater();self.app.processEvents()

 def test_resume_refuses_if_owner_controls_cannot_be_hidden(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);session=Mock(root=root);session.status.return_value={'state':'paused'};owner=Mock();owner.request.return_value={'window':123}
   controller=RecordingController(session,owner);controller.timer.stop()
   try:
    with patch('loomrec.ui.activation.subprocess.check_output',side_effect=OSError('unavailable')):controller.pause_button.click()
    session.resume.assert_not_called();session.stop.assert_not_called();self.assertIn('No se reanudó',controller.warning.text())
   finally:controller.close();controller.deleteLater();self.app.processEvents()

 def test_stop_from_paused_waits_for_terminal_ack_before_opening_owner(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);session=Mock(root=root);session.status.return_value={'state':'paused'};owner=Mock();owner.request.return_value={'window':123}
   controller=RecordingController(session,owner);controller.timer.stop()
   try:
    controller.stop_button.click();session.stop.assert_called_once();controller.poll();owner.request.assert_not_called()
    session.status.return_value={'state':'stopped'}
    with patch('loomrec.ui.activation.focus_window'):controller.poll()
    owner.request.assert_called_once_with('focus',timeout=.7)
   finally:controller.close();controller.deleteLater();self.app.processEvents()
