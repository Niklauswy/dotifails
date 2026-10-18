"""Explicit physical UI test: capture only an owned opaque solid-color fixture."""
import ctypes as C,ctypes.util,json,sys,tempfile,time,subprocess
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QPointF,QEvent
from PySide6.QtGui import QColor,QPalette,QMouseEvent
from PySide6.QtWidgets import QApplication,QWidget
from loomrec.ui.main import Window,apply_theme
from loomrec.library import Library
app=QApplication([]);apply_theme(app)
fixture=QWidget();fixture.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.X11BypassWindowManagerHint)
fixture.setGeometry(100,100,640,360);fixture.setAutoFillBackground(True)
palette=fixture.palette();palette.setColor(QPalette.Window,QColor(70,110,140));fixture.setPalette(palette);fixture.show();fixture.raise_()
root=Path(tempfile.mkdtemp(prefix='loom-ui-capture-'));w=Window(Library(root),False)
w.setWindowFlags(Qt.FramelessWindowHint|Qt.X11BypassWindowManagerHint);w.setGeometry(800,50,940,900)
w.stack.setCurrentWidget(w.setup_page);w.show();errors=[];w.error=lambda text:errors.append(str(text))
w.countdown.setValue(1);w.quiet.setChecked(False);w.mic.setCurrentIndex(0);w.system.setCurrentIndex(0)
# XTest synthesizes only our explicitly grabbed non-VT chord.
x=C.CDLL(ctypes.util.find_library('X11'));xt=C.CDLL(ctypes.util.find_library('Xtst'))
x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p;display=x.XOpenDisplay(None)
x.XStringToKeysym.argtypes=[C.c_char_p];x.XStringToKeysym.restype=C.c_ulong
x.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x.XKeysymToKeycode.restype=C.c_uint
x.XFlush.argtypes=[C.c_void_p];xt.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
def chord(letter):
 keys=[x.XKeysymToKeycode(display,x.XStringToKeysym(k.encode())) for k in ['Super_L','Control_L','Shift_L',letter]]
 for code in keys:xt.XTestFakeKeyEvent(display,code,True,0)
 for code in reversed(keys):xt.XTestFakeKeyEvent(display,code,False,0)
 x.XFlush(display)
real_start=w.start_capture
def start():
 info=subprocess.check_output(['xwininfo','-id',str(int(fixture.winId()))],text=True)
 for item in ['Absolute upper-left X:  100','Absolute upper-left Y:  100','Width: 640','Height: 360','Map State: IsViewable','Override Redirect State: yes']:assert item in info,(item,info)
 assert not w.isVisible() and not w.picker.isVisible() and not w.tray.isVisible(),'capture UI must be unmapped'
 fixture.raise_();app.processEvents();real_start()
w.start_capture=start
started=time.monotonic();phase=0;last=started;project=None

def tick():
 global phase,last,project
 try:
  if errors:raise RuntimeError('; '.join(errors))
  if time.monotonic()-started>40:raise TimeoutError('UI capture timed out')
  if phase==0:
   w.pick_region()
   a=QPointF(116,116);b=QPointF(724,444)
   w.picker.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress,a,a,Qt.LeftButton,Qt.LeftButton,Qt.NoModifier))
   w.picker.mouseMoveEvent(QMouseEvent(QEvent.MouseMove,b,b,Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
   w.picker.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease,b,b,Qt.LeftButton,Qt.NoButton,Qt.NoModifier))
   assert [spin.value() for spin in w.rect]==[116,116,608,328]
   w.begin_countdown();phase=1
  elif phase==1 and w.session and w.session.status()['state']=='recording':
   project=w.session.root/'project.json';last=time.monotonic();phase=2
  elif phase==2 and time.monotonic()-last>2:
   chord('p');phase=3
  elif phase==3 and w.session.status()['state']=='paused':
   chord('p');last=time.monotonic();phase=4
  elif phase==4 and time.monotonic()-last>2:
   chord('s');phase=5
  elif phase==5 and w.session is None and w.editor:
   assert w.editor.path==project and len(w.editor.project.clips)==2
   for source in w.editor.project.sources:
    if source.kind!='screen':continue
    # Check every decoded frame; all must remain the uniform owned fixture.
    data=subprocess.check_output(['ffmpeg','-v','error','-i',str(project.parent/source.path),'-vf','scale=8:8','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
    assert data
    for channel,target in enumerate((70,110,140)):
     values=data[channel::3];assert max(abs(v-target) for v in values)<=8,(channel,min(values),max(values))
   print(json.dumps({'status':'passed','project':str(project),'clips':2,'selector':'drag events','countdown':'actual1s','controls':'XTest global pause/resume/stop','pixels':'all decoded frames uniform fixture; no controls'}),flush=True)
   w.close();fixture.close();app.quit()
 except Exception as exc:
  print('FAILED',repr(exc),flush=True)
  if w.session:w.session.stop()
  if w.keys:w.keys.close()
  w.player.shutdown();fixture.close();app.exit(1)
timer=QTimer();timer.timeout.connect(tick);timer.start(100)
sys.exit(app.exec())
