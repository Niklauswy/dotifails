import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from loomrec.cursor import effect_settings,local_point,point_at,write_ass,load_trace,CursorRecorder
from loomrec.capture import CaptureConfig
from loomrec.worker import capture_command
from loomrec.schema import Source,Project,Clip,save_project,load_project,project_from_dict
from loomrec.render import RenderJob

class CursorTests(unittest.TestCase):
 def test_default_and_hidden_native_cursor_contract(self):
  config=CaptureConfig('/tmp/owned',':0',[0,0,320,180]);self.assertEqual(config.cursor_effects,{})
  for visible,effects,expected in [(True,{},'1'),(False,{},'0'),(True,{'preset':'presentation'},'0'),(False,{'preset':'trail'},'0')]:
   config.cursor=visible;config.cursor_effects=effects;cmd=capture_command(config,Path('/tmp/owned'),'s',origin=123)
   self.assertEqual(cmd[cmd.index('-draw_mouse')+1],expected);self.assertIn('setpts=PTS-123/TB,fps=fps=30',cmd)
 def test_option_validation_and_negative_monitor_locality(self):
  self.assertEqual(effect_settings({}),{});self.assertTrue(effect_settings({'preset':'trail'})['trail'])
  for value in ({'preset':'x'},{'preset':'trail','trail_duration':40},{'size':65},{'halo':1},{'keyboard':True}):
   with self.assertRaises(ValueError):effect_settings(value)
  self.assertEqual(local_point([-640,-200,640,480],-639,-199),(1,1))
  self.assertIsNone(local_point([-640,-200,640,480],0,0))
 def test_no_interpolation_across_outside_or_teleport(self):
  points=[[0,10,10,0],[.05,20,20,0],[.1,None,None,0],[.2,300,150,0],[.25,10,10,0]]
  self.assertEqual(point_at(points,.025),(15,15));self.assertIsNone(point_at(points,.15))
  self.assertEqual(point_at(points,.225),(300,150))
 def trace(self,root):
  path=root/'s.cursor.jsonl';path.write_text('\n'.join(json.dumps(x) for x in [dict(version=1,width=320,height=180,settings={'preset':'trail'}),[0,50,50,0],[.1,55,50,1],[.2,None,None,0],[.3,250,100,0],[.5,None,None,0]])+'\n');return path
 def test_sidecar_trim_timing_no_old_cursor_invented_and_relative_path(self):
  old=project_from_dict({'sources':[{'id':'s','path':'s.mkv','duration':1}], 'clips':[{'source_id':'s','in_s':0,'out_s':1}]});self.assertIsNone(old.sources[0].cursor_path)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);path=self.trace(root);out=root/'cursor.ass';write_ass(path,out,.3,.5,{'preset':'presentation'})
   text=out.read_text();self.assertIn('0:00:00.00',text);self.assertIn('pos(250.00,100.00)',text);self.assertNotIn('pos(55.00,50.00)',text)
   p=Project(sources=[Source('s','s.mkv',duration=1,cursor_path='../outside')],clips=[Clip('s',0,1)])
   with self.assertRaises(ValueError):save_project(p,root/'project.json')
 def test_shared_render_effects_precede_crop_and_final_redaction(self):
  from loomrec.schema import Annotation
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);trace=self.trace(root);p=Project(sources=[Source('s','s.mkv',duration=.5,width=320,height=180,cursor_path=trace.name,cursor_effects={'preset':'trail'})],clips=[Clip('s',.3,.5)],crop=[.1,.1,.8,.8],annotations=[Annotation('mask',0,.2),Annotation('highlight',0,.2)])
   save_project(p,root/'project.json');job=RenderJob(root/'project.json',root/'out.mp4');job.project=p
   cmd=job._clip_command(p.clips[0],0,root,0);f=cmd[cmd.index('-filter_complex')+1]
   self.assertLess(f.index('ass='),f.index('crop='));self.assertGreater(f.index('color=black'),f.index('color=yellow'))
   self.assertIn('0:00:00.00',(root/'cursor-0.ass').read_text())
 def test_trace_rejects_outside_points_and_cancelled_generation(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);trace=self.trace(root);cancel=threading.Event();cancel.set()
   with self.assertRaises(InterruptedError):write_ass(trace,root/'out.ass',0,.5,{'preset':'trail'},cancel)
   with trace.open('a') as f:f.write('[0.6, 999, 0, 1]\n')
   with self.assertRaises(ValueError):load_trace(trace)
 def test_sampler_discards_outside_clicks_and_closes_on_failure(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);reader=Mock();reader.position.side_effect=[(110,110),(99,99),(120,120)];reader.clicks.side_effect=[[1],[1],[]]
   with patch('loomrec.cursor.PointerReader',return_value=reader):
    recorder=CursorRecorder(root/'ok.jsonl',':0',[100,100,320,180],{'preset':'trail'})
   recorder.origin=1;recorder.stop_event=Mock();recorder.stop_event.is_set.side_effect=[False,False,False,True]
   with patch('loomrec.cursor.time.time',side_effect=[1,1.02,1.04,1.06]):recorder._run()
   header,points,clicks=load_trace(root/'ok.jsonl');self.assertEqual(len(clicks),1);self.assertEqual(clicks[0][1:3],[10,10]);self.assertTrue(any(p[1] is None for p in points));reader.close.assert_called_once()
   failed=Mock();failed.position.side_effect=OSError('synthetic X connection failure')
   with patch('loomrec.cursor.PointerReader',return_value=failed):
    recorder=CursorRecorder(root/'error.jsonl',':0',[100,100,320,180],{'preset':'trail'})
   recorder.origin=1;recorder._run();self.assertIn('synthetic X connection failure',recorder.error);failed.close.assert_called_once()
   # Telemetry failure is reported without raising into/stopping the video worker.
   self.assertTrue((root/'error.jsonl').exists())
