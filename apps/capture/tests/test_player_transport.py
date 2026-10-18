import os,tempfile,unittest,json
from pathlib import Path
from unittest.mock import Mock,patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from loomrec.ui.player import Player
class TransportTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):self.player=Player()
 def tearDown(self):self.player.client=None;self.player.shutdown();self.player.deleteLater();self.app.processEvents()
 def test_preferences_use_playback_properties_only(self):
  p=self.player;p.command=Mock();p.set_volume(37);p.set_speed(1.5);p.toggle_mute();p.seek(12)
  self.assertEqual([c.args for c in p.command.call_args_list],[('set_property','volume',37),('set_property','speed',1.5),('set_property','mute',True),('seek',12,'absolute+exact')])
 def test_observed_state_drives_transport(self):
  p=self.player;p.client=Mock();p.client.recv.side_effect=[b'{"event":"property-change","name":"duration","data":12}\n{"event":"property-change","name":"pause","data":false}\n',BlockingIOError()]
  p.read_messages();self.assertEqual(p.duration,12);self.assertFalse(p.paused)
 def test_load_direct_video_does_not_create_project(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'video.mp4';path.write_bytes(b'owned')
   with patch.object(self.player.process,'start') as start:self.player.load(path)
   self.assertEqual(start.call_args.args[0],'mpv');self.assertEqual(start.call_args.args[1][-1],str(path));self.assertEqual(list(Path(directory).iterdir()),[path])
