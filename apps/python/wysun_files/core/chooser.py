"""The file chooser's rules (portal and Wysun's own picker), independent of the window that shows them.

A ``ChooserSession`` knows where to start, what to show (folders always; files by name query and the portal's
glob/MIME filters, none in folder mode), and turns a selection or a typed name into a result: an error message,
a request to confirm replacing a file, or the URIs to return. It never writes a file."""
import fnmatch
import os
from pathlib import Path


def byte_path(value):
    """A portal ``ay`` path (NUL-terminated bytes) as text."""
    return os.fsdecode(bytes(value).rstrip(b'\0')) if value else ''


def local_path(value):
    """A local path from a path or ``file://`` URI; other schemes are refused."""
    from urllib.parse import unquote, urlparse
    text = str(value)
    url = urlparse(text)
    if url.scheme and url.scheme != 'file':
        raise ValueError('Solo se admiten ubicaciones locales.')
    return Path(unquote(url.path) if url.scheme == 'file' else text).expanduser().absolute()


class ChooserSession:
    def __init__(self, mode, title, options):
        self.mode = mode                                     # open | save | savefiles
        self.options = dict(options or {})
        initial = byte_path(self.options.get('current_folder'))
        current = byte_path(self.options.get('current_file'))
        if current and Path(current).is_file():
            initial = str(Path(current).parent)
        if not initial or not Path(initial).is_dir():
            initial = str(Path.home())
        self.initial_folder = initial
        # A fixed suffix lets the Hyprland rule float and centre every chooser (see hyprland.lua).
        self.title = (title or ('Guardar archivo' if mode == 'save' else 'Seleccionar archivos')) + ' — Wysun Selector'
        self.directory = bool(self.options.get('directory')) or mode == 'savefiles'
        self.multiple = bool(self.options.get('multiple')) and mode == 'open'
        self.modal = bool(self.options.get('modal', True))
        self.filters = [(str(name), [(int(kind), str(pattern)) for kind, pattern in rules])
                        for name, rules in self.options.get('filters', [])]
        current_filter = self.options.get('current_filter')
        self.filter_index = next((i for i, f in enumerate(self.options.get('filters', [])) if f == current_filter), 0)
        self.choices = [(str(ident), str(label), [(str(v), str(t)) for v, t in entries], str(selected))
                        for ident, label, entries, selected in self.options.get('choices', [])]
        self.accept_label = str(self.options.get('accept_label') or ('Guardar' if mode != 'open' else 'Seleccionar'))
        self.current_name = str(self.options.get('current_name') or (Path(current).name if current else ''))
        self._mime = None

    # -------------------------------------------------------------- filtering
    def rules(self):
        return self.filters[self.filter_index][1] if self.filters else []

    def accepts(self, path, is_dir, query=''):
        """Folders stay navigable; files pass the name query and (any of) the current filter's rules."""
        if is_dir:
            return True
        if self.directory:
            return False
        name = Path(path).name
        if query.casefold() not in name.casefold():
            return False
        rules = self.rules()
        if not rules:
            return True
        for kind, pattern in rules:
            if kind == 0 and fnmatch.fnmatchcase(name, pattern):
                return True
            if kind == 1:
                if self._mime is None:
                    from PySide6.QtCore import QMimeDatabase
                    self._mime = QMimeDatabase()
                from PySide6.QtCore import QMimeDatabase
                mime = self._mime.mimeTypeForFile(str(path), QMimeDatabase.MatchExtension)
                if mime.name() == pattern or mime.inherits(pattern) or fnmatch.fnmatchcase(mime.name(), pattern):
                    return True
        return False

    # -------------------------------------------------------------- resolving
    def resolve(self, folder, selected, name='', replace=False):
        """``('error', text)``, ``('confirm', targets)`` (replace an existing file) or ``('ok', targets)``."""
        folder = Path(folder)
        paths = [str(p) for p in selected or []]
        if self.mode == 'save':
            name = (name or '').strip()
            if not name or Path(name).name != name or name in ('.', '..'):
                return 'error', 'Escribe un nombre de archivo válido.'
            suffix = str(self.options.get('default_suffix', '')).lstrip('.')
            if suffix and not Path(name).suffix:
                name += '.' + suffix
            targets = [folder / name]
            if targets[0].is_dir():
                return 'error', 'El nombre corresponde a una carpeta.'
            if not os.access(str(folder), os.W_OK):
                return 'error', 'No puedes guardar archivos en esta carpeta.'
            if targets[0].exists() and not replace:
                return 'confirm', targets
            return 'ok', targets
        if self.mode == 'savefiles':
            target = local_path(paths[0]) if paths and Path(paths[0]).is_dir() else folder
            targets = []
            for raw in self.options.get('files', []):
                base = Path(byte_path(raw)).name
                if not base or base in ('.', '..'):
                    return 'error', 'Nombre de archivo inválido.'
                candidate, number = target / base, 1
                while candidate.exists() or candidate in targets:
                    candidate = target / f'{Path(base).stem} ({number}){Path(base).suffix}'
                    number += 1
                targets.append(candidate)
            if not os.access(str(target), os.W_OK):
                return 'error', 'No puedes guardar archivos en esta carpeta.'
            return 'ok', targets
        if self.directory and not paths:
            paths = [str(folder)]
        if not paths:
            return 'error', 'Selecciona un archivo.'
        targets = [local_path(p) for p in paths]
        if not self.multiple and len(targets) > 1:
            return 'error', 'Selecciona un solo elemento.'
        if any(not p.exists() or p.is_dir() != self.directory or not os.access(p, os.R_OK) for p in targets):
            return 'error', 'La selección ya no está disponible o no es del tipo solicitado.'
        return 'ok', targets

    def result(self, targets, choice_values=None):
        """``(code, results)`` as the portal replies: 0 with uris (+ current_filter, choices), 1 when cancelled."""
        if not targets:
            return 1, {}
        result = {'uris': [Path(t).as_uri() for t in targets]}
        if self.filters:
            result['current_filter'] = self.filters[self.filter_index]
        values = choice_values or {}
        result['choices'] = [(ident, str(values.get(ident, selected))) for ident, _label, _entries, selected in self.choices]
        return 0, result
