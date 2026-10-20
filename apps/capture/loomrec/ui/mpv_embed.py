"""Native Qt video surface using the public libmpv software render API.

Reference: mpv-player/mpv include/mpv/render.h (SW_SIZE=17, SW_FORMAT=18,
SW_STRIDE=19, SW_POINTER=20). No foreign window IDs, X11 or QtMultimedia.
The identical distribution copy in loomrec/ui keeps both apps self-contained.
"""
import ctypes as C
import ctypes.util
import locale
import os
import threading
from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtWidgets import QWidget


class Param(C.Structure):
    _fields_=[('type',C.c_int),('data',C.c_void_p)]


def normalize_numeric_locale():
    """libmpv refuses mpv_create unless LC_NUMERIC is C."""
    try:locale.setlocale(locale.LC_NUMERIC,'C')
    except locale.Error:pass


def library():
    name=os.environ.get('WYSUN_LIBMPV') or ctypes.util.find_library('mpv')
    try:lib=C.CDLL(name or 'libmpv.so.2')
    except OSError as exc:raise RuntimeError('Falta libmpv2 para la reproducción embebida Wayland') from exc
    declarations={
        'mpv_create':([],C.c_void_p),
        'mpv_set_option_string':([C.c_void_p,C.c_char_p,C.c_char_p],C.c_int),
        'mpv_initialize':([C.c_void_p],C.c_int),
        'mpv_terminate_destroy':([C.c_void_p],None),
        'mpv_render_context_create':([C.POINTER(C.c_void_p),C.c_void_p,C.POINTER(Param)],C.c_int),
        'mpv_render_context_update':([C.c_void_p],C.c_uint64),
        'mpv_render_context_render':([C.c_void_p,C.POINTER(Param)],C.c_int),
        'mpv_render_context_free':([C.c_void_p],None),
        'mpv_render_context_set_update_callback':([C.c_void_p,C.c_void_p,C.c_void_p],None),
    }
    for name,(args,result) in declarations.items():
        fn=getattr(lib,name);fn.argtypes=args;fn.restype=result
    return lib


def sw_frame(lib,context,width,height):
    """Aligned buffer lifetime covers render; the emitted QImage owns its bytes."""
    width=max(1,min(4096,int(width)));height=max(1,min(4096,int(height)))
    stride=(width*4+63)//64*64
    allocation=C.create_string_buffer(stride*height+63)
    address=(C.addressof(allocation)+63)&~63
    size=(C.c_int*2)(width,height);line=C.c_size_t(stride);fmt=C.create_string_buffer(b'rgb0')
    params=(Param*5)(Param(17,C.cast(size,C.c_void_p)),Param(18,C.cast(fmt,C.c_void_p)),
                     Param(19,C.cast(C.pointer(line),C.c_void_p)),Param(20,address),Param(0,None))
    rc=lib.mpv_render_context_render(context,params)
    if rc<0:raise RuntimeError('libmpv no pudo dibujar el fotograma ('+str(rc)+')')
    view=(C.c_ubyte*(stride*height)).from_address(address)
    # libmpv leaves the padding byte of rgb0 at 0. Qt may blit RGBX bytes
    # verbatim, and the compositor then blends a "transparent" video with the
    # desktop behind the window. Normalise every frame to opaque RGB32.
    return QImage(memoryview(view),width,height,stride,QImage.Format_RGBX8888).convertToFormat(QImage.Format_RGB32)


