"""Launcher-integrated clipboard regression tests using private temporary data."""
import os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/wysun'))
from PySide6.QtWidgets import QApplication,QMessageBox,QWidget
from PySide6.QtCore import Qt,QItemSelectionModel,QEvent,QCoreApplication,QPoint
from PySide6.QtGui import QImage,QColor,QKeyEvent
from data_v2 import StoreV2
from desktop_v3 import OrbitV3
from clipboard_launcher import LauncherClipboard
from ui_theme import PALETTE_STYLE
from theme_tokens import theme_css
from media import png_bytes

class ClipboardUITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.config=tempfile.TemporaryDirectory();os.environ['XDG_CONFIG_HOME']=cls.config.name;cls.app=QApplication.instance() or QApplication([]);cls.app.setStyleSheet(theme_css(PALETTE_STYLE))
 @classmethod
 def tearDownClass(cls):cls.app.clipboard().clear();cls.config.cleanup()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=StoreV2(self.temp.name);self.a=self.store.clip('text','Texto de prueba',source='Editor');self.b=self.store.clip('color','#C19AFA',source='Diseño')
  self.owner=OrbitV3(store=self.store,test=True);self.owner.resize(860,550);self.owner.set_mode('clipboard');self.owner.show();self.owner.activateWindow();self.w=self.owner.clipboard_ui;self.pump()
 def pump(self,t=.06):
  end=time.monotonic()+t
  while time.monotonic()<end:self.app.processEvents();time.sleep(.005)
 def key(self,target,key,mods=Qt.NoModifier):
  self.app.sendEvent(target,QKeyEvent(QEvent.KeyPress,key,mods));self.app.sendEvent(target,QKeyEvent(QEvent.KeyRelease,key,mods));self.pump(.03)
 def tearDown(self):
  menu=getattr(self.w,'active_menu',None)
  if menu:menu.close()
  self.w.shutdown_jobs();self.owner.hide();self.owner.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.pump(.01);self.store.db.close();self.temp.cleanup()
 def select(self,ids):
  self.w.cards.clearSelection()
  for i in range(self.w.cards.count()):
   item=self.w.cards.item(i)
   if item.data(Qt.UserRole)['id'] in ids:self.w.cards.setCurrentItem(item,QItemSelectionModel.NoUpdate);item.setSelected(True)
 def test_history_uses_same_window_size_search_chrome_and_theme(self):
  self.assertIsInstance(self.w,LauncherClipboard);self.assertFalse(self.w.isWindow());self.assertIs(self.w.window(),self.owner);self.assertIs(self.w.search,self.owner.search);self.assertIs(self.w.copy_button,self.owner.go)
  self.assertEqual((self.owner.width(),self.owner.height()),(860,550));self.assertTrue(self.owner.tabs['clipboard'].isChecked());self.assertEqual(self.w.styleSheet(),'')
  self.owner.set_mode('home');self.assertIs(self.owner.content_pages.currentWidget(),self.owner.content_home);self.assertFalse(self.w.isVisible());self.assertEqual((self.owner.width(),self.owner.height()),(860,550))
  self.owner.set_mode('clipboard');self.assertIs(self.owner.content_pages.currentWidget(),self.w);self.assertTrue(self.w.isVisible());self.assertEqual(self.w.cards.count(),2)
 def test_filters_sources_collections_and_favorites(self):
  self.w.choose_type('text');self.assertEqual(self.w.cards.count(),1);self.w.choose_type('');self.select([self.a]);self.owner.pin_current();self.w.choose_type('favorite');self.assertEqual(self.w.cards.count(),1)
  c=self.w.library.create_collection('Personal');self.w.assign_selected(c);self.w.collection=c;self.w.refresh(True);self.assertEqual(self.w.current()['id'],self.a)
 def test_native_search_results_keyboard_and_copy(self):
  self.owner.search.setFocus();self.key(self.owner.search,Qt.Key_Left);self.assertEqual(self.app.focusWidget(),self.owner.search);self.key(self.owner.search,Qt.Key_Down);self.assertEqual(self.app.focusWidget(),self.w.cards)
  self.w.cards.setCurrentRow(0);self.key(self.w.cards,Qt.Key_Down);self.assertEqual(self.w.current()['id'],self.a);self.key(self.w.cards,Qt.Key_C,Qt.ControlModifier);self.assertEqual(self.app.clipboard().text(),'Texto de prueba');self.assertTrue(self.owner.isVisible())
  self.key(self.w.cards,Qt.Key_Return);self.assertFalse(self.owner.isVisible())
 def test_native_navigation_shortcuts_are_preserved(self):
  self.w.cards.setFocus();self.key(self.w.cards,Qt.Key_1,Qt.AltModifier);self.assertEqual(self.owner.mode,'home');self.assertTrue(self.owner.tabs['home'].isChecked());self.key(self.owner.search,Qt.Key_2,Qt.AltModifier);self.assertEqual(self.owner.mode,'clipboard')
 def test_ocr_visible_text_copy_retry_and_zoom_are_preserved(self):
  image=QImage(70,50,QImage.Format_RGB32);image.fill(QColor('white'));ident=self.store.clip('image','Imagen',png_bytes(image));self.store.save_media(ident,'Entrega 47291',{'ocr_status':'listo'},None);self.w.refresh(True);self.select([ident]);self.assertEqual(self.w.stack.currentIndex(),1)
  from PySide6.QtCore import QPointF
  self.w.image.zoom_at(2,QPointF(15,15));self.w.refresh(True);self.assertEqual(self.w.image.zoom,2);self.w.show_ocr_text();self.w.refresh(True);self.w.copy_selected();self.assertEqual(self.app.clipboard().text(),'Entrega 47291');self.assertFalse(self.app.clipboard().mimeData().hasImage())
  self.w.toggle_ocr_text();self.w.copy_selected();self.assertTrue(self.app.clipboard().mimeData().hasImage())
  with patch.object(self.owner,'next_ocr') as next_ocr:self.w.retry_ocr();next_ocr.assert_called_once()
 def test_web_hero_title_description_and_original_url_copy(self):
  url='https://example.org/post';ident=self.store.clip('url',url);self.w.refresh(True);self.select([ident]);image=QImage(400,220,QImage.Format_RGB32);image.fill(QColor('green'))
  self.w.link_ready(ident,url,{'status':'ready','stamp':time.time(),'title':'Una web','description':'Descripción','site':'Example'},png_bytes(image));self.assertEqual(self.w.stack.currentIndex(),4);self.assertEqual(self.w.link_title.text(),'Una web');self.assertFalse(self.w.link_hero.pixmap.isNull());self.w.copy_selected();self.assertEqual(self.app.clipboard().text(),url)
 def test_color_values_fit_in_native_launcher_and_shortcuts(self):
  self.select([self.b]);self.pump();self.assertEqual((self.owner.width(),self.owner.height()),(860,550))
  for name,row in self.w.color_rows.items():
   self.assertTrue(row.value);self.assertTrue(self.w.stack.rect().contains(row.mapTo(self.w.stack,QPoint())),name);self.assertTrue(self.w.stack.rect().contains(row.mapTo(self.w.stack,row.rect().bottomRight())),name)
  self.w.cards.setFocus();self.key(self.w.cards,Qt.Key_2,Qt.ControlModifier|Qt.AltModifier);self.assertTrue(self.app.clipboard().text().startswith('rgb('));self.assertEqual(self.owner.mode,'clipboard')
 def test_copy_menu_keyboard_and_footer_actions(self):
  self.select([self.b]);self.w.cards.setFocus();self.key(self.w.cards,Qt.Key_C,Qt.ControlModifier|Qt.ShiftModifier);menu=self.w.active_menu;self.assertTrue(menu.isVisible());self.key(menu,Qt.Key_Down);self.key(menu,Qt.Key_Return);self.assertTrue(self.app.clipboard().text().startswith('rgb('))
  self.owner.actions();self.assertTrue(self.w.active_menu.isVisible());self.w.active_menu.close()
 def test_groups_keep_content_and_reordering(self):
  self.select([self.a,self.b]);self.w.combine_selected();self.assertEqual(self.w.current()['kind'],'bundle');self.assertEqual(self.w.parts.count(),2);self.w.parts.setCurrentRow(0);before=[p['text'] for p in self.w.library.parts(self.w.current()['id'])];self.w.move_part(1);self.assertEqual([p['text'] for p in self.w.library.parts(self.w.current()['id'])],list(reversed(before)))
 def test_delete_confirmation_and_refresh_selection(self):
  self.select([self.a]);self.store.clip('text','Nuevo');self.w.refresh();self.assertEqual(self.w.selected_ids(),[self.a])
  with patch.object(QMessageBox,'question',return_value=QMessageBox.No):self.owner.delete_current()
  self.assertIsNotNone(self.w.library.row(self.a))
  with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):self.owner.delete_current()
  self.assertIsNone(self.w.library.row(self.a))
 def test_hiding_preview_expands_results_and_restores_detail(self):
  self.w.toggle_detail();self.pump();self.assertFalse(self.w.detail.isVisible());self.assertGreater(self.w.list_column.width(),325);self.w.toggle_detail();self.pump();self.assertTrue(self.w.detail.isVisible());self.assertLessEqual(self.w.list_column.width(),325)
 def test_common_footer_activation_copies_and_closes(self):
  self.select([self.a]);self.owner.activate();self.assertFalse(self.owner.isVisible());self.assertEqual(self.app.clipboard().text(),'Texto de prueba')
 def test_leaving_history_restores_other_previews_and_clipboard_actions(self):
  self.w.show_ocr_text();self.owner.set_mode('calculator');self.assertIs(self.owner.content_pages.currentWidget(),self.owner.content_home);self.assertFalse(self.w.isVisible());self.owner.search.setText('2+2');self.pump(.15);self.assertEqual(self.owner.current()['result'],'4');self.owner.set_mode('clipboard');self.assertTrue(self.w.isVisible());self.assertIs(self.owner.content_pages.currentWidget(),self.w)
if __name__=='__main__':unittest.main()
