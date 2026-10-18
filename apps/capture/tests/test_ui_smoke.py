"""Offscreen native UI construction/navigation without devices or media jobs."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from PySide6.QtWidgets import QApplication
from loomrec.ui.main import Window
from loomrec.library import Library
from loomrec.schema import Project,Source,Clip,save_project

class UISmokeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_construct_open_edit_undo_and_close(self):
  with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{"XDG_STATE_HOME": d}):
   library=Library(d);directory=library.new_directory();path=directory/'project.json'
   save_project(Project(title='Synthetic smoke',sources=[Source('s','synthetic.mkv',duration=3)],clips=[Clip('s',0,3)]),path)
   window=Window(library,probe_devices=False)
   try:
    self.assertEqual(window.items.count(),1)
    window.open_project(path,edit=True)
    self.assertEqual(window.clips.count(),1)
    window.editor.trim(0,.5,2.5);window.refresh_editor()
    self.assertEqual(window.editor.project.duration,2)
    window.undo();self.assertEqual(window.editor.project.duration,3)
    window.redo();self.assertEqual(window.editor.project.duration,2)
    self.assertEqual(window.player.process.state(),window.player.process.ProcessState.NotRunning)
   finally:
    window.timer.stop();window.close();window.deleteLater();self.app.processEvents()
