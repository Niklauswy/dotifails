"""Serial native synthetic-only controlbar exclusion and finished playback proof."""
import ctypes as C,ctypes.util,json,sys,tempfile,time,subprocess,os
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor,QPalette,QPainter
from PySide6.QtWidgets import QApplication,QWidget
from loomrec.ui.main import Window,apply_theme
from loomrec.library import Library
app=QApplication([]);app.setQuitOnLastWindowClosed(False);apply_theme(app);root=Path(tempfile.mkdtemp(prefix='wybie-safe-proof-'));os.environ['XDG_STATE_HOME']=str(root/'state');os.environ['XDG_CONFIG_HOME']=str(root/'config')
class Fixture(QWidget):
 def paintEvent(self,event):
  painter=QPainter(self);painter.fillRect(self.rect(),QColor(70,110,140))
fixture=Fixture();fixture.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.X11BypassWindowManagerHint);fixture.setGeometry(0,0,1920,1080);fixture.setAutoFillBackground(True);fixture.setAttribute(Qt.WA_OpaquePaintEvent)
pal=fixture.palette();pal.setColor(QPalette.Window,QColor(70,110,140));fixture.setPalette(pal);fixture.show()
w=Window(Library(root/'library'),False);w.countdown.setValue(1);w.quiet.setChecked(False);w.fps.setCurrentIndex(0);w.quality.setCurrentIndex(0)
for source in [w.mic,w.system,w.camera]:source.setCurrentIndex(0)
for spin,value in zip(w.rect,[100,100,640,360]):spin.setValue(value)
w.ensure_keys=lambda:None
errors=[];w.error=lambda text:errors.append(str(text))
x=C.CDLL(ctypes.util.find_library('X11'));x.XOpenDisplay.restype=C.c_void_p;x.XOpenDisplay.argtypes=[C.c_char_p];display=x.XOpenDisplay(None)
x.XDefaultRootWindow.argtypes=[C.c_void_p];x.XDefaultRootWindow.restype=C.c_ulong;x.XRaiseWindow.argtypes=[C.c_void_p,C.c_ulong];x.XSync.argtypes=[C.c_void_p,C.c_int]
x.XQueryTree.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.POINTER(C.c_ulong)),C.POINTER(C.c_uint)]
# The synthetic backdrop shares this proof process; production surfaces do not.
# Exclude only the fixture from the application-owned top-level hide enumeration.
from unittest.mock import patch
real_hide=w.hide_capture_controls
real_top_levels=QApplication.topLevelWidgets
def hide_controls():
 with patch.object(QApplication,'topLevelWidgets',return_value=[widget for widget in real_top_levels() if widget is not fixture]):real_hide()
w.hide_capture_controls=hide_controls
real_start=w.start_capture
popup=None
def start():
 assert not w.isVisible() and not w.quick.isVisible() and not popup.isVisible() and not w.tray.isVisible()
 assert not w.countdown_overlay.isVisible() and not w.camera_preview.is_running
 assert fixture.grab().toImage().pixelColor(100,100).getRgb()[:3]==(70,110,140)
 info=subprocess.check_output(['xwininfo','-id',str(int(fixture.winId()))],text=True)
 for item in ['Absolute upper-left X:  0','Absolute upper-left Y:  0','Width: 1920','Height: 1080','Map State: IsViewable','Override Redirect State: yes']:assert item in info,(item,info)
 x.XRaiseWindow(display,int(fixture.winId()));x.XSync(display,0)
 r=C.c_ulong();p=C.c_ulong();children=C.POINTER(C.c_ulong)();n=C.c_uint();x.XQueryTree(display,x.XDefaultRootWindow(display),C.byref(r),C.byref(p),C.byref(children),C.byref(n));assert children[n.value-1]==int(fixture.winId())
 real_start()
w.start_capture=start
controller=None
phase=0;began=time.monotonic();last=began

def tick():
 global phase,last,popup,controller
 try:
  if errors:raise RuntimeError(';'.join(errors))
  if time.monotonic()-began>60:raise TimeoutError('proof timeout')
  if phase==0:
   w.quick.present();w.quick.settings();popup=w.quick.popup;assert popup.isVisible();w.quick.start.click();assert w.countdown_overlay.isVisible();phase=1
  elif phase==1 and w.session and w.session.status()['state']=='recording':
   from PySide6.QtCore import QRect
   assert w.recording_indicator.windows
   for widget in w.recording_indicator.windows:assert widget.isVisible() and not widget.geometry().intersects(QRect(100,100,640,360))
   last=time.monotonic();phase=2
  elif phase==2 and time.monotonic()-last>1:
   from loomrec.ui.activation import RecordingController
   class Owner:
    def request(self,action,timeout=.7):return w.activate_instance(action)
   controller=RecordingController(w.session,Owner());controller.prepare_show()
   assert not controller.isVisible();phase=3
  elif phase==3:
   if w.session.status()['state']!='paused':assert not controller.isVisible()
   elif controller.isVisible():
    assert 'En pausa' in controller.timer_label.text()
    controller.pause_button.click();assert not controller.isVisible() and not w.isVisible()
    assert w.session.status()['state']=='paused';last=time.monotonic();phase=4
  elif phase==4 and w.session.status()['state']=='recording':
   assert time.monotonic()-last>=.45
   assert not controller.isVisible() and not w.quick.isVisible() and not w.isVisible()
   last=time.monotonic();phase=5
  elif phase==5 and time.monotonic()-last>1:
   controller.prepare_show();assert not controller.isVisible();phase=6
  elif phase==6 and w.session.status()['state']=='paused' and controller.isVisible():
   controller.stop_button.click();phase=7
  elif phase==7 and w.session is None and w.editor and w.job is None:
   assert w.viewing and w.isVisible();phase=8
  elif phase==8 and w.player.command('get_property','duration'):
   w.play_button.click();phase=9
  elif phase==9 and w.position>.3:
   w.play_button.click();w.player.seek(.5);phase=10
  elif phase==10 and abs(w.position-.5)<.2:
   for source in w.editor.project.sources:
    if source.kind!='screen':continue
    data=subprocess.check_output(['ffmpeg','-v','error','-i',str(w.editor.path.parent/source.path),'-vf','scale=16:16','-f','rawvideo','-pix_fmt','rgb24','pipe:1']);assert data
    for ch,target in enumerate((70,110,140)):assert max(abs(v-target) for v in data[ch::3])<=8,(ch,min(data[ch::3]),max(data[ch::3]))
   print(json.dumps({'status':'passed','pause_ack_before_mapping':True,'resume_hide_guard':True,'finished_player_play_pause_seek':True,'quick_and_popup_hidden_before_capture':True,'all_decoded_frames':'owned uniform fixture RGB +-8','geometry':[100,100,640,360],'outside_indicator_visible':True,'countdown_hidden':True,'camera_preview_released':True,'clips':len(w.editor.project.clips)}),flush=True)
   timer.stop();controller.timer.stop();controller.close();w.close();fixture.close();app.quit()
 except Exception as exc:
  import traceback;traceback.print_exc();print('FAILED phase',phase,repr(exc),flush=True)
  if w.session:w.session.stop()
  if w.keys:w.keys.close()
  w.player.shutdown();fixture.close();app.exit(1)
timer=QTimer();timer.timeout.connect(tick);timer.start(100);sys.exit(app.exec())
