import json,tempfile,unittest
from pathlib import Path
from dataclasses import asdict
from unittest.mock import Mock,patch
from wysun_recorder.capture import CaptureConfig,append_segment
from wysun_recorder.schema import Project
from wysun_core.jsonio import atomic_write_json
from wysun_recorder.worker import main

class LiveBackendTests(unittest.TestCase):
 def test_baked_marker_recovery_and_native_fallback_metadata(self):
  info={'format':{'duration':'1'},'streams':[{'codec_type':'video','start_time':'0.1','width':640,'height':360,'avg_frame_rate':'60/1'}]}
  with tempfile.TemporaryDirectory() as td,patch('wysun_recorder.capture.probe',return_value=info):
   root=Path(td);c=CaptureConfig(td,':0',[0,0,640,360],auto_finalize=False,cursor_effects={'preset':'trail'},quality='high')
   atomic_write_json(root/'s.cursor-live.json',{'baked':True});p=Project();append_segment(p,root,'s.recovered',c)
   s=p.sources[0];self.assertTrue(s.cursor_baked);self.assertIsNone(s.cursor_path);self.assertEqual((s.width,s.height,s.fps,s.quality),(640,360,60,'high'))
   p=Project();append_segment(p,root,'native',c);self.assertFalse(p.sources[0].cursor_baked);self.assertEqual(p.sources[0].cursor_effects,{})
 def test_x11_live_effects_fall_back_to_the_native_pointer_without_aborting_capture(self):
  """No helper draws X11 effects live: the segment keeps ffmpeg's own pointer, says so, and the recording goes on."""
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);atomic_write_json(root/'capture.json',asdict(CaptureConfig(td,':0',[0,0,640,360],auto_finalize=False,cursor_effects={'preset':'trail'})))
   commands=[];appended=[]
   def spawn(command,**kwargs):
    commands.append(command);p=Mock();p.poll.return_value=None;p.returncode=0
    atomic_write_json(root/'command-stop.json',{'command':'stop'})
    return p
   def append(project,root,stem,config):appended.append(config)
   with patch('wysun_recorder.devices.display_bounds',return_value=[1920,1080]),patch('wysun_recorder.worker.shutil.disk_usage') as disk,patch('wysun_recorder.worker.subprocess.Popen',side_effect=spawn),patch('wysun_recorder.worker.append_segment',side_effect=append),patch('wysun_recorder.worker.time.sleep'):
    disk.return_value.free=10**10;main(root)
   status=json.loads((root/'status.json').read_text());self.assertEqual(status['state'],'stopped',status);self.assertTrue(status['cursor_warning'])
   self.assertEqual([c[c.index('-draw_mouse')+1] for c in commands],['1']);self.assertEqual(appended[-1].cursor_effects,{})
   self.assertEqual(list(root.glob('*.cursor-live.json')),[])
