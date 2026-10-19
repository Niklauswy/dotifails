"""Opt-in cursor telemetry and vector video effects; never a desktop overlay.

Only pointer positions and button presses 1..3 inside the selected rectangle are
persisted, with timestamps relative to the same epoch as the segment encoder.
"""
import bisect
import ctypes as C
import ctypes.util
import json
import math
from pathlib import Path
import subprocess
import threading
import time

CURSOR_ARROW=((0,0),(0,27),(7,20),(13,31),(18,28),(12,17),(22,17))
CURSOR_FILL='#FCFDFF'
CURSOR_OUTLINE='#26384C'
CURSOR_ACCENT='#2165D5'
HALO_RADIUS=23
CLICK_DURATION=.40


def effect_settings(value):
    if not isinstance(value,dict):raise ValueError('Cursor effects must be an object')
    if set(value)-{'preset','size','halo','clicks','trail','trail_duration'}:raise ValueError('Unknown cursor option')
    preset=value.get('preset','simple')
    if preset not in ('simple','presentation','trail'):raise ValueError('Unknown cursor preset')
    defaults=dict(preset=preset,size=32,halo=True,clicks=True,trail=preset=='trail',trail_duration=.20)
    defaults.update(value)
    if type(defaults['size']) is not int or not 16<=defaults['size']<=64:raise ValueError('Cursor size must be 16–64 pixels')
    if any(type(defaults[k]) is not bool for k in ('halo','clicks','trail')):raise ValueError('Cursor effects require booleans')
    duration=defaults['trail_duration']
    if type(duration) not in (int,float) or not math.isfinite(duration) or not .10<=duration<=.40:raise ValueError('Trail duration must be 0.10–0.40 seconds')
    return {} if preset=='simple' else defaults


def check_available():
    if not C.util.find_library('X11') or not C.util.find_library('Xi'):
        raise ValueError('Los efectos del cursor necesitan X11 y XInput2. Usa Sencillo para el cursor nativo.')
    result=subprocess.run(['ffmpeg','-hide_banner','-filters'],capture_output=True,text=True,timeout=10)
    if result.returncode or not any(line.split()[1:2]==['ass'] for line in result.stdout.splitlines()):
        raise ValueError('Los efectos del cursor necesitan FFmpeg con libass. Usa Sencillo para el cursor nativo.')


def local_point(rect,x,y):
    left,top,width,height=rect
    return (x-left,y-top) if left<=x<left+width and top<=y<top+height else None


class Cookie(C.Structure):
    _fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),('display',C.c_void_p),('extension',C.c_int),('evtype',C.c_int),('cookie',C.c_uint),('data',C.c_void_p)]
class Event(C.Union):_fields_=[('cookie',Cookie),('pad',C.c_long*24)]
class RawButton(C.Structure):
    # Only this prefix is read; no valuators or keyboard/modifier fields.
    _fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),('display',C.c_void_p),('extension',C.c_int),('evtype',C.c_int),('time',C.c_ulong),('deviceid',C.c_int),('sourceid',C.c_int),('detail',C.c_int)]
class EventMask(C.Structure):_fields_=[('deviceid',C.c_int),('mask_len',C.c_int),('mask',C.POINTER(C.c_ubyte))]


