"""Actual Screenshot QThread/Continue/cancel/export on two owned outputs."""
import json

CHILD=r'''
import json,os,sys,time,subprocess
from pathlib import Path
import PySide6
PySide6.__path__.insert(0,'/tmp/wysun-qml-bindings/root/usr/lib/python3/dist-packages/PySide6')
from PySide6.QtWidgets import QApplication,QPushButton,QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from wybieshot.ui.main import Window
run=Path(sys.argv[1]);assert str(run).startswith('/tmp/ws-') and Path.home().is_relative_to(run)
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
w=Window();w.storage.update_settings(include_cursor=True,reduced_motion=True);w.capture_mode='desktop';w.show()
seen=[];events=[];cancel_second=False
def drive():
 f=w._capture_feedback
 if not f or not f.dialog or not f.dialog.isVisible() or id(f.dialog) in seen:return
 d=f.dialog;seen.append(id(d));text=' '.join(x.text() for x in d.findChildren(QLabel))
 index=2 if 'Monitor 2 de 2' in text else 1
 assert 'de 2' in text,text
 native=any(c['pid']==os.getpid() and c['mapped'] and not c['xwayland'] and c['title']==d.windowTitle()
  for c in json.loads(subprocess.check_output(['hyprctl','-j','clients'],text=True)))
 if not native:seen.pop();return
 (run/'picker-choice').write_text('screen:WYSUN-TEST-'+str(index))
 label='Cancelar todo' if cancel_second and index==2 else 'Continuar al portal'
 button=next(x for x in d.findChildren(QPushButton) if x.text()==label)
 events.append(dict(index=index,action=label,native=True));QTest.mouseClick(button,Qt.LeftButton)
def spin(fn,description,timeout=35):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  app.processEvents();drive();time.sleep(.04)
  if fn():return
 raise RuntimeError(description)
try:
 w.begin_capture();spin(lambda:not w.busy and not w.jobs and w.document is not None,'Screenshot GUI complete')
 assert [x['index'] for x in events]==[1,2],events
 output=run/'native-screenshot-gui-export.png';w.storage.export(w.document,output)
 image=QImage(str(output));assert (image.width(),image.height())==(1920,800),image.size()
 for _ in range(20):app.processEvents();time.sleep(.04)
 previous=sorted(str(p) for p in w.storage.sessions.rglob('*') if p.is_file())
 seen=[];cancel_second=True;w.begin_capture()
 spin(lambda:not w.busy and not w.jobs,'Screenshot GUI cancellation')
 for _ in range(10):app.processEvents();time.sleep(.04)
 assert events[-1]['action']=='Cancelar todo' and events[-1]['index']==2,events
 assert previous==sorted(str(p) for p in w.storage.sessions.rglob('*') if p.is_file()),'Cancellation persisted a partial capture'
 result=dict(result='WYSUN_NATIVE_SCREENSHOT_GUI_OK',events=events,export_size=[image.width(),image.height()],
  cancelled_second_without_new_session=True,scope='actual installed Window/Work/feedback Qt buttons and export API, private picker fixture; no human permission claim')
 (run/'native-screenshot-gui-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
finally:
 w.cancel_capture();spin(lambda:not w.jobs,'Screenshot workers finish');w.close()
'''


def run_case(run_dir,env,command,start,wait_for):
    from wayland_portal_cases import prepare_picker
    prepare_picker(run_dir)
    command(['hyprctl','eval','hl.monitor({output="WYSUN-TEST-1",mode="1280x800@60",position="0x0",scale=1})'])
    command(['hyprctl','eval','hl.monitor({output="WYSUN-TEST-2",mode="640x480@60",position="1280x0",scale=1})'])
    command(['hyprctl','output','create','headless','WYSUN-TEST-2'])
    wait_for(lambda:len(json.loads(command(['hyprctl','-j','monitors'])))==2,'two owned outputs')
    child=run_dir/'native-screenshot-gui-child.py';child.write_text(CHILD)
    try:
        process=start('native-screenshot-gui',['/usr/bin/python3',child,run_dir],
            {'LD_LIBRARY_PATH':'/tmp/wysun-qml-bindings/root/usr/lib/x86_64-linux-gnu:'+env.get('LD_LIBRARY_PATH','')})
        wait_for(lambda:process.poll() is not None,'native Screenshot GUI proof',timeout=90)
        assert process.returncode==0,(run_dir/'native-screenshot-gui.log').read_text(errors='replace')[-6000:]
        result=json.loads((run_dir/'native-screenshot-gui-results.json').read_text());print(json.dumps(result,indent=2),flush=True)
        return result
    finally:command(['hyprctl','output','destroy','WYSUN-TEST-2'])
