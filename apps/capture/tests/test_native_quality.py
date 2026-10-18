import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from loomrec.render import RenderJob,native_canvas,render_profile_signature
from loomrec.schema import Source,Project,Clip,project_from_dict

class NativeQualityTests(unittest.TestCase):
 def test_native_crop_and_compact_never_enlarge(self):
  self.assertEqual(native_canvas([(1920,1080)]),(1920,1080))
  self.assertEqual(native_canvas([(920,704)],cap=(1280,720)),(920,704))
  self.assertEqual(native_canvas([(1920,1080)],crop=[.1,.1,.5,.5]),(960,540))
  self.assertEqual(native_canvas([(2560,1440)],cap=(1280,720)),(1280,720))
  self.assertEqual(native_canvas([(640,480),(320,600)]),(640,600))
 def test_native_timestamps_and_baked_effects_not_reapplied(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=Project(sources=[Source('s','s.mkv',duration=1,width=1920,height=1080,fps=60,quality='high',cursor_path='absent.jsonl',cursor_baked=True,cursor_effects={'preset':'trail'})],clips=[Clip('s',0,1)])
   job=RenderJob(root/'project.json',root/'out.mp4','preview');job.project=p
   cmd=job._clip_command(p.clips[0],0,root,0);graph=cmd[cmd.index('-filter_complex')+1]
   self.assertNotIn('fps=',graph);self.assertNotIn('ass=',graph);self.assertIn('pad=1920:1080',graph)
   self.assertEqual(cmd[cmd.index('-crf')+1],'16');self.assertEqual(cmd[cmd.index('-fps_mode')+1],'passthrough')
 def test_legacy_metadata_probe_and_pipeline_cache_identity(self):
  p=project_from_dict({'sources':[{'id':'s','path':'s.mkv','duration':1}],'clips':[{'source_id':'s','in_s':0,'out_s':1}]})
  self.assertFalse(p.sources[0].cursor_baked)
  with tempfile.TemporaryDirectory() as td,patch('loomrec.capture.probe',return_value={'streams':[{'codec_type':'video','width':920,'height':704}]}):
   root=Path(td);job=RenderJob(root/'p.json',root/'o.mp4','preview');job.project=p;job._prepare_geometry()
   self.assertEqual((job.width,job.height),(920,704))
   (root/'capture.json').write_text(json.dumps({'quality':'high'}));job._prepare_geometry();self.assertEqual(job.crf,16)
  self.assertNotEqual(render_profile_signature('preview'),render_profile_signature('compact'))
  self.assertFalse(render_profile_signature()['upscale'])
