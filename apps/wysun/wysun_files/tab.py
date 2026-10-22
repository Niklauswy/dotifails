"""A browsing tab: history, model, view, header and the empty/loading message."""
import os
from pathlib import Path

from PySide6.QtCore import QDir, QItemSelectionModel, Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .fileview import FileView, ListHeader
from .model import NAME, FileModel


class FolderTab(QWidget):
    changed = Signal()
    selected = Signal()
    activated = Signal(str)
    context = Signal(object)

    def __init__(self, path, hidden=False, grid=True):
        super().__init__()
        self.setObjectName('folderPage')
        self.history, self.position = [], -1
        self.loaded_paths = set()
        self.path = str(Path.home())
        self.filter_text = ''
        self._entered = False
        self._direction = 1
        self.reselect = ''
        self.model = FileModel(self)
        self.model.set_hidden(hidden)
        self.model.setRootPath('/')
        self.file_view = FileView(self.model)
        self.header = ListHeader()
        self.header.sort_requested.connect(self.sort)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.file_view, 1)
        view = self.file_view
        view.context_requested.connect(self.context)
        view.doubleClicked.connect(lambda index: self.activated.emit(self.model.filePath(index)))
        view.selectionModel().selectionChanged.connect(lambda *_: self.selected.emit())
        self.model.directoryLoaded.connect(self.directory_loaded)
        self.model.rowsInserted.connect(lambda *_: self.refresh_count())
        self.model.rowsRemoved.connect(lambda *_: self.refresh_count())
        self.set_grid(grid)
        self.sort(NAME, Qt.AscendingOrder)
        self.navigate(path)

    # ------------------------------------------------------------ accessors
    def view(self):
        return self.file_view

    def selected_paths(self):
        return list(dict.fromkeys(self.model.filePath(index) for index in self.file_view.selectionModel().selectedIndexes()
                                  if index.column() == 0))

    def use_model(self, model):
        """Swap in a proxy of the file model (portal chooser) keeping selection signals wired."""
        self.model = model
        self.file_view.setModel(model)
        self.file_view.selectionModel().selectionChanged.connect(lambda *_: self.selected.emit())
        self.navigate(self.path, False)

    # ----------------------------------------------------------- navigation
    def directory_loaded(self, path):
        self.loaded_paths.add(os.path.abspath(path))
        if os.path.abspath(path) == self.path:
            self.model.sort(self.header.column, self.header.order)
        self.refresh_count()

    def navigate(self, path, history=True, direction=1):
        path = os.path.abspath(os.path.expanduser(str(path)))
        if not os.path.isdir(path) or not os.access(path, os.R_OK | os.X_OK):
            return False
        self.path = path
        if history and (self.position < 0 or self.history[self.position] != path):
            self.history = self.history[:self.position + 1] + [path]
            self.position = len(self.history) - 1
        root = self.model.setRootPath(path)
        self.file_view.setRootIndex(root)
        self.file_view.clearSelection()
        self.file_view.verticalScrollBar().setValue(0)
        self._entered = False
        self._direction = direction
        if getattr(self, 'kind', 'all') != 'all':
            self.kind = 'all'
            self._refilter()
        self.refresh_count()
        self._apply_reselect()
        self.changed.emit()
        return True

    def select_when_ready(self, path):
        """Select and reveal ``path`` as soon as the model has it (e.g. the folder we just left)."""
        self.reselect = path
        self._apply_reselect()

    def _apply_reselect(self):
        if not self.reselect:
            return
        index = self.model.index(self.reselect)
        if index.isValid():
            self.reselect = ''
            self.file_view.setCurrentIndex(index)
            self.file_view.selectionModel().select(index, QItemSelectionModel.ClearAndSelect)
            self.file_view.scrollTo(index)

    def go(self, offset):
        target = self.position + offset
        if 0 <= target < len(self.history) and self.navigate(self.history[target], False, 1 if offset > 0 else -1):
            self.position = target
            self.changed.emit()

    # --------------------------------------------------------- presentation
    def set_hidden(self, enabled):
        self.model.set_hidden(enabled)

    def set_grid(self, enabled):
        self.model.show_thumbnails = True
        self.header.setVisible(not enabled)
        self.file_view.set_mode('grid' if enabled else 'list')
        self.file_view.start_entrance()
        self.selected.emit()

    def sort(self, column, order):
        self.header.set_sort(column, order)
        self.model.sort(column, order)

    def set_filter(self, text):
        self.filter_text = text
        self._refilter()

    def set_kind(self, kind):
        self.kind = kind
        self._refilter()

    def _refilter(self):
        if hasattr(self.model, 'set_kind'):
            self.model.set_kind(getattr(self, 'kind', 'all'), self.filter_text)
        else:
            self.model.setNameFilters(['*' + self.filter_text + '*'] if self.filter_text else [])
        self.refresh_count()

    def refresh_count(self):
        count = self.model.rowCount(self.model.index(self.path))
        view = self.file_view
        view.set_loading(self.path not in self.loaded_paths)
        if self.path not in self.loaded_paths:
            view.message, view.symbol = 'Cargando carpeta…', 'hourglass_empty'
        elif self.filter_text or getattr(self, 'kind', 'all') != 'all':
            view.message, view.symbol = 'Nada coincide con el filtro.', 'search_off'
        else:
            view.message, view.symbol = 'Esta carpeta está vacía.', 'folder_open'
        if count and not self._entered:
            self._entered = True
            view.start_entrance(self._direction)
        self._apply_reselect()
        view.viewport().update()
        self.changed.emit()