class MpvSurface(QWidget):
    frameReady=Signal()
    failed=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.image=QImage();self.handle=None;self.lib=None;self.thread=None
        self._stop=threading.Event();self._update=threading.Event();self._ready=threading.Event();self._size=(640,360);self.start_error='';self._hidden=True;self._latest=QImage();self._frame_pending=False
        self.frameReady.connect(self._frame);self.setMinimumSize(160,90)
    def _frame(self):self.image=self._latest;self._frame_pending=False;self.update()
    def resizeEvent(self,event):
        ratio=self.devicePixelRatioF();self._size=(max(1,round(self.width()*ratio)),max(1,round(self.height()*ratio)))
        self._update.set();super().resizeEvent(event)
    def showEvent(self,event):
        self._hidden=False;self._update.set();super().showEvent(event)
    def hideEvent(self,event):
        self._hidden=True;super().hideEvent(event)
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor('#090A0E'))
        if not self.image.isNull():painter.drawImage(self.rect(),self.image)
    def start(self,path,ipc,options=None):
        normalize_numeric_locale()
        self.stop();self.lib=library();self.handle=self.lib.mpv_create()
        if not self.handle:raise RuntimeError('No se pudo crear libmpv')
        self._stop.clear();self._update.clear();self._ready.clear();self.start_error=''
        settings={'config':'no','terminal':'no','load-scripts':'no','ytdl':'no',
                  'access-references':'no','audio-file-auto':'no','sub-auto':'no','input-default-bindings':'no',
                  'input-vo-keyboard':'no','osc':'no','idle':'yes','keep-open':'yes','pause':'yes',
                  'vo':'libmpv','hwdec':'no','vd-lavc-threads':'2','input-ipc-server':str(ipc)}
        settings.update(options or {})
        try:
            for key,value in settings.items():
                if self.lib.mpv_set_option_string(self.handle,key.encode(),str(value).encode())<0:raise RuntimeError('Opción libmpv no disponible: '+key)
            if self.lib.mpv_initialize(self.handle)<0:raise RuntimeError('No se pudo iniciar libmpv')
            self.thread=threading.Thread(target=self._render,name='wysun-mpv-render',daemon=True);self.thread.start()
            if not self._ready.wait(5):raise RuntimeError('No se pudo iniciar el renderizador libmpv')
            if self.start_error:raise RuntimeError(self.start_error)
            # Load through the same private JSON IPC used by existing controls.
            import json,socket,time
            deadline=time.monotonic()+2
            while True:
                try:
                    with socket.socket(socket.AF_UNIX) as client:
                        client.settimeout(.2);client.connect(str(ipc));client.sendall((json.dumps({'command':['loadfile',str(path),'replace']})+'\n').encode())
                    break
                except (FileNotFoundError,ConnectionRefusedError):
                    if time.monotonic()>=deadline:raise RuntimeError('libmpv no abrió su socket de control')
                    self._stop.wait(.01)
        except BaseException:self.stop();raise
    def _render(self):
        context=C.c_void_p()
        callback_type=C.CFUNCTYPE(None,C.c_void_p)
        callback=callback_type(lambda _:self._update.set())
        try:
            api=C.create_string_buffer(b'sw');params=(Param*2)(Param(1,C.cast(api,C.c_void_p)),Param(0,None))
            rc=self.lib.mpv_render_context_create(C.byref(context),self.handle,params)
            if rc<0:raise RuntimeError('libmpv no admite render SW ('+str(rc)+')')
            self.lib.mpv_render_context_set_update_callback(context,C.cast(callback,C.c_void_p),None)
            self._ready.set();self._update.set()
            while not self._stop.is_set():
                if not self._update.wait(.2):continue
                self._update.clear()
                self.lib.mpv_render_context_update(context)
                if self._hidden:
                    skip=C.c_int(1);params=(Param*2)(Param(13,C.cast(C.pointer(skip),C.c_void_p)),Param(0,None))
                    self.lib.mpv_render_context_render(context,params);continue
                image=sw_frame(self.lib,context,*self._size)
                if not self._stop.is_set():
                    self._latest=image
                    if not self._frame_pending:self._frame_pending=True;self.frameReady.emit()
        except Exception as exc:
            self.start_error=str(exc);self._ready.set();self.failed.emit(str(exc))
        finally:
            if context:
                self.lib.mpv_render_context_set_update_callback(context,None,None)
                self.lib.mpv_render_context_free(context)
    def stop(self):
        self._stop.set();self._update.set()
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():raise RuntimeError('El renderizador sigue finalizando; no se destruye su contexto activo')
            self.thread=None
        if self.handle:
            self.lib.mpv_terminate_destroy(self.handle);self.handle=None
        self.image=QImage();self._latest=QImage();self._frame_pending=False;self.update()