class PointerReader:
    """Private X connection, subscribed only to XI2 raw mouse-button presses."""
    def __init__(self,display):
        self.x=C.CDLL(C.util.find_library('X11'));self.xi=C.CDLL(C.util.find_library('Xi'));self.display=None
        for name,args,restype in [
            ('XOpenDisplay',[C.c_char_p],C.c_void_p),('XCloseDisplay',[C.c_void_p],C.c_int),
            ('XDefaultRootWindow',[C.c_void_p],C.c_ulong),('XQueryExtension',[C.c_void_p,C.c_char_p,C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int)],C.c_int),
            ('XQueryPointer',[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_uint)],C.c_int),
            ('XPending',[C.c_void_p],C.c_int),('XNextEvent',[C.c_void_p,C.POINTER(Event)],C.c_int),
            ('XGetEventData',[C.c_void_p,C.POINTER(Cookie)],C.c_int),('XFreeEventData',[C.c_void_p,C.POINTER(Cookie)],None),('XFlush',[C.c_void_p],C.c_int)]:
            fn=getattr(self.x,name);fn.argtypes=args;fn.restype=restype
        try:
            self.display=self.x.XOpenDisplay(display.encode())
            if not self.display:raise ValueError('No se pudo conectar a X11 para los efectos del cursor')
            self.root=self.x.XDefaultRootWindow(self.display);opcode=C.c_int();event=C.c_int();error=C.c_int()
            if not self.x.XQueryExtension(self.display,b'XInputExtension',C.byref(opcode),C.byref(event),C.byref(error)):raise ValueError('XInput2 no disponible')
            self.opcode=opcode.value
            self.xi.XIQueryVersion.argtypes=[C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_int)];major=C.c_int(2);minor=C.c_int(0)
            if self.xi.XIQueryVersion(self.display,C.byref(major),C.byref(minor))!=0:raise ValueError('XInput2 no disponible')
            self.xi.XISelectEvents.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(EventMask),C.c_int]
            mask=(C.c_ubyte*2)(0,128) # XI_RawButtonPress=15; NO key/motion event subscription.
            selection=EventMask(1,2,mask) # XIAllMasterDevices
            if self.xi.XISelectEvents(self.display,self.root,C.byref(selection),1)!=0:raise ValueError('No se pudo observar clics XInput2')
            self.x.XFlush(self.display)
        except Exception:self.close();raise
    def position(self):
        root=C.c_ulong();child=C.c_ulong();rx=C.c_int();ry=C.c_int();wx=C.c_int();wy=C.c_int();mask=C.c_uint()
        ok=self.x.XQueryPointer(self.display,self.root,C.byref(root),C.byref(child),C.byref(rx),C.byref(ry),C.byref(wx),C.byref(wy),C.byref(mask))
        # The returned modifier mask is deliberately neither read nor persisted.
        return (rx.value,ry.value) if ok else None
    def clicks(self):
        result=[]
        for _ in range(min(256,self.x.XPending(self.display))):
            event=Event();self.x.XNextEvent(self.display,C.byref(event));cookie=event.cookie
            if cookie.type!=35 or cookie.extension!=self.opcode or cookie.evtype!=15:continue
            if self.x.XGetEventData(self.display,C.byref(cookie)):
                try:
                    button=C.cast(cookie.data,C.POINTER(RawButton)).contents.detail
                    if button in (1,2,3):result.append(button)
                finally:self.x.XFreeEventData(self.display,C.byref(cookie))
        return result
    def close(self):
        if self.display:self.x.XCloseDisplay(self.display);self.display=None


class CursorRecorder:
    """One bounded sampler per active segment, with incremental local JSONL writes."""
    def __init__(self,path,display,rect,settings,reader=None,native_cursor=False):
        self.native_cursor=native_cursor
        self.reader=reader if reader is not None else PointerReader(display);self.path=Path(path);self.rect=tuple(rect);self.settings=effect_settings(settings)
        self.stop_event=threading.Event();self.thread=None;self.error=None;self.count=0
    def start(self,origin):
        self.reader.clicks() # Discard any events queued during encoder setup.
        self.origin=origin;self.thread=threading.Thread(target=self._run,name='wybie-cursor',daemon=True);self.thread.start()
    def _run(self):
        try:
            with self.path.open('x',buffering=1) as out:
                out.write(json.dumps(dict(version=1,width=self.rect[2],height=self.rect[3],settings=self.settings,native_cursor_embedded=self.native_cursor,origin=self.origin))+'\n')
                last=None;last_time=-1.;was_inside=False
                while not self.stop_event.is_set():
                    if self.count>=1_000_000:raise RuntimeError('Límite de datos del cursor alcanzado; el vídeo sigue grabándose')
                    position=self.reader.position();point=local_point(self.rect,*position) if position else None
                    clicks=self.reader.clicks();now=max(0.,time.time()-self.origin)
                    if point:
                        if point!=last or now-last_time>=.25 or clicks:
                            out.write(json.dumps([round(now,6),*point,0])+'\n');self.count+=1;last_time=now
                        for button in clicks:
                            out.write(json.dumps([round(now,6),*point,button])+'\n');self.count+=1
                        was_inside=True
                    elif was_inside:
                        out.write(json.dumps([round(now,6),None,None,0])+'\n');self.count+=1;was_inside=False
                    last=point
                    self.stop_event.wait(1/60)
                out.write(json.dumps([round(max(0.,time.time()-self.origin),6),None,None,0])+'\n')
        except Exception as exc:self.error=str(exc)
        finally:self.reader.close()
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=2)
        else:self.reader.close()


