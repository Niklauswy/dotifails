"""Explicit reopen vs stale focus callbacks; Notes keys use own temporary data."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
from PySide6.QtCore import QEvent,Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from core import Store
from orbit import Orbit
from notes_window import NotesWindow


def wait(ms):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:QApplication.processEvents();time.sleep(.003)


class LauncherLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,dict(HOME=self.temp.name,XDG_CONFIG_HOME=self.temp.name,XDG_DATA_HOME=self.temp.name,XDG_STATE_HOME=self.temp.name,ORBIT_REDUCED_MOTION='1'));self.env.start()
        self.catalog=patch('orbit.applications',return_value=[]);self.catalog.start()
        self.store=Store(Path(self.temp.name)/'store');self.window=Orbit(self.store,test=True)
    def tearDown(self):
        self.window.hide();self.window.deleteLater();wait(5);self.store.db.close();self.catalog.stop();self.env.stop();self.temp.cleanup()
    def stale_callback(self):
        callbacks=[];self.window.show_mode('home');self.app.processEvents();self.window.test=False
        with patch('orbit.QTimer.singleShot',side_effect=lambda *args:callbacks.append(args[-1])):
            self.app.sendEvent(self.window,QEvent(QEvent.WindowDeactivate))
        self.assertEqual(len(callbacks),1);return callbacks[0]
    def test_old_deactivation_does_not_hide_explicitly_reopened_mode(self):
        callback=self.stale_callback();self.window.hide()
        with patch('orbit.previous_window',return_value=''):self.window.show_mode('snippets')
        with patch.object(self.window,'isActiveWindow',return_value=False):callback()
        self.assertTrue(self.window.isVisible());self.assertEqual(self.window.mode,'snippets')
    def test_current_deactivation_still_hides_when_focus_was_lost(self):
        callback=self.stale_callback()
        with patch.object(self.window,'isActiveWindow',return_value=False):callback()
        self.assertFalse(self.window.isVisible())
    def test_show_mode_interrupts_exit_motion_without_finishing_hidden(self):
        with patch('ui_motion.reduced_motion',return_value=False):
            self.window.show_mode('calculator');wait(230);self.window.dismiss();wait(30)
            self.assertTrue(self.window._motion_exiting)
            self.window.show_mode('snippets');wait(320)
            self.assertTrue(self.window.isVisible());self.assertFalse(self.window._motion_exiting);self.assertEqual(self.window.mode,'snippets')
    def test_notes_escape_from_editor_saves_and_closes_offscreen(self):
        root=Path(self.temp.name)/'notes';notes=NotesWindow(root)
        try:
            notes.present();notes.new();notes.editor.setPlainText('# Owned fixture\n\nExact Markdown\n')
            notes.editor.setFocus();notes.activateWindow();self.app.processEvents()
            self.assertTrue(notes.editor.hasFocus())
            for kind in (QEvent.KeyPress,QEvent.KeyRelease):self.app.sendEvent(notes.editor,QKeyEvent(kind,Qt.Key_Escape,Qt.NoModifier))
            wait(30);self.assertFalse(notes.isVisible())
            self.assertTrue(any(path.read_text()=='# Owned fixture\n\nExact Markdown\n' for path in root.glob('*.md')))
        finally:notes.hide();notes.deleteLater();self.app.processEvents()

if __name__=='__main__':unittest.main()
