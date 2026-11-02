"""The state of a Wysun Files window for QML: its tabs, each with a folder model and its own history, and the
settings shared by all of them (view mode, hidden files, inspector), kept in ``QSettings('Wysun', 'Files')`` with
the keys the Widgets window used."""
import json
import os
from pathlib import Path

from PySide6.QtCore import Property, QObject, QSettings, Signal, Slot

from wysun_files.core import listing, places
from .folder import FolderModel
from .thumbs import Thumbnails

HISTORY = 100


def _resolve(path):
    return os.path.abspath(os.path.expanduser(path)) if path else ''


class Tab(QObject):
    changed = Signal()

    def __init__(self, controller, path):
        super().__init__(controller)
        self.controller = controller
        self._model = FolderModel(thumbs=controller.thumbs, special=controller.special, parent=self)
        self._model.setShowHidden(controller._hidden)
        self._model.loaded.connect(self._loaded)
        self._model.stateChanged.connect(self._settled)
        self._model.userSorted.connect(self._sorted)
        self._path, self._history, self._future, self._reselect = '', [], [], []
        if not self.navigate(path):
            self.navigate(str(Path.home()))

    # ---------------------------------------------------------------- navigation
    @Slot(str, result=bool)
    def navigate(self, path, remember=True, reselect=None):
        """Show a folder (a file shows its folder with the file selected). False for a missing or unreadable one."""
        path = _resolve(path)
        if os.path.isfile(path) or (os.path.lexists(path) and not os.path.isdir(path)):
            return self.navigate(os.path.dirname(path), remember, [path])
        if not os.path.isdir(path) or not os.access(path, os.R_OK | os.X_OK):
            return False
        if remember and self._path and path != self._path:
            self._history = (self._history + [self._path])[-HISTORY:]
            self._future = []
        if reselect is None:
            # Going to an ancestor (up, back): reselect the folder we come from.
            inside = self._path.startswith(path.rstrip('/') + '/') if self._path else False
            reselect = [os.path.join(path, os.path.relpath(self._path, path).split('/')[0])] if inside else []
        self._path, self._reselect = path, list(reselect)
        self._model.setFilterText('')
        self._model.setGroup('all')
        self._model.set_order(*self.controller.order_of(path))
        self._model.setRoot(path)
        self.changed.emit()
        return True

    def _sorted(self, key, descending):
        self.controller.remember_order(self._path, key, descending)

    @Slot()
    def back(self):
        while self._history:
            target = self._history.pop()
            current = self._path
            if self.navigate(target, remember=False):
                self._future.append(current)
                self.changed.emit()
                return

    @Slot()
    def forward(self):
        while self._future:
            target = self._future.pop()
            current = self._path
            if self.navigate(target, remember=False):
                self._history.append(current)
                self.changed.emit()
                return

    @Slot()
    def up(self):
        parent = os.path.dirname(self._path)
        if parent and parent != self._path:
            self.navigate(parent)

    @Slot()
    def home(self):
        self.navigate(str(Path.home()))

    def _loaded(self, root):
        if root == self._path and self._reselect:
            self._model.selectPaths(self._reselect)
            self._reselect = []

    def _settled(self):
        """A refresh (after an operation) finished: select what it was waiting for."""
        if self._reselect and not self._model.property('loading') and self._model.property('root') == self._path:
            if all(self._model.rowOf(p) >= 0 for p in self._reselect):
                self._model.selectPaths(self._reselect)
                self._reselect = []

    def select_when_loaded(self, paths):
        """Select ``paths`` once the folder is listed (or now, when it already is)."""
        if self._model.property('loading'):
            self._reselect = list(paths)
        else:
            self._model.selectPaths(list(paths))

    # ---------------------------------------------------------------- properties
    @Property(QObject, constant=True)
    def model(self):
        return self._model

    @Property(str, notify=changed)
    def path(self):
        return self._path

    @Property(str, notify=changed)
    def title(self):
        return place_title(self._path)

    @Property(bool, notify=changed)
    def canBack(self):
        return bool(self._history)

    @Property(bool, notify=changed)
    def canForward(self):
        return bool(self._future)

    @Property(bool, notify=changed)
    def canUp(self):
        return self._path not in ('', '/')

    @Property(str, notify=changed)
    def glyph(self):
        return listing.folder_glyph(self._path, os.path.basename(self._path), self.controller.special)

    @Property(str, notify=changed)
    def freeText(self):
        return places.usage(self._path)[1] if self._path else ''

    @Property(float, notify=changed)
    def usedFraction(self):
        return places.usage(self._path)[0] if self._path else 0.0

    @Property('QVariantList', notify=changed)
    def crumbs(self):
        return crumbs(self._path)

    def close(self):
        self._model.close()


def place_title(path):
    if path == str(Path.home()):
        return 'Inicio'
    if path == '/':
        return 'Sistema'
    return os.path.basename(path.rstrip('/')) or path


def crumbs(path):
    """Segments of the path bar: from «Inicio» inside the home folder, else from «Sistema»."""
    home = str(Path.home())
    if path == home or path.startswith(home + '/'):
        out, base, rest = [{'label': 'Inicio', 'path': home, 'icon': 'home'}], home, path[len(home):]
    else:
        out, base, rest = [{'label': 'Sistema', 'path': '/', 'icon': 'hard_drive'}], '', path
    for part in [p for p in rest.split('/') if p]:
        base = base.rstrip('/') + '/' + part
        out.append({'label': part, 'path': base, 'icon': ''})
    return out


