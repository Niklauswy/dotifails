"""What the inspector and the expanded preview show (F-50…F-55), computed off the GUI thread: the kind of preview
(image, video, audio, pdf, markdown, code, text, or none), the label/value pairs of the mock-ups, the picture or
media URL, the text and its HTML (code highlighted and Markdown rendered with the theme colours QML passes in),
and the summaries of a folder or of a multiple selection. Only the latest selection is ever shown."""
import hashlib
from html import escape
import json
import os
from pathlib import Path
import subprocess
import threading

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QImageReader

from wysun_core import paths as core_paths
from wysun_files import highlight, markdown
from wysun_files.core import listing
from wysun_files.kinds import preview_kind
from wysun_player.client import launch
from wysun_services.file_media import probe_media

TEXT_LIMIT = 512 * 1024
FOLDER_WALK_LIMIT = 20_000
LANGUAGES = {'python': 'Python', 'javascript': 'JavaScript', 'typescript': 'TypeScript', 'clike': 'C', 'rust': 'Rust',
             'go': 'Go', 'java': 'Java', 'shell': 'Shell', 'config': 'Configuración', 'css': 'CSS', 'markup': 'HTML',
             'lua': 'Lua', 'sql': 'SQL', 'json': 'JSON', 'plain': 'Texto'}
PLURALS = {'image': ('imagen', 'imágenes'), 'video': ('vídeo', 'vídeos'), 'audio': ('audio', 'audios'),
           'pdf': ('PDF', 'PDF'), 'md': ('documento', 'documentos'), 'doc': ('documento', 'documentos'),
           'code': ('archivo de código', 'archivos de código'), 'archive': ('archivo comprimido', 'archivos comprimidos'),
           'folder': ('carpeta', 'carpetas'), 'other': ('archivo', 'archivos')}
BROKEN = {'image': 'No se pudo abrir la imagen. El archivo sigue seleccionado.',
          'pdf': 'No se pudo abrir el PDF. El archivo sigue seleccionado.',
          'video': 'No se pudo leer el vídeo. El archivo sigue seleccionado.',
          'audio': 'No se pudo leer el audio. El archivo sigue seleccionado.'}


def _row(label, value):
    return {'label': label, 'value': value}


def _home(path):
    home = str(Path.home())
    return '~' + path[len(home):] if path == home or path.startswith(home + '/') else path


def _code_html(text, language, colours):
    """``highlight.highlight_html`` with the theme's colours (role colours from QML, never literals here)."""
    out, state = [], None
    for line in text.split('\n'):
        spans, state = highlight.tokenize(line, language, state)
        cursor, parts = 0, []
        for start, end, kind in sorted(spans):
            if start < cursor:
                continue
            parts.append(escape(line[cursor:start]))
            style = f'color:{colours.get(kind, colours.get("text", ""))};'
            if kind == 'keyword':
                style += 'font-weight:600;'
            if kind in ('comment', 'meta'):
                style += 'font-style:italic;'
            parts.append(f'<span style="{style}">{escape(line[start:end])}</span>')
            cursor = end
        parts.append(escape(line[cursor:]))
        out.append(''.join(parts))
    return '<br>'.join(out).replace('  ', '&nbsp; ')


def _markdown_html(text, colours):
    ink = {k: colours.get(k, '') for k in ('link', 'code_bg', 'code_fg', 'mono', 'muted')}
    _front, body = markdown.split_front_matter(text)

    def blocks(items):
        html = []
        for block in items:
            kind = block['t']
            if kind == 'heading':
                level = block['level']
                size = {1: 140, 2: 125, 3: 112}.get(level, 100)      # percent of the body text
                html.append(f'<h{level} style="font-size:{size}%;">{markdown.inline(escape(block["text"]), ink)}</h{level}>')
            elif kind == 'para':
                html.append(f'<p>{markdown.inline(escape(block["text"]), ink).replace(chr(10), "<br>")}</p>')
            elif kind == 'code':
                language = highlight.language_for_fence(block.get('lang'))
                html.append(f'<pre style="background-color:{ink["code_bg"]};font-family:{ink["mono"]};">'
                            f'{_code_html(block["text"], language, colours)}</pre>')
            elif kind == 'quote':
                html.append(f'<blockquote style="color:{ink["muted"]};">{blocks(block["children"])}</blockquote>')
            elif kind == 'list':
                tag = 'ol' if block['ordered'] else 'ul'
                items_html = []
                for item in block['items']:
                    mark = '' if item.get('task') is None else ('☑ ' if item['task'] else '☐ ')
                    inner = blocks(item['children'])
                    if inner.startswith('<p>') and inner.count('<p>') == 1:
                        inner = inner[3:-4]
                    items_html.append(f'<li>{mark}{inner}</li>')
                start = f' start="{block["start"]}"' if block['ordered'] and block['start'] != 1 else ''
                html.append(f'<{tag}{start}>{"".join(items_html)}</{tag}>')
            elif kind == 'table':
                head = ''.join(f'<th>{markdown.inline(escape(c), ink)}</th>' for c in block['head'])
                rows = ''.join('<tr>' + ''.join(f'<td>{markdown.inline(escape(c), ink)}</td>' for c in row) + '</tr>'
                               for row in block['rows'])
                html.append(f'<table cellpadding="4"><tr>{head}</tr>{rows}</table>')
            elif kind == 'rule':
                html.append('<hr>')
            elif kind == 'image':
                html.append(f'<p style="color:{ink["muted"]};">[{escape(block["alt"] or "imagen")}]</p>')
        return ''.join(html)

    return blocks(markdown.parse(body))


