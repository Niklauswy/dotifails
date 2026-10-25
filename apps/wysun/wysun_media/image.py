"""Still images and animations: bounded off-thread decoding and a zoomable canvas.

Decoding runs on a small private thread pool with ``QImageReader`` and hands owned
``QImage`` objects to the GUI thread (pixmaps are never created off-thread). A decode
is sized for the viewport first and refined once zoom settles; results of replaced
requests are discarded by token. One cache keeps at most ``CACHE_BYTES`` of decoded
images for every viewer in the process.
"""
import itertools
import math
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QImage, QImageIOHandler, QImageReader, QMovie, QPainter, QTransform
from PySide6.QtWidgets import QWidget

from . import host
from .errors import MediaError

CACHE_BYTES = 128 * 1024 * 1024         # retained decoded images, whole process
JOB_BYTES = 128 * 1024 * 1024           # largest single decode allowed
WORKERS = 2
MIN_SCALE, MAX_SCALE = 0.02, 64.0       # logical pixels per image pixel
DETAIL_DELAY_MS = 160                   # zoom must rest this long before more detail is decoded
SPINNER_DELAY_MS = 220                  # a decode faster than this never flashes a "loading" message
PIXELATE_ABOVE = 3.0                    # device pixels per image pixel from which pixels stay crisp


@dataclass
class Frame:
    """A decoded image. ``scale`` is decoded pixels per original pixel (1 = full resolution)."""
    image: QImage
    size: QSize                          # original size after orientation
    scale: float
    format: str
    animated: bool
    fingerprint: str

    @property
    def bytes(self):
        return self.image.sizeInBytes()


def ratio_for(size, want):
    """Largest useful decode ratio (<= 1) of an image of ``size`` for a ``want``-sized display."""
    if not want.isValid() or size.isEmpty():
        return 1.0
    return min(1.0, want.width() / size.width(), want.height() / size.height())


class Cache:
    """LRU of decoded images keyed by file fingerprint and detail, bounded by bytes."""

    def __init__(self, limit=CACHE_BYTES):
        self.limit, self.used = limit, 0
        self.sizes = {}                  # fingerprint -> original oriented QSize, remembered after the first decode
        self._items = OrderedDict()
        self._lock = Lock()

    def best(self, fingerprint, scale):
        """The least detailed cached decode with at least ``scale`` detail, or None."""
        with self._lock:
            options = [(key, frame) for key, frame in self._items.items()
                       if key[0] == fingerprint and frame.scale >= scale * .95]
            if not options:
                return None
            key, frame = min(options, key=lambda item: item[1].scale)
            self._items.move_to_end(key)
            return frame

    def put(self, frame):
        self.sizes[frame.fingerprint] = frame.size
        if frame.bytes > self.limit:
            return
        with self._lock:
            key = (frame.fingerprint, round(frame.scale, 3))
            if key in self._items:
                self.used -= self._items.pop(key).bytes
            self._items[key] = frame
            self.used += frame.bytes
            while self.used > self.limit and len(self._items) > 1:
                _, dropped = self._items.popitem(last=False)
                self.used -= dropped.bytes

    def clear(self):
        with self._lock:
            self._items.clear()
            self.used = 0


