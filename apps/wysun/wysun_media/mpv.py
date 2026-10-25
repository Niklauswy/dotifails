"""Narrow ctypes binding of libmpv's client and render APIs (mpv 0.40, client API 2.x).

Only what the player needs: asynchronous commands, observed properties, an event
drain and the OpenGL/software render contexts. Callbacks from mpv's threads only
write a byte into a pipe; every other call happens on the thread that owns the
object. References: include/mpv/client.h and include/mpv/render.h.
"""
import ctypes as C
import ctypes.util
import errno
import locale
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

# mpv_format
FMT_NONE, FMT_STRING, FMT_FLAG, FMT_INT64, FMT_DOUBLE, FMT_NODE, FMT_NODE_ARRAY, FMT_NODE_MAP = 0, 1, 3, 4, 5, 6, 7, 8
# mpv_event_id
EV_NONE, EV_SHUTDOWN, EV_COMMAND_REPLY, EV_START_FILE, EV_END_FILE, EV_FILE_LOADED = 0, 1, 5, 6, 7, 8
EV_SEEK, EV_PLAYBACK_RESTART, EV_PROPERTY_CHANGE = 20, 21, 22
# mpv_end_file_reason
END_EOF, END_STOP, END_QUIT, END_ERROR, END_REDIRECT = 0, 2, 3, 4, 5
# mpv_render_param_type
RP_API_TYPE, RP_OPENGL_INIT, RP_OPENGL_FBO, RP_FLIP_Y, RP_SKIP_RENDERING = 1, 2, 3, 4, 13
RP_SW_SIZE, RP_SW_FORMAT, RP_SW_STRIDE, RP_SW_POINTER = 17, 18, 19, 20
RENDER_UPDATE_FRAME = 1
MIN_API = (2 << 16) | 2           # mpv 0.38: loadfile takes per-file options

# mpv_error: the codes the UI distinguishes.
ERROR_CATEGORY = {-13: 'unreadable', -14: 'audio', -15: 'render', -16: 'nothing', -17: 'unsupported'}

# Options applied before mpv_initialize: no user configuration, scripts, network
# extractors, sibling-file discovery or foreign protocols, and no built-in UI.
FIXED_OPTIONS = {
    'vo': 'libmpv', 'config': 'no', 'terminal': 'no', 'load-scripts': 'no', 'ytdl': 'no', 'osc': 'no', 'osd-level': '0',
    'input-default-bindings': 'no', 'input-vo-keyboard': 'no', 'input-cursor': 'no', 'cursor-autohide': 'no',
    'audio-file-auto': 'no', 'sub-auto': 'no', 'cover-art-auto': 'no', 'load-unsafe-playlists': 'no',
    'access-references': 'no', 'demuxer-lavf-o': 'protocol_whitelist=file', 'idle': 'yes', 'keep-open': 'yes',
    'pause': 'yes', 'audio-display': 'no', 'volume-max': '150', 'screenshot-format': 'png',
    'background-color': '#000000',  # theme-exception: lienzo negro de vídeo
}


class Param(C.Structure):
    _fields_ = [('type', C.c_int), ('data', C.c_void_p)]


class _Node(C.Structure):
    pass


class _NodeList(C.Structure):
    _fields_ = [('num', C.c_int), ('values', C.POINTER(_Node)), ('keys', C.POINTER(C.c_char_p))]


class _Value(C.Union):
    _fields_ = [('string', C.c_char_p), ('flag', C.c_int), ('int64', C.c_int64), ('double', C.c_double),
                ('list', C.POINTER(_NodeList))]


_Node._fields_ = [('u', _Value), ('format', C.c_int)]


class _Event(C.Structure):
    _fields_ = [('event_id', C.c_int), ('error', C.c_int), ('reply_userdata', C.c_uint64), ('data', C.c_void_p)]


class _PropertyEvent(C.Structure):
    _fields_ = [('name', C.c_char_p), ('format', C.c_int), ('data', C.c_void_p)]


class _EndFile(C.Structure):
    _fields_ = [('reason', C.c_int), ('error', C.c_int), ('playlist_entry_id', C.c_int64)]


class _StartFile(C.Structure):
    _fields_ = [('playlist_entry_id', C.c_int64)]


class _CommandReply(C.Structure):
    _fields_ = [('result', _Node)]


class GLInit(C.Structure):
    _fields_ = [('get_proc_address', C.c_void_p), ('get_proc_address_ctx', C.c_void_p)]


class GLFbo(C.Structure):
    _fields_ = [('fbo', C.c_int), ('w', C.c_int), ('h', C.c_int), ('internal_format', C.c_int)]


@dataclass(frozen=True)
class Event:
    kind: int
    userdata: int = 0
    error: int = 0
    name: str = ''
    value: Any = None
    reason: int = 0
    entry: int = 0


