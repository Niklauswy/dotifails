"""Wysun Files main window: places, raised file surface, inspector and quick actions."""
import datetime
import os
from pathlib import Path
import shutil
import subprocess

from PySide6.QtCore import QEasingCurve, QEvent, QMimeData, QSettings, Qt, QThread, QTimer, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QActionGroup, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from file_media import human_size
from files_ops import execute_operation
from theme_tokens import color, on_theme_changed, tokens
from ui_motion import WindowMotion, reduced_motion, reveal_content
from ui_theme import paint_surface
from .chrome import Hero, Segmented, SelectionBar, StatusLine, Surface, TabArea
from .menu import ActionMenu
from .kit import IconButton, PillButton, apply_kit_style, metric, text_font
from .model import DATE, KIND, NAME, SIZE
from .pathbar import PathBar
from .preview import SelectionPreview
from .sheet import Sheet, Toast
from .sidebar import Sidebar
from .tab import FolderTab

INSPECTOR_WIDTH = 372
RESIZE_MARGIN = 6
SHORTCUTS = '''Alt+K: opciones del elemento actual · escribe para filtrar · Retroceso o ←: carpeta superior
Ctrl+T / Ctrl+W: nueva pestaña / cerrar pestaña
Ctrl+L: escribir una ruta · Alt+←/→: historial · Alt+↑: carpeta superior
Ctrl+F: filtrar nombres · Ctrl+H: archivos ocultos
Ctrl+1 / Ctrl+2: cuadrícula / lista · Ctrl+I: vista previa automática · Ctrl+Tab: cambiar pestaña
Espacio: ampliar la vista previa · F: pantalla completa (vídeo)
Ctrl+C / X / V: copiar, cortar, pegar · F2: cambiar nombre · Supr: papelera
Ctrl+Shift+N: nueva carpeta · Ctrl+Shift+C: copiar ruta · Esc: cerrar o quitar selección'''


class OperationJob(QThread):
    result = Signal(object, str)

    def __init__(self, kind, sources, destination, parent):
        super().__init__(parent)
        self.kind, self.sources, self.destination = kind, sources, destination

    def run(self):
        try:
            self.result.emit(execute_operation(self.kind, self.sources, self.destination), '')
        except Exception as error:
            self.result.emit([], str(error))


