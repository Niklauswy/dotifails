import os,sys,tempfile,subprocess,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'apps/orbit'))
from utility_data import Notes,Colors,Processes,digest,process_record
class UtilityDataTests(unittest.TestCase):
 def test_legacy_notes_import_once_without_changing_original(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=Path(tmp)/'old.md';old.write_text('## 2026-09-25\nOriginal');n=Notes(Path(tmp)/'notes');n.import_legacy(old);n.import_legacy(old);self.assertEqual(len(n.all()),1);self.assertEqual(old.read_text(),'## 2026-09-25\nOriginal');self.assertEqual(n.all()[0]['body'],old.read_text())
 def test_notes_conflict_trash_and_favorites(self):
  with tempfile.TemporaryDirectory() as tmp:
   n=Notes(tmp);key=n.create('# Title\nSearchable body');n.toggle_favorite(key);self.assertTrue(n.all('body')[0]['favorite']);n.save(key,'# Updated',digest('# Title\nSearchable body'))
   with self.assertRaises(RuntimeError):n.save(key,'lost update',digest('old'))
   n.move(key);self.assertEqual(n.all(),[]);self.assertEqual(len(n.all(trash=True)),1);n.move(key,True);self.assertEqual(n.all()[0]['title'],'Updated')
 def test_colors_recent_and_favorites(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=Colors(Path(tmp)/'colors.json');c.save('#123456');c.save('#123456');c.save('#123456',True);self.assertEqual(c.read(),dict(recent=['#123456'],favorites=['#123456']));c.save('#123456',True);self.assertEqual(c.read()['favorites'],[])
 def test_process_identity_and_signal(self):
  p=subprocess.Popen(['sleep','30'])
  try:
   model=Processes();row=process_record(p.pid);bad=dict(row,start='invalid')
   with self.assertRaises(RuntimeError):model.terminate(bad)
   self.assertIsNone(p.poll());model.terminate(row);self.assertEqual(p.wait(timeout=2),-15)
   with self.assertRaises(PermissionError):model.terminate(process_record(os.getpid()))
  finally:
   if p.poll() is None:p.kill();p.wait()
if __name__=='__main__':unittest.main()
