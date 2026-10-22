"""Artwork: lazy lookup, rounded pixmap cache, playlist mosaics and tones.

Every key is requested at most once per session. Network and decoding run in
``Metadata``'s small thread pool; painting only reads ``QPixmapCache``.
"""
import re
import subprocess

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap, QPixmapCache

from music_metadata import Metadata
import music_data

QPixmapCache.setCacheLimit(48 * 1024)  # KiB: ~200 list thumbnails plus a few heroes.


def youtube_thumbnail(url):
    match = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', url or '')
    return f'https://i.ytimg.com/vi/{match[1]}/hqdefault.jpg' if match else ''


class CoverStore(QObject):
    updated = Signal(str)

    def __init__(self, library, network=True, parent=None):
        super().__init__(parent)
        self.library = library
        self.network = network
        self.metadata = Metadata(music_data.DATA, self)
        self.metadata.ready.connect(self._ready)
        self._paths = {}
        self._requested = set()
        self._tones = {}

    # ---------------------------------------------------------------- lookup
    def path(self, key):
        """Image path for a track or collection; requests it on first use."""
        if key in self._paths:
            return self._paths[key]
        if key not in self._requested:
            self._requested.add(key)
            self._request(key)
        return self._paths.get(key)

    def _request(self, key):
        if not key:
            return
        track = self.library.track(key)
        if key.startswith('local-'):
            # Imported files: their own embedded picture, no network involved.
            if track.get('path'):
                path = track['path']
                self.metadata.request('embedded', key, lambda: self._embedded(key, path))
            return
        if not self.network:
            return
        if key.startswith('artist:'):
            self.metadata.artist(key.split(':', 1)[1])  # Wikimedia photo, credited source
            return
        collection = self.library.state['collections'].get(key)
        if collection is not None:
            if collection.get('cover_url'):
                url = collection['cover_url']
                self.metadata.request('cover', key, lambda: dict(path=self.metadata.download_image(url)))
            elif '/album/' in collection.get('source', ''):
                self.metadata.cover(key, collection['source'])
            return
        if not track:
            return
        spotify = self.library.spotify_url(key)
        if spotify:
            self.metadata.cover(key, spotify)
        elif track.get('youtube_url'):
            url = youtube_thumbnail(track['youtube_url'])
            self.metadata.request('cover', key, lambda: dict(path=self.metadata.download_image(url)))

    def _embedded(self, key, path):
        """Attached picture of a local file, decoded off the UI thread."""
        result = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-an', '-frames:v', '1',
                                 '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, timeout=15)
        image = QImage.fromData(result.stdout)
        if image.isNull():
            return {'unavailable': True}
        target = self.metadata.root / ('embedded-' + key + '.image')
        image.scaled(512, 512, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(str(target), 'PNG')
        return {'path': str(target)}

    def _ready(self, kind, key, data):
        if kind == 'artist':
            key = 'artist:' + key
        if kind in ('cover', 'embedded', 'artist') and data.get('path'):
            self._paths[key] = data['path']
            self._tones.pop(key, None)
            self.updated.emit(key)

    # -------------------------------------------------------------- painting
    def pixmap(self, key, size, radius, ratio=1.0):
        path = self.path(key)
        return rounded(path, size, radius, ratio) if path else None

    def collection_pixmap(self, collection, size, radius, ratio=1.0):
        """The collection's own art, else a 2×2 mosaic of its first covers."""
        own = self.pixmap(collection.id, size, radius, ratio)
        if own is not None:
            return own
        paths = []
        for key in collection.keys[:12]:
            path = self.path(key)
            if path and path not in paths:
                paths.append(path)
            if len(paths) == 4:
                break
        if not paths:
            return None
        if len(paths) < 4:
            return rounded(paths[0], size, radius, ratio)
        return mosaic(tuple(paths), size, radius, ratio)

    def tone(self, key):
        """Dominant colour of the artwork, for hero gradients (user image data)."""
        if key in self._tones:
            return self._tones[key]
        path = self.path(key)
        if not path:
            return None
        image = QImage(path)
        if image.isNull():
            return None
        average = image.scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).pixelColor(0, 0)
        hue, saturation, value, _ = average.getHsv()
        # theme-exception: tone derived from the user's artwork, clamped for legible text on top.
        tone = QColor.fromHsv(max(0, hue), min(255, int(saturation * 1.25)), max(70, min(150, value)))
        self._tones[key] = tone
        return tone

    def collection_tone(self, collection):
        own = self.tone(collection.id)
        if own is not None:
            return own
        return next((t for t in (self.tone(k) for k in collection.keys[:4]) if t is not None), None)


def _clip(painter, size, radius):
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    painter.setClipPath(path)


def rounded(path, size, radius, ratio=1.0):
    cache_key = f'wm:{path}:{size}:{radius}:{ratio}'
    found = QPixmapCache.find(cache_key)
    if found is not None and not found.isNull():
        return found
    source = QImage(path)
    if source.isNull():
        return None
    pixels = round(size * ratio)
    scaled = source.scaled(pixels, pixels, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    result = QPixmap(pixels, pixels)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    painter.scale(ratio, ratio)
    _clip(painter, size, radius)
    painter.scale(1 / ratio, 1 / ratio)
    painter.drawImage((pixels - scaled.width()) // 2, (pixels - scaled.height()) // 2, scaled)
    painter.end()
    result.setDevicePixelRatio(ratio)
    QPixmapCache.insert(cache_key, result)
    return result


def mosaic(paths, size, radius, ratio=1.0):
    cache_key = f'wm-mosaic:{"|".join(paths)}:{size}:{radius}:{ratio}'
    found = QPixmapCache.find(cache_key)
    if found is not None and not found.isNull():
        return found
    pixels = round(size * ratio)
    half = pixels / 2
    result = QPixmap(pixels, pixels)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    painter.scale(ratio, ratio)
    _clip(painter, size, radius)
    painter.scale(1 / ratio, 1 / ratio)
    for index, path in enumerate(paths):
        image = QImage(path).scaled(int(half) + 1, int(half) + 1, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        target = QRectF((index % 2) * half, (index // 2) * half, half, half)
        painter.drawImage(target, image, QRectF((image.width() - half) / 2, (image.height() - half) / 2, half, half))
    painter.end()
    result.setDevicePixelRatio(ratio)
    QPixmapCache.insert(cache_key, result)
    return result
