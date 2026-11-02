"""libmpv video inside a QML scene: an OpenGL item (QQuickFramebufferObject) and a software fallback.

Both take a ``session`` (wysun_media.session.MediaSession). mpv wakes the owner through the session's pipe, never by
calling Qt from its own threads; the item then schedules a frame. The Player runs the basic render loop
(``QSG_RENDER_LOOP=basic``): rendering happens on the GUI thread, so Python never runs on a render thread that the GUI
thread waits for while holding the GIL, and the item can make the scene's GL context current to free mpv's context
before the core goes away (mpv blocks destroying a core whose render context is alive).
"""
import ctypes as C
import os
import threading

from PySide6.QtCore import Property, QObject, QRectF, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QImage, QOpenGLContext
from PySide6.QtQuick import QQuickFramebufferObject, QQuickPaintedItem, QQuickWindow, QSGRendererInterface

from wysun_media import mpv

URI = 'Wysun.Player'


def _void(pointer):
    return C.cast(C.pointer(pointer), C.c_void_p)


def renderer_name(window=None):
    """'software' when asked (WYSUN_PLAYER_RENDERER) or when the scene graph does not draw with OpenGL."""
    if os.environ.get('WYSUN_PLAYER_RENDERER') == 'software':
        return 'software'
    api = window.rendererInterface().graphicsApi() if window is not None else QQuickWindow.graphicsApi()
    return 'opengl' if api == QSGRendererInterface.GraphicsApi.OpenGL else 'software'


class _GLRenderer(QQuickFramebufferObject.Renderer):
    """Lives as long as the item's scene-graph node; draws mpv's current frame into the item's framebuffer."""

    def __init__(self, item):
        super().__init__()
        self.item = item
        item._renderer = self

    def render(self):
        self.item._render(self.framebufferObject())


class MpvVideo(QQuickFramebufferObject):
    failed = Signal(str)
    sessionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session = None
        self._context = None          # mpv_render_context
        self._gl = None               # (QOpenGLContext, QSurface) the context was created in
        self._proc = self._update_callback = None
        self._renderer = None
        self._broken = False
        self.setMirrorVertically(False)

    # ---------------------------------------------------------------- session
    def _get_session(self):
        return self._session

    def _set_session(self, session):
        if session is self._session:
            return
        self.release()
        self._session = session
        if session is not None:
            session.render_hook = self._frame_ready
            self.update()
        self.sessionChanged.emit()

    session = Property(QObject, _get_session, _set_session, notify=sessionChanged)

    def createRenderer(self):
        return _GLRenderer(self)

    # ---------------------------------------------------------------- frames
    def _render(self, fbo):
        session = self._session
        if session is None or session.core is None or self._broken:
            return
        if self._context is None and not self._create(session):
            return
        lib = session.core.lib
        lib.mpv_render_context_update(self._context)
        target = mpv.GLFbo(fbo.handle(), fbo.width(), fbo.height(), 0)
        flip = C.c_int(0)
        params = (mpv.Param * 3)(mpv.Param(mpv.RP_OPENGL_FBO, _void(target)), mpv.Param(mpv.RP_FLIP_Y, _void(flip)),
                                 mpv.Param(0, None))
        lib.mpv_render_context_render(self._context, params)

    def _create(self, session):
        gl = QOpenGLContext.currentContext()
        if gl is None:
            return False
        try:
            core = session.ensure_core()

            def resolve(_data, name):
                address = gl.getProcAddress(name)
                return int(address) if address else None

            self._proc = mpv.GET_PROC(resolve)
            init = mpv.GLInit(C.cast(self._proc, C.c_void_p), None)
            self._context = core.render_context('opengl', [mpv.Param(mpv.RP_OPENGL_INIT, _void(init))])
            self._update_callback = mpv.WAKEUP(lambda _: core.poke(b'r'))
            core.lib.mpv_render_context_set_update_callback(self._context, self._update_callback, None)
        except Exception as error:                       # MediaError or RuntimeError: the owner falls back
            self._context, self._broken = None, True
            QTimer.singleShot(0, self, lambda: self.failed.emit(str(error)))
            return False
        self._gl = (gl, gl.surface())
        window = self.window()
        if window is not None:
            window.sceneGraphInvalidated.connect(self._lost)
        QTimer.singleShot(0, self, lambda: session.set_surface_ready(True))   # not from inside the render pass
        return True

    def _frame_ready(self):
        """mpv has a new frame (GUI thread, through the session's pipe)."""
        if self._context is None:
            self.update()                                 # the first frame creates the context
            return
        window = self.window()
        if self.isVisible() and window is not None and window.isExposed():
            self.update()
            return
        lib = self._session.core.lib                      # nothing on screen: drop the frame instead of queueing it
        lib.mpv_render_context_update(self._context)
        skip = C.c_int(1)
        params = (mpv.Param * 2)(mpv.Param(mpv.RP_SKIP_RENDERING, _void(skip)), mpv.Param(0, None))
        lib.mpv_render_context_render(self._context, params)

    # ---------------------------------------------------------------- teardown
    def _lost(self):
        """The scene graph is going away (window closing, screen change): its GL context is current here."""
        self._free(current=True)
        if self._session is not None and self._session.core is not None:
            self._session.set_surface_ready(False)

    @Slot()
    def release(self):
        """Free mpv's render context (before the session closes its core). Idempotent."""
        self._free(current=False)

    def _free(self, current):
        if self._context is None:
            return
        context, self._context = self._context, None
        gl, surface = self._gl or (None, None)
        self._gl = None
        session = self._session
        lib = session.core.lib if session is not None and session.core is not None else mpv.library()
        made = False
        if not current and gl is not None and surface is not None:
            made = gl.makeCurrent(surface)
        try:
            lib.mpv_render_context_set_update_callback(context, mpv.WAKEUP(), None)
            lib.mpv_render_context_free(context)
        finally:
            if made:
                gl.doneCurrent()
        self._update_callback = self._proc = None


