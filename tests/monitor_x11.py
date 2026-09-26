"""Isolated real BSPWM desktop migration test. Set XVFB_BIN if not on PATH."""
import os,sys,json,subprocess,tempfile,time,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/orbit'))
from display_workspaces import reconcile
xvfb_bin=os.environ.get('XVFB_BIN') or shutil.which('Xvfb')
if not xvfb_bin:raise SystemExit('Set XVFB_BIN to run the isolated monitor test.')
folder=Path(tempfile.mkdtemp(prefix='orbit-monitor-x11-'))
processes=[]
try:
 with (folder/'display').open('w+') as display_file:
  xvfb=subprocess.Popen([xvfb_bin,'-displayfd',str(display_file.fileno()),'-screen','0','2400x800x24','-nolisten','tcp'],pass_fds=(display_file.fileno(),),stdout=subprocess.DEVNULL,stderr=(folder/'xvfb.log').open('w'));processes.append(xvfb)
  for _ in range(50):
   display_file.seek(0);number=display_file.read().strip()
   if number:break
   time.sleep(.1)
  assert number,'Xvfb did not start'
 env=dict(os.environ,DISPLAY=':'+number,BSPWM_SOCKET=str(folder/'bspwm.sock'))
 def run(args):
  try:return subprocess.check_output(args,env=env,text=True,stderr=subprocess.PIPE,timeout=10).strip()
  except subprocess.CalledProcessError:raise
 wm=subprocess.Popen(['bspwm','-c','/dev/null'],env=env,stdout=subprocess.DEVNULL,stderr=(folder/'bspwm.log').open('w'));processes.append(wm)
 for _ in range(50):
  try:state=json.loads(run(['bspc','wm','-d']));break
  except (subprocess.CalledProcessError,FileNotFoundError):time.sleep(.1)
 else:raise AssertionError('BSPWM did not start')
 run(['bspc','monitor','-n','eDP-1'])
 run(['bspc','monitor','eDP-1','-g','800x800+0+0'])
 for name,pos in [('DP-2','800x800+800+0'),('DP-1','800x800+1600+0')]:run(['bspc','wm','-a',name,pos])
 def outputs(names):return [dict(name=name,connected=True,enabled=True,primary=name==('DP-2' if 'DP-2' in names else 'eDP-1'),x=i*800) for i,name in enumerate(names)]
 triple=outputs(['eDP-1','DP-2','DP-1']);single=outputs(['eDP-1']);dual=outputs(['eDP-1','DP-1'])
 reconcile(triple,runner=run)
 def snap():return json.loads(run(['bspc','wm','-d']))
 def desktops():return {d['name']:d for m in snap()['monitors'] for d in m['desktops']}
 def windows(node):
  if not node:return set()
  return ({node['id']} if node.get('client') else set())|windows(node.get('firstChild'))|windows(node.get('secondChild'))
 for name in ['1','8']:
  run(['bspc','desktop',name,'-f'])
  p=subprocess.Popen(['xmessage','-name','OrbitMonitorTest','Window on desktop '+name],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(p)
  for _ in range(50):
   if windows(desktops()[name]['root']):break
   time.sleep(.1)
  else:raise AssertionError('Test window did not appear')
 run(['bspc','monitor','DP-1','-a','Proyecto'])
 original={name:(d['id'],windows(d['root'])) for name,d in desktops().items()}
 assert len(set.union(*(nodes for _,nodes in original.values())))==2
 def unchanged():
  now=desktops()
  for name,(identifier,nodes) in original.items():
   assert name in now,(name,'missing');assert now[name]['id']==identifier,(name,'changed ID');assert windows(now[name]['root'])==nodes,(name,'lost windows')
 reconcile(single,runner=run);unchanged()
 assert [m['name'] for m in snap()['monitors']]==['eDP-1']
 assert [d['name'] for d in snap()['monitors'][0]['desktops']][:10]==[str(i) for i in range(1,11)]
 run(['bspc','wm','-a','DP-1','800x800+800+0']);reconcile(dual,runner=run);unchanged()
 assert next(m['name'] for m in snap()['monitors'] if any(d['name']=='8' for d in m['desktops']))=='DP-1'
 run(['bspc','wm','-a','DP-2','800x800+1600+0']);reconcile(triple,runner=run);unchanged()
 for _ in range(3):reconcile(triple,runner=run);unchanged()
 # Reproduce legacy duplicate numbers: preserve occupied trees, remove only empty duplicates.
 run(['bspc','monitor','DP-2','-a','1','2'])
 duplicate=next(d for m in snap()['monitors'] for d in reversed(m['desktops']) if d['name']=='1')
 run(['bspc','desktop',f"0x{duplicate['id']:08X}",'-f'])
 p=subprocess.Popen(['xmessage','-name','OrbitMonitorTest','Duplicate desktop'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(p)
 for _ in range(50):
  records={d['id']:d for m in snap()['monitors'] for d in m['desktops']}
  if windows(records[duplicate['id']]['root']):break
  time.sleep(.1)
 else:raise AssertionError('Duplicate test window did not appear')
 occupied={identifier:windows(d['root']) for identifier,d in records.items() if d['root'] is not None}
 reconcile(single,runner=run)
 final=[d for m in snap()['monitors'] for d in m['desktops']]
 assert len({d['name'] for d in final})==len(final)
 assert all(next(windows(d['root']) for d in final if d['id']==identifier)==nodes for identifier,nodes in occupied.items())
 assert any('recuperado' in d['name'] for d in final)
 print('MONITOR_RECOVERY_OK: 3 -> 1 -> 2 -> 3; repeated reload; original desktops/windows and custom names kept; occupied duplicates recovered, empty duplicates removed.')
finally:
 for p in reversed(processes):
  if p.poll() is None:p.terminate()
 for p in reversed(processes):
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:p.kill();p.wait()
