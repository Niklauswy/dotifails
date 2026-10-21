import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
APP=QApplication.instance() or QApplication([])

class NativeUITests(unittest.TestCase):
    def test_lock_and_suspend_use_managed_acquire_wrapper(self):
        import screen_lock
        with tempfile.TemporaryDirectory() as home,patch.dict(os.environ,{'HOME':home,'WAYLAND_DISPLAY':'owned'}):
            wrapper=Path(home)/'.local/bin/wysun-lock';wrapper.parent.mkdir(parents=True);wrapper.write_text('# synthetic no execution\n');wrapper.chmod(0o700)
            self.assertEqual(screen_lock.lock_command(),[str(wrapper)])

if __name__=='__main__':unittest.main()