GET_PROC = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_char_p)
WAKEUP = C.CFUNCTYPE(None, C.c_void_p)


def normalize_numeric_locale():
    """libmpv refuses mpv_create unless LC_NUMERIC is C; call before any mpv thread exists."""
    try:
        locale.setlocale(locale.LC_NUMERIC, 'C')
    except locale.Error:
        pass


_lib = None
_closing = set()


def library():
    """The loaded libmpv with typed signatures; raises RuntimeError when it is missing."""
    global _lib
    if _lib is not None:
        return _lib
    name = os.environ.get('WYSUN_LIBMPV') or ctypes.util.find_library('mpv') or 'libmpv.so.2'
    try:
        lib = C.CDLL(name)
    except OSError as error:
        raise RuntimeError('Falta libmpv2') from error
    void, ptr, cstr = None, C.c_void_p, C.c_char_p
    declarations = {
        'mpv_create': ([], ptr),
        'mpv_client_api_version': ([], C.c_ulong),
        'mpv_set_option_string': ([ptr, cstr, cstr], C.c_int),
        'mpv_initialize': ([ptr], C.c_int),
        'mpv_terminate_destroy': ([ptr], void),
        'mpv_command_async': ([ptr, C.c_uint64, C.POINTER(cstr)], C.c_int),
        'mpv_observe_property': ([ptr, C.c_uint64, cstr, C.c_int], C.c_int),
        'mpv_wait_event': ([ptr, C.c_double], C.POINTER(_Event)),
        'mpv_set_wakeup_callback': ([ptr, WAKEUP, ptr], void),
        'mpv_error_string': ([C.c_int], cstr),
        'mpv_render_context_create': ([C.POINTER(ptr), ptr, C.POINTER(Param)], C.c_int),
        'mpv_render_context_update': ([ptr], C.c_uint64),
        'mpv_render_context_render': ([ptr, C.POINTER(Param)], C.c_int),
        'mpv_render_context_report_swap': ([ptr], void),
        'mpv_render_context_free': ([ptr], void),
        'mpv_render_context_set_update_callback': ([ptr, WAKEUP, ptr], void),
    }
    for symbol, (args, result) in declarations.items():
        function = getattr(lib, symbol)
        function.argtypes, function.restype = args, result
    _lib = lib
    return lib


def _node(node):
    """Python value of an mpv_node (copied, so it outlives the event)."""
    kind = node.format
    if kind == FMT_STRING:
        return node.u.string.decode('utf-8', 'replace') if node.u.string else ''
    if kind == FMT_FLAG:
        return bool(node.u.flag)
    if kind == FMT_INT64:
        return int(node.u.int64)
    if kind == FMT_DOUBLE:
        return float(node.u.double)
    if kind == FMT_NODE_ARRAY:
        items = node.u.list.contents
        return [_node(items.values[index]) for index in range(items.num)]
    if kind == FMT_NODE_MAP:
        items = node.u.list.contents
        return {items.keys[index].decode('utf-8', 'replace'): _node(items.values[index]) for index in range(items.num)}
    return None


def _property(data, fmt):
    if not data or fmt == FMT_NONE:
        return None
    if fmt == FMT_FLAG:
        return bool(C.cast(data, C.POINTER(C.c_int)).contents.value)
    if fmt == FMT_INT64:
        return int(C.cast(data, C.POINTER(C.c_int64)).contents.value)
    if fmt == FMT_DOUBLE:
        return float(C.cast(data, C.POINTER(C.c_double)).contents.value)
    if fmt == FMT_STRING:
        raw = C.cast(data, C.POINTER(C.c_char_p)).contents.value
        return raw.decode('utf-8', 'replace') if raw is not None else None
    if fmt in (FMT_NODE, FMT_NODE_ARRAY, FMT_NODE_MAP):
        return _node(C.cast(data, C.POINTER(_Node)).contents)
    return None


def error_text(code):
    return library().mpv_error_string(code).decode('utf-8', 'replace')


