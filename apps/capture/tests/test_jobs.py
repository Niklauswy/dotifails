import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile,unittest
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from loomrec.ui.main import Window
from loomrec.library import Library
from loomrec.schema import Project,Source,Clip,save_project
from loomrec.render import RenderJob

class JobTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'XDG_STATE_HOME':self.temp.name});self.env.start()
  self.library=Library(self.temp.name);self.path=self.library.new_directory()/'project.json';save_project(Project(sources=[Source('s','source.mkv',duration=4)],clips=[Clip('s',0,4)]),self.path)
  self.window=Window(self.library,False);self.window.timer.stop();self.window.open_project(self.path,edit=True);self.window.show();self.window.job_export=False;self.window.job_revision=0
  self.status={'state':'running','progress':.25,'error':None,'output':str(self.path.parent/'out.mp4'),'phase':'Renderizando clip 1 de 1'}
  self.job=Mock();self.job.poll.side_effect=lambda:dict(self.status);self.window.job=self.job
 def tearDown(self):
  self.window.job=None;self.window.analysis=None;self.window.close();self.window.deleteLater();self.app.processEvents();self.env.stop();self.temp.cleanup()
 def test_running_visible_across_pages_and_real_cancel_pending(self):
  before=self.path.read_bytes();w=self.window;w.poll_job();w.back_library();self.app.processEvents()
  self.assertTrue(w.job_panel.isVisible());self.assertFalse(w.preview_button.isEnabled());self.assertFalse(w.inspector.isEnabled())
  self.assertIn('Vista previa',w.job_panel.title.text());self.assertEqual(w.job_panel.progress.value(),25)
  self.assertTrue(w.operation_busy())
  w.job_panel.cancel.click();self.job.cancel.assert_called_once();self.assertIn('Cancelando',w.job_panel.title.text());self.assertIs(w.job,self.job)
  self.status['state']='cancelled';w.poll_job();self.assertIsNone(w.job);self.assertTrue(w.preview_button.isEnabled());self.assertIn('Cancelada',w.job_panel.title.text());self.assertEqual(self.path.read_bytes(),before)
 def test_done_export_and_preview_labels_and_no_stale_guard(self):
  w=self.window;self.status.update(state='done',progress=1);w.job_export=True
  with patch.object(w.player,'load'),patch.object(w.wave_process,'start'):w.poll_job()
  self.assertIsNone(w.job);self.assertIn('Exportación MP4',w.job_panel.title.text());self.assertIn('Completada',w.job_panel.title.text());self.assertFalse(w.operation_busy())
  self.assertTrue(w.inspector.isEnabled())
 def test_failed_job_unblocks_and_exposes_error(self):
  self.status.update(state='error',error='No space left');self.window.poll_job()
  self.assertIsNone(self.window.job);self.assertIn('Falló',self.window.job_panel.title.text());self.assertIn('No space left',self.window.job_panel.detail.text());self.assertFalse(self.window.operation_busy())
 def test_within_clip_progress_is_real_and_monotonic(self):
  job=RenderJob(self.path,self.path.parent/'out.mp4');job._step_base=.2;job._step_span=.5;job._step_duration=10
  progress=self.path.parent/'progress';progress.write_text('out_time_us=4000000\n');job._read_progress(progress);self.assertAlmostEqual(job.poll()['progress'],.4)
  progress.write_text('out_time_us=1000000\n');job._read_progress(progress);self.assertAlmostEqual(job.poll()['progress'],.4)
 def test_legacy_interrupt_rechecks_identity_and_never_guesses(self):
  from loomrec.ui.legacy_jobs import interrupt_render
  target={'pid':123,'identity':'old','kind':'Vista previa'}
  with patch('loomrec.ui.legacy_jobs.owned_render',return_value={**target,'identity':'new'}),patch('loomrec.ui.legacy_jobs.os.kill') as kill:
   with self.assertRaises(RuntimeError):interrupt_render(1,target)
   kill.assert_not_called()
  with patch('loomrec.ui.legacy_jobs.owned_render',return_value=target),patch('loomrec.ui.legacy_jobs.os.kill') as kill:
   interrupt_render(1,target);self.assertEqual(kill.call_args.args[0],123)
