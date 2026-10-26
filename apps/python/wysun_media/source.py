"""Local media sources: validation and classification, with no decoder involved."""
import os
import re
import stat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QMimeDatabase
from PySide6.QtGui import QImageReader

from .errors import MediaError

VIDEO = {'.mp4', '.m4v', '.mkv', '.webm', '.mov', '.avi', '.wmv', '.flv', '.mpg', '.mpeg', '.ts', '.m2ts', '.mts',
         '.3gp', '.ogv', '.vob', '.divx'}
AUDIO = {'.mp3', '.flac', '.ogg', '.oga', '.opus', '.wav', '.m4a', '.aac', '.wma', '.aiff', '.aif', '.ape', '.mka',
         '.wv', '.mpc', '.amr', '.weba'}
IMAGE = {'.jpg', '.jpeg', '.jfif', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.ico', '.tga', '.ppm', '.pgm',
         '.pbm', '.svg', '.svgz', '.avif', '.heic', '.heif'}
# Playlists and manifests make a decoder open other files and URLs: never accepted.
INDEXES = {'.m3u', '.m3u8', '.pls', '.mpd', '.xspf', '.asx', '.wpl', '.cue', '.ram', '.smil', '.sdp'}
NATURAL = re.compile(r'(\d+)')


@lru_cache(maxsize=1)
def _readable_images():
    """Extensions Qt can really decode here, which is less than the names above promise."""
    return {'.' + bytes(name).decode().lower() for name in QImageReader.supportedImageFormats()}


def image_decodable(path):
    extension = Path(path).suffix.lower()
    if extension in ('.jpg', '.jpeg', '.jfif'):
        return '.jpg' in _readable_images() or '.jpeg' in _readable_images()
    if extension in ('.tif', '.tiff'):
        return '.tif' in _readable_images() or '.tiff' in _readable_images()
    return extension in _readable_images()


def kind_of(path):
    """'video', 'audio', 'image' or '' for a path, judged by name and then by MIME."""
    suffix = Path(path).suffix.lower()
    if suffix in INDEXES:
        return ''
    if suffix in IMAGE:
        return 'image' if image_decodable(path) else ''
    if suffix in VIDEO:
        return 'video'
    if suffix in AUDIO:
        return 'audio'
    major = QMimeDatabase().mimeTypeForFile(str(path)).name().partition('/')[0]
    if major == 'image':
        return 'image' if image_decodable(path) else ''
    return major if major in ('video', 'audio') else ''


def group_of(kind):
    """Collections group videos with audio; images browse among images."""
    return 'image' if kind == 'image' else 'av' if kind else ''


def natural_key(name):
    return [int(part) if part.isdigit() else part for part in NATURAL.split(name.casefold())]


@dataclass(frozen=True)
class MediaSource:
    path: Path
    kind: str
    size: int
    mtime_ns: int

    @property
    def name(self):
        return self.path.name

    @property
    def fingerprint(self):
        return f'{self.path}\0{self.size}\0{self.mtime_ns}'

    @property
    def group(self):
        return group_of(self.kind)


def to_path(value):
    """Local path from a path, ``file:`` URL or text. Remote hosts and other schemes are rejected."""
    if isinstance(value, Path):
        return value
    text = str(value)
    if '://' in text or text.startswith('file:'):
        parsed = urlparse(text)
        if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost'):
            raise MediaError('rejected', detail=parsed.scheme or 'url')
        text = unquote(parsed.path)
    return Path(text)


def open_source(value):
    """Validate ``value`` and describe it. Raises :class:`MediaError`."""
    path = to_path(value)
    if '\0' in str(path):
        raise MediaError('rejected', detail='nul')
    try:
        info = path.stat()          # follows symlinks: devices, FIFOs and sockets resolve to non-regular files
    except FileNotFoundError:
        raise MediaError('missing') from None
    except OSError as error:
        raise MediaError('unreadable', detail=str(error)) from None
    if not stat.S_ISREG(info.st_mode):
        raise MediaError('rejected', detail='no es un archivo regular')
    kind = kind_of(path)
    if not kind:
        raise MediaError('unsupported', detail=path.suffix)
    return MediaSource(path.absolute(), kind, info.st_size, info.st_mtime_ns)


def argument(path):
    """A path mpv and ffmpeg cannot mistake for an option or a URL."""
    text = str(path)
    return text if os.path.isabs(text) else os.path.abspath(text)
