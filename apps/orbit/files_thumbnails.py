"""Bounded asynchronous image thumbnails; all pixmaps stay on the GUI thread."""
from collections import OrderedDict
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QRunnable, QSize, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QIcon, QImage, QImageReader, QPixmap

# A module-owned pool outlives individual windows. Closing a browser never waits
# on a decoder and cannot destroy a pool whose jobs are still running.
_POOL = QThreadPool()
_POOL.setMaxThreadCount(2)
_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'})
_MAX_FILE_BYTES = 32 * 1024 * 1024
_MAX_PIXELS = 16_000_000  # Also bounds readers which cannot decode scaled data.


class _Result(QObject):
    finished = Signal(str, QImage)


class _ReadImage(QRunnable):
    def __init__(self, path, cancelled):
        super().__init__()
        self.path = path
        self.cancelled = cancelled
        self.signals = _Result()

    def run(self):
        result = QImage()
        try:
            if not self.cancelled.is_set():
                source = Path(self.path)
                if source.is_file() and source.stat().st_size <= _MAX_FILE_BYTES:
                    reader = QImageReader(self.path)
                    reader.setAutoTransform(True)
                    size = reader.size()
                    if (size.isValid() and size.width() > 0 and size.height() > 0
                            and size.width() * size.height() <= _MAX_PIXELS):
                        reader.setScaledSize(size.scaled(QSize(160, 160), Qt.KeepAspectRatio))
                        if not self.cancelled.is_set():
                            result = reader.read()  # GIF: first frame only.
                            if not result.isNull():
                                result = result.scaled(160, 160, Qt.KeepAspectRatio,
                                                       Qt.SmoothTransformation)
        except (OSError, RuntimeError, ValueError):
            pass  # Broken, deleted, or unsupported files keep their generic icon.
        self.signals.finished.emit(self.path, result)


class ThumbnailCache(QObject):
    """get() returns immediately; ready(path) asks a model to repaint that item.

    Missing/invalid images are negatively cached. Call invalidate(path) when an
    image changes on disk. close() cancels queued reads without blocking the UI.
    """
    ready = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = OrderedDict()
        self._pending = {}
        self._cancelled = Event()
        # Do not capture self: this remains usable during QObject destruction.
        cancellation = self._cancelled
        self.destroyed.connect(lambda *_: cancellation.set())

    def get(self, path: str) -> QIcon | None:
        if self._cancelled.is_set():
            return None
        path = str(path)
        if path in self._cache:
            self._cache.move_to_end(path)
            return self._cache[path]
        if (Path(path).suffix.lower() not in _EXTENSIONS
                or path in self._pending or len(self._pending) >= 32):
            return None
        job = _ReadImage(path, self._cancelled)
        job.signals.finished.connect(self._received, Qt.QueuedConnection)
        self._pending[path] = job
        _POOL.start(job)
        return None

    @Slot(str, QImage)
    def _received(self, path, image):
        self._pending.pop(path, None)
        if self._cancelled.is_set():
            return
        self._cache[path] = None if image.isNull() else QIcon(QPixmap.fromImage(image))
        self._cache.move_to_end(path)
        while len(self._cache) > 128:
            self._cache.popitem(last=False)
        self.ready.emit(path)

    def invalidate(self, path: str):
        """Drop a completed thumbnail after a known file operation."""
        self._cache.pop(str(path), None)

    def close(self):
        self._cancelled.set()
        self._cache.clear()
