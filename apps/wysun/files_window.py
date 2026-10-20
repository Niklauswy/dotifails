"""Wysun Archivos: native, non-destructive local file management."""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess

from PySide6.QtCore import Qt, QDir, QSize, QUrl, QMimeData, QSettings, QStandardPaths, QThread, Signal, QTimer
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QTabWidget, QTreeView,
    QListView, QFileSystemModel, QStackedWidget, QSplitter, QAbstractItemView,
    QMenu, QMessageBox, QInputDialog, QProgressBar, QFrame, QSizePolicy)
from icons import icon, glyph
from ui_theme import PANEL_STYLE
from theme_tokens import apply_style
from file_media import human_size

from files_visuals import STYLE, COLORS, apply_palette, ui_icon, file_icon
from files_motion import SoftButton, animate_popup, reduced_motion
from files_inspector import SelectionPreview, BreadcrumbButton
from PySide6.QtCore import QVariantAnimation, QEasingCurve, QEvent


class LocationLabel(QLabel):
    """Keep a long location on one line while retaining the full accessible path."""
    def __init__(self,parent=None):
        super().__init__(parent);self.full_text=''
        self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
    def setText(self,text):
        self.full_text=str(text);self.setToolTip(self.full_text);self.setAccessibleName(self.full_text);self.refresh()
    def refresh(self):
        QLabel.setText(self,self.fontMetrics().elidedText(self.full_text,Qt.ElideMiddle,max(0,self.width())))
    def resizeEvent(self,event):
        super().resizeEvent(event);self.refresh()


def button(label, symbol, callback, tooltip=None):
    result = SoftButton(label)
    result.setIcon(ui_icon(symbol))
    result.setFixedHeight(30)
    if not label: result.setFixedWidth(32)
    result.setCursor(Qt.PointingHandCursor)
    result.setToolTip(tooltip or label)
    result.setAccessibleName(tooltip or label)
    result.clicked.connect(callback)
    return result


class FileModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        from files_thumbnails import ThumbnailCache
        self.thumbnails=ThumbnailCache(self)
        self.show_thumbnails=True
        self.thumbnails.ready.connect(self.thumbnail_ready)

    def thumbnail_ready(self,path):
        index=self.index(path)
        if index.isValid():self.dataChanged.emit(index,index,[Qt.DecorationRole])

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ('Nombre', 'Tamaño', 'Tipo', 'Modificado')[section] if section < 4 else ''
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and index.column() == 1 and not self.isDir(index):
            return human_size(self.size(index))
        if role == Qt.DisplayRole and index.column() == 2 and self.isDir(index):
            return 'Carpeta'
        if role == Qt.DecorationRole and index.column() == 0:
            if self.show_thumbnails and not self.isDir(index):
                thumb=self.thumbnails.get(self.filePath(index))
                if thumb is not None:return thumb
            return file_icon(self.filePath(index), 80)
        return super().data(index, role)


class OperationJob(QThread):
    result = Signal(object, str)

    def __init__(self, kind, sources, destination, parent):
        super().__init__(parent)
        self.kind, self.sources, self.destination = kind, sources, destination

    def run(self):
        from files_ops import execute_operation
        try:
            result = execute_operation(self.kind, self.sources, self.destination)
            self.result.emit(result, '')
        except Exception as error:
            self.result.emit([], str(error))


