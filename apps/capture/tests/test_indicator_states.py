"""Feedback states and geometry only: no device probes, media, or desktop input."""
import os,unittest
from unittest.mock import Mock,patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QRect,Qt
from PySide6.QtWidgets import QApplication
from loomrec.ui.capture_feedback import RecordingIndicator,indicator_geometry,elapsed_text

class IndicatorStateTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.now=10.;self.indicator=RecordingIndicator(clock=lambda:self.now)
  self.motion=patch('loomrec.ui.motion.reduced_motion',return_value=False);self.motion.start()
  self.rect=[100,100,640,360];self.screens=[[0,0,1920,1080]]
 def tearDown(self):self.indicator.hide();self.app.processEvents();self.motion.stop()
 def assert_safe(self):
  for widget in self.indicator.windows:
   self.assertFalse(widget.geometry().intersects(QRect(*self.indicator.rect)))
   self.assertTrue(any(QRect(*screen).contains(widget.geometry()) for screen in self.indicator.screens))
 def test_idle_selection_is_immediate_blue_and_not_recording(self):
  i=self.indicator;self.assertTrue(i.select(self.rect,self.screens))
  self.assertEqual(i.state,'selected');self.assertEqual(i.badge.text(),'Área seleccionada')
  self.assertTrue(i.badge.isVisible());self.assertTrue(i.timer.isActive());self.assert_safe()
  phase=i.phase;i.animate();self.assertNotEqual(i.phase,phase)
  self.assertTrue(all(b.state=='selected' for b in i.borders))
 def test_countdown_recording_pause_resume_and_elapsed(self):
  i=self.indicator;i.select(self.rect,self.screens);i.update('countdown',remaining=3)
  self.assertEqual(i.badge.text(),'Comienza en 3 s');i.update('starting');self.now=30.;i.update('recording')
  self.now=95.;i.update('recording');self.assertIn('01:05',i.badge.text())
  i.update('paused');phase=i.phase;self.now=150.;i.update('paused')
  self.assertIn('01:05',i.badge.text());self.assertFalse(i.timer.isActive());self.assertEqual(i.phase,phase)
  i.update('recording');self.now=152.;i.update('recording');self.assertIn('01:07',i.badge.text())
  i.update('stopping');self.assertIn('Finalizando',i.badge.text());self.assertFalse(i.timer.isActive())
  i.update('stopped');self.assertEqual(i.windows,[]);self.assertEqual(i.elapsed,0)
 def test_relayout_preserves_active_clock_but_changes_safe_windows(self):
  i=self.indicator;i.present(self.rect,self.screens);i.update('recording');self.now+=4
  i.relayout([0,0,1920,1080],[[0,0,1920,1080],[-1600,100,1600,900]])
  self.assertEqual(i.state,'recording');self.assertEqual(i.elapsed,4);self.assert_safe()
  self.assertLess(i.badge.geometry().right(),0)
  i.relayout([0,0,1920,1080],self.screens);self.assertEqual(i.windows,[]);self.assertEqual(i.elapsed,4)
 def test_reduced_motion_retains_state_and_status_without_animation(self):
  with patch('loomrec.ui.motion.reduced_motion',return_value=True):
   i=self.indicator;i.select(self.rect,self.screens);self.assertFalse(i.timer.isActive())
   i.update('recording');self.now+=8;i.update('recording')
   self.assertIn('00:08',i.badge.text());self.assertFalse(i.timer.isActive());self.assertTrue(all(not b.motion for b in i.borders))
 def test_safe_badge_callbacks_wait_for_owner_state_ack(self):
  pause=Mock();stop=Mock();i=self.indicator;i.present(self.rect,self.screens,on_pause=pause,on_stop=stop)
  i.update('recording');self.assert_safe();self.assertIsNotNone(i.badge.pause_button)
  self.assertFalse(i.badge.windowFlags()&Qt.WindowTransparentForInput)
  self.assertTrue(i.badge.windowFlags()&Qt.WindowDoesNotAcceptFocus)
  self.assertTrue(all(b.windowFlags()&Qt.WindowTransparentForInput for b in i.borders))
  i.badge.pause_button.click();i.badge.pause_button.click();pause.assert_called_once()
  i.update('recording');self.assertFalse(i.badge.pause_button.isEnabled())
  i.update('paused');self.assertEqual(i.badge.pause_button.text(),'Reanudar');i.badge.pause_button.click();self.assertEqual(pause.call_count,2)
  i.update('recording');i.badge.stop_button.click();stop.assert_called_once()
 def test_other_monitor_preferred_and_status_only_fallback(self):
  rect=[100,100,640,360];screens=[[0,0,1920,1080],[1920,0,1920,1080]]
  _,badge=indicator_geometry(rect,screens);self.assertTrue(QRect(*screens[1]).contains(badge))
  i=self.indicator;i.present([0,0,800,600],[[0,0,800,600],[1000,0,250,200]],on_pause=Mock(),on_stop=Mock())
  self.assertIsNotNone(i.badge);self.assertIsNone(i.badge.pause_button);self.assert_safe()
 def test_edges_negative_coordinates_and_disconnected_monitors(self):
  screens=[[-1600,-900,1600,900],[0,0,1920,1080],[2200,300,1280,720]]
  for rect in ([0,0,1920,1080],[-1600,-900,1600,900],[-400,-200,1200,900],[1900,0,600,400],[0,0,3480,1080]):
   for size in ((224,40),(390,44)):
    borders,badge=indicator_geometry(rect,screens,size)
    for geometry in borders+([badge] if badge else []):
     self.assertFalse(geometry.intersects(QRect(*rect)))
     self.assertTrue(any(QRect(*screen).contains(geometry) for screen in screens))
  self.assertEqual(indicator_geometry([0,0,1920,1080],[[0,0,1920,1080]]),([],None))
  self.assertEqual(indicator_geometry([0,0,0,0],screens),([],None))
 def test_all_terminal_states_cleanup_selection_and_timers(self):
  for state in ('stopped','error','interrupted','cleared'):
   self.indicator.select(self.rect,self.screens);self.indicator.update(state)
   self.assertEqual(self.indicator.windows,[]);self.assertFalse(self.indicator.timer.isActive())
  self.assertEqual(elapsed_text(3661),'01:01:01')
