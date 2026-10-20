"""Manual serial synthetic playback proof. No real audio/device or host changes.

Run only in the coordinated media turn, with WYSUN_LIBMPV if privately extracted.
Qt is offscreen; this verifies real software rendering, not a Wayland compositor.
"""
import os,sys,tempfile,subprocess,time,json,resource,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='wysun-mpv-proof-') as temporary:
 os.environ.update(HOME=temporary,QT_QPA_PLATFORM='offscreen',WYSUN_LIBMPV=os.environ.get('WYSUN_LIBMPV','libmpv.so.2'))
 for var,folder in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache'),('XDG_STATE_HOME','state'),('XDG_RUNTIME_DIR','run')]:
  os.environ[var]=str(Path(temporary)/folder);Path(os.environ[var]).mkdir(mode=0o700)
 video=Path(temporary)/'test.mkv'
 subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=24','-t','6','-an','-c:v','libx264','-preset','ultrafast','-threads','1',str(video)],check=True)
 sys.path.insert(0,str(ROOT/'apps/wysun'))
 from PySide6.QtWidgets import QApplication
 from mpv_embed import MpvSurface
 app=QApplication([]);surface=MpvSurface();surface.resize(640,360);surface.show();app.processEvents()
 errors=[];frames=[];surface.failed.connect(errors.append);surface.frameReady.connect(lambda:frames.append(time.monotonic()))
 ipc=Path(temporary)/'mpv.sock'
 surface.start(video,ipc,{'ao':'null','audio':'no','volume':0})
 def pump(seconds):
  end=time.monotonic()+seconds
  while time.monotonic()<end:app.processEvents();time.sleep(.005)
 def cmd(*args):
  with socket.socket(socket.AF_UNIX) as c:
   c.settimeout(1);c.connect(str(ipc));c.sendall((json.dumps({'command':list(args),'request_id':9})+'\n').encode());data=b''
   while b'\n' not in data:data+=c.recv(65536)
   return json.loads(data.split(b'\n')[0])
 pump(.4)
 assert not errors,errors
 assert not surface.image.isNull(),'No rendered image'
 assert len({surface.image.pixel(x,y) for x,y in [(20,20),(100,100),(300,100),(500,200)]})>1,'Image lacks synthetic pattern'
 phases=[]
 def phase(name,duration):
  first=resource.getrusage(resource.RUSAGE_SELF);count=len(frames);start=time.monotonic();pump(duration);last=resource.getrusage(resource.RUSAGE_SELF)
  phases.append(dict(name=name,wall_s=round(time.monotonic()-start,3),cpu_s=round(last.ru_utime+last.ru_stime-first.ru_utime-first.ru_stime,4),frames=len(frames)-count,peak_rss_kib=last.ru_maxrss))
 phase('paused-visible',.6)
 cmd('set_property','pause',False);phase('playing-visible-640x360',1.5)
 position=cmd('get_property','time-pos').get('data');assert position and position>.8,position
 cmd('set_property','pause',True);phase('paused-visible-after-play',.6)
 cmd('seek',3,'absolute+exact');surface.resize(800,450);pump(.3)
 assert surface.image.width()==800,(surface.image.size(),errors)
 seekpos=cmd('get_property','time-pos').get('data');assert seekpos and abs(seekpos-3)<.15,seekpos
 surface.hide();cmd('set_property','pause',False);phase('playing-hidden',.6)
 surface.show();pump(.2);assert not surface.image.isNull()
 before=time.monotonic();surface.stop();stop_s=time.monotonic()-before
 assert not surface.thread and not surface.handle
 print(json.dumps(dict(kind='real libmpv SW embedded Qt offscreen',api='2.5',video='640x360@24 synthetic/no audio',phases=phases,seek_s=seekpos,stop_s=round(stop_s,3),errors=errors)))
 surface.close()
