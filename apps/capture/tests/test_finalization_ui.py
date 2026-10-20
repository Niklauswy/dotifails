"""UI/catalogue handoff for durable MP4 publication; no media or desktop access."""
import os,tempfile,unittest,hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QListWidgetItem
from PySide6.QtCore import Qt
from loomrec.ui.main import Window
from loomrec.library import Library
from loomrec.videolibrary import VideoLibrary,recording_video
from loomrec.schema import Project,Source,Clip,save_project

class FinalizationUITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.root/'config'),'XDG_STATE_HOME':str(self.root/'state')});self.env.start()
  self.w=Window(Library(self.root/'projects'),False);self.w.timer.stop()
  self.path=self.w.library.new_directory()/'project.json'
  save_project(Project(title='Own fixture',sources=[Source('v','source.mkv',duration=2)],clips=[Clip('v',0,2)]),self.path)
  (self.path.parent/'capture.json').write_text('{}')
  self.output=self.root/'Video listo 日本語.mp4';self.output.write_bytes(b'not decoded')
  self.state={'state':'ready','output':str(self.output),'project_sha256':hashlib.sha256(self.path.read_bytes()).hexdigest(),'progress':1}
  self.status_patch=patch('loomrec.videolibrary.finalization_status',side_effect=lambda _:dict(self.state));self.status_patch.start()
  self.w.refresh_library=Mock();self.w.player.load=Mock();self.w.stop_metadata=Mock();self.w.active_metadata=0
  self.w.stack.setCurrentWidget(self.w.library_page)
  item=QListWidgetItem('Own fixture');item.setData(Qt.UserRole,str(self.path));self.w.items.addItem(item);self.w.items.setCurrentRow(0)
 def tearDown(self):
  self.w.session=None;self.w.finalization_path=None;self.w.job=None;self.w.close();self.w.deleteLater();self.app.processEvents()
  self.status_patch.stop();self.env.stop();self.tmp.cleanup()
 def test_ready_copies_video_and_plays_without_render(self):
  self.w.copy_video_path();self.assertEqual(self.app.clipboard().text(),str(self.output))
  with patch('loomrec.ui.main.CaptureSession.attach',return_value=SimpleNamespace(status=lambda:{'state':'stopped'})),patch('loomrec.render.RenderJob') as render:
   self.w.open_project(self.path);render.assert_not_called()
  self.w.player.load.assert_called_once_with(self.output)
  self.assertFalse(hasattr(self.w,'enter_editor'))
 def test_changed_edit_keeps_mp4_and_warns_copy(self):
  self.path.write_text(self.path.read_text()+'\n')
  self.w.copy_video_path();self.assertEqual(self.app.clipboard().text(),str(self.output))
  self.assertIn('no incluye',self.w.statusBar().currentMessage())
  self.assertEqual(recording_video(self.path),(self.output,True))
 def test_pending_then_ready_only_loads_once_without_preview(self):
  self.state['state']='running';self.w.finalization_path=self.path
  with patch('loomrec.render.RenderJob') as render:
   self.w.poll_finalization();self.assertFalse(self.w.library_copy_path.isEnabled());self.w.player.load.assert_not_called()
   self.state['state']='ready';self.w.poll_finalization();self.w.poll_finalization();render.assert_not_called()
  self.w.player.load.assert_called_once_with(self.output)
 def test_error_cancel_preserve_original_and_never_play_partial(self):
  self.w.finalization_path=self.path
  for state in ('error','cancelled'):
   self.state['state']=state;self.w.poll_finalization();self.assertFalse(self.w.finalization_panel.retry.isHidden());self.assertTrue(self.path.exists());self.w.player.load.assert_not_called()
  self.assertEqual(recording_video(self.path),(None,False))
 def test_catalogue_one_editable_row_only_for_verified_receipt(self):
  library=VideoLibrary(self.root,legacy=self.root/'no-legacy')
  # Existing project belongs to the registered legacy catalogue; output is public.
  library.legacy=self.w.library.root
  self.assertEqual([e.path for e in library.entries()],[self.path])
  self.state['state']='error'
  self.assertEqual({e.path for e in library.entries()},{self.path,self.output})
  self.output.unlink();self.state['state']='ready'
  self.assertEqual(recording_video(self.path),(None,False))
 def test_snapshot_and_discard_use_engine_contract(self):
  self.w.mic_gain.setValue(.6);self.w.system_gain.setValue(1.4)
  self.w.fps.setCurrentIndex(self.w.fps.findData(30))
  for spin,value in zip(self.w.rect,[0,0,100,100]):spin.setValue(value)
  with patch.dict(os.environ,{'DISPLAY':':synthetic'}),patch('loomrec.ui.main.shutil.which',return_value='/bin/true'),patch.object(self.w,'ensure_keys'),patch.object(self.w,'countdown_tick'),patch.object(self.w.recording_indicator,'present'):
   self.w.begin_countdown()
  config=self.w.pending_config
  self.assertTrue(config.auto_finalize);self.assertEqual(config.mic_gain,.6);self.assertEqual(config.system_gain,1.4);self.assertTrue(Path(config.output_dir).is_absolute());self.assertTrue(config.title)
  self.w.mic_gain.setValue(2);self.assertEqual(config.mic_gain,.6)
  with patch.object(self.w,'restore_capture_surface'):self.w.cancel_countdown()
  session=Mock();self.w.session=session;self.w.cancel_capture();session.stop.assert_called_once_with(discard=True)
 def test_retry_and_cancel_route_to_detached_service(self):
  self.w.finalization_path=self.path;self.state['state']='error'
  with patch('loomrec.finalize.retry') as retry:
   self.w.retry_finalization();retry.assert_called_once_with(self.path,output_dir=str(Path.home()/'Videos'))
  with patch('loomrec.finalize.cancel') as cancel:
   self.w.cancel_finalization();cancel.assert_called_once_with(self.path)
  self.assertTrue(self.path.exists());self.w.player.load.assert_not_called()
 def test_reopened_ui_reads_real_durable_receipt_without_new_render(self):
  import json
  (self.path.parent/'finalization.json').write_text(json.dumps(self.state))
  self.status_patch.stop()
  try:
   fresh=Window(Library(self.w.library.root),False);fresh.timer.stop();fresh.player.load=Mock();fresh.active_metadata=0
   try:
    with patch('loomrec.ui.main.CaptureSession.attach',return_value=SimpleNamespace(status=lambda:{'state':'stopped'})),patch('loomrec.render.RenderJob') as render:
     fresh.open_project(self.path);render.assert_not_called()
    fresh.player.load.assert_called_once_with(self.output)
    fresh.stack.setCurrentWidget(fresh.library_page);fresh.items.setCurrentRow(0);fresh.copy_video_path()
    self.assertEqual(self.app.clipboard().text(),str(self.output));self.assertTrue(fresh.library_copy_path.isEnabled());self.assertTrue(fresh.library_open.isEnabled())
   finally:fresh.finalization_path=None;fresh.close();fresh.deleteLater();self.app.processEvents()
  finally:self.status_patch.start()
 def test_stopped_auto_capture_waits_for_publication_without_mutating_snapshot(self):
  before=self.path.read_bytes();self.state['state']='running'
  self.w.capture_gains={'mic':.2,'system':.3}
  self.w.session=SimpleNamespace(config=SimpleNamespace(auto_finalize=True),status=lambda:{'state':'stopped','project_path':str(self.path)})
  with patch.object(self.w,'open_project') as opened,patch('loomrec.render.RenderJob') as render,patch.object(self.w,'restore_concentration'):
   self.w.poll();opened.assert_not_called();render.assert_not_called()
  self.assertIsNone(self.w.session);self.assertEqual(self.w.finalization_path,self.path)
  self.assertEqual(self.path.read_bytes(),before);self.w.player.load.assert_not_called()
