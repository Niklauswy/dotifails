"""Thumbnails for QML as file URLs, in the freedesktop thumbnail cache (``thumbnails/large`` under the user's cache) that
other file managers share. Images keep today's limits (32 MB, 16 Mpx, two decoder threads); videos take a frame
and their length (``Thumb::Movie::Length``), songs their embedded cover, both through ffmpeg with a timeout. A
file that cannot be thumbnailed is remembered in ``fail/wysun`` until it changes. ``url()`` never blocks: it
returns what the cache already has and queues the rest, newest request first; ``ready(path)`` announces it."""
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading

from PySide6.QtCore import QObject, QRunnable, QSize, QThreadPool, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QImage, QImageReader

from wysun_core import paths as core_paths
from wysun_core.jsonio import atomic_path
from wysun_services.file_media import duration_label

EDGE = 256                                   # freedesktop «large»
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 16_000_000
FFMPEG_TIMEOUT = 10
QUEUE = 256
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.avif', '.heic', '.tif', '.tiff'}

_POOL = QThreadPool()                        # module-owned: closing a window never waits on a decoder
_POOL.setMaxThreadCount(2)


def default_cache():
    return core_paths.cache('thumbnails')


def uri_of(path):
    return QUrl.fromLocalFile(str(path)).toString(QUrl.FullyEncoded)


def _private_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def _write(image, target, uri, mtime, extra=None):
    """Save atomically with the spec's keys; the file is private (0600) like the folder."""
    image.setText('Thumb::URI', uri)
    image.setText('Thumb::MTime', str(int(mtime)))
    image.setText('Software', 'Wysun Files')
    for key, value in (extra or {}).items():
        image.setText(key, value)
    _private_dir(target.parent)
    with atomic_path(target, mode=0o600) as temporary:
        if not image.save(str(temporary), 'PNG'):
            raise OSError('could not write the thumbnail')


def _valid(file, uri, mtime):
    if not file.is_file():
        return None
    reader = QImageReader(str(file))
    if reader.text('Thumb::URI') != uri or reader.text('Thumb::MTime') != str(int(mtime)):
        return None
    return reader


def _fit(image):
    if image.isNull():
        return image
    if max(image.width(), image.height()) > EDGE:
        image = image.scaled(EDGE, EDGE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return image


def _ffmpeg(args):
    try:
        done = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', *args, '-f', 'image2pipe',
                               '-vcodec', 'png', '-'], capture_output=True, timeout=FFMPEG_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return QImage()
    image = QImage()
    if done.returncode == 0 and done.stdout:
        image.loadFromData(done.stdout, 'PNG')
    return image


def _length(path):
    try:
        done = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', path],
                              capture_output=True, timeout=FFMPEG_TIMEOUT, check=False, text=True)
        return float(json.loads(done.stdout or '{}').get('format', {}).get('duration') or 0)
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        return 0.0


def make(path, kind):
    """``(image, extra texts)`` of a file's thumbnail (null image when it has none). Runs in a worker thread."""
    if kind == 'image':
        try:
            if os.path.getsize(path) > MAX_FILE_BYTES:
                return QImage(), {}
        except OSError:
            return QImage(), {}
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        size = reader.size()
        if not size.isValid() or size.width() <= 0 or size.height() <= 0 or size.width() * size.height() > MAX_PIXELS:
            return QImage(), {}
        if max(size.width(), size.height()) > EDGE:
            reader.setScaledSize(size.scaled(QSize(EDGE, EDGE), Qt.KeepAspectRatio))
        return _fit(reader.read()), {}          # GIF: first frame
    if kind == 'video':
        seconds = _length(path)
        image = _ffmpeg(['-ss', f'{min(1.0, seconds / 3):.2f}', '-i', path, '-frames:v', '1'])
        return _fit(image), ({'Thumb::Movie::Length': str(int(round(seconds)))} if seconds else {})
    if kind == 'audio':
        return _fit(_ffmpeg(['-i', path, '-an', '-map', '0:v:0', '-frames:v', '1'])), {}
    return QImage(), {}


class _Relay(QObject):
    done = Signal(str, str, str)                 # path, thumbnail file ('' = none), length text


