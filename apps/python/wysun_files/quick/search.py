"""Search everywhere from Wysun Files, as the launcher does: its index of the home folder and its scoring. The index
is read and searched in a worker thread and refreshed in the background by the launcher's own command; only the
latest query is shown. A QML list model of the best results."""
import os
from pathlib import Path
import subprocess
import sys
import threading

from PySide6.QtCore import Property, QAbstractListModel, QByteArray, QModelIndex, QObject, QTimer, Qt, Signal, Slot

from wysun_core import launch
from wysun_files.core import listing, search

NAMES = ('path', 'name', 'folder', 'isDir', 'kind', 'icon', 'glyph', 'role', 'badge', 'thumb')
ROLES = {Qt.UserRole + i: name for i, name in enumerate(NAMES)}
LIMIT = 150


class _Relay(QObject):
    found = Signal(int, object)


class FileSearch(QAbstractListModel):
    changed = Signal()

    def __init__(self, thumbs=None, parent=None):
        super().__init__(parent)
        from wysun_services.store import HOME, STATE
        self.thumbs = thumbs
        self._file, self._home = STATE / 'launcher-files.idx', Path(HOME)
        self._index, self._loaded = None, None
        self._lock = threading.Lock()
        self._rows, self._query, self._generation, self._busy = [], '', 0, False
        self._relay = _Relay(self)
        self._relay.found.connect(self._found, Qt.QueuedConnection)
        self._debounce = QTimer(self, singleShot=True, interval=120)
        self._debounce.timeout.connect(self._start)
        if thumbs is not None:
            thumbs.ready.connect(self._thumb_ready)

    def use_index(self, file, home):
        """Another index and home (tests)."""
        self._file, self._home, self._index, self._loaded = Path(file), Path(home), None, None

    def roleNames(self):
        return {role: QByteArray(name.encode()) for role, name in ROLES.items()}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row, name = self._rows[index.row()], ROLES.get(role, '')
        if name == 'thumb':
            return self.thumbs.url(row['path'], row['modified'], row['kind']) if self.thumbs and row['modified'] else ''
        return row.get(name)

    @Slot(str)
    def _thumb_ready(self, path):
        for number, row in enumerate(self._rows):
            if row['path'] == path:
                index = self.index(number)
                self.dataChanged.emit(index, index, [Qt.UserRole + NAMES.index('thumb')])

    @Slot()
    def refreshIndex(self):
        """Let the launcher's command bring its index up to date (detached; it decides whether it is stale)."""
        try:
            subprocess.Popen(launch.argv('wysun_services.launcher_data', 'files-index', python=str(Path(sys.base_prefix) / 'bin/python3')),
                             env=launch.environment(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            pass

    @Slot(str)
    def setQuery(self, text):
        self._query = text
        self._generation += 1
        if not text.strip():
            self._debounce.stop()
            self._show([])
            return
        self._set_busy(True)
        self._debounce.start()

    def _set_busy(self, value):
        if value != self._busy:
            self._busy = value
            self.changed.emit()

    def _current_index(self):
        """The index, read again when the file changed. Worker thread."""
        with self._lock:
            try:
                stamp = self._file.stat().st_mtime
            except OSError:
                stamp = None
            if self._index is None or stamp != self._loaded:
                self._index, self._loaded = search.load(self._file), stamp
            return self._index

    def _start(self):
        generation, query, relay, home = self._generation, self._query, self._relay, self._home

        def work():
            rows = []
            for relative, is_dir in search.search(self._current_index(), query, LIMIT):
                path = str(home / relative)
                try:
                    modified = os.stat(path).st_mtime
                except OSError:
                    continue                       # the index is older than the disk
                name = os.path.basename(path)
                kind = listing.classify(name, is_dir)
                folder = os.path.dirname(path)
                rows.append({'path': path, 'name': name, 'folder': '~' + folder[len(str(home)):] if folder.startswith(str(home)) else folder,
                             'isDir': is_dir, 'kind': kind.kind, 'icon': kind.icon, 'role': kind.role, 'badge': kind.badge,
                             'glyph': listing.folder_glyph(path, name) if is_dir else '', 'modified': modified})
            relay.found.emit(generation, rows)

        threading.Thread(target=work, name='wysun-files-search', daemon=True).start()

    @Slot(int, object)
    def _found(self, generation, rows):
        if generation == self._generation:
            self._show(rows)

    def _show(self, rows):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        self._busy = False
        self.changed.emit()

    @Slot(int, result=str)
    def pathAt(self, row):
        return self._rows[row]['path'] if 0 <= row < len(self._rows) else ''

    @Property(int, notify=changed)
    def count(self):
        return len(self._rows)

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def query(self):
        return self._query
