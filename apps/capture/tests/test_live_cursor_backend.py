import json,tempfile,unittest
from pathlib import Path
from dataclasses import asdict
from unittest.mock import Mock,patch
from loomrec.capture import CaptureConfig,append_segment
from loomrec.schema import Project,atomic_json
from loomrec.worker import main

class LiveBackendTests(unittest.TestCase):
 def test_baked_marker_recovery_and_native_fallback_metadata(self):
  info={'format':{'duration':'1'},'streams':[{'codec_type':'video','start_time':'0.1','width':640,'height':360,'avg_frame_rate':'60/1'}]}
  with tempfile.TemporaryDirectory() as td,patch('loomrec.capture.probe',return_value=info):
   root=Path(td);c=CaptureConfig(td,':0',[0,0,640,360],auto_finalize=False,cursor_effects={'preset':'trail'},quality='high')
   atomic_json(root/'s.cursor-live.json',{'baked':True});p=Project();append_segment(p,root,'s.recovered',c)
   s=p.sources[0];self.assertTrue(s.cursor_baked);self.assertIsNone(s.cursor_path);self.assertEqual((s.width,s.height,s.fps,s.quality),(640,360,60,'high'))
   p=Project();append_segment(p,root,'native',c);self.assertFalse(p.sources[0].cursor_baked);self.assertEqual(p.sources[0].cursor_effects,{})
 def worker_case(self,ready):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);atomic_json(root/'capture.json',asdict(CaptureConfig(td,':0',[0,0,640,360],auto_finalize=False,cursor_effects={'preset':'trail'})))
   helper=Mock();helper.prepare.side_effect=None if ready else RuntimeError('synthetic helper unavailable');helper.prepare.return_value=helper;helper.alive.return_value=False
   commands=[];appended=[]
   def spawn(command,**kwargs):
    commands.append(command);p=Mock();p.poll.return_value=None;p.returncode=0
    if len(commands)==(2 if ready else 1):atomic_json(root/'command-stop.json',{'command':'stop'})
    return p
   def append(project,root,stem,config):appended.append(config)
   with patch('loomrec.devices.display_bounds',return_value=[1920,1080]),patch('loomrec.worker.shutil.disk_usage') as disk,patch('loomrec.live_cursor.LiveCursor',return_value=helper),patch('loomrec.worker.subprocess.Popen',side_effect=spawn),patch('loomrec.worker.append_segment',side_effect=append),patch('loomrec.worker.time.sleep'):
    disk.return_value.free=10**10;main(root)
   status=json.loads((root/'status.json').read_text());self.assertEqual(status['state'],'stopped',status);self.assertTrue(status['cursor_warning'])
   draws=[c[c.index('-draw_mouse')+1] for c in commands];self.assertEqual(draws,['0','1'] if ready else ['1'])
   self.assertEqual(appended[-1].cursor_effects,{});helper.prepare.assert_called_once()
   if ready:helper.stop.assert_called_once();self.assertEqual(len(list(root.glob('*.cursor-live.json'))),1)
 def test_start_failure_native_warning_does_not_abort_capture(self):self.worker_case(False)
 def test_helper_death_splits_once_and_preserves_original_baked_segment(self):self.worker_case(True)