class FilesWindow(WindowMotion, QMainWindow):
    def __init__(self, paths=None):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.settings = QSettings('Orbita', 'Files')
        self.jobs, self.viewers = [], []
        self.hidden = self.settings.value('hidden', False, type=bool)
        self.grid_mode = self.settings.value('viewMode', 'icons') == 'icons'
        self.details_on = self.settings.value('details', True, type=bool)
        self.bookmarks = self.settings.value('bookmarks', [], type=list)
        self.expanded, self.fullscreen_restore = False, None
        self.quick_actions = True
        self.shortcuts = []
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('Wysun Archivos')
        self.setMouseTracking(True)
        self.resize(1240, 780)
        self.setMinimumSize(760, 480)
        apply_kit_style(self)
        self._build()
        self.sheet = Sheet(self)
        self.toast = Toast(self.centralWidget())
        self.add_shortcuts()
        if isinstance(paths, (str, Path)):
            paths = [paths]
        for path in paths or [str(Path.home())]:
            target = Path(path).expanduser()
            self.new_tab(str(target if target.is_dir() else target.parent))
        self.set_grid(self.grid_mode)
        self.selection_changed()
        self.current().view().setFocus()
        QApplication.clipboard().dataChanged.connect(self.sync_cut)
        on_theme_changed(self.refresh_theme)

    # ----------------------------------------------------------------- build
    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        margin = metric('space_s')
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(margin)

        left = QVBoxLayout()
        left.setSpacing(metric('space_s'))
        nav = QHBoxLayout()
        nav.setContentsMargins(metric('space_xs'), metric('space_xs'), 0, 0)
        nav.setSpacing(2)
        self.close_button = IconButton('close', 'Cerrar · Ctrl+Q', self.close, size=34)
        self.back_button = IconButton('chevron_left', 'Atrás · Alt+←', lambda: self.current().go(-1), size=34)
        self.forward_button = IconButton('chevron_right', 'Adelante · Alt+→', lambda: self.current().go(1), size=34)
        self.up_button = IconButton('arrow_upward', 'Carpeta superior · Alt+↑', self.up, size=34)
        keys = IconButton('keyboard', 'Atajos de teclado · F1', self.show_shortcuts, size=34)
        for button in (self.close_button, self.back_button, self.forward_button, self.up_button, keys):
            button.setFocusPolicy(Qt.TabFocus)
        nav.addWidget(self.close_button)
        nav.addSpacing(metric('space_s'))
        for button in (self.back_button, self.forward_button, self.up_button):
            nav.addWidget(button)
        nav.addStretch()
        nav.addWidget(keys)
        left.addLayout(nav)
        left.addSpacing(metric('space_s'))
        self.sidebar = Sidebar(self.bookmarks)
        self.sidebar.navigate.connect(self.navigate)
        self.sidebar.bookmark_menu.connect(self.bookmark_menu)
        left.addWidget(self.sidebar, 1)
        self.column = QWidget()
        self.column.setLayout(left)
        self.column.setFixedWidth(244)
        outer.addWidget(self.column)

        self.right = QHBoxLayout()
        self.right.setSpacing(margin)
        self.files_surface = Surface()
        files = self.files_layout = QVBoxLayout(self.files_surface)
        files.setContentsMargins(metric('space_m'), metric('space_m'), metric('space_m'), 0)
        files.setSpacing(metric('space_s'))
        top = QHBoxLayout()
        top.setSpacing(metric('space_s'))
        self.pathbar = PathBar()
        self.pathbar.navigate_requested.connect(self.navigate)
        self.pathbar.copy_requested.connect(self.copy_current_path)
        self.filter_edit = _filter_field()
        self.filter_edit.textChanged.connect(self.filter_files)
        self.filter_edit.textChanged.connect(lambda _t: self._widen_filter())
        self.filter_edit.installEventFilter(self)
        top.addWidget(self.pathbar, 1)
        top.addWidget(self.filter_edit)
        files.addLayout(top)
        tools = QHBoxLayout()
        tools.setSpacing(metric('space_xs'))
        self.view_toggle = Segmented(('grid_view', 'view_list'), ('Cuadrícula · Ctrl+1', 'Lista · Ctrl+2'))
        self.view_toggle.changed.connect(lambda index: self.set_grid(index == 0))
        self.sort_button = IconButton('sort', 'Ordenar', self.sort_menu, variant='tonal', size=38)
        self.details_button = IconButton('right_panel_open', 'Vista previa automática · Ctrl+I', self.toggle_inspector, variant='tonal', size=38, checkable=True)
        self.details_button.setChecked(self.details_on)
        self.details_button.outline = True
        tools.addWidget(self.view_toggle)
        tools.addSpacing(metric('space_s'))
        tools.addWidget(self.sort_button)
        tools.addWidget(self.details_button)
        tools.addStretch()
        self.new_button = PillButton('add', 'Nuevo', self.new_menu, variant='filled', height=38)
        self.more_button = IconButton('more_horiz', 'Más acciones', self.more_menu, size=38)
        tools.addWidget(self.new_button)
        tools.addWidget(self.more_button)
        files.addLayout(tools)
        self.hero = Hero()
        self.hero.kind_changed.connect(self.set_kind)
        files.addWidget(self.hero)
        self.tabs = TabArea()
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.new_requested.connect(self.new_tab)
        files.addWidget(self.tabs, 1)
        self.status = StatusLine()
        files.addWidget(self.status)
        self.selection_bar = SelectionBar(self.files_surface)
        self.selection_bar.action.connect(self.bar_action)
        self.files_surface.resized.connect(self.selection_bar.place)
        self.right.addWidget(self.files_surface, 1)

        self.inspector = Surface()
        inside = QVBoxLayout(self.inspector)
        inside.setContentsMargins(metric('space_l'), metric('space_l'), metric('space_l'), metric('space_l'))
        self.inline_preview = SelectionPreview()
        self.inline_preview.open_requested.connect(self.open_selected)
        self.inline_preview.message.connect(self.say)
        self.inline_preview.link_requested.connect(self.follow_link)
        self.inline_preview.expand_requested.connect(self.toggle_expanded)
        self.inline_preview.fullscreen_requested.connect(self.set_preview_fullscreen)
        inside.addWidget(self.inline_preview)
        self.inspector.setFixedWidth(0)
        self.inspector.hide()
        self.right.addWidget(self.inspector)
        outer.addLayout(self.right, 1)
        self.slide = QVariantAnimation(self, duration=tokens()['motion_enter'] + 40)
        self.slide.setEasingCurve(QEasingCurve.OutCubic)
        self.slide.valueChanged.connect(self._slide_step)
        self.slide.finished.connect(self._slide_done)
        self.slide_mode, self.slide_goal = None, 0

    # -------------------------------------------------------------- feedback
    def say(self, text):
        self.toast.show_message(text)

    def statusBar(self):                      # compatibility with callers that expect a status bar
        return _StatusProxy(self)

    def warn(self, title, message):
        self.sheet.info(title, [('', message)])

    # ------------------------------------------------------------------ tabs
    def current(self):
        return self.tabs.currentWidget()

    def new_tab(self, path=None):
        if not isinstance(path, (str, Path)):
            path = self.current().path if self.current() else str(Path.home())
        tab = FolderTab(path, self.hidden, self.grid_mode)
        tab.changed.connect(self.update_location)
        tab.selected.connect(self.selection_changed)
        tab.activated.connect(self.open_path)
        tab.context.connect(self.context_menu)
        self.add_view_shortcuts(tab.view())
        tab.view().up_requested.connect(self.up)
        tab.view().type_requested.connect(self.type_to_filter)
        index = self.tabs.addTab(tab, Path(tab.path).name or 'Sistema')
        self.tabs.setCurrentIndex(index)
        self.update_location()
        self.sync_cut()

    def close_tab(self, index):
        if self.tabs.count() == 1:
            self.close()
            return
        page = self.tabs.widget(index)
        self.tabs.removeTab(index)
        page.deleteLater()
        if self.current():
            self.current().view().setFocus()

    def tab_changed(self, *_):
        if self.current():
            self.filter_edit.blockSignals(True)
            self.filter_edit.setText(self.current().filter_text)
            self.filter_edit.blockSignals(False)
            self.update_location()
            self.selection_changed()

    # ------------------------------------------------------------ navigation
    def navigate(self, path):
        if not self.current().navigate(path):
            self.warn('Carpeta no disponible', 'No se puede acceder a esta carpeta:\n' + str(path))
        else:
            self.filter_edit.clear()
            self.current().view().setFocus()

    def up(self):
        here = self.current().path
        if here == '/':
            return
        if self.current().navigate(str(Path(here).parent), True, -1):
            self.filter_edit.clear()
        self.current().select_when_ready(here)         # keep your place: the folder you left is selected

    def follow_link(self, target):
        """A relative link inside a previewed Markdown file: open that file or folder here."""
        base = Path(self.inline_preview.path).parent
        path = (base / target.split('#')[0]).resolve()
        if path.is_dir():
            self.navigate(str(path))
        elif path.exists():
            self.navigate(str(path.parent))
            self.select_path(str(path))

    def select_path(self, path):
        tab = self.current()
        index = tab.model.index(path)
        if index.isValid():
            tab.view().selectionModel().select(index, tab.view().selectionModel().ClearAndSelect)
            tab.view().scrollTo(index)

    def update_location(self):
        tab = self.current()
        if not tab:
            return
        title = Path(tab.path).name or 'Sistema'
        self.pathbar.set_path(tab.path)
        self.hero.show_kind(getattr(tab, 'kind', 'all'))
        self.sidebar.set_current(tab.path)
        self.tabs.setTabText(self.tabs.currentIndex(), title)
        self.tabs.setTabToolTip(self.tabs.currentIndex(), tab.path)
        self.back_button.setEnabled(tab.position > 0)
        self.forward_button.setEnabled(tab.position < len(tab.history) - 1)
        self.up_button.setEnabled(tab.path != '/')
        self.setWindowTitle(self.window_title(title))
        self.update_status()

    def place_title(self, path):
        if path == str(Path.home()):
            return 'Inicio'
        return Path(path).name or 'Sistema'

    def window_title(self, folder):
        return folder + ' · Wysun Archivos'

    def update_status(self):
        tab = self.current()
        if not tab or self.jobs:
            return
        count = tab.model.rowCount(tab.model.index(tab.path))
        selection = tab.selected_paths()
        try:
            free = human_size(shutil.disk_usage(tab.path).free) + ' libres'
        except OSError:
            free = ''
        root_index = tab.model.index(tab.path)
        folders = sum(1 for row in range(count) if tab.model.isDir(tab.model.index(row, 0, root_index)))
        files = count - folders
        total = sum(tab.model.size(tab.model.index(row, 0, root_index)) for row in range(min(count, 4000))
                    if not tab.model.isDir(tab.model.index(row, 0, root_index)))
        parts = [f'{folders} carpeta' + ('' if folders == 1 else 's'), f'{files} archivo' + ('' if files == 1 else 's')]
        if total:
            parts.append(human_size(total))
        self.hero.set_info(self.place_title(tab.path), ' · '.join(parts))
        left = f'{count} elemento' + ('' if count == 1 else 's')
        if selection:
            left += f' · {len(selection)} seleccionado' + ('' if len(selection) == 1 else 's')
        self.status.set_text(left, free)

    # ----------------------------------------------------------- presentation
    def set_grid(self, enabled):
        self.grid_mode = enabled
        self.settings.setValue('viewMode', 'icons' if enabled else 'list')
        self.view_toggle.set_index(0 if enabled else 1)
        for number in range(self.tabs.count()):
            self.tabs.widget(number).set_grid(enabled)
        self.arrange_inspector()

    def set_kind(self, kind):
        if self.current():
            self.current().set_kind(kind)

    def filter_files(self, value):
        if self.current():
            self.current().set_filter(value)

    def toggle_hidden(self):
        self.hidden = not self.hidden
        self.settings.setValue('hidden', self.hidden)
        for number in range(self.tabs.count()):
            self.tabs.widget(number).set_hidden(self.hidden)

    def sort_menu(self):
        menu = ActionMenu(self)
        header = self.current().header
        for column, title in ((NAME, 'Nombre'), (DATE, 'Fecha de modificación'), (SIZE, 'Tamaño'), (KIND, 'Tipo')):
            menu.add('sort', title, lambda c=column: self.apply_sort(c, self.current().header.order), checked=header.column == column)
        menu.separator()
        for title, order, symbol in (('Ascendente', Qt.AscendingOrder, 'arrow_upward'), ('Descendente', Qt.DescendingOrder, 'arrow_downward')):
            menu.add(symbol, title, lambda o=order: self.apply_sort(self.current().header.column, o), checked=header.order == order)
        menu.popup(self.sort_button.mapToGlobal(self.sort_button.rect().bottomLeft()))

    def apply_sort(self, column, order):
        self.current().sort(column, order)

    def new_menu(self):
        menu = ActionMenu(self)
        menu.add('create_new_folder', 'Carpeta', self.new_folder, 'Ctrl+Shift+N')
        menu.add('note_add', 'Archivo vacío', self.new_file)
        menu.popup(self.new_button.mapToGlobal(self.new_button.rect().bottomLeft()))

    def more_menu(self):
        menu = ActionMenu(self)
        menu.add('tab_new_right', 'Nueva pestaña', self.new_tab, 'Ctrl+T')
        menu.add('arrow_upward', 'Carpeta superior', self.up, 'Alt+↑')
        menu.separator()
        menu.add('bookmark_add', 'Añadir a marcadores', self.bookmark)
        menu.add('terminal', 'Abrir terminal aquí', self.terminal)
        menu.add('visibility', 'Archivos ocultos', self.toggle_hidden, 'Ctrl+H', checked=self.hidden)
        menu.separator()
        menu.add('content_copy', 'Copiar ruta de la carpeta', self.copy_current_path, 'Ctrl+Shift+C')
        menu.add('info', 'Propiedades', self.properties)
        menu.popup(self.more_button.mapToGlobal(self.more_button.rect().bottomLeft()))

    # ------------------------------------------------------------- inspector
    def wants_inspector(self):
        """The details panel opens only for a single file that has something to show."""
        tab = self.current()
        paths = tab.selected_paths() if tab else []
        return self.details_on and self.width() >= 1000 and len(paths) == 1 and SelectionPreview.supported(paths[0])

    def inspector_target(self):
        """About half of the area right of the places column, within sane bounds."""
        total = self.width() - self.column.width() - metric('space_s') * 3
        return max(INSPECTOR_WIDTH, min(round(total * .5), 860))

    def arrange_inspector(self):
        if self.expanded or self.fullscreen_restore is not None or not hasattr(self, 'slide'):
            return
        show = self.wants_inspector()
        target = self.inspector_target() if show else 0
        running = self.slide.state() == QVariantAnimation.Running
        if (running and self.slide_goal == target) or (not running and self.inspector.width() == target
                                                         and self.inspector.isVisible() == show):
            return
        self.slide.stop()
        self.slide_goal, self.slide_mode = target, ('inspector', show)
        if show:
            self.inspector.show()
        start = self.inspector.width() if self.inspector.isVisible() else 0
        if reduced_motion(self):
            self._slide_step(target)
            self._slide_done()
            return
        self.slide.setStartValue(start)
        self.slide.setEndValue(target)
        self.slide.start()

    def toggle_inspector(self):
        self.details_on = self.details_button.isChecked()
        self.settings.setValue('details', self.details_on)
        if self.expanded and not self.details_on:
            self.set_expanded(False)
            return
        if self.details_on and self.width() < 1000:
            self.say('Amplía la ventana para ver el panel de detalles')
        if self.details_on:
            paths = self.current().selected_paths()
            self.inline_preview.set_selection(paths if self.wants_inspector() else [], self.current().path)
        self.arrange_inspector()

    def _slide_step(self, value):
        mode = self.slide_mode
        if mode and mode[0] == 'inspector':
            self.inspector.setFixedWidth(max(0, round(float(value))))

    def _slide_done(self):
        mode, self.slide_mode = self.slide_mode, None
        if mode and mode[0] == 'inspector' and not mode[1] and self.slide_goal == 0:
            self.inspector.hide()
            self.inline_preview.set_selection([], '')

    def toggle_expanded(self):
        self.set_expanded(not self.expanded)

    def set_expanded(self, enabled):
        if enabled == self.expanded:
            return
        paths = self.current().selected_paths()
        if enabled and not (len(paths) == 1 and SelectionPreview.supported(paths[0])):
            self.say('Selecciona un archivo con vista previa')
            return
        self.slide.stop()
        self.slide_mode = None
        self.expanded = enabled
        spacing = self.right.spacing()
        self.expand_start = self.inspector.width() if self.inspector.isVisible() else 0
        self.right_total = self.files_surface.width() + (self.inspector.width() if self.inspector.isVisible() else 0) + spacing
        if enabled:
            self.inline_preview.set_selection(paths, self.current().path)
            self.inspector.show()
            self.inspector.setFixedWidth(self.expand_start)
            self.files_surface.setFixedWidth(self.files_surface.width())
        else:
            self.files_surface.show()
        self.right.setStretch(0, 0)
        self.right.setStretch(1, 0)
        self.expand_anim = QVariantAnimation(self, duration=tokens()['motion_enter'] + 60)
        self.expand_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.expand_anim.setStartValue(0.0 if enabled else 1.0)
        self.expand_anim.setEndValue(1.0 if enabled else 0.0)
        self.expand_anim.valueChanged.connect(self._expand_step)
        self.expand_anim.finished.connect(self._expand_done)
        if reduced_motion(self):
            self._expand_step(self.expand_anim.endValue())
            self._expand_done()
        else:
            self.expand_anim.start()

    def _expand_step(self, value):
        value = float(value)
        spacing = self.right.spacing()
        inspector = round(self.expand_start + (self.right_total - spacing - self.expand_start) * value)
        self.inspector.setFixedWidth(inspector)
        self.files_surface.setFixedWidth(max(0, self.right_total - spacing - inspector))

    def _expand_done(self):
        for surface in (self.files_surface, self.inspector):
            surface.setMinimumWidth(0)
            surface.setMaximumWidth(16777215)
        if self.expanded:
            self.files_surface.hide()
            self.right.setStretch(1, 1)
        else:
            self.right.setStretch(0, 1)
            self.right.setStretch(1, 0)
            self.inspector.setFixedWidth(self.inspector_target() if self.wants_inspector() else 0)
            self.inspector.setVisible(self.wants_inspector())
            if not self.wants_inspector():
                self.inline_preview.set_selection([], '')
            self.current().view().setFocus()


    def set_preview_fullscreen(self, enabled):
        if enabled:
            if self.fullscreen_restore is not None:
                return
            if not self.expanded:
                self.set_expanded(True)
            self.fullscreen_restore = (self.windowState(), self.saveGeometry(), self.column.isVisible())
            self.column.hide()
            self.showFullScreen()
        else:
            state = self.fullscreen_restore
            if state is None:
                return
            self.fullscreen_restore = None
            window_state, geometry, column = state
            self.setWindowState(window_state)
            self.restoreGeometry(geometry)
            self.column.setVisible(column)

    # --------------------------------------------------------------- selection
    def selection_changed(self):
        tab = self.current()
        if not tab:
            return
        paths = tab.selected_paths()
        if self.quick_actions:
            self.selection_bar.set_count(len(paths), len(paths) == 1)
        self.inline_preview.open_button.setEnabled(bool(paths))
        previewable = len(paths) == 1 and SelectionPreview.supported(paths[0])
        if previewable and (self.inspector.isVisible() or self.wants_inspector()):
            self.inline_preview.set_selection(paths, tab.path)
        if self.expanded and not previewable:
            self.set_expanded(False)
        self.arrange_inspector()
        self.update_status()

    def bar_action(self, key):
        {'open': self.open_selected, 'copy': lambda: self.copy(False), 'rename': self.rename, 'trash': self.trash,
         'options': self.show_actions, 'clear': lambda: self.current().view().clearSelection()}[key]()

    # ------------------------------------------------------------- opening
    def open_path(self, path):
        if Path(path).is_dir():
            self.navigate(path)
        elif Path(path).suffix.lower() == '.pdf':
            from files_browser import open_pdf
            try:
                open_pdf(path)
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                self.warn('No se pudo abrir el PDF', str(error))
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            self.warn('No se pudo abrir', 'No hay una aplicación disponible para abrir este archivo.')

    def open_selected(self):
        paths = self.current().selected_paths()
        if len(paths) > 10:
            self.warn('Selecciona menos archivos', 'Abre hasta 10 archivos a la vez.')
            return
        for path in paths:
            self.open_path(path)

    def preview(self):
        paths = self.current().selected_paths()
        if len(paths) == 1 and SelectionPreview.supported(paths[0]):
            self.toggle_expanded()
        elif self.expanded:
            self.set_expanded(False)
        else:
            self.say('Este archivo no tiene vista previa')

    def terminal(self):
        for command in ('ghostty', 'x-terminal-emulator', 'alacritty', 'kitty', 'xterm'):
            binary = shutil.which(command)
            if binary:
                subprocess.Popen([binary], cwd=self.current().path, start_new_session=True)
                return
        self.warn('Terminal no disponible', 'No se encontró una terminal compatible.')

    # ---------------------------------------------------------------- bookmarks
    def bookmark(self):
        path = self.current().path
        if path not in self.bookmarks:
            self.bookmarks.append(path)
            self.settings.setValue('bookmarks', self.bookmarks)
            self.sidebar.set_bookmarks(self.bookmarks)
            self.say('Carpeta añadida a marcadores')

    def bookmark_menu(self, path, point):
        menu = ActionMenu(self)
        menu.add('bookmark_remove', 'Quitar de marcadores', lambda: self.remove_bookmark(path), danger=True)
        menu.popup(point)

    def remove_bookmark(self, path):
        if path in self.bookmarks:
            self.bookmarks.remove(path)
            self.settings.setValue('bookmarks', self.bookmarks)
            self.sidebar.set_bookmarks(self.bookmarks)

    # -------------------------------------------------------------- clipboard
    def copy_current_path(self):
        QApplication.clipboard().setText(os.path.abspath(self.current().path))
        self.say('Ruta absoluta copiada')

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
        self.say(f'{len(paths)} elemento' + ('' if len(paths) == 1 else 's') + (' listos para mover' if cut else ' copiados'))

    def sync_cut(self):
        mime = QApplication.clipboard().mimeData() or QMimeData()
        cut = set()
        if bytes(mime.data('x-special/gnome-copied-files')).startswith(b'cut\n'):
            cut = {url.toLocalFile() for url in mime.urls() if url.isLocalFile()}
        for number in range(self.tabs.count()):
            self.tabs.widget(number).view().set_cut(cut)

    def paste(self):
        mime = QApplication.clipboard().mimeData() or QMimeData()
        paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
        if not paths:
            return
        cut = bytes(mime.data('x-special/gnome-copied-files')).startswith(b'cut\n')
        self.operation('move' if cut else 'copy', paths, self.current().path)

    # --------------------------------------------------------------- operations
    def valid_name(self, name):
        if not name or name in ('.', '..') or '/' in name or '\x00' in name:
            return 'Escribe un nombre sin barras que no sea «.» ni «..».'
        return ''

    def new_folder(self):
        self.sheet.prompt('Nueva carpeta', 'Nombre de la carpeta', 'Carpeta nueva', 'Crear',
                          lambda name: self.operation('mkdir', [], str(Path(self.current().path) / name)), self.valid_name)

    def new_file(self):
        def create(name):
            target = Path(self.current().path) / name
            if target.exists():
                self.warn('Ya existe', f'«{name}» ya existe en esta carpeta.')
                return
            try:
                target.touch(exist_ok=False)
            except OSError as error:
                self.warn('No se pudo crear el archivo', str(error))
        self.sheet.prompt('Archivo nuevo', 'Nombre del archivo', 'Sin título.txt', 'Crear', create, self.valid_name, select_stem=True)

    def rename(self):
        paths = self.current().selected_paths()
        if len(paths) != 1:
            return
        path = Path(paths[0])

        def apply(name):
            if name != path.name:
                self.operation('rename', paths, str(path.parent / name))
        self.sheet.prompt('Cambiar nombre', 'Nuevo nombre', path.name, 'Renombrar', apply, self.valid_name, select_stem=True)

    def trash(self):
        paths = self.current().selected_paths()
        if not paths:
            return
        title = 'Enviar a la papelera'
        one = len(paths) == 1
        message = f'¿Enviar «{Path(paths[0]).name}» a la papelera?' if one else f'¿Enviar {len(paths)} elementos a la papelera?'
        self.sheet.confirm(title, message, 'Enviar a la papelera', lambda: self.operation('trash', paths, ''),
                           'Podrás recuperarlos desde la papelera del sistema.')

    def operation(self, kind, sources, destination):
        if self.jobs:
            self.say('Espera a que termine la operación actual')
            return
        job = OperationJob(kind, sources, destination, self)
        self.jobs.append(job)
        self.status.set_busy(True)
        self.status.set_text('Trabajando… mantén la ventana abierta hasta que termine', '')
        snapshot = bytes((QApplication.clipboard().mimeData() or QMimeData()).data('x-special/gnome-copied-files'))
        job.result.connect(lambda result, error: self.operation_result(kind, error, snapshot))
        job.finished.connect(lambda: self.operation_finished(job))
        job.start()

    def operation_result(self, kind, error, snapshot):
        if error:
            self.warn('La operación no se completó',
                      error + '\n\nRevisa las carpetas de origen y destino antes de reintentar; algunas operaciones podrían haberse completado.')
        else:
            self.say({'copy': 'Copiado', 'move': 'Movido', 'trash': 'Enviado a la papelera', 'mkdir': 'Carpeta creada',
                      'rename': 'Nombre cambiado'}.get(kind, 'Listo'))
            if kind == 'move':
                mime = QApplication.clipboard().mimeData() or QMimeData()
                if snapshot.startswith(b'cut\n') and bytes(mime.data('x-special/gnome-copied-files')) == snapshot:
                    QApplication.clipboard().clear()

    def operation_finished(self, job):
        self.jobs.remove(job)
        job.deleteLater()
        self.status.set_busy(bool(self.jobs))
        self.update_status()

    def properties(self):
        paths = self.current().selected_paths() or [self.current().path]
        if len(paths) != 1:
            return
        path = Path(paths[0])
        try:
            stat = path.lstat()
        except OSError as error:
            self.warn('Propiedades', str(error))
            return
        kind = 'Enlace simbólico' if path.is_symlink() else 'Carpeta' if path.is_dir() else 'Archivo'
        rows = [('Nombre', path.name or '/'), ('Ruta', str(path)), ('Tipo', kind), ('Tamaño', human_size(stat.st_size)),
                ('Permisos', oct(stat.st_mode & 0o777)),
                ('Modificado', datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%d %b %Y · %H:%M'))]
        if path.is_symlink():
            rows.append(('Destino del enlace', os.readlink(path)))
        self.sheet.info('Propiedades', rows)

    def build_menu(self):
        paths = self.current().selected_paths()
        idle = not self.jobs
        menu = ActionMenu(self)
        single = len(paths) == 1
        menu.add('open_in_new', 'Abrir', self.open_selected, 'Enter', bool(paths))
        menu.add('tab_new_right', 'Abrir en nueva pestaña', lambda: self.new_tab(paths[0]), '', single and Path(paths[0]).is_dir())
        menu.add('visibility', 'Vista previa ampliada', self.preview, 'Espacio', single and SelectionPreview.supported(paths[0]))
        menu.separator()
        clipboard = QApplication.clipboard().mimeData()
        menu.add('content_copy', 'Copiar', lambda: self.copy(False), 'Ctrl+C', bool(paths))
        menu.add('content_cut', 'Cortar', lambda: self.copy(True), 'Ctrl+X', bool(paths) and idle)
        menu.add('content_paste', 'Pegar aquí', self.paste, 'Ctrl+V', bool(clipboard and clipboard.hasUrls()) and idle)
        menu.add('drive_file_rename_outline', 'Cambiar nombre', self.rename, 'F2', single and idle)
        menu.add('delete', 'Enviar a la papelera', self.trash, 'Supr', bool(paths) and idle, danger=True)
        menu.separator()
        menu.add('link', 'Copiar ruta', self.copy_current_path, 'Ctrl+Shift+C')
        menu.add('create_new_folder', 'Nueva carpeta', self.new_folder, 'Ctrl+Shift+N', idle)
        menu.add('terminal', 'Terminal aquí', self.terminal)
        menu.add('info', 'Propiedades', self.properties)
        return menu

    def context_menu(self, point):
        self.build_menu().popup(point)

    def show_actions(self):
        """Alt+K: the options menu, anchored to the current item and fully keyboard driven."""
        view = self.current().view()
        index = view.currentIndex() if view.selectionModel().hasSelection() or view.currentIndex().isValid() else None
        if index is not None and index.isValid() and not view.selectionModel().hasSelection():
            view.selectionModel().select(index, view.selectionModel().ClearAndSelect)
        if index is not None and index.isValid():
            rect = view.visualRect(index)
            point = view.viewport().mapToGlobal(rect.bottomLeft())
        else:
            point = view.viewport().mapToGlobal(view.viewport().rect().center())
        self.context_menu(point)

    def type_to_filter(self, text):
        self.filter_edit.setFocus()
        self.filter_edit.setText(self.filter_edit.text() + text)

    # ----------------------------------------------------------------- input
    def focus_path(self):
        self.pathbar.begin_edit()

    def show_shortcuts(self):
        self.sheet.info('Atajos de teclado', [(line.split(': ')[0], line.split(': ', 1)[1]) if ': ' in line else ('', line)
                                              for line in SHORTCUTS.split('\n')])

    def escape(self):
        if self.sheet.isVisible():
            return
        if self.fullscreen_restore is not None and self.inline_preview.player:
            self.inline_preview.player.set_fullscreen(False)
        elif self.pathbar.edit.isVisible():
            self.pathbar.end_edit()
        elif self.filter_edit.hasFocus():
            self.filter_edit.clear()
        elif self.expanded:
            self.set_expanded(False)
        elif self.current().selected_paths():
            self.current().view().clearSelection()
        elif self.filter_edit.text():
            self.filter_edit.clear()
        else:
            return
        self.current().view().setFocus()

    cancel_path = escape

    def add_shortcuts(self):
        actions = {'Ctrl+1': lambda: self.set_grid(True), 'Ctrl+2': lambda: self.set_grid(False), 'Escape': self.escape,
                   'Ctrl+L': self.focus_path, 'Ctrl+T': self.new_tab, 'Ctrl+W': lambda: self.close_tab(self.tabs.currentIndex()),
                   'Ctrl+H': self.toggle_hidden, 'Ctrl+F': self.filter_edit.setFocus, 'Alt+Left': lambda: self.current().go(-1),
                   'Alt+Right': lambda: self.current().go(1), 'Alt+Up': self.up, 'Ctrl+Shift+N': self.new_folder,
                   'Ctrl+Shift+C': self.copy_current_path, 'Ctrl+I': lambda: (self.details_button.toggle(), self.toggle_inspector()),
                   'F1': self.show_shortcuts, 'Ctrl+Q': self.close, 'Alt+K': self.show_actions,
                   'Ctrl+Tab': lambda: self.cycle_tab(1), 'Ctrl+Shift+Tab': lambda: self.cycle_tab(-1),
                   'Ctrl+PgDown': lambda: self.cycle_tab(1), 'Ctrl+PgUp': lambda: self.cycle_tab(-1),
                   'Alt+Home': lambda: self.navigate(str(Path.home()))}
        for key, action in actions.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)

    def cycle_tab(self, step):
        if self.tabs.count() > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % self.tabs.count())
            self.current().view().setFocus()

    def add_view_shortcuts(self, view):
        for key, action in {'Ctrl+C': lambda: self.copy(False), 'Ctrl+X': lambda: self.copy(True), 'Ctrl+V': self.paste,
                            'F2': self.rename, 'Delete': self.trash, 'Space': self.preview, 'Return': self.open_selected,
                            'Enter': self.open_selected, 'Ctrl+A': lambda: self.current().view().selectAll()}.items():
            shortcut = QShortcut(QKeySequence(key), view)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)

    # ----------------------------------------------------------------- window
    def present(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh_theme(self):
        apply_kit_style(self)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange_inspector()

    def paintEvent(self, _event):
        paint_surface(self)

    def _edges(self, point):
        edges = Qt.Edges()
        if point.x() <= RESIZE_MARGIN:
            edges |= Qt.LeftEdge
        if point.x() >= self.width() - RESIZE_MARGIN:
            edges |= Qt.RightEdge
        if point.y() <= RESIZE_MARGIN:
            edges |= Qt.TopEdge
        if point.y() >= self.height() - RESIZE_MARGIN:
            edges |= Qt.BottomEdge
        return edges

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.windowHandle() is None or self.fullscreen_restore is not None:
            return
        edges = self._edges(event.position().toPoint())
        if edges:
            self.windowHandle().startSystemResize(edges)
        elif event.position().y() < 56:
            self.windowHandle().startSystemMove()

    def mouseMoveEvent(self, event):
        edges = self._edges(event.position().toPoint())
        horizontal, vertical = bool(edges & (Qt.LeftEdge | Qt.RightEdge)), bool(edges & (Qt.TopEdge | Qt.BottomEdge))
        if horizontal and vertical:
            diagonal = edges in (Qt.Edges(Qt.LeftEdge | Qt.TopEdge), Qt.Edges(Qt.RightEdge | Qt.BottomEdge))
            self.setCursor(Qt.SizeFDiagCursor if diagonal else Qt.SizeBDiagCursor)
        elif horizontal or vertical:
            self.setCursor(Qt.SizeHorCursor if horizontal else Qt.SizeVerCursor)
        else:
            self.unsetCursor()

    def _widen_filter(self):
        wide = self.filter_edit.hasFocus() or bool(self.filter_edit.text())
        target = 340 if wide else 230
        if self.filter_edit.width() == target:
            return
        anim = getattr(self, '_filter_anim', None)
        if anim is None:
            anim = self._filter_anim = QVariantAnimation(self, duration=tokens()['motion_enter'])
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.valueChanged.connect(lambda v: self.filter_edit.setFixedWidth(round(float(v))))
        anim.stop()
        if reduced_motion(self):
            self.filter_edit.setFixedWidth(target)
            return
        anim.setStartValue(self.filter_edit.width())
        anim.setEndValue(target)
        anim.start()

    def eventFilter(self, watched, event):
        if watched is self.filter_edit and event.type() in (QEvent.FocusIn, QEvent.FocusOut):
            QTimer.singleShot(0, self, self._widen_filter)
        if watched is self.filter_edit and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Down, Qt.Key_Return, Qt.Key_Enter):
            view = self.current().view()
            view.setFocus()
            view.keyboard = True
            if not view.currentIndex().isValid() and view.model().rowCount(view.rootIndex()):
                view.setCurrentIndex(view.model().index(0, 0, view.rootIndex()))
            return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        preview = self.inline_preview
        preview.shutdown()
        if preview.job is not None:
            preview.job.finished.connect(self.close)
            event.ignore()
            return
        if self.jobs:
            self.warn('Operación en curso', 'Espera a que termine la operación antes de cerrar. Tus archivos se están procesando.')
            event.ignore()
            return
        self.settings.sync()
        super().closeEvent(event)


class _StatusProxy:
    """Minimal ``statusBar().showMessage`` for callers written against the old window."""

    def __init__(self, window):
        self.window = window

    def showMessage(self, text, _timeout=0):
        self.window.say(text)


def _filter_field():
    from wysun_music.ui.sidebar import SearchField
    field = SearchField()
    field.setPlaceholderText('Filtrar carpeta')
    field.setAccessibleName('Filtrar nombres en esta carpeta')
    field.setToolTip('Filtrar nombres · Ctrl+F')
    field.setFixedWidth(230)
    return field
