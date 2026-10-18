import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,unittest
from unittest.mock import patch,Mock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop,QTimer
from loomrec.ui.main import Window,apply_theme
from loomrec.library import Library
from loomrec.integration import Concentration

class ControlsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.app=QApplication.instance() or QApplication([]);apply_theme(cls.app)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'XDG_STATE_HOME':self.temp.name});self.env.start();self.window=Window(Library(self.temp.name),False)
 def tearDown(self):
  self.window.close();self.app.processEvents();self.temp.cleanup();self.env.stop()
 def test_all_pages_fit_both_sizes(self):
  w=self.window
  for width,height in [(940,1054),(1280,800)]:
   w.resize(width,height);w.show()
   for page in [w.library_page,w.setup_page,w.editor_page]:
    w.stack.setCurrentWidget(page);self.app.processEvents()
    self.assertEqual((w.width(),w.height()),(width,height))
    self.assertLessEqual(w.minimumSizeHint().width(),width)
 def test_cancel_after_countdown_before_engine_start(self):
  w=self.window;w.capture_pending=True;w.remaining=0
  with patch.object(w,'start_capture') as start:
   w.countdown_tick();w.cancel_countdown();loop=QEventLoop();QTimer.singleShot(600,loop.quit);loop.exec()
   start.assert_not_called()
 def test_dunst_restores_prior_pause(self):
  for previous in ('true','false'):
   with patch('loomrec.integration.subprocess.check_output',return_value=previous),patch('loomrec.integration.subprocess.run') as run:
    concentration=Concentration();concentration.begin();concentration.restore()
    self.assertEqual(run.call_args.args[0],['dunstctl','set-paused',previous])

 def test_reopen_recording_waits_for_pause_before_showing_controls(self):
  from loomrec.schema import Project,save_project
  path=self.window.library.new_directory()/'project.json';save_project(Project(),path)
  (path.parent/'capture.json').write_text('{}')
  session=Mock();session.status.return_value={'state':'recording'}
  with patch('loomrec.ui.main.CaptureSession.attach',return_value=session),patch.object(self.window,'ensure_keys'):
   self.window.open_project(path)
   self.assertIs(self.window.session,session);self.assertIsNone(self.window.editor)
   session.stop.assert_not_called();session.pause.assert_called_once();session.resume.assert_not_called()
   self.assertFalse(self.window.isVisible());self.assertTrue(self.window.show_paused)
  self.window.session=None

 def test_reopen_paused_capture_stays_visible_and_preserves_current_session(self):
  from loomrec.schema import Project,save_project
  path=self.window.library.new_directory()/'project.json';save_project(Project(),path)
  (path.parent/'capture.json').write_text('{}')
  session=Mock(root=path.parent);session.status.return_value={'state':'paused'}
  w=self.window;w.session=session;w.capture_gains={'mic':.5};w.hide()
  try:
   with patch('loomrec.ui.main.CaptureSession.attach',return_value=session),patch.object(w,'ensure_keys'),patch('loomrec.ui.main.RenderJob') as render:
    w.open_project(path)
    self.assertIs(w.session,session);self.assertTrue(w.isVisible());self.assertEqual(w.capture_gains,{'mic':.5})
    self.assertIs(w.stack.currentWidget(),w.setup_page);self.assertEqual(w.record.text(),'Reanudar')
    self.assertTrue(w.record.isEnabled());self.assertTrue(w.stop_record.isVisible());self.assertFalse(w.pause_record.isVisible())
    render.assert_not_called();session.stop.assert_not_called();session.pause.assert_not_called();session.resume.assert_not_called()
    self.assertFalse(w.activate_instance('quick').get('quick',False))
  finally:w.session=None

 def test_persisted_concentration_recovery_respects_live_lock(self):
  import fcntl,json
  from pathlib import Path
  root=Path(self.temp.name)/'capture';root.mkdir()
  with patch('loomrec.integration.subprocess.check_output',return_value='false'),patch('loomrec.integration.subprocess.run') as run:
   state=Concentration();state.begin(root)
   self.assertTrue(state.lease.exists())
   with (root/'capture.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    restored=Concentration();self.assertFalse(restored.recover())
   self.assertTrue(restored.recover());self.assertFalse(state.lease.exists())
   self.assertEqual(run.call_args.args[0],['dunstctl','set-paused','false'])
 def test_configured_shortcuts_and_vt_rejection(self):
  import json
  from pathlib import Path
  from loomrec.integration import shortcut_settings,parse_chord
  path=Path(self.temp.name)/'keys.json';path.write_text(json.dumps({'pause':'Super+Ctrl+Shift+x'}))
  self.assertEqual(shortcut_settings(path)['pause'],'Super+Ctrl+Shift+x')
  with self.assertRaises(ValueError):parse_chord('Ctrl+Alt+F9')

 def test_equivalent_custom_chords_rejected(self):
  import json
  from pathlib import Path
  from loomrec.integration import shortcut_settings
  path=Path(self.temp.name)/'keys.json'
  path.write_text(json.dumps({'pause':'Shift+Control+Super+s'}))
  with self.assertRaises(ValueError):shortcut_settings(path)
