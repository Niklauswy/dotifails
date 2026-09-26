"""Keyboard activation must follow the focused power action without executing it."""
import sys,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parents[1]/'apps/orbit'))
from PySide6.QtCore import Qt,QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication,QPushButton
from connections_window import PowerWindow

class PowerKeyboardTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.owner=Mock();self.owner.power_action.return_value=False;self.w=PowerWindow(self.owner);self.w.present();self.app.processEvents()
  self.buttons=[b for b in self.w.findChildren(QPushButton) if b.text()]
 def tearDown(self):self.w.close();self.w.deleteLater();self.app.processEvents()
 def key(self,button,key,repeat=False):
  self.app.sendEvent(button,QKeyEvent(QEvent.KeyPress,key,Qt.NoModifier,'',repeat))
 def test_enter_dispatches_each_focused_action(self):
  for button,action in zip(self.buttons,['lock','suspend','logout','reboot','shutdown']):
   for key in (Qt.Key_Return,Qt.Key_Enter):
    with self.subTest(action=action,key=key):
     self.owner.reset_mock();button.setFocus();self.key(button,key)
     self.owner.power_action.assert_called_once();self.assertEqual(self.owner.power_action.call_args.args[0]['action'],action);self.assertTrue(self.w.isVisible())
 def test_arrows_and_initial_focus(self):
  self.assertTrue(self.buttons[0].hasFocus());self.key(self.buttons[0],Qt.Key_Right);self.assertTrue(self.buttons[1].hasFocus())
  self.key(self.buttons[1],Qt.Key_Down);self.assertTrue(self.buttons[2].hasFocus());self.key(self.buttons[2],Qt.Key_Up);self.assertTrue(self.buttons[1].hasFocus())
  self.owner.power_action.assert_not_called()
 def test_success_hides_and_auto_repeat_does_not_dispatch(self):
  self.key(self.buttons[0],Qt.Key_Return,True);self.owner.power_action.assert_not_called()
  self.owner.power_action.return_value=True;self.key(self.buttons[0],Qt.Key_Return);self.assertFalse(self.w.isVisible())
 def test_clock_and_uptime_refresh_only_while_visible(self):
  self.assertRegex(self.w.clock_label.text(),r'^\d{2}:\d{2}$');self.assertIn(' de ',self.w.date_label.text())
  self.assertTrue(self.w.uptime_label.text().startswith('Encendido hace '));self.assertTrue(self.w.clock_timer.isActive())
  self.w.hide();self.assertFalse(self.w.clock_timer.isActive())
  self.w.present();self.assertTrue(self.w.clock_timer.isActive());self.assertLess(self.w.height(),380)
 def test_uptime_includes_days_hours_and_minutes(self):
  for seconds,expected in [(20,'menos de 1 min'),(120,'2 min'),(3660,'1 h 1 min'),(183840,'2 d 3 h 4 min')]:
   with self.subTest(seconds=seconds):self.assertEqual(PowerWindow.uptime_text(seconds),'Encendido hace '+expected)

if __name__=='__main__':unittest.main()
