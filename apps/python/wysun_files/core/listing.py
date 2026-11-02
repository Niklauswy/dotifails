"""What a folder shows, without Qt: entries, their kind (icon, badge, colour role, chip group), the Spanish
texts of the views (dates, sizes, counts, summary), sorting and filtering. The QML model (``quick/folder.py``)
runs this in a worker thread and only keeps the result."""
from dataclasses import dataclass
from datetime import datetime
import itertools
import os
from pathlib import Path
import re
import unicodedata

from wysun_services.file_media import AUDIO, CODE, IMAGES, VIDEOS
from wysun_files.kinds import ARCHIVES, FONTS, MARKDOWN, NOTES, SCRIPTS, SHEETS, SLIDES, TEXTS, describe

DOCUMENTS = {'.pdf', '.doc', '.docx', '.odt', '.rtf', '.txt', '.md', '.markdown', '.rst', '.csv', '.xls', '.xlsx',
             '.ods', '.ppt', '.pptx', '.odp', '.tex'}
GROUPS = ('all', 'folders', 'images', 'videos', 'audio', 'documents', 'code')
SORT_KEYS = ('name', 'modified', 'size', 'kind')
MONTHS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')
SNIPPET_LINES, SNIPPET_WIDTH, SNIPPET_BYTES = 6, 48, 1024
SNIPPET_LIMIT = 4 * 1024 * 1024        # larger «text» files are not peeked at
# Folder glyphs by name (case-insensitive), besides the XDG places the caller passes as ``special``.
GLYPHS = {'descargas': 'download', 'downloads': 'download', 'música': 'music_note', 'music': 'music_note',
          'imágenes': 'image', 'pictures': 'image', 'fotos': 'photo_camera', 'photos': 'photo_camera',
          'vídeos': 'movie', 'videos': 'movie', 'documentos': 'description', 'documents': 'description',
          'escritorio': 'desktop_windows', 'desktop': 'desktop_windows', 'repos': 'code', 'src': 'code', 'code': 'code',
          'git': 'code', 'proyectos': 'rocket_launch', 'projects': 'rocket_launch', 'latex': 'functions',
          'clases': 'school', 'universidad': 'school', 'plantillas': 'dashboard', 'templates': 'dashboard',
          'público': 'public', 'public': 'public', 'juegos': 'sports_esports', 'games': 'sports_esports',
          'libros': 'menu_book', 'books': 'menu_book', 'backup': 'backup', 'respaldos': 'backup'}


@dataclass(frozen=True)
class Entry:
    name: str
    path: str
    is_dir: bool
    hidden: bool
    symlink: bool
    size: int
    modified: float


@dataclass(frozen=True)
class Kind:
    kind: str           # folder image video audio pdf md doc code archive other (the mock-up's icon families)
    icon: str           # Material symbol
    role: str           # M3 colour role of the badge/emblem: primary secondary tertiary error
    badge: str          # extension band on document icons ('' for folders and media)
    group: str          # filter chip: images videos audio documents code ('' = only «Todo»)
    label: str          # Spanish type name (list column, properties)


def scan(folder):
    """Every entry of ``folder`` (hidden ones flagged); raises OSError when the folder cannot be read."""
    out = []
    with os.scandir(folder) as entries:
        for item in entries:
            try:
                symlink = item.is_symlink()
                try:
                    stat = item.stat()                     # follows links: a link to a folder is a folder
                    is_dir = item.is_dir()
                except OSError:                           # broken link: show the link itself
                    stat, is_dir = item.stat(follow_symlinks=False), False
            except OSError:
                continue                                   # vanished while listing
            out.append(Entry(item.name, item.path, is_dir, item.name.startswith('.'), symlink,
                             0 if is_dir else stat.st_size, stat.st_mtime))
    return out


def _suffix(name):
    return Path(name).suffix.lower()


def classify(name, is_dir):
    if is_dir:
        return Kind('folder', 'folder', 'secondary', '', 'folders', 'Carpeta')
    suffix = _suffix(name)
    label = describe(name, is_dir=False)[2]
    badge = suffix[1:5].upper()
    if suffix in IMAGES:
        return Kind('image', 'image', 'tertiary', '', 'images', label)
    if suffix in VIDEOS:
        return Kind('video', 'movie', 'tertiary', '', 'videos', label)
    if suffix in AUDIO:
        return Kind('audio', 'music_note', 'primary', '', 'audio', label)
    if suffix == '.pdf':
        return Kind('pdf', 'picture_as_pdf', 'error', 'PDF', 'documents', label)
    if suffix in MARKDOWN:
        return Kind('md', 'article', 'primary', 'MD', 'documents', label)
    if suffix in CODE or suffix in SCRIPTS:
        return Kind('code', 'code', 'tertiary', badge, 'code', label)
    if suffix in ARCHIVES:
        return Kind('archive', 'folder_zip', 'secondary', badge, '', label)
    if suffix in DOCUMENTS or suffix in TEXTS or suffix in NOTES or suffix in SHEETS or suffix in SLIDES:
        return Kind('doc', describe(name, is_dir=False)[0], 'primary', badge, 'documents', label)
    if suffix in FONTS:
        return Kind('other', 'font_download', 'secondary', badge, '', label)
    return Kind('other', describe(name, is_dir=False)[0], 'secondary', badge, '', label)


