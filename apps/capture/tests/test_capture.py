import unittest
from pathlib import Path
from loomrec.capture import CaptureConfig
from loomrec.worker import capture_command
class CaptureTests(unittest.TestCase):
 def test_missing_status_does_not_mean_starting_forever(self):
  import tempfile,json,time,os
  from dataclasses import asdict
  from loomrec.capture import CaptureSession
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'capture.json';path.write_text(json.dumps(asdict(CaptureConfig(d,':0',[0,0,640,360],auto_finalize=False))))
   session=CaptureSession.attach(d)
   self.assertEqual(session.status()['state'],'starting')
   os.utime(path,(time.time()-60,time.time()-60))
   self.assertEqual(session.status()['state'],'interrupted')
 def test_selection_mapping_and_shared_clock(self):
  c=CaptureConfig('/tmp/p',':0',[0,0,640,360],mic='mic',system_audio='sink.monitor',camera='/dev/video0')
  c.validate();cmd=capture_command(c,Path('/tmp/p'),'s')
  self.assertIn('-copyts',cmd);self.assertNotIn('-start_at_zero',cmd)
  self.assertEqual(cmd.count('-use_wallclock_as_timestamps'),1)
  self.assertIn('1:a:0',cmd);self.assertIn('2:a:0',cmd);self.assertIn('3:v:0',cmd)
 def test_invalid_region(self):
  for rect in [[-1,0,640,360],[0,0,641,360],[0,0,0,2]]:
   with self.assertRaises(ValueError):CaptureConfig('/tmp/p',':0',rect).validate()

 def test_negative_monitor_and_live_resize(self):
  from loomrec.devices import clamp_rect
  self.assertEqual(clamp_rect([-100,0,640,360],[1920,1080]),[0,0,540,360])
  self.assertEqual(clamp_rect([100,100,640,360],[600,400]),[100,100,500,300])
  with self.assertRaises(ValueError):clamp_rect([-1920,0,1920,1080],[1920,1080])

 def test_rewind_preserves_sources(self):
  from loomrec.schema import Project,Source,Clip
  from loomrec.capture import trim_tail
  p=Project(sources=[Source('s','s.mkv',duration=10)],clips=[Clip('s',0,4),Clip('s',5,9)])
  trim_tail(p,5)
  self.assertEqual(p.clips,[Clip('s',0,3)])
  self.assertEqual(len(p.sources),1)
  trim_tail(p,20);self.assertEqual(p.clips,[])

 def test_storage_and_encoder_failure_are_visible(self):
  import tempfile,json
  from unittest.mock import patch
  from dataclasses import asdict
  from loomrec.schema import atomic_json
  from loomrec.worker import main
  for storage,spawn in [(0,None),(10**10,OSError('encoder missing'))]:
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);atomic_json(root/'capture.json',asdict(CaptureConfig(d,':0',[0,0,640,360],auto_finalize=False)))
    with patch('loomrec.devices.display_bounds',return_value=[1920,1080]),patch('loomrec.worker.shutil.disk_usage') as disk,patch('loomrec.worker.subprocess.Popen',side_effect=spawn):
     disk.return_value.free=storage;main(root)
    status=json.loads((root/'status.json').read_text())
    self.assertEqual(status['state'],'error')
    self.assertTrue(status['error'])

 def test_attach_queues_control_without_starting(self):
  import tempfile,json
  from dataclasses import asdict
  from loomrec.schema import atomic_json
  from loomrec.capture import CaptureSession
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);atomic_json(root/'capture.json',asdict(CaptureConfig('/old/path',':0',[0,0,640,360])))
   session=CaptureSession.attach(root);session.pause()
   self.assertEqual(session.root,root)
   command=next(root.glob('command-*.json'))
   self.assertEqual(json.loads(command.read_text())['command'],'pause')

 def test_segment_uses_common_first_real_timestamp(self):
  import tempfile
  from unittest.mock import patch
  from loomrec.capture import append_segment
  from loomrec.schema import Project
  info={'format':{'duration':'4'},'streams':[{'codec_type':'video','start_time':'0.10'},{'codec_type':'audio','start_time':'0.25'}]}
  with tempfile.TemporaryDirectory() as d,patch('loomrec.capture.probe',return_value=info):
   p=Project();append_segment(p,Path(d),'segment',CaptureConfig(d,':0',[0,0,640,360],mic='synthetic'))
   self.assertEqual(p.clips[0].in_s,.25)
   self.assertEqual(p.duration,3.75)
