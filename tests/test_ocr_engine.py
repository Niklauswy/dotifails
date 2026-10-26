"""OCR under the real desktop PATH, and an unavailable engine never reported as success."""
import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.append(str(Path(__file__).resolve().parents[1]/'apps/python'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter,QColor,QFont
from PySide6.QtCore import QEventLoop,QTimer
from wysun_services.media import OCRJob,png_bytes
from wysun_services.ocr_engine import tesseract_binary

class OCREngineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_async_ocr_under_graphical_session_path(self):
  if not tesseract_binary():self.skipTest('Tesseract no instalado')
  image=QImage(720,180,QImage.Format_RGB32);image.fill(QColor('#202024'));painter=QPainter(image);painter.setPen(QColor('#f7f7f8'));painter.setFont(QFont('DejaVu Sans',12));painter.drawText(25,55,'Entrega del proyecto 47291');painter.drawText(25,95,'Revisar los documentos el viernes');painter.end()
  result=[];loop=QEventLoop();job=OCRJob(1,png_bytes(image));job.done.connect(lambda *args:result.append(args));job.finished.connect(loop.quit);QTimer.singleShot(20000,loop.quit)
  with patch.dict(os.environ,{'PATH':'/usr/bin:/bin'}):job.start();loop.exec();self.assertTrue(job.wait(2000))
  self.assertTrue(result);self.assertEqual(result[0][2]['ocr_status'],'listo');self.assertIn('47291',result[0][1]);self.assertIn('viernes',result[0][1].lower());job.deleteLater()
 def test_unavailable_engine_is_not_reported_as_success(self):
  from wysun_services.ocr_engine import recognize
  image=QImage(20,20,QImage.Format_RGB32);image.fill(QColor('white'))
  with patch('wysun_services.ocr_engine.tesseract_binary',return_value=None):text,meta=recognize(image)
  self.assertEqual(meta['ocr_status'],'no disponible');self.assertIn('Tesseract',meta['ocr_error']);self.assertFalse(text)
if __name__=='__main__':unittest.main()
