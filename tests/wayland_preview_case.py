"""Native installed Files/Recorder players with a generated silent video."""
import json

CHILD = r'''
import json,os,sys,time,subprocess
from pathlib import Path
import PySide6
PySide6.__path__.insert(0,'/tmp/wysun-qml-bindings/root/usr/lib/python3/dist-packages/PySide6')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
run=Path(sys.argv[1]);home=Path.home()
assert str(run).startswith('/tmp/ws-') and home.is_relative_to(run)
sys.path.insert(0,str(home/'.local/share/orbit/app'))
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
def spin(fn,description,timeout=12):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  app.processEvents();time.sleep(.025)
  if fn():return
 raise RuntimeError(description)
def native():
 return any(c['pid']==os.getpid() and c['mapped'] and not c['xwayland'] for c in json.loads(subprocess.check_output(['hyprctl','-j','clients'],text=True)))
result={};frames=[]
from file_viewer import FileViewer
viewer=FileViewer(run/'synthetic-preview.mkv');viewer.show();player=viewer.player
try:
 spin(native,'Files native preview')
 spin(lambda:player.sock and not player.surface.image.isNull(),'Files embedded first frame')
 player.surface.frameReady.connect(lambda:frames.append(time.monotonic()))
 QTest.mouseClick(player.play_button,Qt.LeftButton)
 spin(lambda:(player.props.get('time-pos') or 0)>.5 and len(frames)>3,'Files playback frames')
 QTest.mouseClick(player.play_button,Qt.LeftButton)
 spin(lambda:player.props.get('pause') is True,'Files pause')
 player.position.setValue(500);player.seek()
 spin(lambda:abs((player.props.get('time-pos') or 0)-2)<.4,'Files seek')
 player.surface.image.save(str(run/'native-files-preview-frame.png'))
 result['files']=dict(native=True,embedded_frames=len(frames),pause_seek=True,image_size=[player.surface.image.width(),player.surface.image.height()])
finally:
 viewer.reject();spin(lambda:player.surface.thread is None and player.surface.handle is None,'Files shutdown')
from loomrec.ui.player import Player
recorder=Player();recorder.setWindowTitle('Wysun synthetic Recorder preview');recorder.show();errors=[];frames=[]
recorder.failed.connect(errors.append);recorder.surface.frameReady.connect(lambda:frames.append(time.monotonic()))
try:
 recorder.load(run/'synthetic-preview.mkv')
 spin(lambda:native() and recorder.client and not recorder.surface.image.isNull(),'Recorder native embedded first frame')
 recorder.toggle();spin(lambda:recorder.position>.5 and len(frames)>3,'Recorder playback frames')
 recorder.toggle();spin(lambda:recorder.paused,'Recorder pause');recorder.seek(2)
 spin(lambda:abs(recorder.position-2)<.4,'Recorder seek')
 recorder.resize(800,450);spin(lambda:recorder.surface.image.width()>700,'Recorder resize')
 recorder.surface.image.save(str(run/'native-recorder-preview-frame.png'))
 assert not errors,errors
 result['recorder']=dict(native=True,embedded_frames=len(frames),pause_seek_resize=True,image_size=[recorder.surface.image.width(),recorder.surface.image.height()],errors=errors)
finally:
 recorder.shutdown();recorder.hide()
 assert recorder.surface.thread is None and recorder.surface.handle is None
result.update(result='WYSUN_NATIVE_PREVIEWS_OK',scope='actual installed widgets/native surfaces/libmpv SW and IPC; silent generated video, no public launcher assertion')
(run/'native-preview-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
'''


def run_case(run_dir,env,command,start,wait_for):
    command(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=24:duration=4',
             '-an','-c:v','libx264','-threads','1','-preset','ultrafast',run_dir/'synthetic-preview.mkv'])
    child=run_dir/'native-preview-child.py';child.write_text(CHILD)
    process=start('native-preview',['/usr/bin/python3',child,run_dir],
        {'LD_LIBRARY_PATH':'/tmp/wysun-qml-bindings/root/usr/lib/x86_64-linux-gnu:'+env.get('LD_LIBRARY_PATH',''),
         'WYSUN_LIBMPV':'/tmp/wysun-portal-tools/root/usr/lib/x86_64-linux-gnu/libmpv.so.2'})
    wait_for(lambda:process.poll() is not None,'native preview proof',timeout=45)
    assert process.returncode==0,(run_dir/'native-preview.log').read_text(errors='replace')[-6000:]
    result=json.loads((run_dir/'native-preview-results.json').read_text());print(json.dumps(result,indent=2),flush=True)
    return result
