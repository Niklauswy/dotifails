"""Capture failures use owned exceptions/pixels, never a portal or desktop."""
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import QEvent
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from wybieshot.actions import ActionWindow, CaptureActions
from wybieshot.capture import FrozenDesktop
from wybieshot.instance import CaptureLease
from wybieshot.schema import CaptureRequest, Rect
from wybieshot.storage import Storage


class Failure:
    def __init__(self,message,gate=None):self.message=message;self.gate=gate
    def freeze(self,*_):
        if self.gate:self.gate.wait(1)
        raise RuntimeError(self.message)


class OwnedImage:
    def freeze(self,*_):
        image=QImage(64,48,QImage.Format_ARGB32);image.fill(QColor('#315787'))
        return FrozenDesktop(image,Rect(0,0,64,48),(Rect(0,0,64,48),))


class DirectErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=Storage(self.root/'library');self.window=None
        self.quit=patch.object(self.app,'quit');self.quit_mock=self.quit.start()
        self.wayland=patch('loomrec.portal.is_wayland',return_value=True);self.wayland.start()
    def tearDown(self):
        if self.window:
            for job in list(self.window.jobs):job.wait(2000)
            self.app.processEvents();self.window.close();self.window.quick.close();self.window.deleteLater()
            self.app.sendPostedEvents(None,QEvent.DeferredDelete)
        self.app._wybieshot_window=None;self.wayland.stop();self.quit.stop();self.temp.cleanup()
    def begin(self,engine):
        w=self.window=ActionWindow(CaptureActions(),self.store,engine)
        self.app._wybieshot_window=w
        w._capture_lease=CaptureLease(self.root/'lease');self.assertTrue(w._capture_lease.claim())
        w.pending_request=CaptureRequest(mode='region');w.busy=True;w.countdown=0;w.capture_tick()
        return w
    def drain(self):
        deadline=time.monotonic()+2
        while self.window.jobs and time.monotonic()<deadline:
            self.app.processEvents();time.sleep(.005)
        self.app.processEvents();self.assertEqual(self.window.jobs,[])
    def assert_lease_free(self):
        lease=CaptureLease(self.root/'lease');self.assertTrue(lease.claim());lease.release()
    def test_direct_failure_shows_actionable_error_preserves_lease_data_and_retry(self):
        raw='org.freedesktop.DBus.Error.InvalidArgs: No such interface org.freedesktop.portal.ScreenCast /request/private_token private_payload'
        w=self.begin(Failure(raw));self.drain()
        self.assertFalse(w._closing);self.assertTrue(w.isVisible());self.assertFalse(w.quick.isVisible())
        notice=w.statusBar().currentMessage()
        self.assertIn('portal de captura',notice);self.assertIn('vuelve a intentarlo',notice)
        self.assertNotIn('private_token',notice);self.assertNotIn('private_payload',notice)
        self.quit_mock.assert_not_called();self.assertFalse(w.busy);self.assert_lease_free()
        self.assertEqual(self.store.list_sessions(),[])
        # Retry remains usable without any real screen or output file.
        w.engine=OwnedImage();w.pending_request=CaptureRequest(mode='region');w.busy=True;w.capture_tick();self.drain()
        self.assertIsNotNone(w.frozen);self.assertTrue(w.overlay.isVisible())
        self.assertEqual(self.store.list_sessions(),[])
    def test_missing_screenshot_interface_also_hides_private_dbus_payload(self):
        w=self.begin(Failure('org.freedesktop.DBus.Error.UnknownInterface: org.freedesktop.portal.Screenshot private_token'))
        self.drain();notice=w.statusBar().currentMessage()
        self.assertTrue(w.isVisible());self.assertIn('portal de captura',notice)
        self.assertNotIn('private_token',notice);self.quit_mock.assert_not_called();self.assert_lease_free()
    def test_other_capture_failure_keeps_its_actionable_message_visible(self):
        w=self.begin(Failure('La fuente se cerró antes del primer fotograma'));self.drain()
        self.assertTrue(w.isVisible());self.assertIn('La fuente se cerró',w.statusBar().currentMessage())
        self.quit_mock.assert_not_called();self.assert_lease_free()
    def test_portal_cancel_still_exits_direct_invocation(self):
        w=self.begin(Failure('Selección cancelada en el portal'));self.drain()
        self.assertFalse(w.isVisible());self.assertFalse(w.quick.isVisible());self.assert_lease_free()
        self.quit_mock.assert_called()
    def test_escape_still_cancels_and_releases_direct_invocation(self):
        w=self.window=ActionWindow(CaptureActions(),self.store,OwnedImage());self.app._wybieshot_window=w
        w._capture_lease=CaptureLease(self.root/'lease');self.assertTrue(w._capture_lease.claim())
        w.show_library();w.busy=True;w.escape()
        self.assertFalse(w.isVisible());self.assertFalse(w.quick.isVisible());self.assert_lease_free()
        self.assertEqual(self.store.list_sessions(),[]);self.quit_mock.assert_called()
    def test_explicit_close_during_worker_failure_never_reopens(self):
        gate=threading.Event();w=self.begin(Failure('owned worker failure',gate));w.close()
        self.assertTrue(w._closing);gate.set();self.drain()
        self.assertFalse(w.isVisible());self.assertFalse(w.quick.isVisible());self.assert_lease_free()
        self.quit_mock.assert_called()
