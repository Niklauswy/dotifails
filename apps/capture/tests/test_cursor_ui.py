"""Cursor intention, real configuration snapshots and synthetic UI lifecycle."""
import os,tempfile,unittest
from unittest.mock import patch,Mock
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QWidget,QScrollArea
from loomrec.ui.cursor_settings import CursorOptions,CursorPanel
from loomrec.videolibrary import preferences,save_preferences

class CursorUiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':self.temp.name,'XDG_STATE_HOME':self.temp.name,'LOOMREC_REDUCED_MOTION':'1'});self.env.start()
  self.owner=QWidget();self.owner.session=None;self.owner.capture_pending=False
  self.model=CursorOptions(self.owner,preferences(),save_preferences)
 def tearDown(self):self.owner.close();self.owner.deleteLater();self.app.processEvents();self.env.stop();self.temp.cleanup()
 def test_default_native_and_hidden_restores_exact_effect_intent(self):
  self.assertEqual(self.model.capture_values(),{'cursor':True,'cursor_live':True,'cursor_effects':{}})
  self.model.update(preset='trail');self.model.update(size=48,halo=False,clicks=True)
  self.model.update(visible=False,live=False)
  restored=CursorOptions(self.owner,preferences(),save_preferences)
  self.assertFalse(restored.visible);self.assertFalse(restored.live);self.assertEqual(restored.effects,self.model.effects)
  restored.update(visible=True);self.assertEqual(restored.effects,{'preset':'trail','size':48,'halo':False,'clicks':True})
  restored.update(preset='simple');self.assertEqual(restored.capture_values(),{'cursor':True,'cursor_live':False,'cursor_effects':{}})
 def test_shared_panels_off_and_locked_state(self):
  full=CursorPanel(self.model);quick=CursorPanel(self.model,compact=True)
  self.model.update(preset='presentation');self.assertEqual(quick.preset.currentData(),'presentation');self.assertTrue(quick.live.isChecked())
  quick.live.setChecked(False);self.assertFalse(full.live.isChecked());self.assertFalse(self.model.capture_values()['cursor_live'])
  quick.visible.setChecked(False);self.assertFalse(full.visible.isChecked());self.assertFalse(full.preset.isEnabled());self.assertFalse(full.custom.isEnabled())
  self.model.set_locked(True);full.visible.setChecked(True)
  self.assertFalse(self.model.visible);self.assertFalse(full.visible.isEnabled());self.assertFalse(quick.visible.isChecked())
  self.owner.session=object();self.model.set_locked(False);self.model.update(visible=True);self.assertFalse(self.model.visible)
  full.close();quick.close()
 def test_demo_reduced_motion_does_not_change_recording_effects(self):
  self.model.update(preset='trail');panel=CursorPanel(self.model,demo=True);panel.show();self.app.processEvents()
  self.assertFalse(panel.demo.timer.isActive());self.assertEqual(self.model.effects,{'preset':'trail'})
  with patch('loomrec.ui.cursor_settings.reduced_motion',return_value=False):
   panel.demo.sync();self.assertTrue(panel.demo.timer.isActive());panel.hide();self.assertFalse(panel.demo.timer.isActive())
  panel.close()
 def make_window(self):
  from loomrec.ui.main import Window,apply_theme
  from loomrec.library import Library
  apply_theme(self.app);w=Window(Library(self.temp.name),False);w.timer.stop();return w
 def close_window(self,w):
  w.session=None;w.capture_pending=False;w.countdown_timer.stop();w.quick.hide_all();w.recording_indicator.hide();w.close();w.deleteLater();self.app.processEvents()
 def test_countdown_snapshot_reaches_engine_cancel_unlocks(self):
  from loomrec.capture import CaptureConfig
  w=self.make_window()
  try:
   w.fps.setCurrentIndex(w.fps.findData(30))
   for spin,value in zip(w.rect,[0,0,100,100]):spin.setValue(value)
   with patch.dict(os.environ,{'DISPLAY':':synthetic'}),patch('loomrec.ui.main.shutil.which',return_value='/bin/true'),patch.object(w,'ensure_keys'),patch.object(w,'countdown_tick'),patch.object(w.recording_indicator,'present'):
    w.begin_countdown()
   self.assertTrue(w.pending_config.cursor);self.assertTrue(w.pending_config.cursor_live);self.assertEqual(w.pending_config.cursor_effects,{})
   with patch.object(w,'restore_capture_surface'):w.cancel_countdown()
   w.cursor_options.update(preset='presentation');w.cursor_options.update(visible=False,size=48)
   with patch.dict(os.environ,{'DISPLAY':':synthetic'}),patch('loomrec.ui.main.shutil.which',return_value='/bin/true'),patch.object(w,'ensure_keys'),patch.object(w,'countdown_tick'),patch.object(w.recording_indicator,'present'):
    w.begin_countdown()
   snapshot=w.pending_config
   self.assertIsInstance(snapshot,CaptureConfig);self.assertFalse(snapshot.cursor);self.assertEqual(snapshot.cursor_effects,{'preset':'presentation','size':48})
   self.assertTrue(w.cursor_options.locked);w.cursor_options.update(visible=True,preset='trail');self.assertFalse(w.cursor_options.visible)
   with patch.object(w,'restore_capture_surface'):w.cancel_countdown()
   self.assertFalse(w.cursor_options.locked);self.assertFalse(w.cursor_options.visible)
   w.cursor_options.update(visible=True);self.assertFalse(snapshot.cursor)
   w.pending_config=snapshot;w.quiet.setChecked(False)
   with patch('loomrec.ui.main.CaptureSession') as engine,patch.object(w.concentration,'watch'),patch.object(w.recording_indicator,'present'):
    w.start_capture();self.assertIs(engine.call_args.args[0],snapshot);engine.return_value.start.assert_called_once()
  finally:self.close_window(w)
 def test_settings_dimensions_and_pending_controls(self):
  w=self.make_window()
  try:
   w.cursor_options.update(preset='trail');w.cursor_panel.custom.trigger.setChecked(True)
   for dimensions in [(940,1054),(1280,800)]:
    w.resize(*dimensions);w.stack.setCurrentWidget(w.settings_page);w.show();self.app.processEvents()
    for scroll in w.settings_page.findChildren(QScrollArea):self.assertEqual(scroll.horizontalScrollBar().maximum(),0)
   w.capture_pending=True;w.poll();self.assertFalse(w.cursor_panel.visible.isEnabled())
  finally:self.close_window(w)

 def test_cursor_warning_never_reveals_capture_controls(self):
  w=self.make_window()
  try:
   w.session=Mock();w.session.status.return_value={'state':'recording','cursor_warning':'No se pudo seguir el cursor'}
   with patch.object(w,'notice') as notice,patch.object(w,'show') as show,patch.object(w,'error') as error:
    w.poll();w.poll();notice.assert_called_once_with('No se pudo seguir el cursor');show.assert_not_called();error.assert_not_called()
   self.assertTrue(w.cursor_options.locked)
  finally:self.close_window(w)
