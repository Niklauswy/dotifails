import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/wysun'))
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication,QWidget,QPushButton
import screen_lock

class Signal:
    def __init__(self):self.callback=None
    def connect(self,callback):self.callback=callback
class FakeProcess:
    NormalExit=QProcess.NormalExit;CrashExit=QProcess.CrashExit;FailedToStart=QProcess.FailedToStart
    def __init__(self,parent):self.finished=Signal();self.errorOccurred=Signal()
    def start(self,*args):self.command=args
    def setProcessEnvironment(self,environment):pass
    def deleteLater(self):pass
class ScreenLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.owner=QWidget();self.window=QWidget();self.owner.utilities={'power':self.window}
        self.window.action_buttons=[QPushButton('Bloquear',self.window)]
        self.owner.show();self.window.show()
    def tearDown(self):self.owner.close();self.window.close()
    def start(self):
        with patch.object(screen_lock,'lock_command',return_value=['/usr/bin/wysun-lock']),patch.object(screen_lock,'QProcess',FakeProcess):
            self.assertFalse(screen_lock.start_lock(self.owner))
        return self.owner.lock_process
    def test_menu_closes_only_after_successful_acquisition(self):
        process=self.start();self.assertTrue(self.window.isVisible());self.assertFalse(self.window.action_buttons[0].isEnabled())
        process.finished.callback(0,QProcess.NormalExit)
        self.assertFalse(self.window.isVisible());self.assertFalse(self.owner.isVisible());self.assertIsNone(self.owner.lock_process)
    def test_failed_lock_keeps_menu_and_reports_error(self):
        process=self.start()
        with patch.object(screen_lock.QMessageBox,'warning') as warning:
            process.finished.callback(1,QProcess.NormalExit);warning.assert_called_once()
        self.assertTrue(self.window.isVisible());self.assertTrue(self.window.action_buttons[0].isEnabled())
    def test_launch_error_reports_once(self):
        process=self.start()
        with patch.object(screen_lock.QMessageBox,'warning') as warning:
            process.errorOccurred.callback(QProcess.FailedToStart);process.finished.callback(1,QProcess.CrashExit);warning.assert_called_once()
        self.assertTrue(self.window.isVisible())
    def test_missing_locker_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'WYSUN_LOCK':str(Path(tmp)/'missing')}),patch.object(screen_lock.QMessageBox,'warning') as warning:
            self.assertFalse(screen_lock.start_lock(self.owner));warning.assert_called_once()
        self.assertTrue(self.window.isVisible())
    def test_lock_command_requires_an_executable_wayland_locker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'wysun-lock';path.write_text('#!/bin/sh\n')
            with patch.dict(os.environ,{'WYSUN_LOCK':str(path)}),self.assertRaises(RuntimeError):
                screen_lock.lock_command()
            path.chmod(0o755)
            with patch.dict(os.environ,{'WYSUN_LOCK':str(path)}):
                self.assertEqual(screen_lock.lock_command(),[str(path)])

if __name__=='__main__':unittest.main()
