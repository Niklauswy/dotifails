import subprocess,time,sys,json,re,os,signal
from pathlib import Path
from loomrec.capture import CaptureConfig,CaptureSession
from loomrec.render import RenderJob
root=Path('/tmp/loom-safe-proof-'+str(time.time_ns()));root.mkdir();module=None;window=None;player=None;session=None
try:
 fixture_media=root/'fixture.mkv'
 subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',"color=black:s=640x360:r=30:d=12,drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='lt(mod(t,2),1)'",'-f','lavfi','-i',"sine=frequency=880:sample_rate=48000:duration=12,volume='if(lt(mod(t,2),1),0.6,0)':eval=frame",'-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','pcm_s16le',str(fixture_media)],check=True)
 module=subprocess.check_output(['pactl','load-module','module-null-sink','sink_name=loom_synthetic','sink_properties=device.description=LoomSynthetic'],text=True).strip()
 window=subprocess.Popen([sys.executable,str(Path(__file__).with_name('manual_fixture_window.py'))],stdout=subprocess.PIPE,text=True)
 wid=window.stdout.readline().strip();assert wid.isdigit(),wid
 player=subprocess.Popen(['mpv','--no-config','--really-quiet','--vo=x11','--vd-lavc-threads=1','--audio-buffer=0.05','--framedrop=no','--loop-file=inf','--wid='+wid,'--audio-device=pulse/loom_synthetic',str(fixture_media)])
 time.sleep(2)
 info=subprocess.check_output(['xwininfo','-id',wid],text=True)
 full=os.environ.get('MODE')=='monitor'
 expected=[f'Absolute upper-left X:  {0 if full else 100}',f'Absolute upper-left Y:  {0 if full else 100}',f'Width: {1920 if full else 640}',f'Height: {1080 if full else 360}','Map State: IsViewable','Override Redirect State: yes']
 for s in expected:assert s in info,(s,info)
 # Root child order bottom-to-top from Xlib; owned override window must be topmost.
 import ctypes,ctypes.util
 x=ctypes.CDLL(ctypes.util.find_library('X11'));x.XOpenDisplay.restype=ctypes.c_void_p;x.XOpenDisplay.argtypes=[ctypes.c_char_p]
 display=x.XOpenDisplay(None);x.XDefaultRootWindow.argtypes=[ctypes.c_void_p];x.XDefaultRootWindow.restype=ctypes.c_ulong
 rootwin=x.XDefaultRootWindow(display);r=ctypes.c_ulong();parent=ctypes.c_ulong();children=ctypes.POINTER(ctypes.c_ulong)();count=ctypes.c_uint()
 x.XQueryTree.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),ctypes.POINTER(ctypes.c_uint)]
 x.XRaiseWindow.argtypes=[ctypes.c_void_p,ctypes.c_ulong];x.XRaiseWindow(display,int(wid));x.XSync.argtypes=[ctypes.c_void_p,ctypes.c_int];x.XSync(display,0)
 x.XQueryTree(display,rootwin,ctypes.byref(r),ctypes.byref(parent),ctypes.byref(children),ctypes.byref(count))
 assert children[count.value-1]==int(wid),('fixture not topmost',count.value)
 print('PREFLIGHT opaque owned override window mapped exact geometry and topmost', 'full monitor' if full else 'region',flush=True)
 session=CaptureSession(CaptureConfig(str(root),':0',[0,0,1920,1080] if full else [116,116,608,328],fps=30,auto_finalize=False,mic='loom_synthetic.monitor' if os.environ.get('MODE')!='system' else None,system_audio='loom_synthetic.monitor' if os.environ.get('MODE')!='mic' else None))
 session.start()
 for _ in range(4):
  time.sleep(1)
  pid=session.status().get('pid')
  if pid:print(subprocess.run(['ps','--ppid',str(pid),'-o','comm=,%cpu=,rss='],capture_output=True,text=True).stdout.strip(),flush=True)
 if os.environ.get('MODE')=='crash':
  os.kill(session.status()['pid'],signal.SIGKILL);time.sleep(3)
  from loomrec.capture import recover_project
  print('RECOVERY',recover_project(root),flush=True)
  session=None
  raise SystemExit(0)
 if os.environ.get('MODE')=='rewind':
  session.rewind(2);time.sleep(3);session.stop()
  for _ in range(200):
   if session.status()['state'] in {'stopped','error'}:break
   time.sleep(.1)
  from loomrec.schema import load_project
  project=load_project(root/'project.json')
  removed=sum(s.duration for s in project.sources if s.kind=='screen')-project.duration
  assert abs(removed-2)<.01,(removed,session.status())
  print('REWIND SUCCESS',root,'removed',removed,flush=True)
  raise SystemExit(0)
 session.pause()
 for _ in range(120):
  if session.status()['state'] in {'paused','error'}:break
  time.sleep(.1)
 assert session.status()['state']=='paused',session.status()
 time.sleep(1);session.resume();time.sleep(4);session.stop()
 for _ in range(200):
  if session.status()['state'] in {'stopped','error'}:break
  time.sleep(.1)
 assert session.status()['state']=='stopped',session.status()
 job=RenderJob(root/'project.json',root/'export.mp4').start();job._thread.join(60)
 assert job.poll()['state']=='done',job.poll()
 print('SUCCESS',root,session.status(),flush=True)
finally:
 if session and session.status()['state'] in {'recording','paused'}:session.stop();time.sleep(2)
 for p in [player,window]:
  if p and p.poll() is None:p.terminate();p.wait()
 if module:subprocess.run(['pactl','unload-module',module])
