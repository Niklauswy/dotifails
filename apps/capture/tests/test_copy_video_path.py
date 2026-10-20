"""Synthetic files and Qt offscreen clipboard only; no desktop clipboard/media."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import Qt,QEvent
from PySide6.QtGui import QKeyEvent,QShortcut
from PySide6.QtWidgets import QApplication,QListWidgetItem
from loomrec.videolibrary import absolute_video_path
from loomrec.library import Library
from loomrec.ui.main import Window,apply_theme

class CopyVideoPathTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.app=QApplication.instance() or QApplication([])
  assert cls.app.platformName()=='offscreen','These tests must not use the user clipboard'
  apply_theme(cls.app)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.root/'config'),'XDG_STATE_HOME':str(self.root/'state')});self.env.start()
  self.w=Window(Library(self.root/'projects'),False);self.w.timer.stop();self.w.stack.setCurrentWidget(self.w.library_page)
  self.clipboard=self.app.clipboard();self.clipboard.setText('untouched isolated clipboard')
 def tearDown(self):
  self.w.quick.hide_all();self.w.close();self.w.deleteLater();self.app.processEvents();self.env.stop();self.temp.cleanup()
 def select(self,path):
  self.w.items.clear();item=QListWidgetItem('Synthetic video');item.setData(Qt.UserRole,str(path));self.w.items.addItem(item);self.w.items.setCurrentRow(0);self.w.items.show();self.w.library_empty.hide();return item
 def test_unicode_spaces_exact_absolute_path_and_confirmation(self):
  path=self.root/'Explicación con espacios 日本語.mp4';path.write_bytes(b'synthetic non-decoded video')
  self.select(path);self.assertTrue(self.w.library_copy_path.isEnabled());self.w.library_copy_path.click()
  self.assertEqual(self.clipboard.text(),str(path.resolve()));self.assertEqual(self.w.statusBar().currentMessage(),'Ruta copiada')
  self.assertTrue(Path(self.clipboard.text()).is_absolute())
 def test_project_and_private_sources_never_copy_or_encode(self):
  project=self.root/'recording';project.mkdir();manifest=project/'project.json';manifest.write_text('{}');raw=project/'segment.mp4';raw.write_bytes(b'fixture')
  for path in (manifest,raw):
   self.select(path)
   with patch('loomrec.render.RenderJob') as render:self.w.copy_video_path();render.assert_not_called()
   self.assertEqual(self.clipboard.text(),'untouched isolated clipboard');self.assertIn('MP4 aún no disponible' if path==manifest else 'Exporta el video para copiar su ruta',self.w.statusBar().currentMessage())
  for dirname in ('.preview','.wybie'):
   folder=self.root/dirname;folder.mkdir();video=folder/'cached.mp4';video.write_bytes(b'fixture')
   with self.assertRaisesRegex(ValueError,'Exporta'):absolute_video_path(video)
 def test_missing_no_selection_and_trash_preserve_clipboard(self):
  self.assertFalse(self.w.library_copy_path.isEnabled());self.w.copy_video_path()
  path=self.root/'missing.mp4';self.select(path);self.assertFalse(self.w.library_copy_path.isEnabled())
  self.w.copy_video_path();self.assertIn('ya no existe',self.w.statusBar().currentMessage())
  path.write_bytes(b'fixture');self.select(path);path.unlink();self.w.copy_video_path();self.assertFalse(self.w.library_copy_path.isEnabled())
  path.write_bytes(b'fixture');self.select(path)
  with patch.object(self.w,'refresh_library'):self.w.trash.blockSignals(True);self.w.trash.setChecked(True);self.w.trash.blockSignals(False)
  self.w.update_copy_path_action();self.assertFalse(self.w.library_copy_path.isEnabled());self.w.copy_video_path()
  self.assertEqual(self.clipboard.text(),'untouched isolated clipboard')
 def test_final_export_entry_copies_file_without_project_inference(self):
  path=self.root/'Final.mp4';path.write_bytes(b'fixture');self.select(path);self.w.copy_video_path();self.assertEqual(self.clipboard.text(),str(path))
  folder=self.root/'folder';folder.mkdir()
  for invalid in (folder,self.root/'thumbnail.jpg'):
   if invalid.suffix:invalid.write_bytes(b'fixture')
   with self.assertRaises(ValueError):absolute_video_path(invalid)
 def test_copy_shortcut_scoped_to_list_and_search_keeps_text_copy(self):
  path=self.root/'Video.mp4';path.write_bytes(b'fixture');self.select(path)
  shortcuts=self.w.items.findChildren(QShortcut);copy=[s for s in shortcuts if s.key().toString()=='Ctrl+C'];self.assertEqual(len(copy),1);self.assertEqual(copy[0].context(),Qt.WidgetShortcut)
  self.w.show();self.app.processEvents()
  with patch.object(self.w,'refresh_library'):
   self.w.search.blockSignals(True);self.w.search.setText('copiar búsqueda');self.w.search.blockSignals(False)
  self.w.search.setFocus();self.w.search.selectAll();self.app.processEvents()
  self.app.sendEvent(self.w.search,QKeyEvent(QEvent.KeyPress,Qt.Key_C,Qt.ControlModifier));self.app.sendEvent(self.w.search,QKeyEvent(QEvent.KeyRelease,Qt.Key_C,Qt.ControlModifier))
  self.assertEqual(self.clipboard.text(),'copiar búsqueda')
  self.w.items.setFocus();self.app.processEvents();self.app.sendEvent(self.w.items,QKeyEvent(QEvent.KeyPress,Qt.Key_C,Qt.ControlModifier));self.app.sendEvent(self.w.items,QKeyEvent(QEvent.KeyRelease,Qt.Key_C,Qt.ControlModifier));self.assertEqual(self.clipboard.text(),str(path))
 def test_library_footer_fits_at_tiled_width(self):
  self.w.resize(940,1054);self.w.show();self.app.processEvents()
  button=self.w.library_copy_path
  self.assertTrue(button.accessibleName());self.assertTrue(button.toolTip());self.assertTrue(button.focusPolicy()&Qt.TabFocus)
  self.assertLess(button.geometry().right(),self.w.library_page.width());self.assertLess(self.w.library_more.geometry().right(),self.w.library_page.width())