class FolderTab(QWidget):
    changed = Signal()
    selected = Signal()
    activated = Signal(str)
    context = Signal(object)

    def __init__(self, path, hidden=False, grid=False):
        super().__init__()
        self.setObjectName("folderPage")
        self.history, self.position = [], -1
        self.loaded_paths=set()
        self.path = str(Path.home())
        self.model = FileModel(self)
        self.model.setReadOnly(True)
        self.model.setNameFilterDisables(False)
        self.set_hidden(hidden)
        self.model.setRootPath('/')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        self.stack = QStackedWidget()
        self.tree = QTreeView()
        self.tree.setRootIsDecorated(False)
        self.tree.setItemsExpandable(False)
        self.tree.setSortingEnabled(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setIconSize(QSize(20, 20))
        self.tree.setUniformRowHeights(True)
        self.grid = QListView()
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setWrapping(True)
        self.grid.setWordWrap(True)
        self.grid.setIconSize(QSize(76, 76))
        self.grid.setGridSize(QSize(132, 124))
        self.grid.setSpacing(8)
        self.grid.setTextElideMode(Qt.ElideMiddle)
        for view in (self.tree, self.grid):
            view.setModel(self.model)
            view.setSelectionMode(QAbstractItemView.ExtendedSelection)
            view.setEditTriggers(QAbstractItemView.NoEditTriggers)
            view.setContextMenuPolicy(Qt.CustomContextMenu)
            view.customContextMenuRequested.connect(lambda point, v=view: self.context.emit(v.viewport().mapToGlobal(point)))
            view.doubleClicked.connect(lambda index: self.activated.emit(self.model.filePath(index)))
            view.selectionModel().selectionChanged.connect(lambda *_: self.selected.emit())
            self.stack.addWidget(view)
        self.grid.setSelectionModel(self.tree.selectionModel())
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 95)
        self.tree.setColumnWidth(2, 125)
        self.tree.setColumnWidth(3, 175)
        self.tree.sortByColumn(0, Qt.AscendingOrder)
        layout.addWidget(self.stack)
        self.empty = QLabel('Esta carpeta está vacía o no hay coincidencias con el filtro.')
        self.empty.setObjectName('emptyHint')
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty)
        self.model.directoryLoaded.connect(self.directory_loaded)
        self.model.rowsInserted.connect(lambda *_: self.refresh_count())
        self.model.rowsRemoved.connect(lambda *_: self.refresh_count())
        self.set_grid(grid)
        self.navigate(path)

    def directory_loaded(self, path):
        self.loaded_paths.add(os.path.abspath(path))
        if os.path.abspath(path)==self.path:
            self.model.sort(self.tree.header().sortIndicatorSection(), self.tree.header().sortIndicatorOrder())
            self.grid.doItemsLayout()
        self.refresh_count()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self, self.fit_columns)

    def fit_columns(self):
        width = self.tree.viewport().width()
        compact = width < 650
        tiny = width < 520
        self.tree.setColumnHidden(2, compact)
        self.tree.setColumnHidden(3, tiny)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 110)
        self.tree.setColumnWidth(3, 165)
        remaining = width - 90 - (0 if compact else 110) - (0 if tiny else 165) - 8
        self.tree.setColumnWidth(0, max(180, remaining))

    def view(self):
        return self.stack.currentWidget()

    def selected_paths(self):
        return list(dict.fromkeys(self.model.filePath(index) for index in self.view().selectionModel().selectedIndexes() if index.column() == 0))

    def navigate(self, path, history=True):
        path = os.path.abspath(os.path.expanduser(str(path)))
        if not os.path.isdir(path):
            return False
        if not os.access(path, os.R_OK | os.X_OK):
            return False
        self.path = path
        if history and (self.position < 0 or self.history[self.position] != path):
            self.history = self.history[:self.position + 1] + [path]
            self.position = len(self.history) - 1
        root = self.model.setRootPath(path)
        for view in (self.tree, self.grid):
            view.setRootIndex(root)
            view.clearSelection()
        self.refresh_count()
        self.changed.emit()
        return True

    def go(self, offset):
        new_position = self.position + offset
        if 0 <= new_position < len(self.history):
            path = self.history[new_position]
            if self.navigate(path, False):
                self.position = new_position
                self.changed.emit()

    def set_hidden(self, enabled):
        filters = QDir.AllEntries | QDir.NoDotAndDotDot | QDir.System
        if enabled:
            filters |= QDir.Hidden
        self.model.setFilter(filters)

    def set_grid(self, enabled):
        self.model.show_thumbnails=enabled
        self.stack.setCurrentWidget(self.grid if enabled else self.tree)
        self.selected.emit()

    def refresh_count(self):
        count = self.model.rowCount(self.model.index(self.path))
        if self.path not in self.loaded_paths:
            self.empty.setText('Cargando carpeta…')
        elif self.model.nameFilters():
            self.empty.setText('No hay archivos que coincidan con el filtro.')
        else:
            self.empty.setText('Esta carpeta está vacía.')
        self.empty.setVisible(count == 0)
        self.changed.emit()