def _pdf_page(path, cache, mtime, page=1):
    """A page of a PDF as a PNG in the cache (pdftoppm), and its page count (pdfinfo)."""
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f'{path}\0{mtime}\0{page}'.encode()).hexdigest()
    target = cache / f'{key}.png'
    if not target.is_file():
        done = subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page), '-singlefile', '-scale-to', '1200', '-png', path,
                               str(cache / key)], capture_output=True, timeout=15, check=False)
        if done.returncode != 0 or not target.is_file():
            return '', 0
    pages = 0
    try:
        info = subprocess.run(['pdfinfo', path], capture_output=True, text=True, timeout=5, check=False,
                              env=dict(os.environ, LC_ALL='C'))
        for line in info.stdout.splitlines():
            if line.startswith('Pages:'):
                pages = int(line.split(':', 1)[1])
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return str(target), pages


def _tags(path):
    """``(title, artist)`` of a media file ('' when it has none)."""
    try:
        done = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format_tags=title,artist', '-of', 'json', path],
                              capture_output=True, text=True, timeout=5, check=False)
        tags = {k.lower(): v for k, v in json.loads(done.stdout or '{}').get('format', {}).get('tags', {}).items()}
    except (OSError, subprocess.SubprocessError, ValueError):
        return '', ''
    return tags.get('title', ''), tags.get('artist', '')


def _poster(path, cache, mtime, kind='video'):
    """A video's frame or a song's cover for the player (as its thumbnail), as a PNG in the cache ('' when none)."""
    from .thumbs import make
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (hashlib.md5(f'{path}\0{mtime}\0poster'.encode()).hexdigest() + '.png')
    if not target.is_file():
        image, _extra = make(path, kind)
        if image.isNull() or not image.save(str(target), 'PNG'):
            return ''
    return QUrl.fromLocalFile(str(target)).toString()


def _folder_summary(path):
    """Direct contents, their total size (walking at most FOLDER_WALK_LIMIT entries) and the pictures in it."""
    folders = files = images = 0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    folders += 1
                else:
                    files += 1
                    if listing.classify(entry.name, False).kind == 'image':
                        images += 1
    except OSError:
        pass
    total, seen, capped = 0, 0, False
    for base, dirs, names in os.walk(path):
        for name in names:
            seen += 1
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
        seen += len(dirs)
        if seen > FOLDER_WALK_LIMIT:
            capped = True
            break
    parts = [p for p in ((f'{folders} carpeta' if folders == 1 else f'{folders} carpetas') if folders else '',
                         (f'{files} archivo' if files == 1 else f'{files} archivos') if files else '') if p]
    rows = [_row('Contiene', ' · '.join(parts) or 'Nada'), _row('Tamaño', ('más de ' if capped else '') + listing.size_text(total))]
    if images:
        rows.append(_row('Imágenes', str(images)))
    return rows


