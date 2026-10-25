"""Video surfaces: an OpenGL widget fed by libmpv's render API, and a bounded software fallback.

Both expose ``attach(session)``, ``release()``, the ``ready``/``failed`` signals and a
``renderer`` name. mpv wakes the owner through the session's pipe, never by calling Qt
from its own threads; frames are drawn only while the widget is visible.
"""
import ctypes as C
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

from . import mpv

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
except ImportError:                     # python3-pyside6.qtopenglwidgets is not installed
    QOpenGLWidget = None


def gl_available():
    return QOpenGLWidget is not None


def _void(pointer):
    return C.cast(C.pointer(pointer), C.c_void_p)


if QOpenGLWidget is not None:
    class GLVideoView(QOpenGLWidget):
        """libmpv draws straight into the widget's framebuffer; decoding stays on mpv's threads."""

        ready = Signal()
        failed = Signal(str)
        renderer = 'opengl'

        def __init__(self, parent=None):
            super().__init__(parent)
            self.session = None
            self._context = None
            self._update_callback = None
            self._proc = None
            self._initialized = False
            self.setMinimumSize(160, 90)
            self.setUpdateBehavior(QOpenGLWidget.NoPartialUpdate)

        def attach(self, session):
            self.session = session
            session.render_hook = self._request_frame
            if self._initialized:
                self._create_context()

        # ---------------------------------------------------------- GL events
        def initializeGL(self):
            self._initialized = True
            self.context().aboutToBeDestroyed.connect(self._lost)
            if self.session is not None:
                self._create_context()

        def _create_context(self):
            if self._context is not None or self.session is None:
                return
            try:
                core = self.session.ensure_core()
                self.makeCurrent()
                gl = self.context()

                def resolve(_data, name):
                    address = gl.getProcAddress(name)
                    return int(address) if address else None

                self._proc = mpv.GET_PROC(resolve)
                init = mpv.GLInit(C.cast(self._proc, C.c_void_p), None)
                self._context = core.render_context('opengl', [mpv.Param(mpv.RP_OPENGL_INIT, _void(init))])
                self._update_callback = mpv.WAKEUP(lambda _: core.poke(b'r'))
                core.lib.mpv_render_context_set_update_callback(self._context, self._update_callback, None)
            except Exception as error:      # MediaError or RuntimeError: report, let the owner fall back
                self._context = None
                self.failed.emit(str(error))
                return
            finally:
                self.doneCurrent()
            self.ready.emit()

        def paintGL(self):
            if self._context is None or self.session is None or self.session.core is None:
                return
            lib = self.session.core.lib
            updates = lib.mpv_render_context_update(self._context)
            ratio = self.devicePixelRatioF()
            target = mpv.GLFbo(self.defaultFramebufferObject(), max(1, round(self.width() * ratio)),
                                max(1, round(self.height() * ratio)), 0)
            flip = C.c_int(1)
            params = (mpv.Param * 3)(mpv.Param(mpv.RP_OPENGL_FBO, _void(target)), mpv.Param(mpv.RP_FLIP_Y, _void(flip)),
                                     mpv.Param(0, None))
            lib.mpv_render_context_render(self._context, params)
            lib.mpv_render_context_report_swap(self._context)
            return updates

        def _request_frame(self):
            """mpv has a new frame (called on the GUI thread through the session's pipe)."""
            if self._context is None:
                return
            if self.isVisible():
                self.update()
                return
            lib = self.session.core.lib      # nothing to show: tell mpv to drop the frame instead of queueing it
            lib.mpv_render_context_update(self._context)
            skip = C.c_int(1)
            params = (mpv.Param * 2)(mpv.Param(mpv.RP_SKIP_RENDERING, _void(skip)), mpv.Param(0, None))
            lib.mpv_render_context_render(self._context, params)

        # -------------------------------------------------------------- teardown
        def _lost(self):
            """The GL context is going away (window recreated or screen change): drop mpv's side of it."""
            self.release()
            if self.session is not None and self.session.core is not None:
                self.session.set_surface_ready(False)

        def release(self):
            if self._context is None:
                return
            context, self._context = self._context, None
            lib = self.session.core.lib if self.session and self.session.core else mpv.library()
            self.makeCurrent()
            try:
                lib.mpv_render_context_set_update_callback(context, mpv.WAKEUP(), None)
                lib.mpv_render_context_free(context)
            finally:
                self.doneCurrent()
            self._update_callback = None
            self._proc = None
else:
    GLVideoView = None


class SoftwareVideoView(QWidget):
    """Frames rendered by mpv into memory on a worker thread, painted as one bounded QImage."""

    ready = Signal()
    failed = Signal(str)
    frameReady = Signal()
    renderer = 'software'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = None
        self._image = QImage()
        self._latest = QImage()
        self._pending = False
        self._size = (640, 360)
        self._visible = False
        self._thread = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self.frameReady.connect(self._show_frame)
        self.setMinimumSize(160, 90)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def attach(self, session):
        self.session = session
        core = session.ensure_core()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(core,), name='wysun-mpv-render', daemon=True)
        self._thread.start()

    def _show_frame(self):
        self._image, self._pending = self._latest, False
        self.update()

    def resizeEvent(self, event):
        ratio = self.devicePixelRatioF()
        self._size = (max(1, round(self.width() * ratio)), max(1, round(self.height() * ratio)))
        self._wake.set()
        super().resizeEvent(event)

    def showEvent(self, event):
        self._visible = True
        self._wake.set()
        super().showEvent(event)

    def hideEvent(self, event):
        self._visible = False
        super().hideEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#000000'))  # theme-exception: lienzo negro de vídeo
        if not self._image.isNull():
            painter.drawImage(self.rect(), self._image)

    def _run(self, core):
        lib = core.lib
        callback = mpv.WAKEUP(lambda _: self._wake.set())
        context = None
        try:
            context = core.render_context('sw')
            lib.mpv_render_context_set_update_callback(context, callback, None)
            self.ready.emit()
            while not self._stop.is_set():
                if not self._wake.wait(.25):
                    continue
                self._wake.clear()
                lib.mpv_render_context_update(context)
                if not self._visible:
                    skip = C.c_int(1)
                    params = (mpv.Param * 2)(mpv.Param(mpv.RP_SKIP_RENDERING, _void(skip)), mpv.Param(0, None))
                    lib.mpv_render_context_render(context, params)
                    continue
                image = self._frame(lib, context, *self._size)
                if not self._stop.is_set():
                    self._latest = image
                    if not self._pending:
                        self._pending = True
                        self.frameReady.emit()
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            if context is not None:
                lib.mpv_render_context_set_update_callback(context, mpv.WAKEUP(), None)
                lib.mpv_render_context_free(context)

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
        # With a real alpha channel mpv writes 255 for video, so the frame is opaque on any
        # compositor; a padding byte (bgr0) would be blitted verbatim as transparent.
        return QImage(memoryview(view), width, height, stride, QImage.Format_ARGB32_Premultiplied).copy()

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


def make_view(parent=None, prefer='auto'):
    """OpenGL when available (and not disabled), otherwise the software surface."""
    if prefer != 'software' and GLVideoView is not None:
        return GLVideoView(parent)
    return SoftwareVideoView(parent)