class _Job(QRunnable):
    def __init__(self, owner_cache, path, mtime, kind, relay, cancelled):
        super().__init__()
        self.cache, self.path, self.mtime, self.kind = owner_cache, path, mtime, kind
        self.relay, self.cancelled = relay, cancelled

    def run(self):
        file, length = '', ''
        try:
            if not self.cancelled.is_set():
                file, length = self._work()
        except Exception:                        # a thumbnail never takes the app down
            file, length = '', ''
        if not self.cancelled.is_set():
            self.relay.done.emit(self.path, file, length)

    def _work(self):
        uri = uri_of(self.path)
        digest = hashlib.md5(uri.encode()).hexdigest() + '.png'
        target, failed = self.cache / 'large' / digest, self.cache / 'fail/wysun' / digest
        reader = _valid(target, uri, self.mtime)
        if reader is not None:
            return str(target), _length_text(reader.text('Thumb::Movie::Length'))
        if _valid(failed, uri, self.mtime) is not None:
            return '', ''
        image, extra = make(self.path, self.kind)
        if self.cancelled.is_set():
            return '', ''
        if image.isNull():
            marker = QImage(1, 1, QImage.Format_ARGB32)
            marker.fill(Qt.transparent)
            _write(marker, failed, uri, self.mtime)
            return '', ''
        _write(image, target, uri, self.mtime, extra)
        return str(target), _length_text(extra.get('Thumb::Movie::Length', ''))


def _length_text(seconds):
    try:
        return duration_label(int(seconds)) if seconds else ''
    except ValueError:
        return ''


class Thumbnails(QObject):
    ready = Signal(str)

    def __init__(self, cache=None, parent=None):
        super().__init__(parent)
        self.cache = Path(cache) if cache else default_cache()
        self._done = {}                              # path -> (mtime, url, length)
        self._waiting = OrderedDict()                # path -> (mtime, kind), newest last
        self._running = set()
        self._pending_mtime = {}                     # running path -> the mtime it was asked for
        self._cancelled = threading.Event()
        self._relay = _Relay(self)
        self._relay.done.connect(self._finished, Qt.QueuedConnection)

    def _excluded(self, path):
        try:
            return Path(path).resolve().is_relative_to(self.cache.resolve())
        except OSError:
            return True

    def url(self, path, mtime, kind):
        """The thumbnail's ``file://`` URL, or '' (queued unless it is known to have none)."""
        if kind not in ('image', 'video', 'audio') or self._cancelled.is_set():
            return ''
        if kind == 'image' and Path(path).suffix.lower() not in IMAGE_SUFFIXES:
            return ''
        known = self._done.get(path)
        if known and known[0] == mtime:
            return known[1]
        if path in self._running:
            return ''
        if self._excluded(path):
            self._done[path] = (mtime, '', '')
            return ''
        self._waiting[path] = (mtime, kind)
        self._waiting.move_to_end(path)
        while len(self._waiting) > QUEUE:
            dropped, _ = self._waiting.popitem(last=False)
            self.ready.emit(dropped)                 # a still-visible delegate asks again
        self._pump()
        return ''

    def length(self, path, mtime):
        known = self._done.get(path)
        return known[2] if known and known[0] == mtime else ''

    def _pump(self):
        while self._waiting and len(self._running) < 2 * _POOL.maxThreadCount():
            path, (mtime, kind) = self._waiting.popitem(last=True)
            self._running.add(path)
            self._done.pop(path, None)
            _POOL.start(_Job(self.cache, path, mtime, kind, self._relay, self._cancelled))
            self._pending_mtime[path] = mtime

    @Slot(str, str, str)
    def _finished(self, path, file, length):
        self._running.discard(path)
        mtime = self._pending_mtime.pop(path, None)
        if self._cancelled.is_set():
            return
        url = QUrl.fromLocalFile(file).toString() if file else ''
        self._done[path] = (mtime, url, length)
        while len(self._done) > 4096:
            self._done.pop(next(iter(self._done)))
        self.ready.emit(path)
        self._pump()

    def forget(self, path):
        """Drop what is known of ``path`` (after an operation changed it)."""
        self._done.pop(str(path), None)

    def close(self):
        self._cancelled.set()
        self._waiting.clear()
        self._done.clear()
