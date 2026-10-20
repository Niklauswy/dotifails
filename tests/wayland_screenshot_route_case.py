"""Public Screenshot with app.exec, real portals and owned pixels.

Only through wayland_screenshot_route_probe.py and the guarded nested runner.
The launcher must mount a PRIVATE tmpfs at /tmp/hypr because the upstream picker
stores window geometry there independently of HOME/XDG. No physical screen,
input, audio or host bus is permitted; source guards run before this case.
"""
import json,os,struct,time,subprocess
from pathlib import Path

def run_case(run_dir,env,command,start,wait_for,*,pending_only=False,pending_hold_s=.5):
 from wayland_test_pointer import SyntheticPointer
 from PySide6.QtGui import QImage
 assert str(run_dir).startswith('/tmp/ws-')
 mounts=Path('/proc/self/mountinfo').read_text().splitlines()
 assert any(' /tmp/hypr ' in line and ' - tmpfs ' in line for line in mounts),'Use bwrap --tmpfs /tmp/hypr; never write the host picker settings'
 assert env.get('QT_NO_GLIB') is None,'Do not hide product bootstrap with test env'
 pointer=SyntheticPointer(env);pointer.keyboard();events=[];process=None;bus_monitor=None
 public=Path(env['HOME'])/'.local/bin/wysun';result={'result':'INCOMPLETE','events':events,'scope':'public installed executable; normal Qt app.exec; real Screenshot portal; ScreenCast picker only for cursor preference; private output only'}
 import hashlib
 release=Path(env['PYTHONPATH']);assert release.parent.name=='releases' and str(release).startswith(str(run_dir))
 result['installed_release']=release.name
 result['producer_sha256']={name:hashlib.sha256((release/name).read_bytes()).hexdigest() for name in ('wybieshot/__main__.py','wybieshot/actions.py','wybieshot/ui/main.py','wybieshot/ui/capture_feedback.py','loomrec/portal.py','loomrec/portal_image.py','loomrec/wayland_capture.py')}
 def clients():return json.loads(command(['hyprctl','-j','clients']))
 def wait(fn,desc,t=18):return wait_for(fn,desc,timeout=t)
 def save(): (run_dir/'screenshot-route-result.json').write_text(json.dumps(result,indent=2)+'\n')
 def event(phase,**values):events.append({'phase':phase,'at_s':round(time.monotonic()-began,3),**values});save()
 def key(code,mods=0):
  pointer.send(pointer.keyboard_id,2,struct.pack('IIII',mods,0,0,0));pointer.roundtrip()
  for s in (1,0):pointer.send(pointer.keyboard_id,1,struct.pack('III',int(time.monotonic()*1000)&0xffffffff,code,s));pointer.roundtrip();time.sleep(.05)
  pointer.send(pointer.keyboard_id,2,struct.pack('IIII',0,0,0,0));pointer.roundtrip()
 def window(predicate,pid=None):
  return next((c for c in clients() if c.get('mapped') and not c.get('xwayland') and (pid is None or c.get('pid')==pid) and predicate(c)),None)
 def own(title):return wait(lambda:window(lambda c:c['title'].startswith(title),process.pid),title)
 def capture(name):
  monitors=json.loads(command(['hyprctl','-j','monitors']));assert len(monitors)==1 and monitors[0]['name']=='WYSUN-TEST-1'
  command(['grim','-o','WYSUN-TEST-1',run_dir/name])
 def set_cursor(enabled):
  target=Path(env['XDG_DATA_HOME'])/'wybie-screenshot/preferences.json'
  target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text(json.dumps({'output':str(run_dir/'library'),'settings':{'format':'PNG','delay':0,'include_cursor':enabled,'reduced_motion':False}}))
  event('cursor-preference',enabled=enabled)
 def choose_screen():
  picker=wait(lambda:window(lambda c:c.get('class')=='hyprland-share-picker'),'real portal picker')
  assert Path('/proc') .joinpath(str(picker['pid']),'exe').resolve().name=='hyprland-share-picker'
  event('real-picker-mapped',size=picker['size']);capture('route-real-picker.png')
  pointer.click(picker['at'][0]+picker['size'][0]//2,picker['at'][1]+78)
  event('real-monitor-consent-clicked',output='WYSUN-TEST-1')
 def drag(overlay):
  x,y=overlay['at'];w,h=overlay['size'];x+=round(w*.15);y+=round(h*.18);endx=x+320;endy=y+240
  pointer.move(x,y);pointer.send(pointer.pointer,2,struct.pack('III',int(time.monotonic()*1000)&0xffffffff,272,1));pointer.send(pointer.pointer,4);pointer.roundtrip()
  for f in (.25,.5,.75,1):pointer.move(round(x+(endx-x)*f),round(y+(endy-y)*f));time.sleep(.06)
  pointer.send(pointer.pointer,2,struct.pack('III',int(time.monotonic()*1000)&0xffffffff,272,0));pointer.send(pointer.pointer,4);pointer.roundtrip();time.sleep(.2)
 def launch(mode):
  nonlocal process
  assert process is None or process.poll() is not None
  args=[public,'screenshot']
  if mode!='quick':args+=['--region','--delay','0']
  if mode=='auto':args+=['--accept-on-select','--clipboard','--path',str(run_dir/'route-auto-export.png')]
  process=start('route-'+mode,args);event('public-launch',mode=mode,pid=process.pid)
 def ended(label):
  wait(lambda:process.poll() is not None,label+' normal exit',8);assert process.returncode==0,process.returncode
  event(label+'-exit',code=0)
 def export_check(path):
  i=QImage(str(path));assert not i.isNull();rgb=i.pixelColor(30,30).getRgb();assert rgb==(49,87,135,255),rgb
  assert (i.width(),i.height())==(321,241),(i.width(),i.height())
  raw=i.convertToFormat(QImage.Format_RGBA8888)
  pixels=bytes(raw.constBits());colors={pixels[n:n+4] for n in range(0,len(pixels),4)}
  assert colors=={bytes((49,87,135,255))},'Unexpected UI/pending pixels entered the authorized crop'
  event('png-export-decoded',file=path.name,size=[i.width(),i.height()],rgb=list(rgb),uniform_fixture_pixels=True)
 began=time.monotonic()
 try:
  if pending_only:set_cursor(True)
  else:set_cursor(False)
  if not pending_only:
   # Contrast actual Wayland QApplication vs the QtCore fixture, without a window.
   code='from PySide6.QtWidgets import QApplication; a=QApplication([]);print(a.eventDispatcher().metaObject().className())'
   result['native_dispatcher_without_flag']=command(['/usr/bin/python3','-c',code]).strip()
   result['native_dispatcher_with_flag']=subprocess.check_output(['/usr/bin/python3','-c',code],env=dict(env,QT_NO_GLIB='1'),text=True).strip()
   # Default region path: the Screenshot portal returns the frozen desktop with
   # no ScreenCast source picker, then the product shows its own selection frame.
   launch('direct');overlay=own('Recortar imagen autorizada');event('frozen-image-selection-mapped')
   assert not window(lambda c:c.get('class')=='hyprland-share-picker'),'Default region capture must not open the ScreenCast picker'
   drag(overlay);capture('route-selection-editor.png');event('region-selected-editor-shown')
   key(31,4);dialog=own('Guardar captura');event('save-dialog-mapped')
   pointer.click(dialog['at'][0]+300,dialog['at'][1]+dialog['size'][1]-74);key(30,4)
   command(['wtype','-s','100',str(run_dir/'route-save-export.png')]);pointer.keyboard();key(28)
   wait(lambda:(run_dir/'route-save-export.png').exists(),'GUI exported PNG');ended('direct-save');export_check(run_dir/'route-save-export.png')
   # Cursor-enabled screenshots still use the real ScreenCast provider; keep the
   # picker, consent, cancellation and pending coverage on that supported path.
   set_cursor(True)
   launch('quick');bar=own('Wysun Screenshot · Captura rápida');event('second-open-quickbar',size=bar['size'],at=bar['at']);capture('route-quickbar.png')
   # Mode dropdown explicitly selects Region; Capturar is the separate start action.
   x,y=bar['at'];pointer.click(x+75,y+44);time.sleep(.35);capture('route-mode-menu.png');pointer.click(x+100,y-18);time.sleep(.3);capture('route-mode-selected.png');event('region-mode-selected',selection='real menu first row by pointer')
   pointer.move(100,400);time.sleep(.15);pointer.click(x+560,y+44);choose_screen();own('Recortar imagen autorizada');key(1)
   bar=own('Wysun Screenshot · Captura rápida');event('escape-cancel-restored-quickbar')
   pointer.click(bar['at'][0]+bar['size'][0]-40,bar['at'][1]+44);ended('quick-cancel-close')
   launch('auto');choose_screen();overlay=own('Recortar imagen autorizada');drag(overlay)
   # A release must commit the CLI accept-on-select path, without an Enter workaround.
   wait(lambda:(run_dir/'route-auto-export.png').exists(),'accept-on-select export after mouse release',5)
   export_check(run_dir/'route-auto-export.png')
   bitmap=subprocess.check_output(['wl-paste','--no-newline','--type','image/png'],env=env,timeout=5)
   received=QImage.fromData(bitmap);assert (received.width(),received.height())==(321,241)
   assert received.pixelColor(30,30).getRgb()==(49,87,135,255)
   event('clipboard-png-received',size=[received.width(),received.height()])
   keeper=process;assert keeper.poll() is None;process=None
   # Re-enter real capture while the prior clipboard owner remains alive.
   launch('quick');bar=own('Wysun Screenshot · Captura rápida')
   pointer.click(bar['at'][0]+560,bar['at'][1]+44);choose_screen();own('Recortar imagen autorizada');key(1)
   bar=own('Wysun Screenshot · Captura rápida');event('new-capture-while-old-clipboard-owner-alive',keeper_alive=keeper.poll() is None)
   pointer.click(bar['at'][0]+bar['size'][0]-40,bar['at'][1]+44);ended('post-clipboard-cancel')
   subprocess.run(['wl-copy','--type','text/plain'],env=env,input=b'Wysun synthetic replacement',check=True,timeout=5)
   wait(lambda:keeper.poll() is not None,'prior own clipboard keeper normal exit',5);assert keeper.returncode==0
   event('clipboard-owner-exit-after-replacement',code=0)
   # Cancel the real provider dialog, then confirm direct mode exits and reopens.
   launch('direct');picker=wait(lambda:window(lambda c:c.get('class')=='hyprland-share-picker'),'real picker for cancel')
   command(['hyprctl','dispatch','hl.dsp.window.close({window="address:'+picker['address']+'"})']);ended('portal-cancel')
   launch('quick');bar=own('Wysun Screenshot · Captura rápida');event('reopen-after-portal-cancel')
   pointer.click(bar['at'][0]+bar['size'][0]-40,bar['at'][1]+44);ended('final-close')
  # Cancel the application's pending state while the real provider is open.
  bus_monitor=start('screenshot-pending-bus-events',['dbus-monitor','--session',
   "type='signal',interface='org.freedesktop.portal.Request',member='Response'",
   "type='signal',interface='org.freedesktop.portal.Session',member='Closed'",
   "type='method_call',interface='org.freedesktop.portal.Request',member='Close'",
   "type='method_call',interface='org.freedesktop.portal.Session',member='Close'",
   "type='error'"])
  launch('direct');pending=own('Wysun Screenshot · Preparando selección')
  wait(lambda:window(lambda c:c.get('class')=='hyprland-share-picker'),'real picker while pending')
  # Keep this owned dialog accessible beside the provider's larger dialog.
  command(['hyprctl','dispatch','hl.dsp.window.move({x=20,y=20,relative=false,window="address:'+pending['address']+'"})'])
  command(['hyprctl','dispatch','hl.dsp.focus({window="address:'+pending['address']+'"})'])
  pointer.move(100,100);time.sleep(.2)
  before_cancel=time.monotonic();key(1);time.sleep(.5)
  assert process.poll() is None,'Cancellation may not release the worker while provider is still waiting'
  own('Wysun Screenshot · Preparando selección')
  capture('route-pending-cancelling.png')
  from wybieshot.instance import CaptureLease
  lease=CaptureLease();assert not lease.claim(),'Lease released before portal acknowledgement'
  # A >25s hold exercises the real D-Bus timeout boundary without a bootstrap,
  # altered product timeout, fake response or manual Qt event pumping.
  until=before_cancel+pending_hold_s
  while time.monotonic()<until:
   assert process.poll() is None,'Process ended before provider request termination'
   claimed=lease.claim()
   if claimed:lease.release();raise AssertionError('Lease freed before provider request termination')
   assert window(lambda c:c['title'].startswith('Wysun Screenshot · Preparando selección'),process.pid)
   time.sleep(min(.5,max(0,until-time.monotonic())))
  capture('route-pending-cancelling-after-hold.png')
  event('cancel-request-pending-provider',ui_still_visible=True,lease_held=True,observed_hold_s=round(time.monotonic()-before_cancel,3))
  picker=window(lambda c:c.get('class')=='hyprland-share-picker')
  assert picker and Path('/proc',str(picker['pid']),'exe').resolve().name=='hyprland-share-picker'
  penv=Path('/proc',str(picker['pid']),'environ').read_bytes().split(b'\0')
  assert ('XDG_RUNTIME_DIR='+env['XDG_RUNTIME_DIR']).encode() in penv
  # The provider blocks Request.Close until its picker closes. This is the
  # user's explicit close of our PRIVATE provider window, never a product kill.
  command(['hyprctl','dispatch','hl.dsp.window.close({window="address:'+picker['address']+'"})'])
  ended('pending-escape-cancel')
  assert lease.claim();lease.release()
  event('pending-cancel-finished',latency_s=round(time.monotonic()-before_cancel,3),lease_free=True,provider_close_required=True)
  assert not window(lambda c:c.get('class')=='hyprland-share-picker')
  launch('auto');choose_screen();overlay=own('Recortar imagen autorizada');key(1);ended('reopen-after-pending-cancel')
  result['result']='PUBLIC_SCREENSHOT_PENDING_PASS' if pending_only else 'PUBLIC_SCREENSHOT_ROUTE_PASS'
 except Exception as exc:
  result['result']='PUBLIC_SCREENSHOT_ROUTE_FAILED';result['error']=str(exc)
  result['failure_clients']=clients();capture('route-failure.png');raise
 finally:
  if bus_monitor:
   if bus_monitor.poll() is None:bus_monitor.terminate();bus_monitor.wait(timeout=3)
   raw=(run_dir/'screenshot-pending-bus-events.log').read_text()
   result['private_bus_event_counts']={'session_closed':raw.count('member=Closed'),
    'request_response':raw.count('member=Response'),'wire_no_reply':raw.count('error_name=org.freedesktop.DBus.Error.NoReply')}
  save();pointer.close()
  if process and process.poll() is None:process.terminate();process.wait(timeout=3)
 return result
