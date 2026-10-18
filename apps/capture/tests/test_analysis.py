import tempfile,unittest
from pathlib import Path
from loomrec.analysis import import_srt,parse_silence,AnalysisJob
from loomrec.schema import Project,Source,Clip,save_project
class AnalysisTests(unittest.TestCase):
 def test_srt_and_silence(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'s.srt';p.write_text('1\n00:00:01,200 --> 00:00:02,300\nHola\n\n')
   self.assertEqual(import_srt(p)[0].start,1.2)
   p.write_text('invalid')
   with self.assertRaises(ValueError):import_srt(p)
  self.assertEqual(parse_silence('silence_start: 1\nsilence_end: 2\nsilence_start: 4',5),[{'start':1.,'end':2.},{'start':4.,'end':5}])
 def test_missing_local_model_is_explicit(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'project.json'
   save_project(Project(sources=[Source('s','s.mkv',duration=2,group='g'),Source('a','s.mkv','mic',duration=2,group='g')],clips=[Clip('s',0,2)]),path)
   with self.assertRaises(FileNotFoundError):AnalysisJob(path,'transcription',executable='/missing/whisper',model_path='/missing/model').start()

 def test_actual_silence_on_synthetic_timeline(self):
  import subprocess
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:s=64x64:d=2','-f','lavfi','-i',"sine=frequency=440:duration=2,volume='if(lt(t,1),1,0)':eval=frame",'-c:v','libx264','-threads','1','-c:a','pcm_s16le','-shortest',str(root/'s.mkv')],check=True)
   p=Project(sources=[Source('s','s.mkv',duration=2,group='g'),Source('a','s.mkv','mic',duration=2,group='g')],clips=[Clip('s',0,2)])
   save_project(p,root/'project.json')
   job=AnalysisJob(root/'project.json').start();job._thread.join(15)
   self.assertEqual(job.poll()['state'],'done',job.poll())
   self.assertEqual(len(job.result),1)
   self.assertAlmostEqual(job.result[0]['start'],1,delta=.05)
   self.assertAlmostEqual(job.result[0]['end'],2,delta=.05)
