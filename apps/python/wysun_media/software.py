"""mpv's software renderer on a worker thread, without any toolkit: frames are rendered into memory and handed over.

The owner (a QML item, or a test) supplies callbacks, all called on the worker thread: ``on_ready()`` once the
render context exists, ``on_frame(pixels, width, height, stride)`` for each frame (``pixels`` is a fresh ``bytes``
in premultiplied BGRA, opaque for video), ``on_error(text)``. ``size`` (width, height) and ``visible`` may be changed
from any thread; call ``wake()`` after changing them. While not visible, frames are skipped instead of queued.
"""
import ctypes as C
import threading

from . import mpv

MAX_SIDE = 4096


def _void(pointer):
    return C.cast(C.pointer(pointer), C.c_void_p)


def render(lib, context, width, height):
    """One frame as (bytes, width, height, stride), rendered into an aligned buffer."""
    width, height = max(1, min(MAX_SIDE, width)), max(1, min(MAX_SIDE, height))
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
    # With a real alpha channel mpv writes 255 for video, so the frame is opaque on any compositor.
    return C.string_at(address, stride * height), width, height, stride


class SoftwareRenderer:
    def __init__(self, core, on_ready=None, on_frame=None, on_error=None):
        self.core = core
        self.on_ready, self.on_frame, self.on_error = on_ready, on_frame, on_error
        self.size = (640, 360)
        self.visible = True
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._run, name='wysun-mpv-render', daemon=True)

    def start(self):
        self._thread.start()
        return self

    def wake(self):
        self._wake.set()

    @property
    def alive(self):
        return self._thread.is_alive()

    def _run(self):
        lib = self.core.lib
        callback = mpv.WAKEUP(lambda _: self._wake.set())
        context = None
        try:
            context = self.core.render_context('sw')
            lib.mpv_render_context_set_update_callback(context, callback, None)
            if self.on_ready:
                self.on_ready()
            while not self._stop.is_set():
                if not self._wake.wait(.25):
                    continue
                self._wake.clear()
                lib.mpv_render_context_update(context)
                if not self.visible:
                    skip = C.c_int(1)
                    params = (mpv.Param * 2)(mpv.Param(mpv.RP_SKIP_RENDERING, _void(skip)), mpv.Param(0, None))
                    lib.mpv_render_context_render(context, params)
                    continue
                frame = render(lib, context, *self.size)
                if not self._stop.is_set() and self.on_frame:
                    self.on_frame(*frame)
        except Exception as error:
            if self.on_error:
                self.on_error(str(error))
        finally:
            if context is not None:
                lib.mpv_render_context_set_update_callback(context, mpv.WAKEUP(), None)
                lib.mpv_render_context_free(context)

    def stop(self, timeout=5):
        """End the thread and free the render context (before the session closes its core)."""
        self._stop.set()
        self._wake.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                raise RuntimeError('El renderizador sigue finalizando; no se destruye su contexto activo')
