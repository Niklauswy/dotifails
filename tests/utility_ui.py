import os,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'apps/wysun'))
from PySide6.QtWidgets import QApplication

import time
def wait(ms):
 end=time.monotonic()+ms/1000
 while time.monotonic()<end:QApplication.processEvents();time.sleep(.005)
class UtilityUITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_theme_switch_refreshes_existing_widgets(self):
  from unittest.mock import patch
  from PySide6.QtWidgets import QLabel
  from wysun_core.qt_theme import apply_style,refresh_widgets
  label=QLabel('Tema');original='color: @text; background: @canvas; border-radius: @rounding.largeIncreased;'
  with patch.dict(os.environ,{'WYSUN_THEME':'dark'}):
   refresh_widgets();apply_style(label,original);dark=label.styleSheet()
   with patch.dict(os.environ,{'WYSUN_THEME':'light'}):
    refresh_widgets();self.assertNotIn('@',label.styleSheet());self.assertNotEqual(label.styleSheet(),dark)
    self.assertEqual(label.property('wysunThemeTemplate'),original)
   refresh_widgets();self.assertEqual(label.styleSheet(),dark)
  label.deleteLater();refresh_widgets()
if __name__=='__main__':unittest.main()
