"""Worker-owned live cursor surface. No controls, focus, files, or desktop settings.

The XFixes hide request belongs to one private connection and is balanced on
area exits and normal shutdown; X11 releases it when this process dies.
"""
import argparse
import ctypes as C
import ctypes.util
from collections import deque
import json
import math
import os
import signal
import sys
import time
from PySide6.QtCore import Qt,QTimer,QPointF,QSocketNotifier,QObject
from PySide6.QtGui import QPainter,QColor,QPen,QPolygonF
from PySide6.QtWidgets import QApplication,QWidget
from ..cursor import (PointerReader,local_point,effect_settings,point_at,CURSOR_ARROW,
                      CURSOR_FILL,CURSOR_OUTLINE,CURSOR_ACCENT,HALO_RADIUS,CLICK_DURATION)

class LiveState:
    """Bounded in-area history, discarded on exit and discontinuous motion."""
    def __init__(self,rect,settings):
        self.rect=tuple(rect);self.settings=effect_settings(settings);self.points=deque(maxlen=64);self.clicks=deque(maxlen=32);self.point=None;self.now=0.
    def sample(self,now,position,buttons):
        point=local_point(self.rect,*position) if position else None;self.now=now
        if point is None:
            self.points.clear();self.clicks.clear();self.point=None;return False
        if self.point is not None and math.dist(point,self.point)>80:self.points.clear();self.clicks.clear()
        self.point=point;self.points.append([now,*point,0])
        for button in buttons:
            if button in (1,2,3):self.clicks.append([now,*point,button])
        while self.points and self.points[0][0]<now-.5:self.points.popleft()
        while self.clicks and self.clicks[0][0]<now-CLICK_DURATION:self.clicks.popleft()
        return True

class WindowAttributes(C.Structure):
    _fields_=[('x',C.c_int),('y',C.c_int),('width',C.c_int),('height',C.c_int),('border_width',C.c_int),('depth',C.c_int),('visual',C.c_void_p),('root',C.c_ulong),('class_',C.c_int),('bit_gravity',C.c_int),('win_gravity',C.c_int),('backing_store',C.c_int),('backing_planes',C.c_ulong),('backing_pixel',C.c_ulong),('save_under',C.c_int),('colormap',C.c_ulong),('map_installed',C.c_int),('map_state',C.c_int),('all_event_masks',C.c_long),('your_event_mask',C.c_long),('do_not_propagate_mask',C.c_long),('override_redirect',C.c_int),('screen',C.c_void_p)]

class StackEvent(C.Structure):
    _fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),('display',C.c_void_p),('event',C.c_ulong),('window',C.c_ulong)]

class StackWatcher(QObject):
    """Coalesced root structure notifications; raises only our inputless surface."""
    def __init__(self,x,display_name,window):
        super().__init__();self.x=x;self.window=window;self.display=None;self.notifier=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(60);self.timer.timeout.connect(self.raise_surface)
        self.x.XConnectionNumber.argtypes=[C.c_void_p];self.x.XConnectionNumber.restype=C.c_int
        self.x.XSelectInput.argtypes=[C.c_void_p,C.c_ulong,C.c_long];self.x.XRaiseWindow.argtypes=[C.c_void_p,C.c_ulong]
        try:
            self.display=x.XOpenDisplay(display_name.encode())
            if not self.display:raise RuntimeError('No se pudo mantener visible el cursor en vivo')
            root=x.XDefaultRootWindow(self.display);x.XSelectInput(self.display,root,1<<19);x.XFlush(self.display)
            self.notifier=QSocketNotifier(x.XConnectionNumber(self.display),QSocketNotifier.Read,self);self.notifier.activated.connect(self.drain)
        except Exception:self.close();raise
    def changed(self,window):
        if window!=self.window and not self.timer.isActive():self.timer.start()
    def drain(self,*_):
        from ..cursor import Event
        if not self.display:return
        for _ in range(min(128,self.x.XPending(self.display))):
            event=Event();self.x.XNextEvent(self.display,C.byref(event))
            change=C.cast(C.byref(event),C.POINTER(StackEvent)).contents
            if change.type in (19,21,22,26):self.changed(change.window)
        if self.x.XPending(self.display):QTimer.singleShot(0,self,self.drain)
    def raise_surface(self):
        if self.display:self.x.XRaiseWindow(self.display,self.window);self.x.XFlush(self.display)
    def close(self):
        self.timer.stop()
        if self.notifier:self.notifier.setEnabled(False)
        if self.display:self.x.XCloseDisplay(self.display);self.display=None