def load_trace(path):
    """Strict, size-bounded local input; incomplete final JSONL line is recoverable."""
    if Path(path).stat().st_size>64*1024*1024:raise ValueError('Cursor trace exceeds 64 MiB')
    with Path(path).open() as stream:
        header=json.loads(stream.readline());effect_settings(header.get('settings',{}))
        w,h=header.get('width'),header.get('height')
        if header.get('version')!=1 or type(w) is not int or type(h) is not int or not 16<=w<=32768 or not 16<=h<=32768:raise ValueError('Invalid cursor trace header')
        points=[];clicks=[];last=-1.
        for line in stream:
            try:event=json.loads(line)
            except ValueError:
                if not line.endswith('\n'):break
                raise
            if not isinstance(event,list) or len(event)!=4:raise ValueError('Invalid cursor event')
            t,x,y,button=event
            if type(t) not in (int,float) or not math.isfinite(t) or not last<=t<=7*24*3600:raise ValueError('Invalid cursor time')
            if type(button) is not int or button not in (0,1,2,3):raise ValueError('Invalid cursor button')
            if x is None and y is None and button==0:pass
            elif type(x) is not int or type(y) is not int or not 0<=x<w or not 0<=y<h:raise ValueError('Cursor outside capture area')
            if button:clicks.append(event)
            else:points.append(event)
            last=t
    return header,points,clicks


def point_at(points,t):
    """Hold/interpolate locally; never draw a bridge over exits or large jumps."""
    index=bisect.bisect_right(points,t,key=lambda p:p[0])-1
    if index<0 or points[index][1] is None:return None
    before=points[index];x,y=before[1:3]
    if index+1<len(points):
        after=points[index+1];gap=after[0]-before[0]
        if after[1] is not None and 0<gap<=.10 and math.hypot(after[1]-x,after[2]-y)<=80:
            f=(t-before[0])/gap;x+=(after[1]-x)*f;y+=(after[2]-y)*f
    return x,y


def _stamp(t):
    ticks=max(0,round(t*100));return f'{ticks//360000}:{ticks//6000%60:02}:{ticks//100%60:02}.{ticks%100:02}'
def _color(hexcolor):return hexcolor[5:7]+hexcolor[3:5]+hexcolor[1:3]
def _circle(radius):
    return 'm '+' l '.join(f'{radius+radius*math.cos(i*math.tau/32):.2f} {radius+radius*math.sin(i*math.tau/32):.2f}' for i in range(32))+' c'


def write_ass(trace_path,output,clip_start,clip_end,settings,cancel=None):
    header,points,clicks=load_trace(trace_path);settings=effect_settings(settings)
    if not settings:return False
    width,height=header['width'],header['height'];scale=settings['size']/32
    with Path(output).open('w') as out:
        out.write(f'[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,DejaVu Sans,16,&H00FFFFFF,&H00FFFFFF,&H004C3826,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n')
        def draw(start,end,x,y,path,color,alpha=0,border=0):
            tags=f'\\an7\\pos({x:.2f},{y:.2f})\\p1\\bord{border:.2f}\\shad0\\1c&H{_color(color)}&\\1a&H{alpha:02X}&\\3c&H{_color(CURSOR_OUTLINE)}&'
            out.write(f'Dialogue: 0,{_stamp(start)},{_stamp(end)},Default,,0,0,0,,{{{tags}}}{path}\n')
        def disc(start,end,x,y,radius,alpha):
            draw(start,end,x-radius,y-radius,_circle(radius),CURSOR_ACCENT,alpha)
        frames=math.ceil((clip_end-clip_start)*30)
        for frame in range(frames):
            if cancel and cancel.is_set():raise InterruptedError('Export cancelled')
            start=frame/30;end=min((frame+1)/30,clip_end-clip_start);t=clip_start+start
            point=point_at(points,t)
            if point is None:continue
            x,y=point
            if settings['trail']:
                # Discrete fading dots, no connecting lines or cross-gap streaks.
                previous=point
                for n in range(1,7):
                    past=point_at(points,t-settings['trail_duration']*n/6)
                    if past is None or math.dist(past,previous)>80:break
                    disc(start,end,*past,(7-n*.65)*scale,140+n*16);previous=past
            if settings['halo']:disc(start,end,x,y,HALO_RADIUS*scale,220)
            if settings['clicks']:
                first=bisect.bisect_left(clicks,max(clip_start,t-CLICK_DURATION),key=lambda p:p[0])
                stop=bisect.bisect_right(clicks,t,key=lambda p:p[0])
                for click in clicks[first:stop]:
                    progress=(t-click[0])/CLICK_DURATION
                    if math.dist((x,y),click[1:3])>80:continue
                    # A translucent expanding disk gives a soft pulse without screen overlays.
                    disc(start,end,*click[1:3],(12+20*progress)*scale,round(130+125*progress))
            arrow='m '+' l '.join(f'{px*scale:.2f} {py*scale:.2f}' for px,py in CURSOR_ARROW)+' c'
            if not header.get('native_cursor_embedded',False):draw(start,end,x,y,arrow,CURSOR_FILL,border=max(1,1.3*scale))
    return True
