"""The files a viewer can step through: an explicit list, or the folder around one file."""
import os
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .source import group_of, kind_of, natural_key


def scan(directory, group):
    """Natural-ordered paths of one group ('image' or 'av') directly inside ``directory``."""
    found = []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    if entry.is_file() and group_of(kind_of(entry.path)) == group:
                        found.append(entry.name)
                except OSError:
                    continue
    except OSError:
        return []
    return [str(Path(directory) / name) for name in sorted(found, key=natural_key)]


class _Scan(QRunnable):
    def __init__(self, owner, generation, directory, group):
        super().__init__()
        self.owner, self.generation, self.directory, self.group = owner, generation, directory, group

    def run(self):
        paths = scan(self.directory, self.group)
        try:
            self.owner.scanned.emit(self.generation, paths)
        except RuntimeError:             # the collection was deleted while the folder was being read
            pass


class Collection(QObject):
    """Ordered paths with a current index. Missing files are skipped, ends do not wrap."""

    changed = Signal()
    scanned = Signal(int, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.paths = []
        self.index = -1
        self._generation = 0
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self.scanned.connect(self._adopt)

    def __len__(self):
        return len(self.paths)

    @property
    def current(self):
        return self.paths[self.index] if 0 <= self.index < len(self.paths) else None

    def set_explicit(self, paths, current=0):
        """The caller's list, in the caller's order."""
        self._generation += 1
        self.paths = [str(p) for p in paths]
        self.index = current if 0 <= current < len(self.paths) else 0 if self.paths else -1
        self.changed.emit()

    def follow_folder(self, path, group):
        """Browse the supported files next to ``path``; the list arrives asynchronously."""
        self._generation += 1
        self.paths, self.index = [str(path)], 0
        self.changed.emit()
        self._pool.start(_Scan(self, self._generation, str(Path(path).parent), group))

    def _adopt(self, generation, paths):
        if generation != self._generation or not paths:
            return
        current = self.current
        self.paths = paths
        self.index = paths.index(current) if current in paths else min(self.index, len(paths) - 1)
        self.changed.emit()

    def neighbour(self, step):
        """Nearest existing file in direction ``step`` (+1/-1), or None at either end."""
        index = self.index + step
        while 0 <= index < len(self.paths):
            if os.path.isfile(self.paths[index]):
                return index
            index += step
        return None

    def move(self, step):
        index = self.neighbour(step)
        if index is None:
            return None
        self.index = index
        self.changed.emit()
        return self.paths[index]

    def remove_current(self):
        """Drop the current file from the list (after it was deleted); returns the path now current."""
        if self.current is None:
            return None
        del self.paths[self.index]
        self.index = min(self.index, len(self.paths) - 1)
        self.changed.emit()
        return self.current

    def position(self):
        return self.index + 1, len(self.paths)
