import os,sys,tempfile,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if not (root/'apps/wysun').is_dir():root=Path(__file__).resolve().parent
sys.path.append(str(root/'apps/wysun'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor,QPainter,QFont
from data_v2 import StoreV2
from clipboard_data import ClipboardLibrary
from media import png_bytes,OCRJob
class ClipboardLibraryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.store=StoreV2(self.temp.name);self.lib=ClipboardLibrary(self.store)
 def tearDown(self):self.store.db.close();self.temp.cleanup()
 def test_migration_preserves_content(self):
  ident=self.store.clip('text','Contenido anterior');ClipboardLibrary(self.store);self.assertEqual(self.lib.row(ident)['text'],'Contenido anterior')
 def test_collections_and_cleanup(self):
  ident=self.store.clip('text','Colección');c=self.lib.create_collection('Proyecto');self.lib.assign(c,[ident]);self.assertEqual(self.lib.search(collection=c)[0]['id'],ident)
  self.lib.delete_collection(c);self.assertIsNotNone(self.lib.row(ident))
  c=self.lib.create_collection('Otra');self.lib.assign(c,[ident]);self.store.delete_clip(ident);self.assertEqual(self.lib.collections()[0]['count'],0)
 def test_combined_snapshot_survives_original_deletion(self):
  a=self.store.clip('text','Primero');b=self.store.clip('url','https://example.org');ident=self.lib.combine([a,b]);self.store.delete_clip(a);self.store.delete_clip(b)
  self.assertEqual(self.lib.plain(self.lib.parts(ident)),'Primero\n\nhttps://example.org')
  self.assertEqual(self.lib.mime([ident]).text(),'Primero\n\nhttps://example.org');self.assertEqual(len(self.lib.search()),1)
 def test_reorder_and_delete_group(self):
  a=self.store.clip('text','A');b=self.store.clip('text','B');ident=self.lib.combine([a,b]);self.lib.reorder(ident,[1,0]);self.assertEqual(self.lib.mime([ident]).text(),'B\n\nA')
  self.store.delete_clip(ident);self.assertEqual(self.lib.parts(ident),[])
 def test_mixed_group_mime_and_html_escaping(self):
  image=QImage(60,40,QImage.Format_RGB32);image.fill(QColor('#176aaa'));a=self.store.clip('image','Imagen',png_bytes(image));b=self.store.clip('text','<script>literal</script>')
  c=self.store.clip('files','file',meta={'paths':[str(Path(self.temp.name)/'con espacio.txt')]});ident=self.lib.combine([a,b,c]);mime=self.lib.mime([ident])
  self.assertIn('data:image/png;base64,',mime.html());self.assertIn('&lt;script&gt;',mime.html());self.assertNotIn('<script>',mime.html());self.assertTrue(mime.hasUrls());self.assertIn('application/x-orbit-clip-group',mime.formats())
 def test_single_image_preserves_native_pixels(self):
  image=QImage(22,18,QImage.Format_RGB32);image.fill(QColor('red'));ident=self.store.clip('image','Imagen',png_bytes(image));self.assertTrue(self.lib.mime([ident]).hasImage())
 def test_search_text_ocr_source_and_accents(self):
  ident=self.store.clip('image','Imagen',source='Editor');self.store.save_media(ident,'RECIBO DE CAFÉ',{},None)
  self.assertEqual(self.lib.search('cafe editor')[0]['id'],ident);self.assertFalse(self.lib.search('cafe',source='Navegador'))
 def test_nested_groups_flatten(self):
  ids=[self.store.clip('text',text) for text in ('a','b','c')];one=self.lib.combine(ids[:2]);two=self.lib.combine([one,ids[2]])
  self.assertEqual([p['text'] for p in self.lib.parts(two)],['a','b','c'])
 def test_invalid_group_and_bad_url(self):
  a=self.store.clip('text','Solo')
  with self.assertRaises(ValueError):self.lib.combine([a])
  ident=self.store.clip('url','javascript:alert(1)');self.assertNotIn('href="javascript:',self.lib.mime([ident]).html())
 def test_ocr_retries_failed_images_without_busy_loop(self):
  from enhanced import OrbitV2
  from types import SimpleNamespace,MethodType
  from unittest.mock import MagicMock,patch
  import json,time
  ident=self.store.clip('image','Imagen fallida',b'fixture')
  self.store.save_media(ident,'',{'ocr_status':'no disponible','ocr_attempts':1,'ocr_retry_after':0},None)
  owner=SimpleNamespace(test=False,ocr_job=None,store=self.store,ocr_retry_timer=MagicMock(),ocr_finished=MagicMock(),ocr_cleanup=MagicMock())
  owner.next_ocr=MethodType(OrbitV2.next_ocr,owner)
  with patch('enhanced.OCRJob') as job:
   owner.next_ocr();job.assert_called_once_with(ident,b'fixture');job.return_value.start.assert_called_once()
  owner.ocr_job=None;self.store.save_media(ident,'',{'ocr_status':'no disponible','ocr_engine':2,'ocr_attempts':3,'ocr_retry_after':0},None)
  with patch('enhanced.OCRJob') as job:owner.next_ocr();job.assert_not_called()
  owner.ocr_retry_timer.start.assert_called_with(60000)
 def test_old_exhausted_ocr_is_recovered_once(self):
  from enhanced import OrbitV2
  from types import SimpleNamespace,MethodType
  from unittest.mock import MagicMock,patch
  ident=self.store.clip('image','Imagen anterior',b'fixture');self.store.save_media(ident,'',{'ocr_status':'no disponible','ocr_attempts':3},None)
  owner=SimpleNamespace(test=False,ocr_job=None,store=self.store,ocr_retry_timer=MagicMock(),ocr_finished=MagicMock(),ocr_cleanup=MagicMock());owner.next_ocr=MethodType(OrbitV2.next_ocr,owner)
  with patch('enhanced.OCRJob') as job:owner.next_ocr();job.assert_called_once_with(ident,b'fixture')
 def test_actual_tesseract_image_search(self):
  import shutil
  if not shutil.which('tesseract'):self.skipTest('Tesseract no está instalado')
  image=QImage(1000,180,QImage.Format_RGB32);image.fill(QColor('white'));p=QPainter(image);p.setFont(QFont('DejaVu Sans',40));p.setPen(QColor('black'));p.drawText(35,110,'ORBITA RECIBO 47291');p.end();blob=png_bytes(image)
  ident=self.store.clip('image','Imagen',blob);job=OCRJob(ident,blob);result=[];job.done.connect(lambda *args:result.append(args));job.run()
  self.assertEqual(result[0][2]['ocr_status'],'listo');self.store.save_media(*result[0]);self.assertEqual(self.lib.search('47291')[0]['id'],ident)
if __name__=='__main__':unittest.main()
