"""The folder a Files tab shows, as a QML list model.

The folder is read in a worker thread (``core.listing.scan``); the GUI thread only arranges the result. Changes on
disk (``QFileSystemWatcher``), sorting and filtering are applied as row removals, insertions and data changes,
never as a reset, so views keep their selection, current row and scroll. The selection lives here, keyed by path.
Folder counts and text snippets are read lazily for the rows a view asks about; thumbnails come from
``thumbs.Thumbnails``.
"""
import os
import threading

from PySide6.QtCore import (Property, QAbstractListModel, QByteArray, QFileSystemWatcher, QModelIndex, QObject,
                            QRunnable, QThreadPool, QTimer, Qt, Signal, Slot)

from wysun_files.core import listing
from wysun_qml.engine import collect_on_gui_thread

NAMES = ('path', 'name', 'isDir', 'kind', 'icon', 'glyph', 'role', 'badge', 'label', 'group', 'ext', 'size',
         'sizeText', 'modified', 'modifiedText', 'detail', 'snippet', 'thumb', 'duration', 'selected', 'cut', 'hidden',
         'symlink')
ROLES = {Qt.UserRole + i: name for i, name in enumerate(NAMES)}
TEXT_KINDS = {'md', 'code', 'doc'}
NO_SNIPPET = {'.pdf', '.doc', '.docx', '.odt', '.rtf', '.xls', '.xlsx', '.ods', '.ppt', '.pptx', '.odp'}

_PEEKS = QThreadPool()
_PEEKS.setMaxThreadCount(2)


class _Relay(QObject):
    listed = Signal(int, str, object)            # generation, root, entries or error text
    peeked = Signal(str, float, object)          # path, mtime, (count text) or [lines]


class _Peek(QRunnable):
    def __init__(self, entry, relay, cancelled):
        super().__init__()
        self.entry, self.relay, self.cancelled = entry, relay, cancelled

    def run(self):
        if self.cancelled.is_set():
            return
        entry = self.entry
        if entry.is_dir:
            count, capped = listing.child_count(entry.path)
            value = listing.count_text(count, capped)
        else:
            value = listing.snippet(entry.path)
        if not self.cancelled.is_set():
            self.relay.peeked.emit(entry.path, entry.modified, value)


def _error_text(error):
    if isinstance(error, FileNotFoundError):
        return 'Esta carpeta no existe o ya no está'
    if isinstance(error, PermissionError):
        return 'No tienes permiso para abrir esta carpeta'
    if isinstance(error, NotADirectoryError):
        return 'No es una carpeta'
    return f'No se pudo leer la carpeta: {error.strerror or error}'