def decode(path, fingerprint, want, cache=None, budget=JOB_BYTES):
    """Read ``path`` for a ``want``-sized (pixels) display; raises MediaError.

    Formats whose handler scales while decoding (JPEG, WebP) never allocate the full image.
    The rest decode in full when that fits ``budget``; when the display is smaller, the full
    image goes to ``cache`` (for later zoom) and a display-sized copy is returned.
    """
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    if not reader.canRead():
        category = 'unsupported' if reader.error() == QImageReader.UnsupportedFormatError else 'unreadable'
        raise MediaError(category, detail=reader.errorString())
    raw, name = reader.size(), bytes(reader.format()).decode()
    animated = reader.supportsAnimation() and reader.imageCount() > 1
    size = None
    if raw.isValid():
        turned = bool(reader.transformation() & QImageIOHandler.TransformationRotate90)
        size = QSize(raw.height(), raw.width()) if turned else raw
        ratio = ratio_for(size, want)
        if ratio < 1 and reader.supportsOption(QImageIOHandler.ScaledSize):
            reader.setScaledSize(QSize(max(1, round(raw.width() * ratio)), max(1, round(raw.height() * ratio))))
        elif size.width() * size.height() * 4 > budget:
            raise MediaError('too_large', detail=f'{size.width()} × {size.height()}')
    image = reader.read()
    if image.isNull():
        raise MediaError('decode', detail=reader.errorString())
    if size is None:
        size = image.size()
    scale = min(1.0, image.width() / size.width())
    frame = Frame(image, size, scale, name, animated, fingerprint)
    ratio = ratio_for(size, want)
    if scale >= 1.0 and ratio < .9:      # decoded in full for a smaller display
        if cache is not None:
            cache.put(frame)
        shown = image.scaled(max(1, round(size.width() * ratio)), max(1, round(size.height() * ratio)),
                             Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        frame = Frame(shown, size, ratio, name, animated, fingerprint)
    return frame


class _Relay(QObject):
    loaded = Signal(int, object)         # token, Frame
    failed = Signal(int, object)         # token, MediaError


class _Job(QRunnable):
    def __init__(self, jobs, token, source, want):
        super().__init__()
        self.jobs, self.token, self.source, self.want = jobs, token, source, want
        self.cancelled = False

    def run(self):
        if self.cancelled and self.token:
            return
        try:
            frame, error = decode(self.source.path, self.source.fingerprint, self.want, self.jobs.cache), None
        except MediaError as caught:
            frame, error = None, caught
        except Exception as caught:                     # a decoder plugin must never take the worker down
            frame, error = None, MediaError('decode', detail=str(caught))
        if frame is not None:
            self.jobs.cache.put(frame)
        if self.token == 0 or self.cancelled:
            return
        try:
            self.jobs.relay.failed.emit(self.token, error) if error else self.jobs.relay.loaded.emit(self.token, frame)
        except RuntimeError:                            # interpreter shutting down
            pass


class Jobs:
    """Process-wide decode pool, cache and result relay."""

    def __init__(self):
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(WORKERS)
        self.cache = Cache()
        self.relay = _Relay()
        self._tokens = itertools.count(1)
        self._shown = None

    def lookup(self, source, want):
        """A cached decode good enough for ``want``, or None. Only works after the file was decoded once."""
        size = self.cache.sizes.get(source.fingerprint)
        return self.cache.best(source.fingerprint, ratio_for(size, want)) if size else None

    def request(self, source, want):
        """Decode for display; any decode requested for display before this one is abandoned."""
        if self._shown is not None:
            self._shown.cancelled = True
        token = next(self._tokens)
        self._shown = _Job(self, token, source, want)
        self.pool.start(self._shown)
        return token

    def prefetch(self, source, want):
        """Warm the cache for a neighbour, only while the cache is below three quarters full."""
        if self.cache.used < self.cache.limit * .75 and self.lookup(source, want) is None:
            self.pool.start(_Job(self, 0, source, want))


_jobs = None


def jobs():
    global _jobs
    if _jobs is None:
        _jobs = Jobs()
    return _jobs


class ImageView(QWidget):
    """Fit / actual-pixels / free zoom with cursor-anchored wheel and pinch zoom, panning and rotation."""

    loaded = Signal(object)              # Frame
    failed = Signal(object)              # MediaError
    zoomChanged = Signal()
    animationChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = None
        self.error = None
        self.source = None
        self.mode = 'fit'                # 'fit' | 'actual' | 'zoom'
        self._scale = 1.0
        self._offset = QPointF()
        self._turns = 0                  # presentation-only rotation, quarter turns
        self._token = 0
        self._loading = False
        self._spinner = False
        self._drag = None
        self._movie = None
        self._pending = None
        self._detail = QTimer(self, singleShot=True, interval=DETAIL_DELAY_MS)
        self._detail.timeout.connect(self._refine)
        self._spin = QTimer(self, singleShot=True, interval=SPINNER_DELAY_MS)
        self._spin.timeout.connect(self._show_spinner)
        relay = jobs().relay
        relay.loaded.connect(self._on_loaded, Qt.QueuedConnection)
        relay.failed.connect(self._on_failed, Qt.QueuedConnection)
        self.setMinimumSize(160, 90)
        self.setCursor(Qt.OpenHandCursor)
        self.setAttribute(Qt.WA_AcceptTouchEvents)
        self.setFocusPolicy(Qt.NoFocus)

    # --------------------------------------------------------------- loading
    def _want(self):
        ratio = self.devicePixelRatioF()
        return QSize(max(1, round(self.width() * ratio)), max(1, round(self.height() * ratio)))

    def show_source(self, source):
        """Display a MediaSource of kind image; neighbours may already be cached."""
        self.clear()
        self.source = source
        self.mode, self._offset, self._turns = 'fit', QPointF(), 0
        cached = jobs().lookup(source, self._want())
        if cached is not None:
            self._token = 0
            self._adopt(cached)
            return
        self._loading = True
        self._token = jobs().request(source, self._want())
        self._spin.start()
        self.update()

    def prefetch(self, sources):
        for source in sources:
            jobs().prefetch(source, self._want())

    def clear(self):
        self._stop_movie()
        self.frame = self.error = self.source = None
        self._loading = self._spinner = False
        self._token = 0
        self._spin.stop()
        self._detail.stop()
        self.update()

    def _on_loaded(self, token, frame):
        if token != self._token or self.source is None:
            return                                       # belongs to an image that is no longer shown
        if self._loading:
            self._adopt(frame)
        else:                                            # more detail for the one on screen
            self._token = 0
            self.frame = frame
            self.update()

    def _on_failed(self, token, error):
        if token != self._token:
            return
        self._loading = self._spinner = False
        self._spin.stop()
        self.error = error
        self.update()
        self.failed.emit(error)

    def _adopt(self, frame):
        self._loading = self._spinner = False
        self._spin.stop()
        self.frame, self.error = frame, None
        if frame.animated:
            self._start_movie()
        self.update()
        self.zoomChanged.emit()
        self.loaded.emit(frame)

    def _show_spinner(self):
        if self._loading:
            self._spinner = True
            self.update()

    def _refine(self):
        """Zoom has settled: decode more detail if the display now needs it."""
        frame = self.frame
        if frame is None or frame.animated or frame.scale >= 1.0 or self.source is None:
            return
        need = min(1.0, self.scale * self.devicePixelRatioF())
        if frame.scale >= need * .95:
            return
        want = QSize(math.ceil(frame.size.width() * need), math.ceil(frame.size.height() * need))
        better = jobs().cache.best(frame.fingerprint, need)
        if better is not None:
            self.frame = better
            self.update()
            return
        self._token = jobs().request(self.source, want)

    # -------------------------------------------------------------- animation
    def _start_movie(self):
        movie = QMovie(str(self.source.path))
        movie.setCacheMode(QMovie.CacheNone)
        if not movie.isValid():
            return
        self._movie = movie
        movie.frameChanged.connect(self.update)
        movie.jumpToFrame(0)
        movie.start()
        if host.get().reduced_motion() or not self.isVisible():
            movie.setPaused(True)             # starts on the first frame, with a play control
        self.animationChanged.emit(self.animating)

    def _stop_movie(self):
        if self._movie is not None:
            self._movie.stop()
            self._movie.deleteLater()
            self._movie = None

    @property
    def animated(self):
        return self._movie is not None

    @property
    def animating(self):
        return self._movie is not None and self._movie.state() == QMovie.Running

    def toggle_animation(self):
        movie = self._movie
        if movie is None:
            return
        if movie.state() == QMovie.Running:
            movie.setPaused(True)
        elif movie.state() == QMovie.Paused:
            movie.setPaused(False)
        else:
            movie.start()
        self.animationChanged.emit(self.animating)

    def hideEvent(self, event):
        if self._movie is not None and self._movie.state() == QMovie.Running:
            self._movie.setPaused(True)
        super().hideEvent(event)

    def showEvent(self, event):
        if self._movie is not None and self._movie.state() == QMovie.Paused and not host.get().reduced_motion():
            self._movie.setPaused(False)
        super().showEvent(event)

    # ---------------------------------------------------------------- geometry
    def _extent(self):
        """Original size as displayed (after presentation rotation)."""
        size = self.frame.size if self.frame else QSize(1, 1)
        return (size.height(), size.width()) if self._turns % 2 else (size.width(), size.height())

    @property
    def actual_scale(self):
        return 1.0 / self.devicePixelRatioF()

    @property
    def fit_scale(self):
        width, height = self._extent()
        return min(self.width() / width, self.height() / height, self.actual_scale)

    @property
    def scale(self):
        return self.fit_scale if self.mode == 'fit' else self.actual_scale if self.mode == 'actual' else self._scale

    @property
    def zoom_percent(self):
        """100 means one image pixel per screen pixel."""
        return self.scale * self.devicePixelRatioF() * 100

    def _clamp(self, offset, scale):
        width, height = self._extent()
        limit_x = max(0.0, (width * scale - self.width()) / 2)
        limit_y = max(0.0, (height * scale - self.height()) / 2)
        return QPointF(max(-limit_x, min(limit_x, offset.x())), max(-limit_y, min(limit_y, offset.y())))

    def _transform(self, scale=None, offset=None):
        center = QPointF(self.width() / 2, self.height() / 2) + (self._offset if offset is None else offset)
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(90 * self._turns)
        transform.scale(scale or self.scale, scale or self.scale)
        return transform

    def set_mode(self, mode, anchor=None):
        if self.frame is None:
            return
        if mode == 'actual' and anchor is not None:
            self.zoom_to(self.actual_scale, anchor)
            return
        self.mode = mode
        self._offset = QPointF()
        self._changed()

    def toggle_fit(self, anchor=None):
        """Fit <-> 100 %, keeping the point under ``anchor`` when zooming in."""
        if self.mode == 'fit' and self.fit_scale < self.actual_scale:
            self.zoom_to(self.actual_scale, anchor)
        elif self.mode == 'fit':
            self.zoom_to(min(MAX_SCALE, self.actual_scale * 2), anchor)
        else:
            self.set_mode('fit')

    def zoom_by(self, factor, anchor=None):
        self.zoom_to(self.scale * factor, anchor)

    def zoom_to(self, scale, anchor=None):
        if self.frame is None:
            return
        scale = max(MIN_SCALE, min(MAX_SCALE, scale))
        anchor = anchor if anchor is not None else QPointF(self.width() / 2, self.height() / 2)
        point, _ = self._transform().inverted()
        picked = point.map(anchor)                          # image point under the anchor
        rotation = QTransform().rotate(90 * self._turns)
        centre = QPointF(self.width() / 2, self.height() / 2)
        offset = anchor - centre - rotation.map(picked * scale)
        self._scale, self.mode = scale, 'zoom'
        self._offset = self._clamp(offset, scale)
        self._changed()

    def rotate(self, steps=1):
        if self.frame is None:
            return
        self._turns = (self._turns + steps) % 4
        self._offset = self._clamp(QPointF(), self.scale) if self.mode == 'zoom' else QPointF()
        self._changed()

    def _changed(self):
        self.update()
        self.zoomChanged.emit()
        self._detail.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._offset = self._clamp(self._offset, self.scale)
        self._detail.start()

    # ------------------------------------------------------------------ input
    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120 or event.pixelDelta().y() / 60
        if steps:
            self.zoom_by(1.2 ** steps, event.position())
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.frame is not None:
            self._drag = (event.position(), QPointF(self._offset))
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is not None and self.mode != 'fit':
            start, origin = self._drag
            self._offset = self._clamp(origin + event.position() - start, self.scale)
            self.update()
            self._detail.start()

    def mouseReleaseEvent(self, event):
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.toggle_fit(event.position())

    def event(self, event):
        if event.type() == QEvent.Type.NativeGesture and event.gestureType() == Qt.ZoomNativeGesture:
            self.zoom_by(1 + event.value(), event.position())
            return True
        return super().event(event)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _event):
        h = host.get()
        painter = QPainter(self)
        painter.fillRect(self.rect(), h.color('well'))
        image = self._movie.currentImage() if self._movie is not None and not self._movie.currentImage().isNull() \
            else self.frame.image if self.frame else None
        if image is None or image.isNull():
            self._paint_note(painter, h)
            return
        size = self.frame.size
        scale = self.scale
        transform = self._transform()
        box = transform.mapRect(QRectF(-size.width() / 2, -size.height() / 2, size.width(), size.height()))
        if image.hasAlphaChannel():
            self._paint_checker(painter, h, box)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, scale * self.devicePixelRatioF() < PIXELATE_ABOVE)
        painter.setTransform(transform)
        painter.drawImage(QRectF(-size.width() / 2, -size.height() / 2, size.width(), size.height()), image)

    def _paint_checker(self, painter, h, box):
        cell = max(4, int(h.token('space_m')))
        painter.save()
        painter.setClipRect(box.intersected(QRectF(self.rect())))
        painter.fillRect(box, h.color('well'))
        painter.setPen(Qt.NoPen)
        painter.setBrush(h.color('tile'))
        top, left = int(box.top()), int(box.left())
        for row in range(0, int(box.height() // cell) + 2):
            for column in range(row % 2, int(box.width() // cell) + 2, 2):
                painter.drawRect(left + column * cell, top + row * cell, cell, cell)
        painter.restore()

    def _paint_note(self, painter, h):
        if self.error is not None:
            symbol, text, tint = 'broken_image', self.error.message, 'muted'
        elif self._spinner:
            symbol, text, tint = 'image', 'Cargando…', 'muted'
        else:
            return
        box = QRectF(self.rect())
        h.symbol(painter, QRectF(box.center().x() - 24, box.center().y() - 48, 48, 48), symbol, tint, 40)
        painter.setFont(h.font('body', 500))
        painter.setPen(h.color(tint))
        painter.drawText(QRectF(16, box.center().y() + 8, box.width() - 32, 48), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, text)