def folder_glyph(path, name, special=None):
    """The glyph drawn inside a special folder's icon ('' for an ordinary folder)."""
    if special and path in special:
        return special[path]
    return GLYPHS.get(name.casefold(), '')


# ---------------------------------------------------------------------------------------------- texts
def modified_text(timestamp, now=None):
    """«hoy», «ayer», «hace 3 días» within a week, «2 oct» this year, «may 2025» before."""
    now = datetime.now().timestamp() if now is None else now
    then, today = datetime.fromtimestamp(timestamp), datetime.fromtimestamp(now)
    days = (today.date() - then.date()).days
    if days == 0:
        return 'hoy'
    if days == 1:
        return 'ayer'
    if 1 < days < 7:
        return f'hace {days} días'
    if then.year == today.year:
        return f'{then.day} {MONTHS[then.month - 1]}'
    return f'{MONTHS[then.month - 1]} {then.year}'


def full_date(timestamp):
    then = datetime.fromtimestamp(timestamp)
    return f'{then.day} {MONTHS[then.month - 1]} {then.year}, {then:%H:%M}'


def size_text(size):
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:.0f} B' if unit == 'B' else f'{value:.1f} {unit}'.replace('.', ',')
        value /= 1024
    return ''


def count_text(count, capped=False):
    if capped:
        return f'Más de {count} elementos'
    if count == 0:
        return 'Vacía'
    return '1 elemento' if count == 1 else f'{count} elementos'


def _plural(count, one, many):
    return f'{count} {one if count == 1 else many}'


def summary(entries):
    """«6 carpetas · 8 archivos · 1,3 GB» (sizes of the files only)."""
    folders = sum(1 for e in entries if e.is_dir)
    files = [e for e in entries if not e.is_dir]
    parts = []
    if folders:
        parts.append(_plural(folders, 'carpeta', 'carpetas'))
    if files:
        parts.append(_plural(len(files), 'archivo', 'archivos'))
        parts.append(size_text(sum(e.size for e in files)))
    return ' · '.join(parts) or 'Vacía'


def dominant(entries):
    """The chip group most of the files belong to ('folders' when there are only folders, '' when nothing stands
    out): the folder header picks its emblem from it."""
    counts = {}
    for entry in entries:
        if not entry.is_dir:
            group = classify(entry.name, False).group
            if group:
                counts[group] = counts.get(group, 0) + 1
    if counts:
        return max(sorted(counts), key=counts.get)
    return 'folders' if any(e.is_dir for e in entries) else ''


# ---------------------------------------------------------------------------------------------- order
def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


_NUMBER = re.compile(r'(\d+)')


def natural(name):
    """Case- and accent-insensitive, numbers by value («b2» before «b10»)."""
    return [(0, int(part), '') if part.isdigit() else (1, 0, part) for part in _NUMBER.split(fold(name)) if part]


def arrange(entries, key='name', descending=False, hidden=False, text='', group='all', accept=None):
    """The rows a view shows: folders first, then files, each sorted by ``key``. ``text`` filters names (folders
    too); ``group`` and ``accept`` (the chooser's portal filters) never hide folders, except that «Carpetas» shows
    only them."""
    wanted = fold(text.strip())
    rows = []
    for entry in entries:
        if entry.hidden and not hidden:
            continue
        if wanted and wanted not in fold(entry.name):
            continue
        if not entry.is_dir:
            if group == 'folders' or (group not in ('all', '', None) and classify(entry.name, False).group != group):
                continue
            if accept is not None and not accept(entry):
                continue
        rows.append(entry)

    def order(entry):
        name = natural(entry.name)
        if key == 'size':
            return (entry.size, name)
        if key == 'modified':
            return (entry.modified, name)
        if key == 'kind':
            return (fold(classify(entry.name, entry.is_dir).label), name)
        return (name,)

    folders = sorted((e for e in rows if e.is_dir), key=order, reverse=descending)
    files = sorted((e for e in rows if not e.is_dir), key=order, reverse=descending)
    return folders + files


# ---------------------------------------------------------------------------------------------- peeking
def snippet(path):
    """The first lines of a text file for its icon (``[]`` for binary, unreadable or huge files)."""
    try:
        if os.path.getsize(path) > SNIPPET_LIMIT:
            return []
        with open(path, 'rb') as handle:
            raw = handle.read(SNIPPET_BYTES)
    except OSError:
        return []
    if b'\0' in raw:
        return []
    text = raw.decode('utf-8', errors='replace').expandtabs(4)
    return [line.rstrip()[:SNIPPET_WIDTH] for line in text.splitlines()[:SNIPPET_LINES]]


def child_count(path, limit=5000):
    """``(entries, capped)`` of a folder; ``(0, False)`` when it cannot be read."""
    try:
        with os.scandir(path) as entries:
            count = sum(1 for _ in itertools.islice(entries, limit + 1))
    except OSError:
        return 0, False
    return (limit, True) if count > limit else (count, False)
