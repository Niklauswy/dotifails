#!/usr/bin/env python3
"""Run only under an isolated Xvfb + D-Bus session, with a disposable home."""
import json,os,subprocess,sys,tempfile,time
from pathlib import Path
assert os.environ.get('DOTIFAILS_ISOLATED_TEST')=='1','Use an isolated display and home'
os.environ['PATH']=str(Path.home()/'.local/bin')+':'+os.environ['PATH']
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path.home()/'.local/share/orbit/app'))
from service_runtime import Services

def command(args):return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL).strip()
def wait_for(fn,seconds=15):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  try:
   result=fn()
   if result:return result
  except (OSError,subprocess.SubprocessError):pass
  time.sleep(.15)
 raise AssertionError('Timed out: '+str(fn))
def title_windows(title):
 result=subprocess.run(['xdotool','search','--name',title],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 return result.stdout.split() if result.returncode==0 else []
def mapped(wid):return 'IsViewable' in command(['xwininfo','-id',str(wid)])

with tempfile.TemporaryDirectory(prefix='orbit-session-qa-') as tmp:
 os.environ['XDG_RUNTIME_DIR']=tmp;Path(tmp).chmod(0o700)
 log=open('/tmp/dotifails-session.log','w')
 wm=subprocess.Popen([str(Path.home()/'.local/bin/orbit-session')],stdout=log,stderr=log)
 terminal=None
 try:
  wait_for(lambda:command(['bspc','query','-M']))
  services=Services();wait_for(lambda:services.running('sxhkd'));wait_for(lambda:services.running('picom'))
  wait_for(lambda:len(list(services.root.glob('bar-*.json')))>=3)
  bars=wait_for(lambda:command(['xdotool','search','--class','Polybar']).split())
  wait_for(lambda:any(mapped(w) for w in bars))
  terminal=subprocess.Popen(['ghostty','--title=Orbit QA Terminal','-e','sleep','45'],stdout=log,stderr=log)
  def managed_terminal():
   nodes={int(w,0) for w in command(['bspc','query','-N']).split()}
   return next((w for w in title_windows('Orbit QA Terminal') if int(w) in nodes),None)
  term=wait_for(managed_terminal)
  command(['bspc','node',term,'-t','fullscreen']);wait_for(lambda:all(not mapped(w) for w in bars))
  command(['bspc','node',term,'-t','tiled']);wait_for(lambda:any(mapped(w) for w in bars))
  for mode,title in [('home','Órbita'),('notes','Notas'),('color','Color'),('processes','Procesos')]:
   subprocess.run(['orbit',mode],check=True);windows=wait_for(lambda:title_windows(title));wait_for(lambda:any(mapped(w) for w in windows))
   subprocess.run(['xdotool','key','Escape'],check=True)
  subprocess.run(['orbit','home'],check=True);time.sleep(1)
  from PySide6.QtWidgets import QApplication
  app=QApplication([]);app.primaryScreen().grabWindow(0).save('/tmp/dotifails-session.png')
  print('SESSION_SMOKE_OK: BSPWM, sxhkd, Picom, Polybar, Ghostty, fullscreen and native tools')
 finally:
  if terminal and terminal.poll() is None:terminal.terminate();terminal.wait(timeout=5)
  subprocess.run(['bspc','quit'],stderr=subprocess.DEVNULL)
  try:wm.wait(timeout=5)
  except subprocess.TimeoutExpired:wm.terminate();wm.wait(timeout=5)
  for record in list(Services().root.glob('*.json')):
   try:Services().stop(record.stem)
   except (OSError,RuntimeError):pass
  log.close()
