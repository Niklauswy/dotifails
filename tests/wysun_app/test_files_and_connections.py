import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QImage,QPainter,QFont,QColor,QKeyEvent
from PySide6.QtWidgets import QApplication,QPushButton
from orbit import STYLE
from desktop_v3 import OrbitV3
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

class FileUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion');cls.app.setStyleSheet(STYLE)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'captura.png';fixture_image(self.path);self.code=self.root/'example.py';self.code.write_text('print("hola")');self.store=StoreV2(self.root/'state');self.w=OrbitV3(self.store,test=True);self.w.indexed_at=time.monotonic();files=[(p.name,str(p),p.name) for p in [self.path,self.code]];self.w.files=files;self.w.files_ui.catalog_ready(files);self.w.show();self.w.set_mode('files');wait(150)
    def tearDown(self):
        self.w.debounce.stop();self.w.files_ui.thumb_timer.stop();self.w.status_timer.stop();self.w.prune_timer.stop()
        for job in self.w.jobs+[self.w.files_ui.thumb_job,self.w.indexer]:
            if job:job.wait(8000)
        for v in self.w.files_ui.viewers:
            if v.job:v.job.wait(8000)
            v.reject()
        if getattr(self.w,'popup',None):self.w.popup.hide()
        self.w.preview_path='';wait(100);self.app.clipboard().clear();self.w.files_ui.cache.close();self.w.hide();self.w.deleteLater();QApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.store.db.close();self.tmp.cleanup()
    def select_image(self):self.w.files_ui.choose_filter('Imágenes');wait(150)
    def test_file_filters_ocr_search_and_thumbnail(self):
        index_image(self.path,self.w.files_ui.cache);self.w.search.setText('estrella');wait(100);self.assertEqual(self.w.results.count(),1);self.assertTrue(self.w.current()['ocr_match']);self.assertFalse(self.w.current()['thumbnail'].isNull());wait(160);self.assertIn('Disponible',self.w.metadata.text());self.w.search.clear();self.w.files_ui.choose_filter('Código');self.assertEqual(self.w.results.count(),1);self.assertEqual(self.w.current()['path'],str(self.code))
    def test_grouped_image_actions_copy_file_and_original_pixels(self):
        self.select_image();self.w.actions();menu=self.w.popup;rows=[menu.list.item(i).data(Qt.UserRole) for i in range(menu.list.count())];titles=[r['title'] for r in rows];self.assertIn('Vista previa',titles);self.assertIn('Copiar imagen',titles);self.assertIn('Copiar archivo',titles);self.assertIn('Guardar una copia…',titles);self.assertEqual(sum(r['kind']=='section' for r in rows),2);self.assertNotEqual(menu.list.currentItem().data(Qt.UserRole)['kind'],'section');menu.hide();self.w.files_ui.copy_image();self.assertEqual(self.app.clipboard().image().width(),1000);self.w.files_ui.copy_file();self.assertEqual(self.app.clipboard().mimeData().urls()[0].toLocalFile(),str(self.path))
    def test_quicklook_image_zoom_and_close(self):
        self.select_image();self.w.files_ui.quicklook();viewer=self.w.files_ui.viewers[-1]
        for _ in range(100):
            wait(10)
            if viewer.image is not None:break
        self.assertFalse(viewer.image.isNull());before=viewer.zoom;viewer.scale(1.25);self.assertGreater(viewer.zoom,before);viewer.reject();self.assertFalse(viewer.isVisible())

if __name__=='__main__':unittest.main(verbosity=2)
