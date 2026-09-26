import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'apps/orbit'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
import time
def wait(ms):
 end=time.monotonic()+ms/1000
 while time.monotonic()<end:QApplication.processEvents();time.sleep(.005)
from utilities import NotesWindow,ColorWindow,ProcessesWindow
class UtilityUITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_notes_edit_preview_recover(self):
  with tempfile.TemporaryDirectory() as tmp:
   w=NotesWindow(tmp);w.present();w.new();w.editor.setPlainText('# Test\nBody');self.assertTrue(w.save());w.toggle_preview();self.assertIn('Body',w.preview.toPlainText());w.delete();self.assertEqual(w.list.count(),0);w.folder.setCurrentIndex(1);self.assertEqual(w.list.count(),1);w.delete();w.folder.setCurrentIndex(0);self.assertEqual(w.list.count(),1);w.close()
 def test_color_copy(self):
  with tempfile.TemporaryDirectory() as tmp:
   w=ColorWindow(Path(tmp)/'colors.json');w.present();w.entry.setText('#123456');w.formats.setCurrentIndex(1);w.copy();self.assertEqual(self.app.clipboard().text(),'rgb(18, 52, 86)');w.favorite();self.assertEqual(w.recent.count(),1);w.close()
 def test_process_scan(self):
  w=ProcessesWindow();w.present();wait(500);self.assertTrue(w.rows);w.search.setText(str(os.getpid()));self.assertGreater(w.list.count(),0);w.close();self.assertFalse(w.timer.isActive());w.worker.wait(3000)
if __name__=='__main__':unittest.main()
