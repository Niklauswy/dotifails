import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QImage,QColor,QIcon,QKeyEvent
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
from desktop_common import vim_args,is_text_file
from data_v2 import StoreV2
from media import png_bytes
from orbit import STYLE

def wait(ms):
    until=time.monotonic()+ms/1000
    while time.monotonic()<until:QApplication.processEvents();time.sleep(.005)

class IntegrationDataTests(unittest.TestCase):
    def test_vim_paths_are_separate_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'space $(unsafe).py';path.write_text('print("hello")');args=vim_args(path);self.assertEqual(args[-2:],['--',str(path)]);self.assertTrue(is_text_file(path));binary=Path(tmp)/'binary';binary.write_bytes(b'a\0b');self.assertFalse(is_text_file(binary))

