"""Direct shortcuts: synthetic pixels, isolated storage, offscreen clipboard only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QRect,QEvent,QPointF
from PySide6.QtGui import QImage,QColor,QMouseEvent
from PySide6.QtWidgets import QApplication
from wybieshot.actions import ActionWindow,CaptureActions
from wybieshot.capture import FrozenDesktop
from wybieshot.schema import Rect,CaptureRequest
from wybieshot.storage import Storage
from wybieshot.__main__ import main

app=QApplication.instance() or QApplication([])
class Engine:
    def freeze(self):
        image=QImage(320,240,QImage.Format_ARGB32);image.fill(QColor('#23a6bf'))
        return FrozenDesktop(image,Rect(0,0,320,240),(Rect(0,0,320,240),))
    def capture(self,request,frozen=None):
        from wybieshot.capture import CaptureEngine
        return CaptureEngine().capture(request,frozen)

class ActionsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Storage(Path(self.temp.name)/'private')
        self.store.update_settings(delay=5,format='JPEG');self.window=None
    def tearDown(self):
        if self.window:
            self.window.thumbnail_timer.stop();self.window.save_timer.stop()
            for job in self.window.jobs:job.wait(5000)
            self.window.close();self.window.quick.close();self.window.quick.deleteLater();self.window.deleteLater()
        app.processEvents();app.sendPostedEvents(None,QEvent.DeferredDelete);self.temp.cleanup()
    def start(self,actions):
        self.window=ActionWindow(actions,self.store,Engine());w=self.window
        w.pending_request=CaptureRequest();w.busy=True;w.countdown=0;w.capture_tick();app.processEvents()
        return w
    def test_release_saves_png_copies_and_preserves_preferences(self):
        out=Path(self.temp.name)/'shots';w=self.start(CaptureActions(True,True,out,0));overlay=w.overlay
        # Real overlay handling happens before queued accept-on-release.
        for kind,pos,button,buttons in ((QEvent.MouseButtonPress,(10,10),Qt.LeftButton,Qt.LeftButton),(QEvent.MouseMove,(109,89),Qt.NoButton,Qt.LeftButton),(QEvent.MouseButtonRelease,(109,89),Qt.LeftButton,Qt.NoButton)):
            app.sendEvent(overlay,QMouseEvent(kind,QPointF(*pos),QPointF(*pos),button,buttons,Qt.NoModifier))
        app.processEvents();files=list(out.glob('*.png'));self.assertEqual(len(files),1)
        image=QImage(str(files[0]));self.assertEqual((image.width(),image.height()),(100,80))
        self.assertEqual(image.pixelColor(20,20).name(),'#23a6bf');self.assertEqual(app.clipboard().image(),image)
        self.assertEqual(Storage(self.store.root).settings['delay'],5);self.assertEqual(Storage(self.store.root).settings['format'],'JPEG')
        self.assertEqual(w.prefs()['delay'],0)
    def test_regular_region_waits_for_confirmation_and_cancel_writes_nothing(self):
        w=self.start(CaptureActions());overlay=w.overlay;overlay.selection=QRect(10,10,100,80)
        app.sendEvent(overlay,QMouseEvent(QEvent.MouseButtonRelease,QPointF(109,89),QPointF(109,89),Qt.LeftButton,Qt.NoButton,Qt.NoModifier));app.processEvents()
        self.assertIsNone(w.document);w.cancel_capture();self.assertFalse(w.quick.isVisible());self.assertEqual(self.store.list_sessions(),[])
    def test_export_conflict_preserves_image_and_existing_file(self):
        target=Path(self.temp.name)/'existing.png';target.write_bytes(b'original')
        w=self.start(CaptureActions(True,False,target));w.overlay.selection=QRect(10,10,100,80);w.accept_selection();app.processEvents()
        self.assertEqual(target.read_bytes(),b'original');self.assertIsNotNone(w.document);self.assertTrue(w.isVisible())
        self.assertIn('No se pudo completar',w.statusBar().currentMessage())
    def test_cli_parsing_direct_options(self):
        with patch.dict(os.environ,{'XDG_RUNTIME_DIR':self.temp.name}), patch('wybieshot.actions.run',return_value=0) as run:
            self.assertEqual(main(['--region','--accept-on-select','--clipboard','--path','/tmp/shots','--delay','0']),0)
            options=run.call_args.args[1];self.assertTrue(options.accept_on_select);self.assertTrue(options.clipboard);self.assertEqual(options.path,Path('/tmp/shots'));self.assertEqual(options.delay,0)
        with self.assertRaises(SystemExit):main(['--library','--region'])

if __name__=='__main__':unittest.main()