class FolderModel(QAbstractListModel):
    loaded = Signal(str)                    # the first listing of a root is in (reselect, ShowItems…)
    stateChanged = Signal()                 # root, loading, error
    rowsChanged = Signal()                  # count, total, summary
    orderChanged = Signal()                 # sortKey, descending, filterText, group, showHidden
    selectionChanged = Signal()
    currentRowChanged = Signal()

    def __init__(self, thumbs=None, special=None, parent=None):
        super().__init__(parent)
        collect_on_gui_thread()                  # this model lists folders in worker threads
        self.thumbs = thumbs
        self.special = dict(special or {})       # path -> glyph (XDG places)
        self._root, self._error, self._loading = '', '', False
        self._entries, self._rows, self._index = [], [], {}
        self._key, self._descending, self._text, self._group, self._hidden = 'name', False, '', 'all', False
        self._accept = None
        self._selected, self._anchor, self._current = set(), '', ''
        self._cut = set()
        self._peeked, self._peeking = {}, set()
        self._kinds = {}
        self._generation = 0
        self._fresh = False                       # the next listing is a new root (reset + loaded)
        self._cancelled = threading.Event()
        self._relay = _Relay(self)
        self._relay.listed.connect(self._listed, Qt.QueuedConnection)
        self._relay.peeked.connect(self._peeked_in, Qt.QueuedConnection)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._disk_changed)
        self._debounce = QTimer(self, singleShot=True, interval=120)
        self._debounce.timeout.connect(self.refresh)
        if thumbs is not None:
            thumbs.ready.connect(self._thumb_ready)

    # ------------------------------------------------------------------ model
    def roleNames(self):
        return {role: QByteArray(name.encode()) for role, name in ROLES.items()}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def _kind(self, entry):
        kind = self._kinds.get(entry.path)
        if kind is None or kind[0] != entry.is_dir:
            kind = (entry.is_dir, listing.classify(entry.name, entry.is_dir))
            self._kinds[entry.path] = kind
        return kind[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self.value(self._rows[index.row()], ROLES.get(role, 'name' if role == Qt.DisplayRole else ''))

    def value(self, entry, name):
        if name == 'path':
            return entry.path
        if name == 'name':
            return entry.name
        if name == 'isDir':
            return entry.is_dir
        if name in ('kind', 'icon', 'role', 'badge', 'label', 'group'):
            return getattr(self._kind(entry), name)
        if name == 'glyph':
            return listing.folder_glyph(entry.path, entry.name, self.special) if entry.is_dir else ''
        if name == 'ext':
            return os.path.splitext(entry.name)[1][1:].lower()
        if name == 'size':
            return float(entry.size)
        if name == 'sizeText':
            return '' if entry.is_dir else listing.size_text(entry.size)
        if name == 'modified':
            return entry.modified
        if name == 'modifiedText':
            return listing.modified_text(entry.modified)
        if name == 'detail':
            return self._peek(entry) or '' if entry.is_dir else listing.size_text(entry.size)
        if name == 'snippet':
            kind = self._kind(entry)
            if entry.is_dir or kind.kind not in TEXT_KINDS or os.path.splitext(entry.name)[1].lower() in NO_SNIPPET:
                return []
            return self._peek(entry) or []
        if name == 'thumb':
            return self.thumbs.url(entry.path, entry.modified, self._kind(entry).kind) if self.thumbs else ''
        if name == 'duration':
            return self.thumbs.length(entry.path, entry.modified) if self.thumbs else ''
        if name == 'selected':
            return entry.path in self._selected
        if name == 'cut':
            return entry.path in self._cut
        if name == 'hidden':
            return entry.hidden
        if name == 'symlink':
            return entry.symlink
        return None

    def _peek(self, entry):
        known = self._peeked.get(entry.path)
        if known is not None and known[0] == entry.modified:
            return known[1]
        if entry.path not in self._peeking and not self._cancelled.is_set():
            self._peeking.add(entry.path)
            _PEEKS.start(_Peek(entry, self._relay, self._cancelled))
        return None

    @Slot(str, float, object)
    def _peeked_in(self, path, mtime, value):
        self._peeking.discard(path)
        self._peeked[path] = (mtime, value)
        self._row_changed(path, ('detail', 'snippet'))

    @Slot(str)
    def _thumb_ready(self, path):
        self._row_changed(path, ('thumb', 'duration'))

    def _row_changed(self, path, names):
        row = self._index.get(path)
        if row is not None:
            index = self.index(row)
            self.dataChanged.emit(index, index, [r for r, n in ROLES.items() if n in names])

    # ------------------------------------------------------------------ loading
    @Slot(str, result=bool)
    def setRoot(self, path):
        """Show ``path``; False (and nothing changes) for a file, False with the error state for a missing folder."""
        path = os.path.abspath(os.path.expanduser(path)) if path else ''
        if not path:
            return False
        if os.path.exists(path) and not os.path.isdir(path):
            return False
        if self._root and self._root in self._watcher.directories():
            self._watcher.removePath(self._root)
        self._root = path
        self._kinds.clear()
        self._peeked.clear()
        self._selected.clear()
        self._anchor = self._current = ''
        self._fresh = True
        if not os.path.isdir(path):
            self._fail(FileNotFoundError(path))
            self.selectionChanged.emit()
            return False
        if os.access(path, os.R_OK | os.X_OK):
            self._watcher.addPath(path)
        self._start()
        self.selectionChanged.emit()
        return True

    @Slot()
    def refresh(self):
        """Read the folder again and apply the differences."""
        if self._root:
            if self._root not in self._watcher.directories() and os.access(self._root, os.R_OK | os.X_OK):
                self._watcher.addPath(self._root)
            self._start()

    def _start(self):
        self._generation += 1
        generation, root, relay = self._generation, self._root, self._relay
        self._set_loading(True)

        def work():
            try:
                result = listing.scan(root)
            except OSError as error:
                result = error
            relay.listed.emit(generation, root, result)

        threading.Thread(target=work, name='wysun-files-scan', daemon=True).start()

    @Slot(int, str, object)
    def _listed(self, generation, root, result):
        if generation != self._generation or root != self._root:
            return                                 # a newer listing is on its way
        if isinstance(result, OSError):
            self._fail(result)
            return
        self._error = ''
        self._entries = result
        if self._fresh:
            self._fresh = False
            self.beginResetModel()
            self._rows = self._arranged()
            self._reindex()
            self.endResetModel()
            self._set_loading(False)
            self.rowsChanged.emit()
            self.currentRowChanged.emit()
            self.loaded.emit(root)
        else:
            self._apply()
            self._set_loading(False)

    def _fail(self, error):
        self._error = _error_text(error)
        self._entries = []
        self._fresh = False
        self.beginResetModel()
        self._rows = []
        self._reindex()
        self.endResetModel()
        self._selected.clear()
        self._set_loading(False)
        self.rowsChanged.emit()
        self.selectionChanged.emit()

    def _set_loading(self, value):
        self._loading = value
        self.stateChanged.emit()

    def _disk_changed(self, _path):
        self._debounce.start()

    # ------------------------------------------------------------------ arranging
    def _arranged(self):
        return listing.arrange(self._entries, self._key, self._descending, self._hidden, self._text, self._group,
                               self._accept)

    def _reindex(self):
        self._index = {entry.path: row for row, entry in enumerate(self._rows)}

    def _apply(self):
        """Move from the rows on screen to the newly arranged ones with removals, insertions and data changes."""
        new = self._arranged()
        position = {entry.path: i for i, entry in enumerate(new)}
        # Keep the old rows that still appear in the same relative order; the rest leave and come back.
        keep, last = set(), -1
        for entry in self._rows:
            at = position.get(entry.path)
            if at is not None and at > last:
                keep.add(entry.path)
                last = at
        row = len(self._rows) - 1
        while row >= 0:
            if self._rows[row].path in keep:
                row -= 1
                continue
            end = row
            while row >= 0 and self._rows[row].path not in keep:
                row -= 1
            self.beginRemoveRows(QModelIndex(), row + 1, end)
            del self._rows[row + 1:end + 1]
            self.endRemoveRows()
        changed = []
        i = 0
        while i < len(new):
            if i < len(self._rows) and self._rows[i].path == new[i].path:
                if self._rows[i] != new[i]:
                    self._rows[i] = new[i]
                    changed.append(i)
                i += 1
                continue
            # The kept rows are a subsequence of ``new``: a mismatch here is a row that comes in.
            start = i
            while i < len(new) and new[i].path not in keep:
                i += 1
            self.beginInsertRows(QModelIndex(), start, i - 1)
            self._rows[start:start] = new[start:i]
            self.endInsertRows()
        self._reindex()
        for row in changed:
            self.dataChanged.emit(self.index(row), self.index(row))
        gone = {p for p in self._selected if p not in self._index}
        if gone:
            self._selected -= gone
            self.selectionChanged.emit()
        self.rowsChanged.emit()
        self.currentRowChanged.emit()

    # ------------------------------------------------------------------ order and filters
    @Slot(str, bool)
    def sortBy(self, key, descending):
        if key not in listing.SORT_KEYS:
            return
        self._key, self._descending = key, bool(descending)
        self.orderChanged.emit()
        self._apply()

    @Slot(str)
    def setFilterText(self, text):
        if text != self._text:
            self._text = text
            self.orderChanged.emit()
            self._apply()

    @Slot(str)
    def setGroup(self, group):
        group = group if group in listing.GROUPS else 'all'
        if group != self._group:
            self._group = group
            self.orderChanged.emit()
            self._apply()

    @Slot(bool)
    def setShowHidden(self, value):
        if bool(value) != self._hidden:
            self._hidden = bool(value)
            self.orderChanged.emit()
            self._apply()

    def set_accept(self, predicate):
        """The chooser's portal filters (``predicate(Entry) -> bool``; folders always stay)."""
        self._accept = predicate
        self._apply()

    # ------------------------------------------------------------------ selection
    def _paths(self, rows):
        return {self._rows[r].path for r in rows if 0 <= r < len(self._rows)}

    def _selection_rows(self, before):
        rows = sorted(self._index[p] for p in (before ^ self._selected) if p in self._index)
        for row in rows:
            index = self.index(row)
            self.dataChanged.emit(index, index, [Qt.UserRole + NAMES.index('selected')])
        self.selectionChanged.emit()

    @Slot(int, str)
    def select(self, row, mode='single'):
        """``single`` replaces, ``toggle`` flips one row, ``range`` extends from the anchor, ``add`` adds one."""
        if not 0 <= row < len(self._rows):
            return
        before = set(self._selected)
        path = self._rows[row].path
        if mode == 'toggle':
            self._selected ^= {path}
            self._anchor = path
        elif mode == 'range':
            anchor = self._index.get(self._anchor, row)
            low, high = sorted((anchor, row))
            self._selected = self._paths(range(low, high + 1))
        elif mode == 'add':
            self._selected.add(path)
        else:
            self._selected = {path}
            self._anchor = path
        self._current = path
        self.currentRowChanged.emit()
        self._selection_rows(before)

    @Slot()
    def selectAll(self):
        before = set(self._selected)
        self._selected = {e.path for e in self._rows}
        self._selection_rows(before)

    @Slot()
    def clearSelection(self):
        if self._selected:
            before = set(self._selected)
            self._selected.clear()
            self._selection_rows(before)

    @Slot('QVariantList')
    def selectPaths(self, paths):
        before = set(self._selected)
        self._selected = {p for p in paths if p in self._index}
        first = next((p for p in paths if p in self._index), '')
        if first:
            self._current = self._anchor = first
            self.currentRowChanged.emit()
        self._selection_rows(before)

    @Property('QVariantList', notify=selectionChanged)
    def selectedPaths(self):
        return [e.path for e in self._rows if e.path in self._selected]

    @Property(int, notify=selectionChanged)
    def selectionCount(self):
        return len(self._selected)

    def _get_current(self):
        return self._index.get(self._current, -1)

    def _set_current(self, row):
        path = self._rows[row].path if 0 <= row < len(self._rows) else ''
        if path != self._current:
            self._current = path
            self.currentRowChanged.emit()

    currentRow = Property(int, _get_current, _set_current, notify=currentRowChanged)

    @Slot('QVariantList')
    def setCut(self, paths):
        before = self._cut
        self._cut = set(paths)
        role = Qt.UserRole + NAMES.index('cut')
        for path in before ^ self._cut:
            row = self._index.get(path)
            if row is not None:
                self.dataChanged.emit(self.index(row), self.index(row), [role])

    # ------------------------------------------------------------------ lookups
    @Slot(str, result=int)
    def rowOf(self, path):
        return self._index.get(path, -1)

    @Slot(int, result=str)
    def pathAt(self, row):
        return self._rows[row].path if 0 <= row < len(self._rows) else ''

    @Slot(int, result='QVariantMap')
    def get(self, row):
        """Every role of a row as a map (menus, inspector)."""
        if not 0 <= row < len(self._rows):
            return {}
        entry = self._rows[row]
        return {name: self.value(entry, name) for name in NAMES if name not in ('thumb', 'snippet', 'detail')}

    def entries(self):
        """The rows on screen (``Entry`` objects), in order."""
        return list(self._rows)

    def entry(self, path):
        row = self._index.get(path)
        return self._rows[row] if row is not None else None

    # ------------------------------------------------------------------ properties
    @Property(str, notify=stateChanged)
    def root(self):
        return self._root

    @Property(bool, notify=stateChanged)
    def loading(self):
        return self._loading

    @Property(str, notify=stateChanged)
    def error(self):
        return self._error

    @Property(int, notify=rowsChanged)
    def count(self):
        return len(self._rows)

    @Property(int, notify=rowsChanged)
    def total(self):
        return sum(1 for e in self._entries if self._hidden or not e.hidden)

    @Property(str, notify=rowsChanged)
    def summary(self):
        return listing.summary([e for e in self._entries if self._hidden or not e.hidden])

    @Property(str, notify=rowsChanged)
    def dominant(self):
        return listing.dominant([e for e in self._entries if self._hidden or not e.hidden])

    @Property(str, notify=orderChanged)
    def sortKey(self):
        return self._key

    @Property(bool, notify=orderChanged)
    def descending(self):
        return self._descending

    @Property(str, notify=orderChanged)
    def filterText(self):
        return self._text

    @Property(str, notify=orderChanged)
    def group(self):
        return self._group

    @Property(bool, notify=orderChanged)
    def showHidden(self):
        return self._hidden

    @Slot()
    def close(self):
        """Stop reading: queued peeks are cancelled and late results dropped."""
        self._cancelled.set()
        self._generation += 1
        self._debounce.stop()
        for path in self._watcher.directories():
            self._watcher.removePath(path)
