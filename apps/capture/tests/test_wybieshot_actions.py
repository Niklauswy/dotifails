"""Direct shortcuts: synthetic pixels, isolated storage, offscreen clipboard only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QRect,QEvent,QPoint,QPointF
from PySide6.QtGui import QImage,QColor,QKeyEvent,QMouseEvent
from PySide6.QtWidgets import QApplication
from wybieshot.actions import ActionWindow,CaptureActions
from wybieshot.capture import FrozenDesktop
from wybieshot.schema import Rect,CaptureRequest
from wybieshot.storage import Storage
from wybieshot.__main__ import main
from wybieshot.instance import CaptureLease

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
    def test_control_drag_auto_accepts_region_in_direct_capture(self):
        w=self.start(CaptureActions(True));overlay=w.overlay;start=QPoint(10,10);end=QPoint(109,89)
        with patch('wybieshot.ui.selection.QCursor.pos',return_value=overlay.mapToGlobal(start)):
            app.sendEvent(overlay,QKeyEvent(QEvent.KeyPress,Qt.Key_Control,Qt.NoModifier))
        app.sendEvent(overlay,QMouseEvent(QEvent.MouseMove,QPointF(end),QPointF(overlay.mapToGlobal(end)),Qt.NoButton,Qt.NoButton,Qt.ControlModifier))
        with patch('wybieshot.ui.selection.QCursor.pos',return_value=overlay.mapToGlobal(end)):
            app.sendEvent(overlay,QKeyEvent(QEvent.KeyRelease,Qt.Key_Control,Qt.NoModifier))
        app.processEvents();self.assertIsNotNone(w.document)
        self.assertEqual((w.document.size.width(),w.document.size.height()),(100,80))
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
    def async_selection(self,accept):
        gate=threading.Event()
        class AsyncEngine(Engine):
            def freeze(self,*_,**__):
                if not gate.wait(2):raise RuntimeError('Owned frame fixture timed out')
                return super().freeze()
        self.window=ActionWindow(CaptureActions(accept,clipboard=accept),self.store,AsyncEngine());w=self.window
        directory=Path(self.temp.name)/'owned-lease'
        w._capture_lease=CaptureLease(directory);self.assertTrue(w._capture_lease.claim())
        w.pending_request=CaptureRequest(mode='region');w.busy=True;w.countdown=0
        w.capture_tick();self.assertIsNone(w.overlay)  # Frame has not returned yet.
        gate.set();deadline=time.monotonic()+2
        while (w.overlay is None or w.jobs) and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
        self.assertFalse(w.jobs);self.assertIsNotNone(w.overlay)
        overlay=w.overlay
        expected=overlay.source_rect(QRect(10,10,100,80)).size()
        for kind,pos,button,buttons in ((QEvent.MouseButtonPress,(10,10),Qt.LeftButton,Qt.LeftButton),(QEvent.MouseMove,(109,89),Qt.NoButton,Qt.LeftButton),(QEvent.MouseButtonRelease,(109,89),Qt.LeftButton,Qt.NoButton)):
            app.sendEvent(overlay,QMouseEvent(kind,QPointF(*pos),QPointF(*pos),button,buttons,Qt.NoModifier))
        app.processEvents();return w,directory,expected
    def test_accept_on_select_handles_async_wayland_overlay_and_releases_lease(self):
        with patch('loomrec.portal.is_wayland',return_value=True):
            w,directory,expected=self.async_selection(True)
            self.assertIsNotNone(w.document)
            pixels=w.document.render()
            self.assertEqual(pixels.size(),expected)
            self.assertEqual(pixels.pixelColor(pixels.width()//2,pixels.height()//2).name(),'#23a6bf')
            self.assertEqual(app.clipboard().image(),pixels);self.assertTrue(w._clipboard_pending)
            self.assertIsNone(w.overlay);self.assertFalse(w.busy)
            next_capture=CaptureLease(directory);self.assertTrue(next_capture.claim());next_capture.release()
    def test_regular_async_region_stays_adjustable_until_cancel_and_reopen(self):
        with patch('loomrec.portal.is_wayland',return_value=True):
            w,directory,_=self.async_selection(False)
            self.assertIsNone(w.document);self.assertTrue(w.overlay.isVisible())
            next_capture=CaptureLease(directory);self.assertFalse(next_capture.claim())
            w.cancel_capture();self.assertTrue(next_capture.claim());next_capture.release()
            self.assertEqual(self.store.list_sessions(),[])

if __name__=='__main__':unittest.main()
