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
from connection_details import fields,wifi_inventory,identity
from connections_window import ConnectionsWindow

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
    def test_network_fields_escape_and_connected_ap_priority(self):
        self.assertEqual(fields(r'*:Nombre\: con dos puntos:AA\:BB:70'),['*','Nombre: con dos puntos','AA:BB','70'])
        devices={'wlo1':{'device':'wlo1','GENERAL.TYPE':['wifi'],'GENERAL.STATE':['100 (connected)'],'GENERAL.CON-UUID':['uuid']}}
        text=' :Casa:AA\\:BB:95:WPA2:wlo1:2400 MHz:2:144 Mbit/s:Infra\n*:Casa:CC\\:DD:70:WPA2:wlo1:5200 MHz:40:405 Mbit/s:Infra'
        with patch('connection_details.device_inventory',return_value=devices),patch('connection_details.nm',side_effect=lambda args:text if 'list' in args else 'enabled'):
            rows,meta=wifi_inventory();self.assertEqual(len(rows),1);self.assertTrue(rows[0]['connected']);self.assertEqual(rows[0]['bssid'],'CC:DD');self.assertEqual(rows[0]['uuid'],'uuid')

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

class ConnectionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion')
    def setUp(self):
        self.load_patch=patch.object(ConnectionsWindow,'load');self.load_patch.start();self.w=ConnectionsWindow();self.w.periodic.stop();self.w.show();self.app.processEvents()
    def tearDown(self):
        self.w.periodic.stop();self.w.detail_timer.stop()
        if self.w.detail_scan:self.w.detail_scan.wait(6000)
        self.w.hide();self.w.deleteLater();QApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.load_patch.stop()
    def test_keyboard_page_navigation_and_restored_selection(self):
        rows=[dict(kind='wifi',id='wifi:'+str(i),title='Red '+str(i),subtitle='WPA2',device='wlo1',ssid='Red '+str(i),security='WPA2',signal=70,connected=False,icon='wifi') for i in range(3)];self.w.loaded('wifi',rows,{'enabled':True});self.w.search.setFocus();self.app.sendEvent(self.w.search,QKeyEvent(QEvent.KeyPress,Qt.Key_Down,Qt.NoModifier));self.assertEqual(self.w.list.currentRow(),1);self.w.cycle_mode(1);self.assertEqual(self.w.mode,'bluetooth');self.w.cycle_mode(-1);self.w.loaded('wifi',rows,{'enabled':True});self.assertEqual(self.w.current()['id'],'wifi:1');self.assertEqual(self.w.detail_title.text(),'Red 1')
    def test_bluetooth_and_ssh_actions_are_visible(self):
        self.w.select_mode('bluetooth');row=dict(kind='bluetooth',title='Auriculares',subtitle='Emparejados',address='00:11:22:33:44:55',connected=False,paired=True,trusted=True,battery=80,icon='bluetooth');self.w.loaded('bluetooth',[row],{'available':True,'enabled':True});texts=[self.w.action_grid.itemAt(i).widget().text() for i in range(self.w.action_grid.count())];self.assertIn('Dejar de confiar',texts);self.assertIn('Olvidar dispositivo',texts);self.assertEqual(self.w.info_form.rowCount(),3)
        self.w.select_mode('ssh');row=dict(kind='ssh',title='Pruebas',name='Pruebas',subtitle='localhost',host='localhost',user='test',port=2222,profile_index=0,icon='ssh');self.w.loaded('ssh',[row],{});texts=[self.w.action_grid.itemAt(i).widget().text() for i in range(self.w.action_grid.count())];self.assertIn('Editar conexión',texts);self.assertEqual(self.w.primary.text(),'Abrir terminal SSH');self.assertIn(('Servidor','localhost'),self.w.visible_details)
    def test_stale_async_details_do_not_replace_selection(self):
        row=dict(kind='ssh',title='Actual',name='Actual',subtitle='localhost',host='localhost',user='test',port=22,profile_index=0,icon='ssh');self.w.select_mode('ssh');self.w.loaded('ssh',[row],{});self.w.detail_ready('old-uuid',{'info':[('Perfil','Anterior')]});self.assertEqual(self.w.detail_title.text(),'Actual');self.assertNotIn(('Perfil','Anterior'),self.w.visible_details)

if __name__=='__main__':unittest.main(verbosity=2)
