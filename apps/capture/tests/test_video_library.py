import tempfile,os,unittest,threading
from pathlib import Path
from unittest.mock import patch
from loomrec.videolibrary import VideoLibrary,save_preferences
from loomrec.library import Library
from loomrec.schema import Project,save_project,load_project
class VideoLibraryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.base/'config')});self.env.start();self.videos=self.base/'Videos';self.legacy=self.base/'legacy';self.lib=VideoLibrary(self.videos,self.legacy)
  self.source=self.videos/'Original.mp4';self.source.write_bytes(b'owned synthetic source')
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def test_scan_preserves_legacy_and_excludes_private_sources(self):
  legacy=Library(self.legacy);save_project(Project(title='Legacy'),legacy.new_directory()/'project.json')
  private=self.lib.new_directory();(private/'segment.mp4').write_bytes(b'private')
  entries=self.lib.entries();self.assertEqual({e.title for e in entries},{'Original','Legacy'});self.assertFalse((private/'project.json').exists())
 def test_edit_is_copy_not_hardlink_and_preserves_audio_and_dedupes(self):
  with patch('loomrec.videolibrary.probe',return_value=(4,True)):project=self.lib.create_edit(self.source)
  p=load_project(project);copy=project.parent/p.sources[0].path
  self.assertNotEqual(copy.stat().st_ino,self.source.stat().st_ino);self.assertEqual(copy.read_bytes(),self.source.read_bytes());self.assertEqual([s.kind for s in p.sources],['screen','system'])
  self.source.write_bytes(b'changed external');self.assertEqual(copy.read_bytes(),b'owned synthetic source');self.assertEqual(len(self.lib.entries()),1)
  self.assertEqual(self.lib.create_edit(self.source),project)
 def test_cancel_edit_removes_only_partial_copy(self):
  event=threading.Event();event.set()
  with patch('loomrec.videolibrary.probe',return_value=(4,False)):
   with self.assertRaises(ValueError):self.lib.create_edit(self.source,event)
  self.assertTrue(self.source.exists());self.assertFalse(list(self.lib.root.iterdir()))
 def test_file_trash_restore_conflict_never_overwrites(self):
  moved=self.lib.delete(self.source);self.assertFalse(self.source.exists());self.assertEqual(len(self.lib.entries(trash=True)),1)
  self.source.write_bytes(b'conflict')
  with self.assertRaises(FileExistsError):self.lib.restore(moved)
  self.assertEqual(self.source.read_bytes(),b'conflict');self.source.unlink();self.lib.restore(moved);self.assertEqual(self.source.read_bytes(),b'owned synthetic source')
 def test_previous_folder_survives_new_destination(self):
  save_preferences(previous_video_folders=[str(self.videos)])
  other=VideoLibrary(self.base/'New',self.legacy)
  self.assertIn(self.source,[e.path for e in other.entries()]);other.rename(self.source,'Retained');self.assertIn('Retained',[e.title for e in other.entries()])
 def test_cancelled_probe_starts_no_process(self):
  from loomrec.videolibrary import media_command
  event=threading.Event();event.set()
  with patch('loomrec.videolibrary.subprocess.Popen') as process:
   with self.assertRaises(InterruptedError):media_command(['ffprobe'],1,event)
   process.assert_not_called()
