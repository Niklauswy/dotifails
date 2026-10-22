"""Consent-scoped PipeWire frames to FFmpeg, without a screen-grabbing fallback.

The first line is stream geometry; subsequent bytes are tightly packed BGRA.
A bounded GStreamer queue drops old frames instead of growing recorder memory.
"""
import json
import math
import os
import sys
import queue
import signal
import threading
import time


def pixel_crop(width,height,source,rect=None,even=True):
    if rect is None:return [0,0,width//2*2 if even else width,height//2*2 if even else height]
    position=source.get('position');size=source.get('size')
    if not position or not size or min(size)<=0:
        raise ValueError('El portal no describe las coordenadas del monitor. Elige pantalla completa o una región en el selector del portal.')
    x,y,w,h=rect;px,py=position;lw,lh=size
    if x<px or y<py or x+w>px+lw or y+h>py+lh:
        raise ValueError('La región debe estar dentro del monitor autorizado en el portal')
    left=math.floor((x-px)*width/lw);top=math.floor((y-py)*height/lh)
    right=math.ceil((x+w-px)*width/lw);bottom=math.ceil((y+h-py)*height/lh)
    return [left,top,(min(width,right)-left)//2*2,(min(height,bottom)-top)//2*2]


def packed_frame(data,stride,width,height,crop):
    x,y,w,h=crop
    if stride<width*4 or len(data)<stride*height or w<16 or h<16:
        raise ValueError('Fotograma incompleto o región demasiado pequeña')
    view=memoryview(data)
    return b''.join(view[row*stride+x*4:row*stride+(x+w)*4] for row in range(y,y+h))


def source_geometry(width,height,metadata):
    provenance=metadata.get('wysun_output')
    if not provenance:return width,height
    if tuple(provenance['pixels'])!=(width,height):raise RuntimeError('Cambió el tamaño de píxel de la fuente autorizada antes del recorte')
    return (height,width) if provenance['transform']%2 else (width,height)


def source_frame(data,stride,width,height,metadata,crop):
    source_geometry(width,height,metadata)
    transform=metadata.get('wysun_output',{}).get('transform',0)
    if not transform:return packed_frame(data,stride,width,height,crop)
    from PySide6.QtGui import QImage
    from .desktop_capture import orient_frame
    raw=packed_frame(data,stride,width,height,[0,0,width,height])
    image=orient_frame(QImage(raw,width,height,width*4,QImage.Format_ARGB32),transform)
    return packed_frame(image.constBits(),image.bytesPerLine(),image.width(),image.height(),crop)



def configure_pipewire_source(source,fd,node,metadata):
    """Target only the granted remote; prefer its optional stable object serial.

    Version 6 metadata is not assumed. Older backends use the node ID within
    this remote FD, never a connection to the global PipeWire server.
    """
    source.set_property('fd',int(fd));source.set_property('do-timestamp',True)
    # A screen stream must only ever link to the granted node. Without these,
    # a not-yet-ready target lets the session manager fall back to a default
    # one; with audio playing that is an audio stream ("unhandled format").
    try:
        import gi
        gi.require_version('Gst','1.0')
        from gi.repository import Gst
        if not Gst.is_initialized():Gst.init(None)
        source.set_property('stream-properties',Gst.Structure.new_from_string(
            'props,media.type=Video,media.category=Capture,media.role=Screen,node.dont-fallback=true,node.dont-reconnect=true'))
    except Exception:pass
    serial=metadata.get('pipewire-serial')
    if serial is None:source.set_property('path',str(node));return
    if not isinstance(serial,int) or isinstance(serial,bool) or not 0<=serial<2**64:raise ValueError('object.serial PipeWire inválido')
    if not source.find_property('target-object'):raise RuntimeError('Actualiza el plugin PipeWire para usar object.serial')
    source.set_property('target-object',str(serial))


def startup_diagnostic(source,rate,sink):
    """Own-pipeline counters/readback only on failure; never disclose the FD."""
    def value(element,key):
        try:return element.get_property(key)
        except Exception:return None
    fd=value(source,'fd');values=dict(fd_valid=type(fd) is int and fd>=0)
    for key in ('path','target-object'):
        item=value(source,key);values[key]=item[:64] if isinstance(item,str) else None
    auto=value(source,'autoconnect');values['autoconnect']=auto if type(auto) is bool else None
    try:version=source.get_factory().get_plugin().get_version()
    except Exception:version=None
    values['plugin_version']=version[:64] if isinstance(version,str) else None
    values['videorate']={key:item if type(item) is int else None for key in ('in','out','drop','duplicate') for item in [value(rate,key)]}
    stats=value(sink,'stats');values['appsink']={}
    for key in ('rendered','dropped'):
        try:item=stats.get_value(key)
        except Exception:item=None
        values['appsink'][key]=item if type(item) is int else None
    return json.dumps(values,sort_keys=True)


def start_hyprland_pipeline(pipeline,Gst,stopping,*,clock=time.monotonic,pause=time.sleep):
    """Separate negotiation's initial active/cork from the final uncork.

    GstPW 1.4.2 activates while negotiating READY->PAUSED, then corks.
    XDPH may already have copied a frame whose callback that cork cancels.
    Allow Hyprland 0.55's 500 ms sharing latch to retire after this phase,
    rather than timing only the previous remote FD's closure. This is a
    version-specific compatibility barrier, not a provider readiness ack.
    """
    deadline=clock()+5
    def check():
        if stopping():raise InterruptedError('Inicio PipeWire cancelado')
    try:
        check()
        if pipeline.set_state(Gst.State.PAUSED)==Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('PipeWire no pudo negociar en pausa')
        while True:
            check();remaining=deadline-clock()
            if remaining<=0:raise TimeoutError('PipeWire no completó la negociación en 5 segundos')
            result,current,pending=pipeline.get_state(max(1,int(min(.05,remaining)*Gst.SECOND)))
            if result==Gst.StateChangeReturn.FAILURE:raise RuntimeError('Falló la negociación PipeWire')
            if (result in (Gst.StateChangeReturn.SUCCESS,Gst.StateChangeReturn.NO_PREROLL)
                    and current==Gst.State.PAUSED and pending==Gst.State.VOID_PENDING):break
        ready_at=clock()+.65
        while clock()<ready_at:
            check();remaining=ready_at-clock()
            if remaining>0:pause(min(.05,remaining))
        check()
        if pipeline.set_state(Gst.State.PLAYING)==Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('PipeWire no pudo iniciar el vídeo')
    except BaseException:
        # set_state itself is a native library call; the parent's independent
        # startup deadline/terminate/kill also bounds a stuck plugin teardown.
        try:pipeline.set_state(Gst.State.NULL)
        except Exception:pass
        raise


def stream(fd,node,metadata,fps,rect=None,synthetic=False,even=True,cursor_trace_path=None,cursor_effects=None,cursor_marker=None):
    import gi
    gi.require_version('Gst','1.0');gi.require_version('GstVideo','1.0')
    from gi.repository import Gst,GstVideo
    Gst.init(None)
    pipeline=Gst.Pipeline.new('wysun-pipewire')
    src=Gst.ElementFactory.make('videotestsrc' if synthetic else 'pipewiresrc','source')
    if src is None:raise RuntimeError('Falta el plugin GStreamer pipewiresrc (paquete gstreamer1.0-pipewire)')
    if synthetic:src.set_property('is-live',True);src.set_property('num-buffers',12)
    else:configure_pipewire_source(src,fd,node,metadata)
    # Only raw video formats are offered to PipeWire, never audio or DMA-BUF.
    video_only=Gst.ElementFactory.make('capsfilter','video-only');video_only.set_property('caps',Gst.Caps.from_string('video/x-raw'))
    convert=Gst.ElementFactory.make('videoconvert');caps=Gst.ElementFactory.make('capsfilter')
    # No videorate and no framerate in the caps: constraining the rate makes
    # PipeWire 1.4 renegotiate ~1 s after PLAYING and the stream dies with
    # "unhandled format". The compositor's own cadence is kept and this
    # bridge drops/repeats frames to the requested rate below.
    caps.set_property('caps',Gst.Caps.from_string('video/x-raw,format=BGRA'))
    sink=Gst.ElementFactory.make('appsink');sink.set_property('max-buffers',2);sink.set_property('drop',True);sink.set_property('sync',False)
    for item in (src,video_only,convert,caps,sink):
        if item is None:raise RuntimeError('Faltan plugins básicos de vídeo GStreamer')
        pipeline.add(item)
    for a,b in zip((src,video_only,convert,caps),(video_only,convert,caps,sink)):
        if not a.link(b):raise RuntimeError('No se pudo conectar el flujo PipeWire')
    interval=1./int(fps);due=0.
    # FFmpeg may fall behind (high quality, 1080p+). Writing from this loop would
    # hold the PipeWire buffer being copied, starve XDPH ("Out of buffers") and
    # make it renegotiate until the stream dies. A writer thread takes bounded,
    # newest-first frames instead, so buffers are always returned at once.
    pending=queue.Queue(maxsize=2);broken=threading.Event();write_error=[]
    def put(frame):
        try:pending.put_nowait(frame)
        except queue.Full:
            try:pending.get_nowait()
            except queue.Empty:pass
            try:pending.put_nowait(frame)
            except queue.Full:pass
    def write_frames():
        try:
            while True:
                frame=pending.get()
                if frame is None:return
                sys.stdout.buffer.write(frame);sys.stdout.buffer.flush()
        except BaseException as exc:write_error.append(exc);broken.set()
    writer=threading.Thread(target=write_frames,daemon=True)
    held=None
    geometry=None;last_frame=None;bus=pipeline.get_bus();effects=None;stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    previous=signal.signal(signal.SIGTERM,stop)
    try:
        if not synthetic and os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            start_hyprland_pipeline(pipeline,Gst,lambda:stopping)
        elif pipeline.set_state(Gst.State.PLAYING)==Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('No se pudo iniciar el flujo de vídeo')
        writer.start()
        while not stopping:
            if broken.is_set():raise write_error[0]
            wait=Gst.SECOND//int(fps) if last_frame is not None else Gst.SECOND*10
            if held is not None:wait=max(0,int((due-time.monotonic())*Gst.SECOND))
            sample=sink.emit('try-pull-sample',wait)
            if sample is not None and last_frame is not None and time.monotonic()<due:
                held=sample;continue  # too soon for this rate: the newest one is kept for when it is due
            if sample is None and held is not None:
                if time.monotonic()<due-.001:continue
                sample,held=held,None
            elif sample is not None:held=None
            if sample is None:
                message=bus.pop_filtered(Gst.MessageType.ERROR|Gst.MessageType.EOS)
                if message and message.type==Gst.MessageType.EOS:return
                if message:
                    error,debug=message.parse_error();raise RuntimeError(str(error)+(' ['+debug.splitlines()[0]+']' if debug else ''))
                if last_frame is None:
                    raise RuntimeError('PipeWire no entregó el primer fotograma durante 10 segundos. Los segmentos finalizados se conservan; vuelve a seleccionar la fuente. Diagnóstico de inicio: '+startup_diagnostic(src,None,sink))
                due=time.monotonic()+interval
                if pending.empty():put(effects.render(last_frame) if effects else last_frame)
                continue
            info=GstVideo.VideoInfo.new_from_caps(sample.get_caps())
            current=source_geometry(info.width,info.height,metadata)
            if geometry is not None and geometry!=current:raise RuntimeError('La fuente cambió de tamaño; finaliza el segmento y selecciona de nuevo')
            if geometry is None:
                geometry=current;crop=pixel_crop(*geometry,metadata,rect,even=even)
                if cursor_trace_path:
                    from .live_effects import LiveEffects
                    effects=LiveEffects(cursor_trace_path,crop[2],crop[3],cursor_marker,cursor_effects)
                sys.stdout.buffer.write((json.dumps({'width':crop[2],'height':crop[3],'source_size':list(geometry)})+'\n').encode());sys.stdout.buffer.flush()
            buffer=sample.get_buffer();success,mapped=buffer.map(Gst.MapFlags.READ)
            if not success:raise RuntimeError('No se pudo leer un fotograma PipeWire')
            try:frame=source_frame(mapped.data,info.stride[0],info.width,info.height,metadata,crop)
            finally:buffer.unmap(mapped)
            sample=buffer=None  # hand the PipeWire buffer back before the slow part
            last_frame=frame;due=time.monotonic()+interval*.9
            put(effects.render(frame) if effects else frame)
    finally:
        if writer.is_alive():
            put(None);writer.join(2)
        if effects:effects.close()
        pipeline.set_state(Gst.State.NULL);signal.signal(signal.SIGTERM,previous)


if __name__=='__main__':
    try:
        if sys.argv[1:]==['--synthetic']:stream(-1,0,{},12,synthetic=True)
        else:
            values=json.loads(sys.argv[1]);stream(**values)
    except BrokenPipeError:pass
    except Exception as exc:print(str(exc),file=sys.stderr);raise SystemExit(1)
