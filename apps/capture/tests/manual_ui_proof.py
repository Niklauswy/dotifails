"""Explicit safe-fixture-only native UI proof; never captures the desktop."""
import os,sys,tempfile,shutil,time,json
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QTimer
from loomrec.ui.main import Window
from loomrec.library import Library
from loomrec.integration import GlobalKeys

source=Path(sys.argv[1]);destination=Path(sys.argv[2]);destination.mkdir(parents=True,exist_ok=True)
root=Path(tempfile.mkdtemp(prefix='loom-ui-proof-'));project=root/'fixture';shutil.copytree(source,project)
app=QApplication([]);app.setStyle('Fusion')
window=Window(Library(root),probe_devices=True);errors=[];window.error=lambda text:errors.append(str(text));window.show()
started=time.monotonic(); phase=0; preview=None

def tick():
 global phase,preview
 try:
  if errors:raise RuntimeError('; '.join(errors))
  if time.monotonic()-started>90:raise TimeoutError('UI proof exceeded 90s')
  if phase==0 and not window.tasks:
   assert window.monitor.count()>0,'no physical monitor discovered'
   keys=GlobalKeys({'r':lambda:None,'p':lambda:None,'s':lambda:None,'c':lambda:None,'z':lambda:None,'i':lambda:None});keys.close()
   window.open_project(project/'project.json',edit=True)
   window.editor.trim(0,.2,min(2,window.editor.project.clips[0].out_s))
   window.editor.split(0,.8);window.editor.move(0,1);window.editor.undo();window.editor.redo();window.editor.undo()
   window.editor.add_annotation('mask',0,.5,[.1,.1,.2,.2]);window.refresh_editor()
   window.preset.setCurrentIndex(0);window.render(False);phase=1
  elif phase==1 and window.job is None and window.preview_revision>=0:
   preview=window.player.process.arguments()[-1];phase=2
  elif phase==2 and window.player.command('get_property','duration'):
   duration=window.player.command('get_property','duration');assert abs(duration-window.editor.project.duration)<.2
   window.player.seek(.4);window.player.toggle();phase=3
  elif phase==3 and window.position>.5:
   window.player.toggle()
   # Only the owned application's window, never root-screen pixels.
   app.primaryScreen().grabWindow(int(window.winId())).save(str(destination/'editor.png'))
   result={'status':'passed','discovered_monitors':window.monitor.count(),'duration':window.editor.project.duration,'preview':preview,'mpv_position':window.position,'project':str(project/'project.json'),'screenshots':str(destination/'editor.png')}
   (destination/'ui-proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
   window.timer.stop();window.close();app.quit()
 except Exception as exc:
  print('FAILED: '+str(exc),flush=True);window.timer.stop()
  if window.job:window.job.cancel()
  window.player.shutdown();app.exit(1)

timer=QTimer();timer.timeout.connect(tick);timer.start(200)
sys.exit(app.exec())
