"""Mouse effects on consented, packed BGRA frames; never draws another cursor.

File access and JSON parsing run only on a bounded follower thread. Rendering
uses a nonblocking snapshot and retains the unmodified frame for repeated frames.
"""
from collections import deque
import json
import math
import os
from pathlib import Path
import stat
import threading
import time
from .cursor import effect_settings, point_at, HALO_RADIUS, CLICK_DURATION, CURSOR_ACCENT
from .schema import atomic_json


class TraceState:
    def __init__(self,width,height):
        self.width=width;self.height=height;self.origin=None;self.last=-1.
        self.points=deque(maxlen=512);self.clicks=deque(maxlen=128)
    def accept(self,value):
        if self.origin is None:
            if not isinstance(value,dict) or value.get('version')!=1 or value.get('width')!=self.width or value.get('height')!=self.height or value.get('native_cursor_embedded') is not True:
                raise ValueError('Cabecera de efectos nativos inválida')
            origin=value.get('origin')
            if type(origin) not in (int,float) or not math.isfinite(origin) or origin<=0:raise ValueError('Origen temporal inválido')
            self.origin=origin;return
        if not isinstance(value,list) or len(value)!=4:raise ValueError('Evento de cursor inválido')
        t,x,y,button=value
        if type(t) not in (int,float) or not math.isfinite(t) or not self.last<=t<=7*24*3600:raise ValueError('Tiempo de cursor inválido')
        if type(button) is not int or button not in (0,1,2,3):raise ValueError('Botón inválido')
        if not (x is None and y is None and button==0):
            if type(x) is not int or type(y) is not int or not 0<=x<self.width or not 0<=y<self.height:raise ValueError('Cursor fuera de la región')
        self.last=t
        (self.clicks if button else self.points).append(value)
    def snapshot(self):return self.origin,tuple(self.points),tuple(self.clicks)


class TraceFollower:
    def __init__(self,path,width,height,marker,settings):
        self.path=Path(path);self.marker=Path(marker);self.settings=settings
        self.state=TraceState(width,height);self.lock=threading.Lock();self.stop=threading.Event();self.error=None
        # Persist before the first painted frame. Exports must never apply a
        # second copy, including if telemetry fails later in this segment.
        atomic_json(self.marker,dict(baked=True,effects=settings,backend='pipewire-bgra'))
        self.thread=threading.Thread(target=self._run,name='wysun-live-effects',daemon=True);self.thread.start()
    def snapshot(self):
        if not self.lock.acquire(blocking=False):return None
        try:return self.state.snapshot()
        finally:self.lock.release()
    def _run(self):
        fd=None;pending=b'';total=0;started=time.monotonic()
        try:
            while not self.stop.is_set():
                if self.error:raise RuntimeError(self.error)
                if fd is None:
                    try:fd=os.open(self.path,os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC|os.O_NOFOLLOW)
                    except FileNotFoundError:
                        if time.monotonic()-started>5:raise RuntimeError('No inició la telemetría del ratón')
                        self.stop.wait(.01);continue
                    info=os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('Traza de ratón no regular o ajena')
                chunk=os.read(fd,65536);total+=len(chunk)
                if total>64*1024*1024:raise ValueError('Traza de ratón excede 64 MiB')
                pending+=chunk
                while b'\n' in pending:
                    line,pending=pending.split(b'\n',1)
                    if len(line)>8192:raise ValueError('Evento demasiado grande')
                    value=json.loads(line)
                    with self.lock:self.state.accept(value)
                if len(pending)>8192:raise ValueError('Evento incompleto demasiado grande')
                self.stop.wait(.01)
        except Exception as exc:
            self.error=str(exc)
            atomic_json(self.marker,dict(baked=True,effects=self.settings,backend='pipewire-bgra',error=self.error))
        finally:
            if fd is not None:os.close(fd)
    def close(self):self.stop.set();self.thread.join(timeout=1)


def paint_frame(frame,width,height,settings,snapshot,now=None):
    """Return packed BGRA; no file access, keyboard data, cursor arrow or GUI."""
    if not snapshot or not any(settings[k] for k in ('halo','clicks','trail')):return frame
    origin,points,clicks=snapshot
    if origin is None or not points:return frame
    t=(time.time() if now is None else now)-origin
    if t<0 or t-points[-1][0]>.5:return frame
    point=point_at(points,t)
    if point is None:return frame
    if len(frame)!=width*height*4:raise ValueError('BGRA debe estar empaquetado')
    from PySide6.QtCore import Qt,QPointF
    from PySide6.QtGui import QImage,QPainter,QColor
    image=QImage(frame,width,height,width*4,QImage.Format_ARGB32).copy()
    painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing);painter.setPen(Qt.NoPen)
    scale=settings['size']/32
    def disc(position,radius,alpha):
        color=QColor(CURSOR_ACCENT);color.setAlpha(max(0,min(255,alpha)))
        painter.setBrush(color);painter.drawEllipse(QPointF(*position),radius,radius)
    if settings['trail']:
        previous=point
        for n in range(1,7):
            past=point_at(points,t-settings['trail_duration']*n/6)
            if past is None or math.dist(past,previous)>80:break
            disc(past,(7-n*.65)*scale,255-(140+n*16));previous=past
    if settings['halo']:disc(point,HALO_RADIUS*scale,35)
    if settings['clicks']:
        for click in clicks:
            age=t-click[0]
            if 0<=age<CLICK_DURATION and math.dist(point,click[1:3])<=80:
                progress=age/CLICK_DURATION
                disc(click[1:3],(12+20*progress)*scale,255-round(130+125*progress))
    painter.end()
    return bytes(image.constBits()[:width*height*4])


class LiveEffects:
    def __init__(self,path,width,height,marker,settings):
        self.settings=effect_settings(settings);self.width=width;self.height=height;self.latest=None
        self.follower=TraceFollower(path,width,height,marker,self.settings)
    def render(self,frame):
        if self.follower.error:return frame
        try:
            snapshot=self.follower.snapshot()
            if snapshot is not None:self.latest=snapshot
            return paint_frame(frame,self.width,self.height,self.settings,self.latest)
        except Exception as exc:
            # The follower persists diagnostics; the video thread never writes files.
            self.follower.error=str(exc);return frame
    def close(self):self.follower.close()
