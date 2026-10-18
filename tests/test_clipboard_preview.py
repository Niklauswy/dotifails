"""Regression coverage for real desktop PATH, OCR output, and link preview boundaries."""
import os,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.append(str(Path(__file__).resolve().parents[1]/'apps/orbit'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter,QColor,QFont
from PySide6.QtCore import QEventLoop,QTimer
from link_preview import PageMetadata,preview,fetch_public
from media import OCRJob,png_bytes
from ocr_engine import tesseract_binary

class ClipboardPreviewTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_metadata_entities_relative_image_and_title(self):
  parser=PageMetadata();parser.feed('<title>Fallback</title><meta property="og:title" content="Notas &amp; ideas"><meta name="description" content="Una descripción"><meta property="og:image" content="/hero.png">')
  result=parser.metadata('https://example.org/post');self.assertEqual(result['title'],'Notas & ideas');self.assertEqual(result['image_url'],'https://example.org/hero.png')
 def test_preview_fetches_real_hero_bytes_and_bounds_content(self):
  image=QImage(480,250,QImage.Format_RGB32);image.fill(QColor('#aa9955'));blob=png_bytes(image);calls=[]
  def fetch(url,limit,accept):
   calls.append((url,limit))
   return (url,b'<meta property="og:title" content="My page"><meta property="og:image" content="/image.png"><meta name="description" content="Read me">','text/html') if len(calls)==1 else (url,blob,'image/png')
  meta,hero=preview('https://example.org/',fetch=fetch);self.assertEqual(meta['status'],'ready');self.assertEqual(meta['description'],'Read me');self.assertFalse(QImage.fromData(hero).isNull());self.assertEqual(calls[1][0],'https://example.org/image.png')
 def test_block_private_and_credentialed_urls(self):
  for url in ['file:///etc/passwd','https://user:secret@example.org/','http://127.0.0.1/','http://[::1]/']:
   with self.assertRaises(ValueError):fetch_public(url,1000,'text/html')
 def test_redirect_target_is_revalidated(self):
  from unittest.mock import MagicMock
  response=MagicMock();response.status=302;response.getheader.return_value='http://127.0.0.1/private'
  connection=MagicMock();connection.getresponse.return_value=response
  def lookup(host,*args,**kwargs):return [(2,1,6,'',('93.184.216.34' if host=='example.org' else '127.0.0.1',80))]
  with patch('link_preview.socket.getaddrinfo',side_effect=lookup),patch('link_preview.socket.create_connection'),patch('link_preview.http.client.HTTPConnection',return_value=connection):
   with self.assertRaises(ValueError):fetch_public('http://example.org/',1000,'text/html')
   self.assertEqual(connection.request.call_count,1)
 def test_missing_hero_keeps_title_and_network_failure_has_explicit_state(self):
  def html(*args):return ('https://example.org/',b'<title>Just text</title>','text/html')
  meta,image=preview('https://example.org',fetch=html);self.assertEqual(meta['title'],'Just text');self.assertFalse(image)
  def fail(*args):raise OSError('offline')
  meta,image=preview('https://example.org',fetch=fail);self.assertEqual(meta['status'],'unavailable');self.assertFalse(image)
 def test_async_ocr_under_graphical_session_path(self):
  if not tesseract_binary():self.skipTest('Tesseract no instalado')
  image=QImage(720,180,QImage.Format_RGB32);image.fill(QColor('#202024'));painter=QPainter(image);painter.setPen(QColor('#f7f7f8'));painter.setFont(QFont('DejaVu Sans',12));painter.drawText(25,55,'Entrega del proyecto 47291');painter.drawText(25,95,'Revisar los documentos el viernes');painter.end()
  result=[];loop=QEventLoop();job=OCRJob(1,png_bytes(image));job.done.connect(lambda *args:result.append(args));job.finished.connect(loop.quit);QTimer.singleShot(20000,loop.quit)
  with patch.dict(os.environ,{'PATH':'/usr/bin:/bin'}):job.start();loop.exec();self.assertTrue(job.wait(2000))
  self.assertTrue(result);self.assertEqual(result[0][2]['ocr_status'],'listo');self.assertIn('47291',result[0][1]);self.assertIn('viernes',result[0][1].lower());job.deleteLater()
 def test_unavailable_engine_is_not_reported_as_success(self):
  from ocr_engine import recognize
  image=QImage(20,20,QImage.Format_RGB32);image.fill(QColor('white'))
  with patch('ocr_engine.tesseract_binary',return_value=None):text,meta=recognize(image)
  self.assertEqual(meta['ocr_status'],'no disponible');self.assertIn('Tesseract',meta['ocr_error']);self.assertFalse(text)
if __name__=='__main__':unittest.main()
