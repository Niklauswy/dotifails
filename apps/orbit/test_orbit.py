import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile,time,unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import Qt,QBuffer,QByteArray,QIODevice
from PySide6.QtGui import QImage,QColor
from PySide6.QtCore import QEvent
from PySide6.QtGui import QKeyEvent
class QTest:
 @staticmethod
 def qWait(ms):
  end=time.monotonic()+ms/1000
  while time.monotonic()<end:QApplication.processEvents();time.sleep(.005)
 @staticmethod
 def keyClick(widget,key):QApplication.sendEvent(widget,QKeyEvent(QEvent.KeyPress,key,Qt.NoModifier))
from core import Store,calculate,sensitive,expand_snippet,file_index
from orbit import Orbit,STYLE,SnippetDialog,PreviewJob

class CoreTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
 def tearDown(self):self.store.db.close();self.tmp.cleanup()
 def test_calculator(self):
  for q,v in [('24 × 8 / 16','12'),('15% de 80','12'),('10 km a mi','6.21371192237 mi'),('32 f a c','0 c'),('2^8','256'),('20%','0.2')]:self.assertEqual(calculate(q),v)
  for q in ['__import__("os").system("true")','2**999999999','1/0','[1]*999999','hola','2**2**200']:self.assertIsNone(calculate(q))
 def test_history_dedupe_pruning_and_sensitive(self):
  self.store.clip('text','sample');self.store.clip('text','sample');self.assertEqual(len(self.store.clips()),1)
  self.store.clip('text','api_key=not-a-real-secret');self.assertEqual(len(self.store.clips()),1)
  self.assertTrue(sensitive('', ['application/x-keepassxc']))
  self.store.db.execute('UPDATE clips SET stamp=?',(time.time()-8*86400,));self.store.prune();self.assertEqual(self.store.clips(),[])
  self.assertEqual((Path(self.tmp.name)/'orbit.sqlite3').stat().st_mode & 0o777,0o600)
 def test_snippets(self):
  self.store.save_snippet('Fecha','!fecha','Hoy: {date}');s=self.store.snippets()[0];self.assertNotIn('{date}',expand_snippet(s['body']))
  self.store.save_snippet('Hora','!hora','{time}',s['id']);self.assertEqual(self.store.snippets()[0]['title'],'Hora');self.store.delete_snippet(s['id']);self.assertEqual(self.store.snippets(),[])
 def test_index_exclusions(self):
  p=Path(self.tmp.name);(p/'hello.txt').write_text('Hello');(p/'.hidden').mkdir();(p/'.hidden/secret.txt').write_text('private');(p/'node_modules').mkdir();(p/'node_modules/no.txt').write_text('no')
  self.assertIn('hello.txt',[x[0] for x in file_index(p)]);self.assertNotIn('secret.txt',[x[0] for x in file_index(p)]);self.assertNotIn('no.txt',[x[0] for x in file_index(p)])

class GuiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion');cls.app.setStyleSheet(STYLE)
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.s=Store(self.tmp.name);self.w=Orbit(self.s,test=True);self.w.show_mode('home');self.app.processEvents()
 def tearDown(self):
  for j in self.w.jobs:j.wait(5000)
  self.w.debounce.stop();self.w.prune_timer.stop();self.w.hide();self.w.deleteLater();self.app.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents();self.s.db.close();self.tmp.cleanup()
 def test_search_calculate_and_copy(self):
  self.w.search.setText('24 × 8 / 16');QTest.qWait(100);self.assertEqual(self.w.current()['result'],'12');self.w.activate();self.assertEqual(self.app.clipboard().text(),'12');self.assertFalse(self.w.isVisible());self.assertEqual(self.s.calcs()[0]['result'],'12')
 def test_clipboard_text_color_image(self):
  self.app.clipboard().setText('Prueba local');self.w.capture_clip();self.app.clipboard().setText('#FF6363');self.w.capture_clip()
  image=QImage(120,80,QImage.Format_ARGB32);image.fill(QColor('#7aa2f7'));self.app.clipboard().setImage(image);self.w.capture_clip();self.assertEqual(len(self.s.clips()),3)
  self.w.set_mode('clipboard');self.assertEqual(self.w.current()['clip_kind'],'image');self.assertTrue(self.w.picture.isVisible());self.w.activate();self.assertEqual(self.app.clipboard().image().size(),image.size())
  self.w.ignore_clip=False;self.w.paused=True;self.app.clipboard().setText('Not stored');self.w.capture_clip();self.assertEqual(len(self.s.clips()),3)
 def test_snippet_keyboard_navigation(self):
  self.s.save_snippet('Saludo','!hola','Hola, {date}');self.w.set_mode('snippets');self.assertEqual(self.w.current()['title'],'Saludo');self.w.activate();self.assertTrue(self.app.clipboard().text().startswith('Hola,'))
  self.w.show_mode('home');self.w.search.setText('portapapeles');QTest.qWait(100);QTest.keyClick(self.w.search,Qt.Key_Return);self.assertEqual(self.w.mode,'clipboard')
 def test_empty_and_actions(self):
  self.w.set_mode('snippets');self.assertTrue(self.w.empty.isVisible());self.w.actions();self.assertTrue(self.w.menu.actions());self.w.menu.close()
  d=SnippetDialog(self.w);d.title.setText('Example');d.body.setPlainText('Text');d.save();self.assertEqual(d.result(),QDialog.DialogCode.Accepted)
 def test_text_file_preview(self):
  p=Path(self.tmp.name)/'example.txt';p.write_text('Vista previa verificada',encoding='utf8');self.w.files=[('example.txt',str(p),'example.txt')];self.w.indexed_at=time.monotonic();self.w.set_mode('files');QTest.qWait(300);self.assertEqual(self.w.body.toPlainText(),'Vista previa verificada')

class MediaTests(unittest.TestCase):
 def test_pdf_and_video_thumbnails(self):
  import subprocess
  from PySide6.QtGui import QPdfWriter,QPainter
  app=QApplication.instance() or QApplication([])
  with tempfile.TemporaryDirectory() as tmp:
   pdf=str(Path(tmp)/'preview.pdf');writer=QPdfWriter(pdf);p=QPainter(writer);p.drawText(100,300,'Documento de prueba');p.end();del writer
   video=str(Path(tmp)/'preview.mp4');subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:d=0.2','-pix_fmt','yuv420p',video],check=True)
   for path in (pdf,video):
    result=[];job=PreviewJob(path);job.ready.connect(lambda p,d:result.append(d));job.run();self.assertFalse(result[0]['image'].isNull())

if __name__=='__main__':unittest.main(verbosity=2)