class _Relay(QObject):
    """Carries the worker's news to the GUI thread and calls the item there.

    The connections are the relay's own: PySide drops connections that an item created by QML makes to its own bound
    methods in ``__init__`` (they are silently never called)."""

    contextReady = Signal()
    frameReady = Signal()
    failed = Signal(str)

    def __init__(self, item):
        super().__init__()
        self.item = item
        self.contextReady.connect(self._context_ready)
        self.frameReady.connect(self._frame_ready)
        self.failed.connect(self._failed)

    @Slot()
    def _context_ready(self):
        self.item._ready()

    @Slot()
    def _frame_ready(self):
        self.item._show_frame()

    @Slot(str)
    def _failed(self, reason):
        self.item.failed.emit(reason)


class MpvSoftwareVideo(QQuickPaintedItem):
    """Frames rendered by mpv into memory on a worker thread, painted as one bounded QImage."""

    failed = Signal(str)
    sessionChanged = Signal()
    framesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session = None
        self._image = QImage()
        self._latest = QImage()
        self._pending = False
        self._size = (640, 360)
        self._thread = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._frames = 0
        self._relay = _Relay(self)
        self.setOpaquePainting(True)
        self.setFillColor(QColor('#000000'))   # theme-exception: lienzo negro de vídeo

    def _get_session(self):
        return self._session

    def _set_session(self, session):
        if session is self._session:
            return
        self.release()
        self._session = session
        if session is not None:
            self._start(session)
        self.sessionChanged.emit()

    session = Property(QObject, _get_session, _set_session, notify=sessionChanged)

    def _get_frames(self):
        return self._frames

    frames = Property(int, _get_frames, notify=framesChanged)

    def _start(self, session):
        try:
            core = session.ensure_core()
        except Exception as error:
            self.failed.emit(str(error))
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(core,), name='wysun-mpv-render', daemon=True)
        self._thread.start()

    def geometryChange(self, new, old):
        super().geometryChange(new, old)
        window = self.window()
        ratio = window.devicePixelRatio() if window is not None else 1.0
        self._size = (max(1, round(new.width() * ratio)), max(1, round(new.height() * ratio)))
        self._wake.set()

    def _show_frame(self):
        self._image, self._pending = self._latest, False
        self._frames += 1
        self.framesChanged.emit()
        self.update()

    def paint(self, painter):
        if not self._image.isNull():
            painter.drawImage(QRectF(0, 0, self.width(), self.height()), self._image)

    def _run(self, core):
        lib = core.lib
        callback = mpv.WAKEUP(lambda _: self._wake.set())
        context = None
        try:
            context = core.render_context('sw')
            lib.mpv_render_context_set_update_callback(context, callback, None)
            self._relay.contextReady.emit()
            while not self._stop.is_set():
                if not self._wake.wait(.25):
                    continue
                self._wake.clear()
                lib.mpv_render_context_update(context)
                if not self._visible_now:
                    skip = C.c_int(1)
                    params = (mpv.Param * 2)(mpv.Param(mpv.RP_SKIP_RENDERING, _void(skip)), mpv.Param(0, None))
                    lib.mpv_render_context_render(context, params)
                    continue
                image = self._frame(lib, context, *self._size)
                if not self._stop.is_set():
                    self._latest = image
                    if not self._pending:
                        self._pending = True
                        self._relay.frameReady.emit()
        except Exception as error:
            self._relay.failed.emit(str(error))
        finally:
            if context is not None:
                lib.mpv_render_context_set_update_callback(context, mpv.WAKEUP(), None)
                lib.mpv_render_context_free(context)

    _visible_now = True               # written on the GUI thread by itemChange; read by the worker

    def itemChange(self, change, value):
        if change == QQuickPaintedItem.ItemVisibleHasChanged:
            self._visible_now = bool(self.isVisible())
            self._wake.set()
        super().itemChange(change, value)

    def _ready(self):
        if self._session is not None and self._session.core is not None:
            self._session.set_surface_ready(True)

    @staticmethod
    def _frame(lib, context, width, height):
        """Render into an aligned buffer; the returned QImage owns a copy of the pixels."""
        width, height = max(1, min(4096, width)), max(1, min(4096, height))
        stride = (width * 4 + 63) // 64 * 64
        buffer = C.create_string_buffer(stride * height + 63)
        address = (C.addressof(buffer) + 63) & ~63
        size = (C.c_int * 2)(width, height)
        line = C.c_size_t(stride)
        fmt = C.create_string_buffer(b'bgra')
        params = (mpv.Param * 5)(mpv.Param(mpv.RP_SW_SIZE, C.cast(size, C.c_void_p)),
                                 mpv.Param(mpv.RP_SW_FORMAT, C.cast(fmt, C.c_void_p)),
                                 mpv.Param(mpv.RP_SW_STRIDE, _void(line)), mpv.Param(mpv.RP_SW_POINTER, address),
                                 mpv.Param(0, None))
        if lib.mpv_render_context_render(context, params) < 0:
            raise RuntimeError('libmpv no pudo dibujar el fotograma')
        view = (C.c_ubyte * (stride * height)).from_address(address)
        # With a real alpha channel mpv writes 255 for video, so the frame is opaque on any compositor.
        return QImage(memoryview(view), width, height, stride, QImage.Format_ARGB32_Premultiplied).copy()

    @Slot()
    def release(self):
        self._stop.set()
        self._wake.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError('El renderizador sigue finalizando; no se destruye su contexto activo')
        self._image = self._latest = QImage()
        self._pending = False


def register():
    from PySide6.QtQml import qmlRegisterType
    qmlRegisterType(MpvVideo, URI, 1, 0, 'MpvVideo')
    qmlRegisterType(MpvSoftwareVideo, URI, 1, 0, 'MpvSoftwareVideo')
