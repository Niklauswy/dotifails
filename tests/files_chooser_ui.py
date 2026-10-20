import os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
if not (root/'apps/wysun').is_dir():root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'apps/wysun'))
from PySide6.QtCore import Qt,QItemSelectionModel,QEvent,QCoreApplication
from PySide6.QtWidgets import QApplication,QMessageBox
from files_chooser import FileChooser
class ChooserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.config=tempfile.TemporaryDirectory();os.environ['XDG_CONFIG_HOME']=cls.config.name;cls.app=QApplication([])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
  for name in ('first.png','second.png','notes.txt','space ñ.pdf'):(self.base/name).write_bytes(b'fixture')
  (self.base/'folder').mkdir();self.windows=[]
 def wait(self,fn):
  end=time.monotonic()+5
  while time.monotonic()<end:
   self.app.processEvents();time.sleep(.01)
   if fn():return
  raise AssertionError('Qt model timeout')
 def chooser(self,mode='open',**options):
  options['current_folder']=os.fsencode(self.base)+b'\0'
  w=FileChooser(mode,'Selector de prueba',options);self.windows.append(w);w.show()
  self.wait(lambda:w.current().model.rowCount(w.current().model.index(str(self.base)))>=1)
  return w
 def tearDown(self):
  for w in self.windows:
   w.result_uris=[];w.close();self.wait(lambda:w.inline_preview.job is None)
   w.close();w.deleteLater()
  QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents();self.temp.cleanup()
 def select(self,w,names):
  tab=w.current();selection=tab.view().selectionModel();selection.clearSelection()
  for name in names:
   self.wait(lambda:tab.model.index(str(self.base/name)).isValid())
   selection.select(tab.model.index(str(self.base/name)),QItemSelectionModel.Select|QItemSelectionModel.Rows)
 def test_multiple_and_utf8_uris(self):
  w=self.chooser(multiple=True);self.select(w,['first.png','space ñ.pdf']);result=[];w.completed.connect(lambda *args:result.append(args));w.accept_selection()
  self.wait(lambda:bool(result));self.assertEqual(result[0][0],0);self.assertEqual(set(result[0][1]['uris']),{(self.base/name).as_uri() for name in ('first.png','space ñ.pdf')})
 def test_filter_intersects_search_and_keeps_folders(self):
  w=self.chooser(filters=[('Imágenes',[(1,'image/*')]),('Texto',[(0,'*.txt')])]);tab=w.current()
  self.wait(lambda:tab.model.index(str(self.base/'first.png')).isValid())
  self.assertFalse(tab.model.index(str(self.base/'notes.txt')).isValid())
  w.filter_edit.setText('second');self.wait(lambda:not tab.model.index(str(self.base/'first.png')).isValid())
  self.assertTrue(tab.model.index(str(self.base/'second.png')).isValid());self.assertTrue(tab.model.index(str(self.base/'folder')).isValid())
  w.filter_edit.clear();w.filter_box.setCurrentIndex(1);self.wait(lambda:tab.model.index(str(self.base/'notes.txt')).isValid())
 def test_cancel_returns_no_files(self):
  w=self.chooser();result=[];w.completed.connect(lambda *args:result.append(args));w.close();self.assertEqual(result,[(1,{})])
 def test_directory_accepts_current_folder(self):
  w=self.chooser(directory=True);w.accept_selection();self.assertEqual(w.result_uris,[self.base.as_uri()])
 def test_single_selection_and_disappearing_file(self):
  w=self.chooser();self.select(w,['first.png']);(self.base/'first.png').unlink();w.accept_selection();self.assertFalse(w.result_uris);self.assertTrue(w.error.text())
 def test_save_is_nonwriting_and_confirms_overwrite(self):
  w=self.chooser('save',current_name='first.png')
  with patch.object(QMessageBox,'question',return_value=QMessageBox.No):w.accept_selection()
  self.assertFalse(w.result_uris)
  with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):w.accept_selection()
  self.assertEqual(w.result_uris,[(self.base/'first.png').as_uri()]);self.assertEqual((self.base/'first.png').read_bytes(),b'fixture')
 def test_save_rejects_path_escape(self):
  w=self.chooser('save',current_name='../escape');w.accept_selection();self.assertFalse(w.result_uris)
 def test_savefiles_chooses_unique_names_without_writing(self):
  w=self.chooser('savefiles',files=[b'first.png\0',b'new.txt\0']);w.accept_selection()
  self.assertEqual(w.result_uris,[(self.base/'first (1).png').as_uri(),(self.base/'new.txt').as_uri()]);self.assertFalse((self.base/'new.txt').exists())
 def test_choices_preserve_values(self):
  w=self.chooser(choices=[('mode','Modo',[('a','A'),('b','B')],'b'),('readonly','Solo lectura',[],'true')])
  self.select(w,['first.png']);result=[];w.completed.connect(lambda *args:result.append(args));w.accept_selection();self.wait(lambda:bool(result))
  self.assertEqual(result[0][1]['choices'],[('mode','b'),('readonly','true')])
if __name__=='__main__':unittest.main()