class Mpv:
    """One mpv core. ``wake_fd`` becomes readable when events or video updates are waiting."""

    def __init__(self, options=None):
        normalize_numeric_locale()
        self.lib = library()
        if self.lib.mpv_client_api_version() < MIN_API:
            raise RuntimeError('La versión de libmpv es demasiado antigua (se necesita mpv 0.38 o posterior)')
        self.handle = self.lib.mpv_create()
        if not self.handle:
            raise RuntimeError('No se pudo crear libmpv')
        self._read, self._write = os.pipe()
        for descriptor in (self._read, self._write):
            os.set_blocking(descriptor, False)
        self._wakeup = WAKEUP(lambda _: self.poke(b'e'))    # kept: mpv holds a raw pointer to it
        try:
            for key, value in {**FIXED_OPTIONS, **(options or {})}.items():
                if self.lib.mpv_set_option_string(self.handle, key.encode(), str(value).encode()) < 0:
                    raise RuntimeError('Opción de libmpv no disponible: ' + key)
            if self.lib.mpv_initialize(self.handle) < 0:
                raise RuntimeError('No se pudo iniciar libmpv')
        except BaseException:
            self.lib.mpv_terminate_destroy(self.handle)
            self.handle = None
            self._release_pipe()
            raise
        self.lib.mpv_set_wakeup_callback(self.handle, self._wakeup, None)

    # ---------------------------------------------------------------- wakeups
    @property
    def wake_fd(self):
        return self._read

    def poke(self, token):
        """Callable from any thread: marks that something needs the owner's attention."""
        if self._write is None:
            return
        try:
            os.write(self._write, token)
        except OSError as error:
            if error.errno not in (errno.EAGAIN, errno.EBADF):
                raise

    def take_wakeups(self):
        """Bytes written since the last call (b'e' events, b'r' render updates)."""
        chunks = []
        while True:
            try:
                data = os.read(self._read, 4096)
            except (BlockingIOError, OSError):
                break
            if not data:
                break
            chunks.append(data)
        return b''.join(chunks)

    # --------------------------------------------------------------- commands
    def command(self, *args, userdata=0):
        """Queue a command; the result arrives later as an EV_COMMAND_REPLY with ``userdata``."""
        if not self.handle:
            return -1
        encoded = (C.c_char_p * (len(args) + 1))(*[str(a).encode() for a in args], None)
        return self.lib.mpv_command_async(self.handle, userdata, encoded)

    def set(self, name, value, userdata=0):
        if isinstance(value, bool):
            value = 'yes' if value else 'no'
        return self.command('set', name, value, userdata=userdata)

    def observe(self, name, fmt, userdata=0):
        return self.lib.mpv_observe_property(self.handle, userdata, name.encode(), fmt)

    def events(self):
        """Every queued event, copied out of mpv's buffer."""
        found = []
        while self.handle:
            raw = self.lib.mpv_wait_event(self.handle, 0).contents
            kind = raw.event_id
            if kind == EV_NONE:
                break
            event = Event(kind, raw.reply_userdata, raw.error)
            if kind == EV_PROPERTY_CHANGE and raw.data:
                prop = C.cast(raw.data, C.POINTER(_PropertyEvent)).contents
                event = Event(kind, raw.reply_userdata, 0, prop.name.decode(), _property(prop.data, prop.format))
            elif kind == EV_END_FILE and raw.data:
                end = C.cast(raw.data, C.POINTER(_EndFile)).contents
                event = Event(kind, raw.reply_userdata, end.error, reason=end.reason, entry=end.playlist_entry_id)
            elif kind == EV_START_FILE and raw.data:
                event = Event(kind, raw.reply_userdata, entry=C.cast(raw.data, C.POINTER(_StartFile)).contents.playlist_entry_id)
            found.append(event)
            if kind == EV_SHUTDOWN:
                break
        return found

    # ------------------------------------------------------- render contexts
    def render_context(self, api, extra=()):
        """Create an mpv_render_context (``api`` 'opengl' or 'sw'); returns the raw handle."""
        context = C.c_void_p()
        name = C.create_string_buffer(api.encode())
        params = (Param * (len(extra) + 2))(Param(RP_API_TYPE, C.cast(name, C.c_void_p)), *extra, Param(0, None))
        code = self.lib.mpv_render_context_create(C.byref(context), self.handle, params)
        if code < 0:
            raise RuntimeError(f'libmpv no admite el renderizado {api} ({error_text(code)})')
        return context

    def close(self):
        """Destroy the core without waiting for it. Render contexts must already be freed.

        mpv_terminate_destroy joins the audio and video threads, which can take long when
        a sound server stalls; it runs on its own thread and the UI never waits for it.
        """
        handle, self.handle = self.handle, None
        if handle:
            self.lib.mpv_set_wakeup_callback(handle, WAKEUP(), None)
            worker = threading.Thread(target=self._destroy, args=(handle,), name='wysun-mpv-destroy', daemon=True)
            _closing.add(worker)
            worker.start()
        self._release_pipe()

    def _destroy(self, handle):
        try:
            self.lib.mpv_terminate_destroy(handle)
        finally:
            _closing.discard(threading.current_thread())

    def _release_pipe(self):
        for attribute in ('_read', '_write'):
            descriptor = getattr(self, attribute, None)
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                setattr(self, attribute, None)


def wait_closed(timeout=3.0):
    """Let cores that are still shutting down finish (call once at process exit)."""
    deadline = time.monotonic() + timeout
    for worker in list(_closing):
        worker.join(max(0.0, deadline - time.monotonic()))
