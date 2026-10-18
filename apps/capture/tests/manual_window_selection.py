"""Explicit X11 click-selection proof against an owned opaque fixture only."""
import ctypes as C,ctypes.util,tempfile,sys
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtCore import Qt,QTimer
from loomrec.ui.main import Window
from loomrec.library import Library
app=QApplication([]);fixture=QWidget();fixture.setWindowFlags(Qt.FramelessWindowHint|Qt.X11BypassWindowManagerHint|Qt.WindowStaysOnTopHint);fixture.setGeometry(100,100,640,360);fixture.setStyleSheet('background:#466e8c');fixture.show()
w=Window(Library(tempfile.mkdtemp()),False);w.show();errors=[];w.error=errors.append
x=C.CDLL(ctypes.util.find_library('X11'));xt=C.CDLL(ctypes.util.find_library('Xtst'));x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p;d=x.XOpenDisplay(None);x.XFlush.argtypes=[C.c_void_p]
xt.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong];xt.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
def click():
 fixture.raise_();xt.XTestFakeMotionEvent(d,0,150,150,0);xt.XTestFakeButtonEvent(d,1,True,0);xt.XTestFakeButtonEvent(d,1,False,0);x.XFlush(d)
def check():
 if errors:print(errors,flush=True);app.exit(1);return
 if not w.tasks:
  actual=[spin.value() for spin in w.rect]
  print('WINDOW_SELECTION',actual,flush=True)
  result=0 if actual==[100,100,640,360] else 1
  w.close();fixture.close();app.exit(result)
QTimer.singleShot(100,w.pick_window);QTimer.singleShot(700,click)
timer=QTimer();timer.timeout.connect(check);timer.start(1000);QTimer.singleShot(5000,lambda:app.exit(2))
sys.exit(app.exec())
