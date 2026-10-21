import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QImage,QPainter,QFont,QColor,QKeyEvent
from PySide6.QtWidgets import QApplication,QPushButton
from orbit import STYLE
from data_v2 import StoreV2
from file_media import FileCache,index_image,preview_file,file_kind,FileOCRIndexer

def wait(ms):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:QApplication.processEvents();time.sleep(.005)

def fixture_image(path,text='DOCUMENTO ESTRELLA SEPTIEMBRE'):
    image=QImage(1000,180,QImage.Format_RGB32);image.fill(QColor('white'));p=QPainter(image);p.setPen(QColor('black'));p.setFont(QFont('DejaVu Sans',30));p.drawText(20,105,text);p.end();image.save(str(path));return image

class FileDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_ocr_content_change_delete_and_literal_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'captura.png';fixture_image(path);cache=FileCache(root/'cache')
            try:
                self.assertTrue(index_image(path,cache));self.assertIn(str(path),cache.search('estrella'));self.assertEqual(cache.search('zz%_'),set());self.assertFalse(index_image(path,cache))
                fixture_image(path,'DOCUMENTO PLANETA OCTUBRE');self.assertEqual(cache.search('estrella'),set());self.assertTrue(index_image(path,cache));self.assertIn(str(path),cache.search('planeta'));path.unlink();self.assertEqual(cache.search('planeta'),set())
            finally:cache.close()
    def test_video_preview_has_frame_duration_and_codec(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'clip prueba.mp4';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:s=320x180:d=2','-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(path)],check=True,capture_output=True);data=preview_file(path);self.assertEqual(data['kind'],'video');self.assertFalse(data['image'].isNull());self.assertEqual(data['meta']['width'],320);self.assertGreater(data['meta']['duration'],1);self.assertEqual(data['meta']['codec_name'],'h264')
    def test_indexer_cancel_and_incremental_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'a.png';fixture_image(path);cache=FileCache(root/'state');index_image(path,cache);cache.close();events=[];job=FileOCRIndexer([str(path)],root/'state');job.progress.connect(lambda done,total:events.append((done,total)));job.run();self.assertEqual(events,[(1,1)])
            self.assertEqual(file_kind('test.ts'),'code')
            self.assertEqual(FileOCRIndexer(['icon.svg',str(path)],root/'state').paths,[str(path)])


if __name__=='__main__':unittest.main(verbosity=2)
