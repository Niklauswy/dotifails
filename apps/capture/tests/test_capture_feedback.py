import os,tempfile,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication
from loomrec.ui.capture_feedback import indicator_geometry,Countdown,load_countdown,save_countdown

class FeedbackTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_hints_use_actual_configured_pause_stop_chords(self):
  from loomrec.ui.capture_feedback import control_hints
  with patch('loomrec.integration.shortcut_settings',return_value={'pause':'Alt+p','stop':'Alt+s'}):
   hint=control_hints();self.assertIn('Alt+p',hint);self.assertIn('Alt+s',hint);self.assertIn('Super+Shift+L',hint)
 def test_region_edges_and_badge_never_intersect_capture(self):
  for area in ([100,100,640,360],[0,0,640,360],[1280,700,640,380],[-1600,0,800,600]):
   screens=[[-1920,0,1920,1080],[0,0,1920,1080]]
   borders,badge=indicator_geometry(area,screens);self.assertTrue(borders)
   for geometry in borders+([badge] if badge else []):
    self.assertFalse(geometry.intersects(QRect(*area)));self.assertTrue(any(QRect(*screen).contains(geometry) for screen in screens))
 def test_fullmonitor_suppresses_on_single_monitor_and_uses_other(self):
  self.assertEqual(indicator_geometry([0,0,1920,1080],[[0,0,1920,1080]]),([],None))
  borders,badge=indicator_geometry([0,0,1920,1080],[[0,0,1920,1080],[-1920,0,1920,1080]])
  self.assertIsNotNone(badge);self.assertFalse(badge.intersects(QRect(0,0,1920,1080)))
 def test_countdown_persists_zero_and_bounds(self):
  with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'XDG_CONFIG_HOME':root}):
   self.assertEqual(load_countdown(),3);save_countdown(0);self.assertEqual(load_countdown(),0);save_countdown(999);self.assertEqual(load_countdown(),30)
 def test_large_countdown_centers_on_region_and_cancels(self):
  calls=[];widget=Countdown(lambda:calls.append(True));widget.present(3,[-1600,100,800,600]);self.app.processEvents()
  self.assertEqual(widget.number.text(),'3');self.assertLessEqual(abs(widget.geometry().center().x()+1201),1)
  from PySide6.QtWidgets import QPushButton
  widget.findChild(QPushButton).click();self.assertEqual(calls,[True]);widget.close()

 def test_zero_countdown_waits_for_preview_release_and_cancel_fences_start(self):
  from loomrec.ui.main import Window
  from loomrec.library import Library
  with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'XDG_CONFIG_HOME':root,'XDG_STATE_HOME':root}):
   w=Window(Library(root),False);w.timer.stop();w.capture_pending=True;w.remaining=0
   release=[];scheduled=[]
   with patch.object(w.camera_preview,'stop',side_effect=lambda callback=None:release.append(callback) if callback else None),patch('loomrec.ui.main.QTimer.singleShot',side_effect=lambda delay,fn:scheduled.append(fn)):
    w.countdown_tick();self.assertEqual(len(release),1);self.assertEqual(scheduled,[])
    self.assertFalse(w.countdown_overlay.isVisible());release[0]();self.assertEqual(len(scheduled),1)
   w.cancel_countdown()
   with patch.object(w,'start_capture') as start:scheduled[0]();start.assert_not_called()
   w.close();w.deleteLater();self.app.processEvents()

 def test_selected_camera_auto_previews_same_widget_in_quick_and_full(self):
  from loomrec.ui.main import Window
  from loomrec.library import Library
  with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'XDG_CONFIG_HOME':root,'XDG_STATE_HOME':root}):
   w=Window(Library(root),False);w.timer.stop()
   with patch.object(w.camera_preview,'set_device') as select,patch.object(w,'ensure_keys'):
    w.camera.addItem('Synthetic camera','/dev/video999');w.camera.setCurrentIndex(1)
    select.assert_called_with('/dev/video999')
    preview=w.camera_preview;w.quick.present();w.quick.device(w.quick.mode,w.camera,'Camera')
    self.assertIs(w.camera_preview,preview);self.assertIs(preview.parentWidget(),w.quick.popup)
    w.activate_instance('setup');self.assertIs(w.camera_preview,preview);self.assertIsNot(preview.parentWidget(),w.quick.popup)
    select.assert_called_with('/dev/video999')
   w.close();w.deleteLater();self.app.processEvents()

 def test_badge_recording_pause_and_terminal_cleanup(self):
  from unittest.mock import Mock
  from loomrec.ui.main import Window
  from loomrec.library import Library
  with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'XDG_CONFIG_HOME':root,'XDG_STATE_HOME':root}):
   w=Window(Library(root),False);w.timer.stop()
   w.recording_indicator.present([100,100,640,360],[[0,0,1920,1080]])
   self.assertTrue(w.recording_indicator.windows)
   session=Mock();w.session=session
   for state,caption in [('starting','Preparando'),('recording','Grabando'),('paused','En pausa'),('stopping','Finalizando')]:
    session.status.return_value={'state':state};w.poll()
    self.assertIn(caption,w.recording_indicator.badge.text())
    self.assertTrue(w.recording_indicator.badge.isVisible())
   session.status.return_value={'state':'stopped','project_path':str(__import__('pathlib').Path(root)/'absent.json')}
   w.poll();self.assertIsNone(w.session);self.assertEqual(w.recording_indicator.windows,[]);self.assertIsNone(w.recording_indicator.badge)
   w.close();w.deleteLater();self.app.processEvents()