class FilesWindow(QMainWindow):
    def __init__(self, paths=None):
        super().__init__()
        self.settings = QSettings('Orbita', 'Files')
        self.jobs, self.viewers = [], []
        self.hidden = self.settings.value('hidden', False, type=bool)
        self.grid_mode = self.settings.value('viewMode', 'icons') == 'icons'
        self.setWindowTitle('Wysun Files')
        self.setWindowIcon(file_icon(str(Path.home()), 48))
        self.resize(1160, 740)
        self.setMinimumSize(740, 460)
        apply_palette(QApplication.instance())
        self.setStyleSheet(STYLE)
        central = QWidget(); central.setObjectName("glassCanvas")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        toolbar = QWidget(); self.toolbar=toolbar; toolbar.setObjectName('toolbar'); toolbar.setFixedHeight(56)
        tools = QHBoxLayout(toolbar); tools.setContentsMargins(12, 0, 14, 0); tools.setSpacing(6)
        self.sidebar_button = button('', 'sidebar', self.toggle_sidebar, 'Mostrar u ocultar barra lateral')
        tools.addWidget(self.sidebar_button)
        self.app_label = QLabel('Archivos'); self.app_label.setObjectName('appLabel'); self.app_label.setFixedWidth(126)
        tools.addWidget(self.app_label)
        self.back_button = button('', 'back', lambda: self.current().go(-1), 'Atrás · Alt+←')
        self.forward_button = button('', 'forward', lambda: self.current().go(1), 'Adelante · Alt+→')
        tools.addWidget(self.back_button); tools.addWidget(self.forward_button)
        self.folder_title = QLabel('Inicio'); self.folder_title.setObjectName('folderTitle')
        self.folder_title.setTextFormat(Qt.PlainText); self.folder_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        tools.addWidget(self.folder_title, 1)
        group = QWidget(); group.setObjectName('viewGroup'); group.setFixedHeight(32)
        controls = QHBoxLayout(group); controls.setContentsMargins(2, 2, 2, 2); controls.setSpacing(1)
        self.grid_button = button('', 'grid', lambda: self.set_grid(True), 'Iconos · Ctrl+1')
        self.list_button = button('', 'list', lambda: self.set_grid(False), 'Lista · Ctrl+2')
        for control in (self.grid_button, self.list_button):
            control.setCheckable(True); control.setFixedSize(30, 26); controls.addWidget(control)
        tools.addWidget(group); tools.addSpacing(6)
        self.new_folder_button = button('', 'new-folder', self.new_folder, 'Nueva carpeta · Ctrl+Shift+N')
        tools.addWidget(self.new_folder_button)
        self.details_button = button('', 'info', self.toggle_inspector, 'Información del archivo')
        self.details_button.setCheckable(True); self.details_button.setChecked(False); tools.addWidget(self.details_button)
        self.sort_button=button('Ordenar','down',self.sort_menu,'Ordenar archivos en lista o iconos')
        tools.addWidget(self.sort_button)
        self.more_button = button('', 'more', self.more_menu, 'Más acciones')
        tools.addWidget(self.more_button)
        self.filter_edit = QLineEdit(); self.filter_edit.setObjectName('search'); self.filter_edit.setFixedWidth(165)
        self.filter_edit.setPlaceholderText('Filtrar carpeta'); self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setAccessibleName('Filtrar nombres en esta carpeta')
        self.filter_edit.addAction(ui_icon('search', 15), QLineEdit.LeadingPosition)
        self.filter_edit.textChanged.connect(self.filter_files); tools.addWidget(self.filter_edit)
        root.addWidget(toolbar)
        self.splitter = QSplitter(); self.splitter.setChildrenCollapsible(False); root.addWidget(self.splitter, 1)
        self.sidebar = QWidget(); self.sidebar.setObjectName('sidebar'); self.sidebar.setMinimumWidth(156); self.sidebar.setMaximumWidth(250)
        side = QVBoxLayout(self.sidebar); side.setContentsMargins(10, 18, 10, 12); side.setSpacing(4)
        self.places = QListWidget(); self.places.setObjectName('places'); self.places.setIconSize(QSize(18,18)); self.places.setSpacing(1)
        self.places.itemClicked.connect(lambda item: self.navigate(item.data(Qt.UserRole)) if item.data(Qt.UserRole) else None)
        self.places.itemActivated.connect(lambda item: self.navigate(item.data(Qt.UserRole)) if item.data(Qt.UserRole) else None)
        self.places.setContextMenuPolicy(Qt.CustomContextMenu); self.places.customContextMenuRequested.connect(self.place_menu)
        side.addWidget(self.places,1)
        side_note=QLabel('Wysun'); side_note.setObjectName('sidebarNote'); side.addWidget(side_note)
        self.splitter.addWidget(self.sidebar)
        main=QWidget(); main.setObjectName('workspace')
        workspace_layout=QVBoxLayout(main); workspace_layout.setContentsMargins(0,8,10,8); workspace_layout.setSpacing(0)
        content=QFrame(); content.setObjectName('contentSurface'); workspace_layout.addWidget(content)
        main_layout=QVBoxLayout(content); main_layout.setContentsMargins(1,1,1,1); main_layout.setSpacing(0)
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True); self.tabs.tabBar().setDrawBase(False)
        self.tabs.setTabsClosable(True); self.tabs.setMovable(True); self.tabs.setTabBarAutoHide(True)
        self.tabs.tabCloseRequested.connect(self.close_tab); self.tabs.currentChanged.connect(self.tab_changed)
        main_layout.addWidget(self.tabs,1)
        self.progress=QProgressBar(); self.progress.setRange(0,0); self.progress.setTextVisible(False); self.progress.setFixedHeight(3); self.progress.hide(); main_layout.addWidget(self.progress)
        self.pathbar=QWidget(); self.pathbar.setObjectName('pathbar'); self.pathbar.setFixedHeight(36); self.pathbar.installEventFilter(self); self.pathbar.setToolTip('Doble clic para copiar la ruta absoluta')
        self.path_layout=QHBoxLayout(self.pathbar); self.path_layout.setContentsMargins(12,0,12,0); self.path_layout.setSpacing(0)
        self.path_edit=QLineEdit(); self.path_edit.setAccessibleName('Ruta de la carpeta'); self.path_edit.hide()
        self.path_edit.returnPressed.connect(self.enter_path)
        self.path_layout.addWidget(self.path_edit)
        main_layout.addWidget(self.pathbar)
        self.splitter.addWidget(main)
        self.inspector=QWidget(); self.inspector.setObjectName('inspector'); self.inspector.setMinimumWidth(260); self.inspector.setMaximumWidth(16777215)
        details=QVBoxLayout(self.inspector); details.setContentsMargins(16,16,16,16); details.setSpacing(10)
        heading=QHBoxLayout(); heading.addWidget(QLabel("Vista previa"),1)
        close_preview=button("×","info",self.close_inspector,"Cerrar vista previa")
        from PySide6.QtGui import QIcon
        close_preview.setIcon(QIcon()); heading.addWidget(close_preview); details.addLayout(heading)
        self.inline_preview=SelectionPreview(); self.inline_preview.fullscreenRequested.connect(self.set_preview_fullscreen); details.addWidget(self.inline_preview,1)
        self.inspector_animation=QVariantAnimation(self); self.inspector_animation.setDuration(200); self.inspector_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.inspector_animation.valueChanged.connect(self.animate_inspector_width)
        self.detail_icon=QLabel(); self.detail_icon.setAlignment(Qt.AlignCenter); self.detail_icon.hide()
        self.detail_name=QLabel('Sin selección'); self.detail_name.setObjectName('inspectorName'); self.detail_name.setWordWrap(True)
        self.detail_name.setTextFormat(Qt.PlainText); self.detail_name.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); details.addWidget(self.detail_name)
        self.detail_text=QLabel(); self.detail_text.setObjectName('muted'); self.detail_text.setWordWrap(True); self.detail_text.setTextFormat(Qt.PlainText)
        self.detail_text.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); self.detail_text.setTextInteractionFlags(Qt.TextSelectableByMouse); details.addWidget(self.detail_text)
        self.detail_location=LocationLabel(); self.detail_location.setObjectName('inspectorLocation'); details.addWidget(self.detail_location)
        self.open_button=button('Abrir','forward',self.open_selected); details.addWidget(self.open_button)
        self.splitter.addWidget(self.inspector); self.inspector.hide(); self.splitter.setStretchFactor(1,1); self.splitter.setSizes([190,970,0])
        self.hidden_button=QPushButton(self); self.hidden_button.setCheckable(True); self.hidden_button.setChecked(self.hidden); self.hidden_button.hide()
        self.statusBar().setSizeGripEnabled(False)
        self.load_places(); self.add_shortcuts()
        if isinstance(paths,(str,Path)): paths=[paths]
        for path in paths or [str(Path.home())]:
            target=Path(path).expanduser(); self.new_tab(str(target if target.is_dir() else target.parent))
        self.set_grid(self.grid_mode); self.selection_changed(); self.current().view().setFocus()

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def enter_path(self):
        self.navigate(self.path_edit.text()); self.path_edit.hide(); self.update_breadcrumbs()

    def update_breadcrumbs(self):
        while self.path_layout.count()>1:
            item=self.path_layout.takeAt(1)
            if item.widget(): item.widget().deleteLater()
        if self.path_edit.isVisible(): return
        path=Path(self.current().path)
        home=Path.home()
        chain=list(reversed(path.parents))+[path]
        if home in chain: chain=chain[chain.index(home):]
        if len(chain)>4: chain=[chain[0]]+chain[-3:]
        for i,part in enumerate(chain):
            if i:
                arrow=QLabel('›'); arrow.setObjectName('muted'); self.path_layout.addWidget(arrow)
            label='Inicio' if part==home else part.name or 'Sistema'
            control=BreadcrumbButton(label,str(part)); control.setObjectName('breadcrumb'); control.setToolTip(str(part)); control.setMaximumWidth(180)
            control.navigateRequested.connect(self.navigate); control.copyRequested.connect(self.copy_current_path); self.path_layout.addWidget(control)
        self.path_layout.addStretch()

    def sort_menu(self):
        from PySide6.QtGui import QActionGroup
        menu=QMenu(self);columns=QActionGroup(menu);directions=QActionGroup(menu)
        header=self.current().tree.header()
        for column,title in enumerate(('Nombre','Tamaño','Tipo','Fecha de modificación')):
            action=menu.addAction(title);action.setCheckable(True);columns.addAction(action)
            action.setChecked(header.sortIndicatorSection()==column)
            action.triggered.connect(lambda checked=False,c=column:self.apply_sort(c,self.current().tree.header().sortIndicatorOrder()))
        menu.addSeparator()
        for title,order in [('Ascendente',Qt.AscendingOrder),('Descendente',Qt.DescendingOrder)]:
            action=menu.addAction(title);action.setCheckable(True);directions.addAction(action)
            action.setChecked(header.sortIndicatorOrder()==order)
            action.triggered.connect(lambda checked=False,o=order:self.apply_sort(self.current().tree.header().sortIndicatorSection(),o))
        animate_popup(menu);menu.exec(self.sort_button.mapToGlobal(self.sort_button.rect().bottomLeft()))

    def apply_sort(self,column,order):
        tab=self.current();tab.tree.sortByColumn(column,order);tab.model.sort((column+1)%4,order);tab.model.sort(column,order);tab.grid.doItemsLayout()

    def more_menu(self):
        menu=QMenu(self)
        menu.addAction(ui_icon('plus'),'Nueva pestaña',self.new_tab)
        menu.addAction(ui_icon('up'),'Carpeta superior',self.up)
        menu.addSeparator()
        menu.addAction(ui_icon('pin'),'Añadir a favoritos',self.bookmark)
        menu.addAction(ui_icon('terminal'),'Abrir terminal aquí',self.terminal)
        action=menu.addAction('Mostrar archivos ocultos'); action.setCheckable(True); action.setChecked(self.hidden); action.triggered.connect(self.toggle_hidden)
        menu.addSeparator()
        menu.addAction('Propiedades',self.properties)
        animate_popup(menu)
        menu.exec(self.more_button.mapToGlobal(self.more_button.rect().bottomLeft()))

    def current(self):
        return self.tabs.currentWidget()

    def place_title(self, path):
        for i in range(self.places.count()):
            item=self.places.item(i)
            if item.data(Qt.UserRole)==path:return item.text()
        return Path(path).name or 'Sistema'

    def cancel_path(self):
        if getattr(self,'fullscreen_restore',None) is not None:
            if self.inline_preview.player:self.inline_preview.player.set_fullscreen(False)
            return
        self.path_edit.hide(); self.update_breadcrumbs(); self.current().view().setFocus()

    def load_places(self):
        self.places.clear()
        def section(title):
            item=QListWidgetItem(title); item.setFlags(Qt.NoItemFlags); item.setSizeHint(QSize(150,29))
            from PySide6.QtGui import QColor, QFont
            item.setForeground(QColor(COLORS['muted'])); font=QFont(); font.setPointSize(9); font.setBold(True); item.setFont(font); self.places.addItem(item)
        def place(title,path,symbol,bookmark=False):
            item=QListWidgetItem(ui_icon(symbol,18,COLORS['accent']),title);item.setData(Qt.UserRole,path); item.setToolTip(path)
            item.setData(Qt.UserRole+1,bookmark); item.setSizeHint(QSize(150,32)); self.places.addItem(item)
        section('Favoritos')
        place('Inicio',str(Path.home()),'home')
        for title,location,symbol in [('Escritorio',QStandardPaths.DesktopLocation,'desktop'),('Descargas',QStandardPaths.DownloadLocation,'download'),('Documentos',QStandardPaths.DocumentsLocation,'documents'),('Imágenes',QStandardPaths.PicturesLocation,'images'),('Vídeos',QStandardPaths.MoviesLocation,'video'),('Música',QStandardPaths.MusicLocation,'music')]:
            path=QStandardPaths.writableLocation(location)
            if path and Path(path).is_dir():place(title,path,symbol)
        self.bookmarks=self.settings.value('bookmarks',[],type=list)
        for path in self.bookmarks:place(Path(path).name or path,path,'pin',True)
        section('Ubicaciones');place('Sistema','/','drive')

    def bookmark(self):
        path = self.current().path
        if path not in self.bookmarks:
            self.bookmarks.append(path)
            self.settings.setValue('bookmarks', self.bookmarks)
            self.load_places()

    def place_menu(self, point):
        item = self.places.itemAt(point)
        if not item or not item.data(Qt.UserRole + 1):
            return
        menu = QMenu(self)
        menu.addAction('Quitar de favoritos', lambda: self.remove_bookmark(item.data(Qt.UserRole)))
        animate_popup(menu)
        menu.exec(self.places.viewport().mapToGlobal(point))

    def remove_bookmark(self, path):
        self.bookmarks.remove(path)
        self.settings.setValue('bookmarks', self.bookmarks)
        self.load_places()

    def new_tab(self, path=None):
        if not isinstance(path, (str, Path)):
            path = self.current().path if self.current() else str(Path.home())
        tab = FolderTab(path, self.hidden, self.grid_mode)
        tab.changed.connect(self.update_location)
        tab.selected.connect(self.selection_changed)
        tab.activated.connect(self.open_path)
        tab.context.connect(self.context_menu)
        self.add_view_shortcuts(tab.tree)
        self.add_view_shortcuts(tab.grid)
        index = self.tabs.addTab(tab, Path(tab.path).name or 'Sistema')
        self.tabs.setCurrentIndex(index)
        self.update_location()

    def close_tab(self, index):
        if self.tabs.count() == 1:
            self.close()
        else:
            page = self.tabs.widget(index)
            self.tabs.removeTab(index)
            page.deleteLater()

    def tab_changed(self, *_):
        if self.current():
            self.filter_edit.blockSignals(True)
            filters = self.current().model.nameFilters()
            self.filter_edit.setText(filters[0][1:-1] if filters else '')
            self.filter_edit.blockSignals(False)
            self.update_location()
            self.selection_changed()

    def navigate(self, path):
        if not self.current().navigate(path):
            QMessageBox.warning(self, 'Carpeta no disponible', 'No se puede acceder a esta carpeta:\n' + str(path))
            self.path_edit.setText(self.current().path)
        else:
            self.filter_edit.clear()

    def up(self):
        self.navigate(str(Path(self.current().path).parent))

    def update_location(self):
        tab = self.current()
        if not tab:
            return
        self.path_edit.setText(tab.path)
        title = Path(tab.path).name or 'Sistema'
        self.folder_title.setText(self.place_title(tab.path))
        self.folder_title.setToolTip(tab.path)
        self.update_breadcrumbs()
        for i in range(self.places.count()):
            item=self.places.item(i)
            if item.data(Qt.UserRole)==tab.path:
                self.places.setCurrentItem(item); break
        else: self.places.clearSelection()
        self.tabs.setTabText(self.tabs.currentIndex(), title)
        self.tabs.setTabToolTip(self.tabs.currentIndex(), tab.path)
        self.back_button.setEnabled(tab.position > 0)
        self.forward_button.setEnabled(tab.position < len(tab.history) - 1)
        self.setWindowTitle(title + ' · Wysun Files')
        self.update_status()

    def update_status(self):
        tab = self.current()
        if not tab or self.jobs:
            return
        count = tab.model.rowCount(tab.model.index(tab.path))
        selection = tab.selected_paths()
        try:
            free = human_size(shutil.disk_usage(tab.path).free) + ' disponibles'
        except OSError:
            free = ''
        self.statusBar().showMessage(f'{count} elementos' + (f' · {len(selection)} seleccionados' if selection else '') + '     ·     ' + free)

    def filter_files(self, value):
        if self.current():
            self.current().model.setNameFilters(['*' + value + '*'] if value else [])
            self.current().refresh_count()

    def toggle_hidden(self):
        self.hidden = not self.hidden
        self.hidden_button.setChecked(self.hidden)
        self.settings.setValue('hidden', self.hidden)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_hidden(self.hidden)

    def set_grid(self, enabled):
        self.grid_mode = enabled
        self.settings.setValue('grid', enabled)
        self.settings.setValue('viewMode', 'icons' if enabled else 'list')
        self.list_button.setChecked(not enabled)
        self.grid_button.setChecked(enabled)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_grid(enabled)

    def set_preview_fullscreen(self,enabled):
        if enabled:
            if getattr(self,'fullscreen_restore',None) is not None:return
            widgets=[self.toolbar,self.sidebar,self.splitter.widget(1),self.statusBar(),self.detail_name,self.detail_text,self.open_button,self.inline_preview.metadata,self.detail_location]
            self.fullscreen_restore=([ (widget,not widget.isHidden()) for widget in widgets],self.windowState(),self.splitter.sizes(),self.saveGeometry())
            for widget in widgets:widget.hide()
            self.showFullScreen()
        else:
            state=getattr(self,'fullscreen_restore',None)
            if state is None:return
            self.fullscreen_restore=None
            widgets,window_state,sizes,geometry=state
            self.setWindowState(window_state)
            self.restoreGeometry(geometry)
            for widget,visible in widgets:widget.setVisible(visible)
            self.splitter.setSizes(sizes)

    def copy_current_path(self):
        QApplication.clipboard().setText(os.path.abspath(self.current().path))
        self.statusBar().showMessage('Ruta absoluta copiada',2500)

    def eventFilter(self, watched, event):
        if watched is getattr(self,'pathbar',None) and event.type()==QEvent.MouseButtonDblClick and event.button()==Qt.LeftButton:
            self.copy_current_path();return True
        return super().eventFilter(watched,event)

    def animate_inspector_width(self,value):
        total=self.splitter.width();side=self.sidebar.width() if self.sidebar.isVisible() else 0
        self.splitter.setSizes([side,max(200,total-side-int(value)),int(value)])

    def reveal_inspector(self):
        if self.inspector.isVisible():return
        self.inspector.show();self.details_button.setChecked(True)
        available=self.splitter.width()-(self.sidebar.width() if self.sidebar.isVisible() else 0)
        target=max(260,int(available*.48))
        self.inspector_animation.stop()
        if reduced_motion():self.animate_inspector_width(target)
        else:
            self.inspector_animation.setStartValue(260);self.inspector_animation.setEndValue(target);self.inspector_animation.start()

    def close_inspector(self):
        self.inspector_animation.stop();self.inspector.hide();self.details_button.setChecked(False)
        self.inline_preview.set_path('')

    def toggle_inspector(self):
        paths=self.current().selected_paths()
        if self.details_button.isChecked() and len(paths)==1 and SelectionPreview.supported(paths[0]):
            self.reveal_inspector();self.inline_preview.set_path(paths[0]);self.inline_preview.show()
        else:self.close_inspector()
        QTimer.singleShot(0,self,self.fit_current_columns)

    def fit_current_columns(self):
        if self.current():
            self.current().fit_columns()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self,'inspector'): return
        self.app_label.setVisible(self.width()>=900)
        self.filter_edit.setFixedWidth(165 if self.width()>=1000 else 135)
        QTimer.singleShot(0,self,self.fit_current_columns)

    def selection_changed(self):
        tab = self.current()
        if not tab:
            return
        paths = tab.selected_paths()
        media=paths[0] if len(paths)==1 and SelectionPreview.supported(paths[0]) else ''
        self.details_button.setEnabled(bool(media))
        if media:self.reveal_inspector()
        else:self.close_inspector()
        self.inline_preview.set_path(media)
        self.inline_preview.setVisible(bool(media))
        self.open_button.setEnabled(bool(paths))
        self.detail_icon.setPixmap(file_icon(paths[0] if paths else tab.path,96).pixmap(96,96))
        self.detail_location.setText('')
        if len(paths) == 1:
            path = Path(paths[0])
            self.detail_name.setText(path.name)
            try:
                stat = path.stat()
                modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%d %b %Y · %H:%M')
                kind = 'Carpeta' if path.is_dir() else (path.suffix.upper().lstrip('.') or 'Archivo')
                self.detail_text.setText(f'{kind} · {human_size(stat.st_size) if path.is_file() else ""}' + (' · Enlace simbólico' if path.is_symlink() else '') + f'\nModificado {modified}')
                self.detail_location.setText(str(path.parent))
            except OSError as error:
                self.detail_text.setText(str(error))
        elif paths:
            self.detail_name.setText(f'{len(paths)} elementos')
            self.detail_text.setText('Copia, mueve o envía la selección a la papelera desde el menú contextual.')
        else:
            self.detail_name.setText('Sin selección')
            self.detail_text.setText('Selecciona un archivo para ver sus detalles.')
        self.update_status()

    def open_path(self, path):
        if Path(path).is_dir():
            self.navigate(path)
        elif Path(path).suffix.lower()=='.pdf':
            from files_browser import open_pdf
            try:open_pdf(path)
            except (OSError,RuntimeError,subprocess.SubprocessError) as error:
                QMessageBox.warning(self,'No se pudo abrir el PDF',str(error))
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            QMessageBox.warning(self, 'No se pudo abrir', 'No hay una aplicación disponible para abrir este archivo.')

    def open_selected(self):
        paths = self.current().selected_paths()
        if len(paths) > 10:
            QMessageBox.information(self, 'Selecciona menos archivos', 'Abre hasta 10 archivos a la vez.')
            return
        for path in paths:
            self.open_path(path)

    def preview(self):
        paths=self.current().selected_paths()
        if len(paths)==1 and SelectionPreview.supported(paths[0]):
            self.reveal_inspector();self.inline_preview.set_path(paths[0]);self.inline_preview.show()

    def release_preview(self, viewer):
        def release():
            if viewer in self.viewers:
                self.viewers.remove(viewer)
        if viewer.job and viewer.job.isRunning():
            viewer.job.finished.connect(release)
        else:
            release()

    def terminal(self):
        for command in ('ghostty', 'x-terminal-emulator', 'alacritty', 'kitty', 'xterm'):
            binary = shutil.which(command)
            if binary:
                subprocess.Popen([binary], cwd=self.current().path, start_new_session=True)
                return
        QMessageBox.information(self, 'Terminal no disponible', 'No se encontró una terminal compatible.')

    def copy(self, cut=False):
        paths = self.current().selected_paths()
        if not paths:
            return
        mime = QMimeData()
        urls = [QUrl.fromLocalFile(path) for path in paths]
        mime.setUrls(urls)
        mime.setData('x-special/gnome-copied-files', (('cut' if cut else 'copy') + '\n' + '\n'.join(url.toString() for url in urls)).encode())
        mime.setText('\n'.join(paths))
        QApplication.clipboard().setMimeData(mime)
        self.statusBar().showMessage(f'{len(paths)} elementos preparados para ' + ('mover' if cut else 'copiar'))

    def paste(self):
        mime = QApplication.clipboard().mimeData() or QMimeData()
        paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
        if not paths:
            return
        cut = bytes(mime.data('x-special/gnome-copied-files')).startswith(b'cut\n')
        self.operation('move' if cut else 'copy', paths, self.current().path)

    def new_folder(self):
        name, ok = QInputDialog.getText(self, 'Nueva carpeta', 'Nombre de la carpeta:')
        if ok and self.valid_name(name):
            self.operation('mkdir', [], str(Path(self.current().path) / name))

    def valid_name(self, name):
        if not name or name in ('.', '..') or '/' in name or '\x00' in name:
            QMessageBox.warning(self, 'Nombre inválido', 'Escribe un nombre que no contenga barras ni sea «.» o «..».')
            return False
        return True

    def rename(self):
        paths = self.current().selected_paths()
        if len(paths) != 1:
            return
        path = Path(paths[0])
        name, ok = QInputDialog.getText(self, 'Cambiar nombre', 'Nuevo nombre:', text=path.name)
        if ok and name != path.name and self.valid_name(name):
            self.operation('rename', paths, str(path.parent / name))

    def trash(self):
        paths = self.current().selected_paths()
        if paths and QMessageBox.question(self, 'Enviar a la papelera', f'¿Enviar {len(paths)} elementos a la papelera?\nPodrás recuperarlos desde la papelera del sistema.', QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.operation('trash', paths, '')

    def operation(self, kind, sources, destination):
        if self.jobs:
            QMessageBox.information(self, 'Operación en curso', 'Espera a que termine la operación actual.')
            return
        job = OperationJob(kind, sources, destination, self)
        self.jobs.append(job)
        self.progress.show()
        self.statusBar().showMessage('Trabajando… Mantén esta ventana abierta hasta que termine.')
        clipboard_snapshot = bytes((QApplication.clipboard().mimeData() or QMimeData()).data('x-special/gnome-copied-files'))
        job.result.connect(lambda result, error: self.operation_result(kind, error, clipboard_snapshot))
        job.finished.connect(lambda: self.operation_finished(job))
        job.start()

    def operation_result(self, kind, error, clipboard_snapshot):
        if error:
            QMessageBox.warning(self, 'La operación no se completó', error + '\n\nRevisa las carpetas de origen y destino antes de reintentar; algunas operaciones podrían haberse completado.')
        elif kind == 'move':
            mime = QApplication.clipboard().mimeData() or QMimeData()
            if clipboard_snapshot.startswith(b'cut\n') and bytes(mime.data('x-special/gnome-copied-files')) == clipboard_snapshot:
                QApplication.clipboard().clear()

    def operation_finished(self, job):
        self.jobs.remove(job)
        job.deleteLater()
        self.progress.setVisible(bool(self.jobs))
        self.update_status()

    def properties(self):
        paths = self.current().selected_paths() or [self.current().path]
        if len(paths) != 1:
            return
        path = Path(paths[0])
        try:
            stat = path.lstat()
            text = f'Ruta: {path}\nTipo: {"Enlace simbólico" if path.is_symlink() else "Carpeta" if path.is_dir() else "Archivo"}\nTamaño: {human_size(stat.st_size)}\nPermisos: {oct(stat.st_mode & 0o777)}\nModificado: {datetime.datetime.fromtimestamp(stat.st_mtime)}'
            if path.is_symlink():
                text += '\nDestino del enlace: ' + os.readlink(path)
            QMessageBox.information(self, 'Propiedades', text)
        except OSError as error:
            QMessageBox.warning(self, 'Propiedades', str(error))

    def context_menu(self, point):
        paths = self.current().selected_paths()
        menu = QMenu(self)
        for title, symbol, callback, enabled in [('Abrir', 'external-link', self.open_selected, bool(paths)), ('Abrir en nueva pestaña', 'plus', lambda: self.new_tab(paths[0]), len(paths) == 1 and Path(paths[0]).is_dir() if paths else False)]:
            action = menu.addAction(ui_icon({'external-link':'forward','eye':'info'}.get(symbol,symbol)), title, callback)
            action.setEnabled(enabled)
        menu.addSeparator()
        for title, callback, enabled in [('Copiar', lambda: self.copy(False), bool(paths)), ('Cortar', lambda: self.copy(True), bool(paths)), ('Pegar aquí', self.paste, bool(QApplication.clipboard().mimeData() and QApplication.clipboard().mimeData().hasUrls())), ('Cambiar nombre', self.rename, len(paths) == 1), ('Enviar a la papelera', self.trash, bool(paths))]:
            action = menu.addAction(title, callback)
            action.setEnabled(enabled and not self.jobs)
        menu.addSeparator()
        menu.addAction('Nueva carpeta', self.new_folder)
        menu.addAction('Terminal aquí', self.terminal)
        menu.addAction('Propiedades', self.properties)
        animate_popup(menu)
        menu.exec(point)

    def focus_path(self):
        self.path_edit.show()
        self.update_breadcrumbs()
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def add_shortcuts(self):
        self.shortcuts = []
        actions = {'Ctrl+1': lambda:self.set_grid(True), 'Ctrl+2': lambda:self.set_grid(False), 'Escape': self.cancel_path, 'Ctrl+L': self.focus_path, 'Ctrl+T': self.new_tab, 'Ctrl+W': lambda: self.close_tab(self.tabs.currentIndex()), 'Ctrl+H': self.toggle_hidden, 'Ctrl+F': self.filter_edit.setFocus, 'Alt+Left': lambda: self.current().go(-1), 'Alt+Right': lambda: self.current().go(1), 'Alt+Up': self.up, 'Ctrl+Shift+N': self.new_folder}
        for key, action in actions.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)

    def add_view_shortcuts(self, view):
        for key, action in {'Ctrl+C': lambda: self.copy(False), 'Ctrl+X': lambda: self.copy(True), 'Ctrl+V': self.paste, 'F2': self.rename, 'Delete': self.trash, 'Space': self.preview, 'Return': self.open_selected, 'Ctrl+A': lambda: self.current().view().selectAll()}.items():
            shortcut = QShortcut(QKeySequence(key), view)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)

    def closeEvent(self, event):
        if self.inline_preview.player:self.inline_preview.player.stop()
        self.inline_preview.timer.stop();self.inline_preview.request=None
        if self.inline_preview.job is not None:
            self.statusBar().showMessage('Terminando vista previa…')
            self.inline_preview.job.finished.connect(self.close)
            event.ignore();return
        if any(viewer.job and viewer.job.isRunning() for viewer in self.viewers):
            self.statusBar().showMessage('Espera a que termine la vista previa antes de cerrar.')
            event.ignore()
            return
        if self.jobs:
            QMessageBox.information(self, 'Operación en curso', 'Espera a que termine la operación antes de cerrar. Tus archivos se están procesando.')
            event.ignore()
            return
        for viewer in list(self.viewers):
            viewer.close()
        self.settings.sync()
        super().closeEvent(event)
