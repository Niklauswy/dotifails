import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QImage,QPainter,QFont,QColor,QKeyEvent
from PySide6.QtWidgets import QApplication,QPushButton
from orbit import STYLE
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
