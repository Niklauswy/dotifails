import tempfile,time,unittest,subprocess
from pathlib import Path
from loomrec.schema import *
from loomrec.render import RenderJob
from loomrec.capture import probe

class RenderTests(unittest.TestCase):
 def test_filters_export_cancel_and_destination_protection(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=320x180:r=15:d=1.5','-f','lavfi','-i','sine=frequency=440:duration=1.5','-c:v','libx264','-threads','1','-c:a','pcm_s16le','-shortest',str(root/'s.mkv')],check=True)
   p=Project(sources=[Source('s','s.mkv',duration=1.5,group='s'),Source('a','s.mkv','mic',duration=1.5,group='s')],clips=[Clip('s',.5,1.2),Clip('s',0,.5)],crop=[0,0,.9,.9],subtitles=[Subtitle(0,1,'literal %{test}: subtitle')])
   p.annotations=[Annotation(kind,0,1,[.1,.1,.2,.2],"literal %{text}: test") for kind in ['text','arrow','highlight','mask','blur']]
   save_project(p,root/'project.json')
   job=RenderJob(root/'project.json',root/'out.mp4').start()
   job._thread.join(30);self.assertEqual(job.poll()['state'],'done',job.poll())
   info=probe(root/'out.mp4');self.assertEqual(len(info['streams']),2)
   self.assertAlmostEqual(float(info['format']['duration']),1.2,delta=.15)
   with self.assertRaises(FileExistsError):RenderJob(root/'project.json',root/'out.mp4').start()
   with self.assertRaises(ValueError):RenderJob(root/'project.json',root/'s.mkv').start()
   job=RenderJob(root/'project.json',root/'cancel.mp4');job.cancel();job.start();job._thread.join(5)
   self.assertEqual(job.poll()['state'],'cancelled');self.assertFalse((root/'cancel.mp4').exists())
   p.clips=p.clips*12;save_project(p,root/'project.json')
   job=RenderJob(root/'project.json',root/'active-cancel.mp4').start()
   deadline=time.monotonic()+5
   while job._process is None and time.monotonic()<deadline:time.sleep(.001)
   self.assertIsNotNone(job._process);job.cancel();job._thread.join(10)
   self.assertEqual(job.poll()['state'],'cancelled');self.assertFalse((root/'active-cancel.mp4').exists())

 def test_export_pixels_gain_and_camera(self):
  import array,math
  with tempfile.TemporaryDirectory(prefix="loom quote ' ") as d:
   root=Path(d)
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=320x180:r=15:d=0.8','-f','lavfi','-i','sine=frequency=440:duration=0.8','-c:v','libx264','-threads','1','-c:a','pcm_s16le','-shortest',str(root/'s.mkv')],check=True)
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:s=64x64:d=0.8','-c:v','libx264','-threads','1',str(root/'cam.mkv')],check=True)
   p=Project(sources=[Source('s','s.mkv',duration=0.8,group='g'),Source('a','s.mkv','mic',gain=0,duration=0.8,group='g'),Source('cam','cam.mkv','camera',duration=0.8,group='g')],clips=[Clip('s',0,.7)],annotations=[Annotation('mask',0,.7,[0,0,.2,.2]),Annotation('text',0,.7,[.3,.1,.4,.2],'Literal colon: quote\'')],camera=Camera(True,[.8,.7,.2,.2]))
   save_project(p,root/'project.json')
   job=RenderJob(root/'project.json',root/'out.mp4',preset='compact').start();job._thread.join(30)
   self.assertEqual(job.poll()['state'],'done',job.poll())
   data=subprocess.check_output(['ffmpeg','-v','error','-ss','0.3','-i',str(root/'out.mp4'),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
   def pixel(x,y):return tuple(data[(y*320+x)*3:(y*320+x)*3+3])
   self.assertLess(max(pixel(20,20)),10)
   r,g,b=pixel(290,145);self.assertGreater(b,200);self.assertLess(max(r,g),30)
   samples=array.array('f',subprocess.check_output(['ffmpeg','-v','error','-i',str(root/'out.mp4'),'-map','0:a:0','-f','f32le','-']))
   self.assertLess(max(abs(x) for x in samples),.001)