class NativeSurface:
    """Per-window hints and one balanced hide reference on the private X client."""
    def __init__(self,reader,window):
        self.reader=reader;self.x=reader.x;self.display=reader.display;self.root=reader.root;self.hidden=False;self.closed=False;self.stacking=None
        path=C.util.find_library('Xfixes')
        if not path:raise RuntimeError('Los efectos en vivo necesitan XFixes')
        self.fx=C.CDLL(path)
        self.fx.XFixesQueryExtension.argtypes=[C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_int)]
        self.fx.XFixesQueryVersion.argtypes=[C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_int)]
        event=C.c_int();error=C.c_int();major=C.c_int(4);minor=C.c_int(0)
        if not self.fx.XFixesQueryExtension(self.display,C.byref(event),C.byref(error)) or not self.fx.XFixesQueryVersion(self.display,C.byref(major),C.byref(minor)) or major.value<4:raise RuntimeError('XFixes 4 no está disponible')
        for name in ('XFixesHideCursor','XFixesShowCursor'):getattr(self.fx,name).argtypes=[C.c_void_p,C.c_ulong]
        self.x.XSync.argtypes=[C.c_void_p,C.c_int]
        self.x.XInternAtom.argtypes=[C.c_void_p,C.c_char_p,C.c_int];self.x.XInternAtom.restype=C.c_ulong
        self.x.XGetSelectionOwner.argtypes=[C.c_void_p,C.c_ulong];self.x.XGetSelectionOwner.restype=C.c_ulong
        self.x.XDefaultScreen.argtypes=[C.c_void_p];self.x.XDefaultScreen.restype=C.c_int
        screen=self.x.XDefaultScreen(self.display)
        if not self.x.XGetSelectionOwner(self.display,self.atom('_NET_WM_CM_S'+str(screen))):raise RuntimeError('Los efectos en vivo necesitan un compositor activo')
        self.x.XChangeProperty.argtypes=[C.c_void_p,C.c_ulong,C.c_ulong,C.c_ulong,C.c_int,C.c_int,C.c_void_p,C.c_int]
        self.property(window,'_WYBIE_ACRYLIC',0)
        self.property(window,'_COMPTON_SHADOW',0)
        self.property(window,'_NET_WM_WINDOW_TYPE',self.atom('_NET_WM_WINDOW_TYPE_DOCK'),'ATOM')
        self.fx.XFixesCreateRegion.argtypes=[C.c_void_p,C.c_void_p,C.c_int];self.fx.XFixesCreateRegion.restype=C.c_ulong
        self.fx.XFixesSetWindowShapeRegion.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_int,C.c_ulong]
        self.fx.XFixesDestroyRegion.argtypes=[C.c_void_p,C.c_ulong]
        region=self.fx.XFixesCreateRegion(self.display,None,0)
        self.fx.XFixesSetWindowShapeRegion(self.display,window,2,0,0,region);self.fx.XFixesDestroyRegion(self.display,region)
        self.x.XSync(self.display,False)
        ext=C.CDLL(C.util.find_library('Xext'))
        ext.XShapeGetRectangles.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.POINTER(C.c_int),C.POINTER(C.c_int)];ext.XShapeGetRectangles.restype=C.c_void_p
        count=C.c_int();order=C.c_int();regions=ext.XShapeGetRectangles(self.display,window,2,C.byref(count),C.byref(order))
        self.x.XFree.argtypes=[C.c_void_p]
        if regions:self.x.XFree(regions)
        if count.value:raise RuntimeError('No se pudo permitir clics a través del cursor en vivo')
    def verify_mapped(self,window,rect):
        self.x.XGetWindowAttributes.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(WindowAttributes)]
        attrs=WindowAttributes()
        if not self.x.XGetWindowAttributes(self.display,window,C.byref(attrs)) or attrs.map_state!=2 or attrs.depth!=32 or attrs.border_width or not attrs.override_redirect or (attrs.x,attrs.y,attrs.width,attrs.height)!=tuple(rect):raise RuntimeError('La superficie del cursor no está preparada')
        self.x.XGetInputFocus.argtypes=[C.c_void_p,C.POINTER(C.c_ulong),C.POINTER(C.c_int)]
        focus=C.c_ulong();revert=C.c_int();self.x.XGetInputFocus(self.display,C.byref(focus),C.byref(revert))
        if focus.value==window:raise RuntimeError('El cursor en vivo no debe recibir el foco')
    def atom(self,name):return self.x.XInternAtom(self.display,name.encode(),False)
    def property(self,window,name,value,kind='CARDINAL'):
        number=C.c_ulong(value);self.x.XChangeProperty(self.display,window,self.atom(name),self.atom(kind),32,0,C.byref(number),1)
    def visible_inside(self,inside):
        if self.closed or inside==self.hidden:return
        operation=self.fx.XFixesHideCursor if inside else self.fx.XFixesShowCursor
        operation(self.display,self.root);self.hidden=inside;self.x.XSync(self.display,False)
    def close(self):
        if self.closed:return
        self.visible_inside(False)
        if self.stacking:self.stacking.close()
        self.closed=True