def describe(paths, colours, cache, page=1):
    """Everything a selection shows. Runs in a worker thread."""
    if not paths:
        return {'mode': 'none'}
    if len(paths) > 1:
        total, kinds = 0, {}
        for path in paths:
            try:
                info = os.lstat(path)
            except OSError:
                continue
            is_dir = os.path.isdir(path)
            total += 0 if is_dir else info.st_size
            kind = listing.classify(os.path.basename(path), is_dir).kind
            kinds[kind] = kinds.get(kind, 0) + 1
        order = sorted(kinds, key=lambda k: (-kinds[k], k))
        types = ' · '.join(f'{kinds[k]} {PLURALS[k][0] if kinds[k] == 1 else PLURALS[k][1]}' for k in order)
        return {'mode': 'multi', 'name': f'{len(paths)} elementos', 'subtitle': listing.size_text(total),
                'meta': [_row('Tamaño', listing.size_text(total)), _row('Tipos', types)]}
    path = paths[0]
    target = Path(path)
    try:
        info = target.stat()
    except OSError:
        return {'mode': 'file', 'name': target.name, 'error': 'El archivo ya no existe.', 'meta': []}
    location = _home(str(target.parent))
    if target.is_dir():
        return {'mode': 'folder', 'name': target.name or '/', 'subtitle': 'Carpeta',
                'meta': _folder_summary(path) + [_row('Ruta', path)]}
    kind_info = listing.classify(target.name, False)
    size = listing.size_text(info.st_size)
    data = {'mode': 'file', 'name': target.name, 'subtitle': f'{kind_info.label} · {size}', 'icon': kind_info.icon,
            'fileKind': kind_info.kind, 'badge': kind_info.badge, 'role': kind_info.role}
    kind = preview_kind(path)
    meta = [_row('Tamaño', size), _row('Modificado', listing.full_date(info.st_mtime)), _row('Ruta', path)]
    url = QUrl.fromLocalFile(path).toString()
    if kind == 'image':
        reader = QImageReader(path)
        dims = reader.size()
        if not reader.canRead() or not dims.isValid() or dims.width() <= 0:
            data['error'] = BROKEN['image']
        else:
            meta[0] = _row('Tamaño', f'{size} · {dims.width()} × {dims.height()}')
            data['imageUrl'] = url
    elif kind in ('video', 'audio'):
        probe = probe_media(path)
        if not probe.get('duration') and not probe.get('codec_name') and not probe.get('audio_codec'):
            data['error'] = BROKEN[kind]
        else:
            from wysun_services.file_media import duration_label
            parts = [duration_label(probe.get('duration', 0))]
            codec = probe.get('codec_name') if kind == 'video' else probe.get('audio_codec')
            if codec:
                parts.append(codec.upper())
            if kind == 'video' and probe.get('width'):
                parts.append(f'{probe["width"]} × {probe["height"]}')
            meta.insert(0, _row('Duración', ' · '.join(parts)))
            data['duration'] = float(probe.get('duration', 0))
            data['mediaUrl'] = url
            data['posterUrl'] = _poster(path, cache, info.st_mtime, kind)
            data['mediaTitle'], data['mediaArtist'] = _tags(path)
    elif kind == 'pdf':
        picture, pages = _pdf_page(path, cache, info.st_mtime, page)
        if picture:
            data['imageUrl'] = QUrl.fromLocalFile(picture).toString()
            data['page'], data['pages'] = page, pages or 1
            meta.insert(1, _row('Páginas', str(pages or 1)))
        else:
            data['error'] = BROKEN['pdf']
    elif kind in ('markdown', 'code', 'text'):
        try:
            with open(path, 'rb') as handle:
                raw = handle.read(TEXT_LIMIT + 1)
        except OSError:
            raw = b'\0'
        if b'\0' in raw[:4096]:
            kind = ''
        else:
            text = raw[:TEXT_LIMIT].decode('utf-8', errors='replace')
            data['text'] = text
            data['truncated'] = len(raw) > TEXT_LIMIT
            data['lineCount'] = text.count('\n') + (0 if text.endswith('\n') else 1)
            if kind == 'code':
                language = highlight.language_for_path(path)
                meta[0] = _row('Tamaño', f'{size} · {LANGUAGES.get(language, language.capitalize())}')
                data['html'] = _code_html(text.rstrip('\n'), language, colours)
            elif kind == 'markdown':
                data['html'] = _markdown_html(text, colours)
    data['kind'] = kind
    data['meta'] = meta
    data['location'] = location
    return data


class _Relay(QObject):
    done = Signal(int, object)


