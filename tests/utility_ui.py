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
   w=NotesWindow(tmp);w.present();w.new();w.editor.setPlainText('# Test\nBody');self.assertTrue(w.save());w.toggle_preview();self.assertIn('Body',w.preview.toPlainText());w.delete();self.assertEqual(w.list.count(),0);w.folder.setCurrentIndex(2);self.assertEqual(w.list.count(),1);w.delete();w.folder.setCurrentIndex(0);self.assertEqual(w.list.count(),1);w.close()
 def test_notes_external_edit_preserves_draft_and_copy(self):
  with tempfile.TemporaryDirectory() as tmp:
   w=NotesWindow(tmp);w.new();key=w.key;w.editor.setPlainText('draft');w.store.path(key).write_text('external');self.assertFalse(w.save());self.assertEqual(w.editor.toPlainText(),'draft');w.copy_note();self.assertNotEqual(w.key,key);self.assertEqual(w.editor.toPlainText(),'draft');self.assertEqual(w.store.path(key).read_text(),'external');w.close()
 def test_color_formats_invalid_input_and_palette(self):
  with tempfile.TemporaryDirectory() as tmp:
   w=ColorWindow(Path(tmp)/'colors.json');w.entry.setText('rgb(255, 0, 0)');self.assertEqual(w.fields['HEX'].text(),'#FF0000');w.favorite();w.copy_palette();self.assertIn('--color-1: #FF0000;',self.app.clipboard().text());w.entry.setText('hsl(120, 100%, 50%)');self.assertEqual(w.fields['HEX'].text(),'#00FF00');w.entry.setText('not a color');w.copy();self.assertIn('--color-1',self.app.clipboard().text());self.assertEqual(w.formats.count(),0);w.close()
 def test_color_copy(self):
  with tempfile.TemporaryDirectory() as tmp:
   w=ColorWindow(Path(tmp)/'colors.json');w.present();w.entry.setText('#123456');w.formats.setCurrentIndex(1);w.copy();self.assertEqual(self.app.clipboard().text(),'rgb(18, 52, 86)');w.favorite();self.assertEqual(w.recent.count(),1);w.close()
 def test_process_scan(self):
  w=ProcessesWindow();w.present();wait(700);self.assertTrue(w.rows);w.search.setText(str(os.getpid()));self.assertGreater(w.tree.topLevelItemCount(),0);w.close();self.assertFalse(w.timer.isActive());w.worker.wait(3000)
if __name__=='__main__':unittest.main()
