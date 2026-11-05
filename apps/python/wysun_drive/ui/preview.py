"""What the selector knows about a local item: icon, kind, dates, and a preview.

Icons are Nerd Font glyphs (single cells in the packaged CaskaydiaCove). Previews run in a
thread and are cached by ``(path, mtime, size, cols, rows)``: images and the first frame of a
video become half-block cells (``▀`` with the top pixel as foreground and the bottom one as
background) through ``ffmpeg``; text files show their first lines; folders a short count.
Preview pixels are the user's own content, so they are not theme colours (declared exception).
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import threading
import time
from collections import OrderedDict

ICON = {'dir': '', 'pdf': '', 'img': '', 'vid': '', 'audio': '', 'ppt': '',
        'doc': '', 'xls': '', 'zip': '', 'code': '', 'md': '', 'text': '',
        'file': ''}
# Palette role of each kind's icon.
ROLE = {'dir': 'primary', 'pdf': 'error', 'img': 'tertiary', 'vid': 'tertiary', 'audio': 'tertiary',
        'ppt': 'secondary', 'doc': 'primary', 'xls': 'success', 'zip': 'secondary', 'code': 'secondary',
        'md': 'onSurfaceVariant', 'text': 'onSurfaceVariant', 'file': 'onSurfaceVariant'}
EXTENSIONS = {
    'pdf': {'pdf'}, 'img': {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tif', 'tiff', 'heic', 'avif', 'svg'},
    'vid': {'mp4', 'mkv', 'webm', 'mov', 'avi', 'm4v'}, 'audio': {'mp3', 'flac', 'ogg', 'opus', 'wav', 'm4a'},
    'ppt': {'ppt', 'pptx', 'odp', 'key'}, 'doc': {'doc', 'docx', 'odt', 'rtf'}, 'xls': {'xls', 'xlsx', 'ods', 'csv'},
    'zip': {'zip', 'tar', 'gz', 'xz', 'zst', '7z', 'rar', 'bz2', 'deb', 'iso'},
    'code': {'py', 'js', 'ts', 'qml', 'c', 'cpp', 'h', 'rs', 'go', 'java', 'sh', 'lua', 'json', 'toml', 'yaml', 'yml',
             'html', 'css', 'xml', 'sql'},
    'md': {'md', 'markdown'}, 'text': {'txt', 'log', 'ini', 'conf', 'cfg', 'tex'},
}
KIND_NAME = {'dir': 'Carpeta', 'pdf': 'Documento PDF', 'img': 'Imagen', 'vid': 'Video', 'audio': 'Audio',
             'ppt': 'Presentación', 'doc': 'Documento', 'xls': 'Hoja de cálculo', 'zip': 'Archivo comprimido',
             'code': 'Código', 'md': 'Markdown', 'text': 'Texto', 'file': 'Archivo'}
TEXT_KINDS = {'code', 'md', 'text'}
TEXT_LIMIT = 64 * 1024
MONTHS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')
DAYS = ('lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom')


def kind_of(name, is_dir=False):
    if is_dir:
        return 'dir'
    ext = name.rpartition('.')[2].lower() if '.' in name else ''
    if ext == 'csv':
        return 'xls'
    for kind, exts in EXTENSIONS.items():
        if ext in exts:
            return kind
    return 'file'


def describe(name, is_dir=False):
    kind = kind_of(name, is_dir)
    ext = name.rpartition('.')[2].upper() if '.' in name and not is_dir else ''
    return KIND_NAME[kind] + (f' {ext}' if ext and kind in ('img', 'vid', 'audio', 'zip') else '')


def when(timestamp, now=None):
    """``hoy 14:32``, ``ayer``, ``lun 3`` within a week, else ``28 oct`` (``28 oct 2025`` another year)."""
    now = time.time() if now is None else now
    then, today = time.localtime(timestamp), time.localtime(now)
    days = (time.mktime(today[:3] + (0, 0, 0, 0, 0, -1)) - time.mktime(then[:3] + (0, 0, 0, 0, 0, -1))) // 86400
    if days <= 0:
        return time.strftime('hoy %H:%M', then)
    if days == 1:
        return 'ayer'
    if days < 7:
        return f'{DAYS[then.tm_wday]} {then.tm_mday}'
    text = f'{then.tm_mday} {MONTHS[then.tm_mon - 1]}'
    return text if then.tm_year == today.tm_year else f'{text} {then.tm_year}'


def group_of(timestamp, now=None):
    """Recientes groups: Hoy, Ayer, Esta semana, Antes."""
    now = time.time() if now is None else now
    then, today = time.localtime(timestamp), time.localtime(now)
    days = (time.mktime(today[:3] + (0, 0, 0, 0, 0, -1)) - time.mktime(then[:3] + (0, 0, 0, 0, 0, -1))) // 86400
    return 'Hoy' if days <= 0 else 'Ayer' if days == 1 else 'Esta semana' if days < 7 else 'Antes'


def _clean(line):
    return ''.join(ch if ch.isprintable() else ' ' for ch in line.expandtabs(4))


def _media_size(path):
    probe = shutil.which('ffprobe')
    if probe is None:
        return None
    try:
        out = subprocess.run([probe, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                              '-of', 'csv=p=0', '--', path], capture_output=True, text=True, timeout=5).stdout
        width, height = out.strip().split('\n')[0].split(',')[:2]
        return int(width), int(height)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _pixels(path, cols, rows, video):
    """``rows`` lists of ``cols`` pairs ``(top_rgb, bottom_rgb)``, scaled to cover and cropped."""
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        return None
    height = rows * 2
    argv = [ffmpeg, '-v', 'error', *(['-ss', '1'] if video else []), '-i', path, '-frames:v', '1',
            '-vf', f'scale={cols}:{height}:force_original_aspect_ratio=increase,crop={cols}:{height}',
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    try:
        raw = subprocess.run(argv, capture_output=True, timeout=10, stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    if video and len(raw) < cols * height * 3:            # shorter than 1 s: the very first frame
        argv.remove('-ss')
        argv.remove('1')
        try:
            raw = subprocess.run(argv, capture_output=True, timeout=10, stdin=subprocess.DEVNULL).stdout
        except (OSError, subprocess.SubprocessError):
            return None
    if len(raw) < cols * height * 3:
        return None

    def px(x, y):
        i = (y * cols + x) * 3
        return raw[i], raw[i + 1], raw[i + 2]
    return [[(px(x, 2 * r), px(x, 2 * r + 1)) for x in range(cols)] for r in range(rows)]


def build(path, cols, rows):
    """The preview of ``path`` for a ``cols`` × ``rows`` area (runs in a worker thread)."""
    try:
        info = os.stat(path)
    except OSError as error:
        return {'kind': 'error', 'text': f'No se puede leer ({error.strerror})'}
    name = os.path.basename(path)
    if stat.S_ISDIR(info.st_mode):
        dirs = files = total = 0
        try:
            with os.scandir(path) as found:
                for count, entry in enumerate(found):
                    if count >= 5000:
                        break
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            dirs += 1
                        elif entry.is_file(follow_symlinks=False):
                            files += 1
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError as error:
            return {'kind': 'error', 'text': f'No se puede abrir ({error.strerror})'}
        return {'kind': 'dir', 'dirs': dirs, 'files': files, 'total': total}
    kind = kind_of(name)
    if kind in ('img', 'vid') and not name.lower().endswith('.svg'):
        pixels = _pixels(path, cols, rows, kind == 'vid')
        if pixels is not None:
            return {'kind': 'image', 'pixels': pixels, 'dims': _media_size(path)}
        return {'kind': 'none', 'text': 'Sin vista previa (instala ffmpeg o el archivo no se puede leer)'}
    if kind in TEXT_KINDS or info.st_size <= TEXT_LIMIT and kind == 'file':
        try:
            with open(path, 'rb') as stream:
                data = stream.read(TEXT_LIMIT)
            text = data.decode('utf-8')
        except (OSError, UnicodeDecodeError):
            return {'kind': 'none', 'text': ''}
        return {'kind': 'text', 'lines': [_clean(line) for line in text.splitlines()[:rows]]}
    return {'kind': 'none', 'text': ''}


class Previews:
    """Previews built off the loop; ``get`` returns a cached one or None and asks for it once."""

    LIMIT = 64

    def __init__(self, on_ready):
        self.on_ready = on_ready
        self._cache: OrderedDict = OrderedDict()
        self._pending: set = set()
        self._lock = threading.Lock()

    @staticmethod
    def key(path, cols, rows):
        try:
            info = os.stat(path)
            return (path, info.st_mtime_ns, info.st_size, cols, rows)
        except OSError:
            return (path, 0, 0, cols, rows)

    def get(self, path, cols, rows):
        key = self.key(path, cols, rows)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            if key in self._pending:
                return None
            self._pending.add(key)

        def work():
            result = build(path, cols, rows)
            with self._lock:
                self._pending.discard(key)
                self._cache[key] = result
                while len(self._cache) > self.LIMIT:
                    self._cache.popitem(last=False)
            self.on_ready()

        threading.Thread(target=work, daemon=True).start()
        return None