class Preview(QObject):
    changed = Signal()
    loadingChanged = Signal()

    def __init__(self, cache=None, parent=None):
        super().__init__(parent)
        self.cache = Path(cache) if cache else core_paths.cache('wysun', 'files-preview')
        self._data, self._paths, self._colours = {'mode': 'none'}, [], {}
        self._generation, self._loading = 0, False
        self._relay = _Relay(self)
        self._relay.done.connect(self._done, Qt.QueuedConnection)
        self._debounce = QTimer(self, singleShot=True, interval=90)
        self._debounce.timeout.connect(self._load)
        self._closed = False
        self._page = 1

    @Slot('QVariantList')
    def setSelection(self, paths):
        paths = [str(p) for p in paths]
        if paths == self._paths and not self._loading:
            return
        if paths != self._paths:
            self._page = 1
        self._paths = paths
        self._generation += 1
        if not paths:
            self._debounce.stop()
            self._data = {'mode': 'none'}
            self._set_loading(False)
            self.changed.emit()
            return
        self._set_loading(True)
        self._debounce.start()

    @Slot(int)
    def setPage(self, page):
        """Show another page of the PDF on view."""
        if 1 <= page <= int(self._data.get('pages', 1)) and page != self._page:
            self._page = page
            self._generation += 1
            self._set_loading(True)
            self._debounce.start()

    @Slot('QVariantMap')
    def setColors(self, colours):
        """Role colours for code and Markdown (``keyword``, ``string``… ``link``, ``code_bg``, ``mono``)."""
        self._colours = {k: (v.name() if hasattr(v, 'name') else str(v)) for k, v in dict(colours).items()}
        if self._paths and self._data.get('html'):
            self._generation += 1
            self._set_loading(True)
            self._debounce.start()

    def _set_loading(self, value):
        if value != self._loading:
            self._loading = value
            self.loadingChanged.emit()

    def _load(self):
        generation, paths, colours, relay, cache, page = (self._generation, list(self._paths), dict(self._colours), self._relay,
                                                          self.cache, self._page)

        def work():
            try:
                data = describe(paths, colours, cache, page)
            except Exception as error:               # a preview never takes the window down
                data = {'mode': 'file', 'name': os.path.basename(paths[0]), 'error': f'No se pudo leer el archivo: {error}',
                        'meta': []}
            data['paths'] = paths
            relay.done.emit(generation, data)

        threading.Thread(target=work, name='wysun-files-preview', daemon=True).start()

    @Slot(int, object)
    def _done(self, generation, data):
        if generation != self._generation or self._closed:
            return
        self._data = data
        self._set_loading(False)
        self.changed.emit()

    def _get(self, key, default=''):
        return self._data.get(key, default)

    @Property('QVariantList', notify=changed)
    def paths(self):
        return list(self._data.get('paths', []))

    @Property(str, notify=changed)
    def mode(self):
        return self._get('mode', 'none')

    @Property(str, notify=changed)
    def kind(self):
        return self._get('kind')

    @Property(str, notify=changed)
    def fileKind(self):
        return self._get('fileKind', 'other')

    @Property(str, notify=changed)
    def icon(self):
        return self._get('icon', 'draft')

    @Property(str, notify=changed)
    def badge(self):
        return self._get('badge')

    @Property(str, notify=changed)
    def role(self):
        return self._get('role', 'primary')

    @Property(str, notify=changed)
    def name(self):
        return self._get('name')

    @Property(str, notify=changed)
    def subtitle(self):
        return self._get('subtitle')

    @Property('QVariantList', notify=changed)
    def meta(self):
        return list(self._get('meta', []))

    @Property(str, notify=changed)
    def imageUrl(self):
        return self._get('imageUrl')

    @Property(int, notify=changed)
    def page(self):
        return int(self._get('page', 1))

    @Property(int, notify=changed)
    def pages(self):
        return int(self._get('pages', 1))

    @Property(str, notify=changed)
    def mediaTitle(self):
        return self._get('mediaTitle')

    @Property(str, notify=changed)
    def mediaArtist(self):
        return self._get('mediaArtist')

    @Property(str, notify=changed)
    def posterUrl(self):
        return self._get('posterUrl')

    @Property(str, notify=changed)
    def mediaUrl(self):
        return self._get('mediaUrl')

    @Property(float, notify=changed)
    def duration(self):
        return float(self._get('duration', 0.0))

    @Property(str, notify=changed)
    def text(self):
        return self._get('text')

    @Property(str, notify=changed)
    def html(self):
        return self._get('html')

    @Property(bool, notify=changed)
    def truncated(self):
        return bool(self._get('truncated', False))

    @Property(int, notify=changed)
    def lineCount(self):
        return int(self._get('lineCount', 0))

    @Property(str, notify=changed)
    def error(self):
        return self._get('error')

    @Property(bool, notify=loadingChanged)
    def loading(self):
        return self._loading

    @Slot(str, result=str)
    def resolveLink(self, href):
        """A link of the Markdown preview: an http(s) URL as it is, a local one as an absolute path ('' for anchors)."""
        if not href or href.startswith('#'):
            return ''
        url = QUrl(href)
        if url.scheme() in ('http', 'https', 'mailto'):
            return href
        if url.isLocalFile():
            return url.toLocalFile()
        base = os.path.dirname(self._paths[0]) if self._paths else ''
        return os.path.normpath(os.path.join(base, href.split('#', 1)[0]))

    @Slot(str, float)
    def continueInPlayer(self, path, seconds):
        """«Seguir en Wysun Player»: the same file from the same second (F-53)."""
        launch([path], start=max(0.0, seconds))

    @Slot()
    def close(self):
        self._closed = True
        self._debounce.stop()