class LiveSurface(QWidget):
    def __init__(self,state):
        super().__init__(None,Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.X11BypassWindowManagerHint|Qt.WindowTransparentForInput|Qt.WindowDoesNotAcceptFocus)
        self.state=state;self.setWindowTitle('Wysun Recorder · Cursor en vivo');self.setAttribute(Qt.WA_TranslucentBackground);self.setAttribute(Qt.WA_TransparentForMouseEvents);self.setAttribute(Qt.WA_ShowWithoutActivating);self.setFocusPolicy(Qt.NoFocus);self.setGeometry(*state.rect)
    def paintEvent(self,event):
        p=QPainter(self);p.setCompositionMode(QPainter.CompositionMode_Source);p.fillRect(self.rect(),Qt.transparent);p.setCompositionMode(QPainter.CompositionMode_SourceOver);p.setRenderHint(QPainter.Antialiasing)
        state=self.state
        if state.point is None:return
        x,y=state.point;e=state.settings;scale=e['size']/32;t=state.now
        def disc(px,py,radius,opacity):
            color=QColor(CURSOR_ACCENT);color.setAlpha(opacity);p.setPen(Qt.NoPen);p.setBrush(color);p.drawEllipse(QPointF(px,py),radius,radius)
        if e['trail']:
            points=list(state.points);previous=state.point
            for n in range(1,7):
                past=point_at(points,t-e['trail_duration']*n/6)
                if past is None or math.dist(past,previous)>80:break
                disc(*past,(7-n*.65)*scale,255-(140+n*16));previous=past
        if e['halo']:disc(x,y,HALO_RADIUS*scale,35)
        if e['clicks']:
            for click in state.clicks:
                progress=(t-click[0])/CLICK_DURATION
                if not 0<=progress<=1 or math.dist((x,y),click[1:3])>80:continue
                disc(*click[1:3],(12+20*progress)*scale,255-round(130+125*progress))
        p.translate(x,y);p.scale(scale,scale);p.setPen(QPen(QColor(CURSOR_OUTLINE),max(1/scale,1.3),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.setBrush(QColor(CURSOR_FILL));p.drawPolygon(QPolygonF([QPointF(px,py) for px,py in CURSOR_ARROW]))


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--display',required=True);parser.add_argument('--rect',required=True);parser.add_argument('--effects',required=True);parser.add_argument('--parent-pid',type=int,required=True);args=parser.parse_args(argv)
    reader=None;native=None;surface=None
    def message(**value):print(json.dumps(value),flush=True)
    try:
        rect=json.loads(args.rect);effects=effect_settings(json.loads(args.effects))
        if not isinstance(rect,list) or len(rect)!=4 or any(type(v) is not int for v in rect) or min(rect[:2])<0 or not all(16<=v<=32768 for v in rect[2:]) or not effects:raise ValueError('Configuración del cursor en vivo inválida')
        if args.parent_pid<=1 or os.getppid()!=args.parent_pid:raise ValueError('El grabador ya no está disponible')
        if os.environ.get('QT_QPA_PLATFORM','xcb')!='xcb':raise ValueError('Los efectos en vivo requieren una sesión X11')
        os.environ['DISPLAY']=args.display;app=QApplication([]);app.setQuitOnLastWindowClosed(False)
        reader=PointerReader(args.display);state=LiveState(rect,effects);surface=LiveSurface(state)
        native=NativeSurface(reader,int(surface.winId()));surface.show();native.stacking=StackWatcher(reader.x,args.display,int(surface.winId()));native.stacking.raise_surface()
        # Never subscribe to keyboard events or persist pointer positions.
        reader.clicks();timer=QTimer();timer.setInterval(16)
        def sample():
            inside=state.sample(time.monotonic(),reader.position(),reader.clicks());native.visible_inside(inside);surface.update()
        sample()
        def tick():
            try:
                if os.getppid()!=args.parent_pid:app.quit();return
                sample()
            except Exception as exc:timer.stop();message(error=str(exc));app.exit(1)
        timer.timeout.connect(tick);timer.start()
        notifier=QSocketNotifier(sys.stdin.fileno(),QSocketNotifier.Read)
        def input_ready(*_):
            if not os.read(sys.stdin.fileno(),4096):notifier.setEnabled(False);app.quit()
        notifier.activated.connect(input_ready)
        for signum in (signal.SIGTERM,signal.SIGINT):signal.signal(signum,lambda *_:app.quit())
        def ready():
            try:
                if os.getppid()!=args.parent_pid:app.quit();return
                native.verify_mapped(int(surface.winId()),rect);message(ready=True)
            except Exception as exc:message(error=str(exc));app.exit(1)
        QTimer.singleShot(120,ready)
        return app.exec()
    except Exception as exc:message(error=str(exc));return 1
    finally:
        if native:native.close()
        if reader:reader.close()
        if surface:surface.close()

if __name__=='__main__':raise SystemExit(main())
