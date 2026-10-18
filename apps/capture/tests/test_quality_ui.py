"""UI render intent and cache invalidation without encoders or user media."""
import os,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch,Mock
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from loomrec.ui.main import Window,apply_theme
from loomrec.library import Library
from loomrec.schema import Project,Source,Clip,save_project
from loomrec.editing import Editor

class QualityUiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);apply_theme(cls.app)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':self.temp.name,'XDG_STATE_HOME':self.temp.name});self.env.start()
  self.w=Window(Library(self.temp.name),False);self.w.timer.stop()
  path=Path(self.temp.name)/'project.json';save_project(Project(title='Owned fixture',sources=[Source(id='screen',path='source.mkv',kind='screen',duration=2)],clips=[Clip('screen',0,2)]),path);self.w.editor=Editor(path)
 def tearDown(self):
  self.w.job=None;self.w.quick.hide_all();self.w.close();self.w.deleteLater();self.app.processEvents();self.env.stop();self.temp.cleanup()
 def test_old_scaled_cache_is_not_reused_and_profile_is_part_of_key(self):
  old=self.w.editor.path.parent/'.preview'/('playback-v1-'+hashlib.sha256(self.w.editor.path.read_bytes()).hexdigest()+'.mp4')
  original=self.w.playback_path();self.assertNotEqual(original,old)
  with patch('loomrec.render.render_profile_signature',return_value={'pipeline':'changed','fps':'source-timestamps'}):self.assertNotEqual(self.w.playback_path(),original)
  with patch('loomrec.render.PIPELINE_VERSION','next'):self.assertNotEqual(self.w.playback_path(),original)
  (self.w.editor.path.parent/'capture.json').write_text('{"quality":"high"}');self.assertNotEqual(self.w.playback_path(),original)
 def test_all_preview_routes_use_native_preview_not_export_selection(self):
  for viewing in (True,False):
   self.w.viewing=viewing;self.w.preset.setCurrentIndex(self.w.preset.findData('compact'));self.w.job=None
   with patch('loomrec.ui.main.RenderJob') as renderer,patch.object(self.w,'poll_job'):
    renderer.return_value.start.return_value=Mock();self.w.render(False)
    self.assertEqual(renderer.call_args.kwargs['preset'],'preview')
 def test_export_retains_explicit_profile_and_labels_fit(self):
  self.w.preset.setCurrentIndex(self.w.preset.findData('high'))
  with patch('loomrec.ui.main.QFileDialog.getSaveFileName',return_value=(str(Path(self.temp.name)/'result.mp4'),'')),patch('loomrec.ui.main.RenderJob') as renderer,patch.object(self.w,'poll_job'):
   renderer.return_value.start.return_value=Mock();self.w.render(True);self.assertEqual(renderer.call_args.kwargs['preset'],'high');self.assertEqual(self.w.preview_label.text(),'Exportando · '+self.w.preset.currentText())
  self.assertNotIn('1080',self.w.preset.currentText());self.assertIn('Original',self.w.preset.currentText())
  self.w.stack.setCurrentWidget(self.w.editor_page);self.w.resize(940,1054);self.w.show();self.app.processEvents()
  self.assertLessEqual(self.w.export_button.geometry().right(),self.w.editor_toolbar.width());self.assertLessEqual(self.w.preset.geometry().right(),self.w.editor_toolbar.width())