class FilesController(QObject):
    tabsChanged = Signal()
    currentChanged = Signal()
    settingsChanged = Signal()
    closeRequested = Signal()
    openRequested = Signal('QVariantList')      # files to open (operations wire it)
    actionRequested = Signal(str, 'QVariantList')    # copy, cut, paste, trash, rename, new, newFolder, preview…
    menuRequested = Signal(str, 'QVariantList', float, float)   # context | more, paths, window x, y
    message = Signal(str)

    def __init__(self, paths=None, settings=None, thumbnails=True, parent=None):
        super().__init__(parent)
        self.settings = settings if settings is not None else QSettings('Wysun', 'Files')
        self._hidden = _flag(self.settings.value('hidden', False))
        self._view = 'list' if self.settings.value('viewMode', 'icons') == 'list' else 'grid'
        self._inspector = _flag(self.settings.value('details', True))
        self.thumbs = Thumbnails(parent=self) if thumbnails else None
        self.special = self.special_glyphs()
        self._tabs = []
        self._index = 0
        for path in (paths or [str(Path.home())]):
            self._tabs.append(Tab(self, path))
        for tab in self._tabs:
            tab.changed.connect(self._tab_changed)

    def order_of(self, path):
        """The folder's own order, else the newest first (settings ``sortKey``/``sortDesc`` change the default)."""
        saved = self._orders().get(path)
        if saved:
            return saved[0], bool(saved[1])
        return str(self.settings.value('sortKey', 'modified')), _flag(self.settings.value('sortDesc', True))

    def remember_order(self, path, key, descending):
        orders = self._orders()
        orders[path] = [key, bool(descending)]
        self.settings.setValue('folderOrders', json.dumps(orders))

    def _orders(self):
        try:
            value = json.loads(self.settings.value('folderOrders', '{}') or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def special_glyphs():
        """The XDG places get their own glyph inside the folder icon."""
        try:
            return {place['path']: place['icon'] for place in places.favourites()}
        except Exception:
            return {}

    def _tab_changed(self):
        if self.sender() is self.current:
            self.currentChanged.emit()
        self.tabsChanged.emit()

    # ---------------------------------------------------------------- tabs
    @Property('QVariantList', notify=tabsChanged)
    def tabs(self):
        return list(self._tabs)

    @Property(QObject, notify=currentChanged)
    def current(self):
        return self._tabs[self._index]

    def _get_index(self):
        return self._index

    def _set_index(self, index):
        if 0 <= index < len(self._tabs) and index != self._index:
            self._index = index
            self.currentChanged.emit()
            self.tabsChanged.emit()

    currentIndex = Property(int, _get_index, _set_index, notify=currentChanged)

    @Slot(str, result=int)
    def newTab(self, path=''):
        tab = Tab(self, path or self.current.property('path'))
        tab.model.setCut(getattr(self, '_cut', []))
        tab.changed.connect(self._tab_changed)
        self._tabs.insert(self._index + 1, tab)
        self.tabsChanged.emit()
        self._set_index(self._index + 1)
        return self._index

    @Slot(int)
    def closeTab(self, index):
        if not 0 <= index < len(self._tabs):
            return
        if len(self._tabs) == 1:
            self.closeRequested.emit()
            return
        tab = self._tabs.pop(index)
        if index < self._index or self._index >= len(self._tabs):
            self._index = max(0, self._index - 1)
        self.tabsChanged.emit()
        self.currentChanged.emit()
        tab.close()
        tab.deleteLater()

    @Slot(int)
    def cycleTab(self, step):
        if len(self._tabs) > 1:
            self._set_index((self._index + step) % len(self._tabs))

    @Slot(str, result=bool)
    def open(self, path):
        return self.current.navigate(path)

    # ---------------------------------------------------------------- settings
    @Property(str, notify=settingsChanged)
    def viewMode(self):
        return self._view

    @Slot(str)
    def setViewMode(self, mode):
        mode = 'list' if mode == 'list' else 'grid'
        if mode != self._view:
            self._view = mode
            self.settings.setValue('viewMode', 'list' if mode == 'list' else 'icons')
            self.settingsChanged.emit()

    @Property(bool, notify=settingsChanged)
    def showHidden(self):
        return self._hidden

    @Slot(bool)
    def setShowHidden(self, value):
        self._hidden = bool(value)
        self.settings.setValue('hidden', self._hidden)
        for tab in self._tabs:
            tab.model.setShowHidden(self._hidden)
        self.settingsChanged.emit()

    @Property(bool, notify=settingsChanged)
    def inspector(self):
        return self._inspector

    @Slot(bool)
    def setInspector(self, value):
        self._inspector = bool(value)
        self.settings.setValue('details', self._inspector)
        self.settingsChanged.emit()

    @Property(str, notify=currentChanged)
    def title(self):
        return f'{self.current.property("title")} · Wysun Archivos'

    @Property(str, constant=True)
    def homePath(self):
        return str(Path.home())

    # ---------------------------------------------------------------- requests from the view
    @Slot('QVariantList')
    def openFiles(self, paths):
        self.openRequested.emit(list(paths))

    @Slot(str, 'QVariantList')
    def keyAction(self, action, paths):
        self.actionRequested.emit(action, list(paths))

    @Slot('QVariantList', float, float)
    def contextMenu(self, paths, x, y):
        self.menuRequested.emit('context', list(paths), x, y)

    @Slot(float, float)
    def moreMenu(self, x, y):
        self.menuRequested.emit('more', [], x, y)

    @Slot('QVariantList')
    def setCut(self, paths):
        """Fade the files waiting to be moved, in every tab."""
        self._cut = list(paths)
        for tab in self._tabs:
            tab.model.setCut(self._cut)

    @Slot(str)
    def copyText(self, text):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(text)

    @Slot()
    def close(self):
        self.settings.sync()
        for tab in self._tabs:
            tab.close()
        if self.thumbs is not None:
            self.thumbs.close()


def _flag(value):
    return value is True or str(value).lower() == 'true'
