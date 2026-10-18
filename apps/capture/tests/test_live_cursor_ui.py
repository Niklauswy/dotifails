"""No native display/capture: live overlay state and balanced XFixes lifecycle."""
import os,unittest
from unittest.mock import Mock
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from loomrec.ui.live_cursor import LiveState,NativeSurface,LiveSurface

class LiveCursorUiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_outside_and_large_jump_discard_history(self):
  s=LiveState([100,200,300,200],{'preset':'trail'})
  self.assertTrue(s.sample(1,(110,210),[1,8]));self.assertEqual(s.point,(10,10));self.assertEqual(len(s.clicks),1)
  self.assertFalse(s.sample(1.02,(99,210),[1]));self.assertIsNone(s.point);self.assertFalse(s.points);self.assertFalse(s.clicks)
  s.sample(1.04,(120,220),[1]);s.sample(1.06,(350,350),[]);self.assertEqual(len(s.points),1);self.assertFalse(s.clicks)
 def test_bounded_events_and_expiration(self):
  s=LiveState([0,0,100,100],{'preset':'trail'})
  for i in range(1000):s.sample(i*.001,(25,25),[1])
  self.assertLessEqual(len(s.points),64);self.assertLessEqual(len(s.clicks),32)
  s.sample(2,(25,25),[]);self.assertFalse(s.clicks);self.assertEqual(len(s.points),1)
 def test_hide_reference_is_balanced_and_close_idempotent(self):
  n=NativeSurface.__new__(NativeSurface);n.fx=Mock();n.x=Mock();n.display=123;n.root=456;n.hidden=False;n.closed=False;n.stacking=None
  for _ in range(100):n.visible_inside(True)
  n.fx.XFixesHideCursor.assert_called_once_with(123,456)
  for _ in range(100):n.visible_inside(False)
  n.fx.XFixesShowCursor.assert_called_once_with(123,456)
  n.visible_inside(True);n.close();n.close();n.visible_inside(True)
  self.assertEqual(n.fx.XFixesHideCursor.call_count,2);self.assertEqual(n.fx.XFixesShowCursor.call_count,2);self.assertFalse(n.hidden)
 def test_overlay_input_focus_and_clipping(self):
  s=LiveState([0,0,100,100],{'preset':'trail','size':64});view=LiveSurface(s)
  try:
   self.assertTrue(view.windowFlags()&Qt.WindowTransparentForInput);self.assertTrue(view.windowFlags()&Qt.WindowDoesNotAcceptFocus);self.assertEqual(view.focusPolicy(),Qt.NoFocus)
   s.sample(1,(0,0),[1]);view.show();self.app.processEvents();frame=view.grab().toImage()
   self.assertEqual(frame.size().toTuple(),(100,100));self.assertGreater(frame.pixelColor(0,0).alpha(),0);self.assertEqual(frame.pixelColor(99,99).alpha(),0)
   s.sample(1.02,(-1,0),[1]);view.update();self.app.processEvents();frame=view.grab().toImage()
   self.assertTrue(all(frame.pixelColor(x,y).alpha()==0 for x,y in [(0,0),(20,20),(99,99)]))
  finally:view.close()

 def test_stacking_events_coalesce_and_never_request_focus(self):
  from loomrec.ui.live_cursor import StackWatcher
  from PySide6.QtCore import QObject
  watcher=StackWatcher.__new__(StackWatcher);QObject.__init__(watcher);watcher.window=25;watcher.display=123;watcher.x=Mock();watcher.timer=Mock();watcher.timer.isActive.return_value=False;watcher.notifier=Mock()
  watcher.changed(25);watcher.timer.start.assert_not_called()
  watcher.changed(99);watcher.timer.start.assert_called_once()
  watcher.timer.isActive.return_value=True;watcher.changed(100);watcher.timer.start.assert_called_once()
  watcher.raise_surface();watcher.x.XRaiseWindow.assert_called_once_with(123,25);watcher.x.XSetInputFocus.assert_not_called()
  watcher.close();watcher.close();watcher.x.XCloseDisplay.assert_called_once_with(123);watcher.notifier.setEnabled.assert_called_with(False)
