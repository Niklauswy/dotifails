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
 def test_construct_open_viewer_and_close(self):
  with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{"XDG_STATE_HOME": d}):
   library=Library(d);directory=library.new_directory();path=directory/'project.json'
   save_project(Project(title='Synthetic smoke',sources=[Source('s','synthetic.mkv',duration=3)],clips=[Clip('s',0,3)]),path)
   window=Window(library,probe_devices=False)
   try:
    self.assertEqual(window.items.count(),1)
    video=Path(d)/'synthetic.mp4';video.write_bytes(b'owned fixture')
    with patch.object(window.player,'load') as load:window.open_media(video)
    load.assert_called_once_with(video);self.assertIs(window.stack.currentWidget(),window.editor_page)
    window.back_library();self.assertIs(window.stack.currentWidget(),window.library_page)
    self.assertEqual(window.player.process.state(),window.player.process.ProcessState.NotRunning)
   finally:
    window.timer.stop();window.close();window.deleteLater();self.app.processEvents()

if __name__=='__main__':unittest.main()
