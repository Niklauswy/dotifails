import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile,time,unittest,json
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QImage,QColor,QPainter,QFont
from enhanced import OrbitV2,RichSnippet,SearchMenu,STYLE
from data_v2 import StoreV2,color_value,color_formats,template
from media import OCRJob,png_bytes
from icons import emoji_pixmap
from core import Store,calculate

def wait(ms):
 end=time.monotonic()+ms/1000
 while time.monotonic()<end:QApplication.processEvents();time.sleep(.005)

class DataTests(unittest.TestCase):
 def test_colors_and_math(self):
  for value,expected in [('F54927','#F54927'),('#abc','#AABBCC'),('rgb(245, 73, 39)','#F54927'),('hsl(0, 100%, 50%)','#FF0000')]:self.assertEqual(color_value(value),expected)
  self.assertIsNone(color_value('rgb(999, 0, 0)'));self.assertIsNone(color_value('hello'));self.assertEqual(calculate('12x5'),'60');self.assertEqual(calculate('12 x 5'),'60');self.assertEqual(calculate('1,5x2'),'3');self.assertEqual(color_formats('F54927')['RGB'],'rgb(245, 73, 39)')
 def test_old_history_migration_and_pins(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=Store(tmp);old.clip('text','F54927');old.save_snippet('Antes','!antes','No perder');old.db.close();s=StoreV2(tmp);self.assertEqual(s.clips()[0]['kind'],'color');self.assertEqual(s.snippets()[0]['body'],'No perder');ident=s.clips()[0]['id'];s.pin(ident);s.db.execute('UPDATE clips SET stamp=0');s.prune();self.assertEqual(len(s.clips()),1);s.pin(ident);s.prune();self.assertEqual(s.clips(),[]);s.db.close()
 def test_templates(self):self.assertNotIn('{',template('{date+4} {week} {clipboard}','Hola'));self.assertIn('Hola',template('{clipboard}','Hola'))

class UITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion');cls.app.setStyleSheet(STYLE)
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.s=StoreV2(self.tmp.name);self.w=OrbitV2(self.s,test=True);self.w.show();self.w.resize(860,550);self.app.processEvents()
 def tearDown(self):
  self.w.status_timer.stop();self.w.debounce.stop();self.w.prune_timer.stop()
  for j in self.w.jobs+[self.w.network_scan,self.w.status_scan]:
   if j:j.wait(6000)
  self.w.hide();self.w.deleteLater();self.app.sendPostedEvents(None,QEvent.DeferredDelete);self.s.db.close();self.tmp.cleanup()
 def test_color_preview_and_filter(self):
  self.s.clip('text','F54927',source='Test');self.s.clip('text','Hello');self.w.set_mode('clipboard');self.w.choose_filter('Colores');self.assertEqual(self.w.results.count(),1);self.assertTrue(self.w.picture.isVisible());self.assertIn('RGB',self.w.metadata.text())
 def test_emoji_color_grid_pin(self):
  self.w.set_mode('emoji');self.assertEqual(self.w.results.gridSize().width(),85);self.assertGreater(self.w.results.count(),1000)
  image=emoji_pixmap('😀',48).toImage();colored=sum(1 for x in range(48) for y in range(48) if image.pixelColor(x,y).alpha()>100 and image.pixelColor(x,y).red()>image.pixelColor(x,y).blue()+50);self.assertGreater(colored,50)
  self.w.choose_filter('Favoritos');before=self.w.results.count();self.w.pin_current();self.assertEqual(self.w.results.count(),before-1)
 def test_ocr_search_thumbnail_metadata(self):
  image=QImage(950,180,QImage.Format_RGB32);image.fill(QColor('white'));p=QPainter(image);p.setFont(QFont('DejaVu Sans',36));p.setPen(QColor('black'));p.drawText(30,105,'FACTURA SEPTIEMBRE 2026');p.end();ident=self.s.clip('image','Imagen de prueba',png_bytes(image),source='Test');job=OCRJob(ident,png_bytes(image));job.done.connect(self.s.save_media);job.run();self.w.set_mode('clipboard');self.w.search.setText('septiembre');wait(90);self.assertEqual(self.w.results.count(),1);r=self.w.current();self.assertIn('SEPTIEMBRE',r['ocr']);self.assertFalse(r['thumbnail'].isNull());self.assertIn('Dimensiones',self.w.metadata.text())
 def test_searchable_actions(self):
  self.s.clip('text','F54927');self.w.set_mode('clipboard');self.w.actions();self.w.popup.search.setText('RGB');self.assertEqual(self.w.popup.list.count(),1);self.w.popup.choose();wait(20);self.assertEqual(self.app.clipboard().text(),'rgb(245, 73, 39)')
 def test_rich_snippet(self):
  self.s.rich_snippet('Saludo','!hola','Hola {date}','<b>Hola {date}</b>','clipboard');self.w.set_mode('snippets');self.w.activate();self.assertTrue(self.app.clipboard().mimeData().hasHtml());self.assertIn('<b>',self.app.clipboard().mimeData().html());self.assertEqual(self.s.snippets()[0]['uses'],1)
 def test_power_cancel_never_executes(self):
  self.w.set_mode('power');self.w.results.setCurrentRow(4)
  QTimer.singleShot(30,lambda:QApplication.activeModalWidget().reject())
  with patch('enhanced.run') as run:self.w.activate();run.assert_not_called()
 def test_network_and_status_read_only(self):
  self.w.set_mode('network')
  for i in range(300):
   wait(10)
   if self.w.network_rows:break
  self.assertTrue(self.w.network_rows);self.assertTrue(any(r['kind']=='network_action' for r in self.w.network_rows));self.w.set_mode('system')
  for i in range(100):
   wait(10)
   if self.w.status_rows:break
  self.assertEqual(len(self.w.status_rows),5)

if __name__=='__main__':unittest.main(verbosity=2)
