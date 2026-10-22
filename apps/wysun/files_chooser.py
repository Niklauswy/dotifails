"""Wysun's portal selector: local paths, explicit acceptance, no implicit uploads."""
import fnmatch
import os
from pathlib import Path

from PySide6.QtCore import QMimeDatabase, QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QMenu, QVBoxLayout, QWidget

from theme_tokens import color
from wysun_files.kit import Chip, PillButton, metric, text_font
from wysun_files.window import FilesWindow


def byte_path(value):
    return os.fsdecode(bytes(value).rstrip(b'\0')) if value else ''


def local_path(value):
    from PySide6.QtCore import QUrl
    url = QUrl(str(value))
    if url.scheme() and not url.isLocalFile():
        raise ValueError('Solo se admiten ubicaciones locales.')
    return Path(url.toLocalFile() if url.isLocalFile() else str(value)).expanduser().absolute()


class ChooserModel(QSortFilterProxyModel):
    """Keep folders navigable while intersecting filename and MIME filters."""

    def __init__(self, source, parent=None):
        super().__init__(parent)
        self.setSourceModel(source)
        self.query, self.rules, self.directories = '', [], False
        self.setDynamicSortFilter(True)
        self.mime = QMimeDatabase()

    def filterAcceptsRow(self, row, parent):
        index = self.sourceModel().index(row, 0, parent)
        if self.sourceModel().isDir(index):
            return True
        if self.directories:
            return False
        name = self.sourceModel().fileName(index)
        if self.query.casefold() not in name.casefold():
            return False
        if not self.rules:
            return True
        for kind, pattern in self.rules:
            if int(kind) == 0 and fnmatch.fnmatchcase(name, str(pattern)):
                return True
            if int(kind) == 1:
                mime = self.mime.mimeTypeForFile(self.sourceModel().filePath(index), QMimeDatabase.MatchExtension)
                if mime.name() == str(pattern) or mime.inherits(str(pattern)) or fnmatch.fnmatchcase(mime.name(), str(pattern)):
                    return True
        return False

    def index(self, *args):
        if args and isinstance(args[0], str):
            return self.mapFromSource(self.sourceModel().index(*args))
        return super().index(*args)

    def setRootPath(self, path):
        return self.mapFromSource(self.sourceModel().setRootPath(path))

    def filePath(self, index):
        return self.sourceModel().filePath(self.mapToSource(index))

    def fileName(self, index):
        return self.sourceModel().fileName(self.mapToSource(index))

    def isDir(self, index):
        return self.sourceModel().isDir(self.mapToSource(index))

    def size_text(self, index):
        return self.sourceModel().size_text(self.mapToSource(index))

    def lastModified(self, index):
        return self.sourceModel().lastModified(self.mapToSource(index))

    def thumbnail(self, index):
        return self.sourceModel().thumbnail(self.mapToSource(index))

    def setNameFilters(self, values):
        self.query = values[0].strip('*') if values else ''
        self.invalidateFilter()

    def nameFilters(self):
        return ['*' + self.query + '*'] if self.query else []

    def setFilter(self, value):
        self.sourceModel().setFilter(value)

    @property
    def show_thumbnails(self):
        return self.sourceModel().show_thumbnails

    @show_thumbnails.setter
    def show_thumbnails(self, value):
        self.sourceModel().show_thumbnails = value


class ChoicePicker(PillButton):
    """Tonal pill that opens a menu of choices; mirrors the bit of QComboBox the chooser relies on."""

    currentIndexChanged = Signal(int)

    def __init__(self, symbol, parent=None):
        super().__init__(symbol, '', None, variant='tonal', height=40, parent=parent)
        self.symbol_name = symbol
        self.entries, self.index = [], -1
        self.clicked.connect(self._menu)

    def addItem(self, text, data=None):
        self.entries.append((text, data))
        if self.index < 0:
            self.setCurrentIndex(0)

    def setCurrentIndex(self, index):
        if 0 <= index < len(self.entries) and index != self.index:
            self.index = index
            self.set_content(self.symbol_name, self.entries[index][0])
            self.currentIndexChanged.emit(index)

    def currentIndex(self):
        return self.index

    def currentData(self):
        return self.entries[self.index][1] if self.index >= 0 else None

    def _menu(self):
        menu = QMenu(self)
        for number, (text, _data) in enumerate(self.entries):
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(number == self.index)
            action.triggered.connect(lambda _=False, n=number: self.setCurrentIndex(n))
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))


class FileChooser(FilesWindow):
    completed = Signal(int, object)

    def __init__(self, mode, title, options, parent_window=''):
        self.mode, self.options, self.replied, self.result_uris = mode, options, False, []
        initial = byte_path(options.get('current_folder'))
        current = byte_path(options.get('current_file'))
        if current and Path(current).is_file():
            initial = str(Path(current).parent)
        if not initial or not Path(initial).is_dir():
            initial = str(Path.home())
        super().__init__([initial])
        self.setWindowFlag(Qt.Dialog, True)
        self.setWindowModality(Qt.WindowModal if options.get('modal', True) else Qt.NonModal)
        # A fixed suffix lets the Hyprland rule float and centre every chooser (see hyprland.lua).
        self.chooser_title = (title or ('Guardar archivo' if mode == 'save' else 'Seleccionar archivos')) + ' — Wysun Selector'
        self.setWindowTitle(self.chooser_title)
        self.directory = bool(options.get('directory')) or mode == 'savefiles'
        self.multiple = bool(options.get('multiple')) and mode == 'open'
        # Selection dialogs never expose editing, terminal, or destructive shortcuts.
        self.quick_actions = False
        self.selection_bar.hide()
        for widget in (self.more_button, self.new_button, self.close_button):
            widget.hide()
        self.inline_preview.open_button.hide()
        self.hero.hide()
        for shortcut in self.shortcuts:
            shortcut.setEnabled(False)
        for key, callback in (('Escape', self.close), ('Ctrl+L', self.focus_path), ('Alt+Up', self.up),
                              ('Alt+Left', lambda: self.current().go(-1)), ('Alt+Right', lambda: self.current().go(1)),
                              ('Ctrl+F', self.filter_edit.setFocus), ('Ctrl+H', self.toggle_hidden),
                              ('Ctrl+A', lambda: self.multiple and self.current().view().selectAll())):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        tab = self.current()
        self.proxy = ChooserModel(tab.model, tab)
        self.proxy.directories = self.directory
        tab.use_model(self.proxy)
        tab.view().setSelectionMode(QAbstractItemView.ExtendedSelection if self.multiple else QAbstractItemView.SingleSelection)
        tab.view().setDragEnabled(False)
        shortcut = QShortcut(QKeySequence('Return'), tab.view())
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.open_selected)
        self.shortcuts.append(shortcut)
        self._footer(options, current)
        self.proxy.invalidateFilter()
        self.selection_changed()
        # Hyprland floats the portal dialog; no foreign window handles are needed.
        screen = self.screen().availableGeometry()
        self.resize(min(1100, int(screen.width() * .82)), min(740, int(screen.height() * .82)))

    def _footer(self, options, current):
        footer = QWidget()
        column = QVBoxLayout(footer)
        column.setContentsMargins(0, metric('space_s'), 0, metric('space_m'))
        column.setSpacing(metric('space_s'))
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f'color:{color("danger").name()};')
        column.addWidget(self.error)
        row = QHBoxLayout()
        row.setSpacing(metric('space_s'))
        self.filename = QLineEdit()
        self.filename.setAccessibleName('Nombre del archivo')
        self.filename.setPlaceholderText('Nombre del archivo')
        self.filename.setText(str(options.get('current_name') or (Path(current).name if current else '')))
        self.filename.returnPressed.connect(self.accept_selection)
        if self.mode == 'save':
            row.addWidget(self.filename, 1)
        else:
            self.filename.hide()
            row.addStretch()
        self.filters = list(options.get('filters', []))
        self.filter_box = ChoicePicker('filter_list')
        self.filter_box.setAccessibleName('Tipo de archivo')
        for name, rules in self.filters:
            self.filter_box.addItem(str(name), rules)
        if self.filters:
            selected = next((i for i, f in enumerate(self.filters) if f == options.get('current_filter')), 0)
            self.filter_box.setCurrentIndex(selected)
            self.proxy.rules = list(self.filters[selected][1])
            self.filter_box.currentIndexChanged.connect(self.change_filter)
            row.addWidget(self.filter_box)
        else:
            self.filter_box.hide()
        self.choice_widgets = []
        for ident, label, entries, selected in options.get('choices', []):
            if entries:
                control = ChoicePicker('tune')
                for value, text in entries:
                    control.addItem(f'{label}: {text}', str(value))
                control.setCurrentIndex(max(0, next((i for i, (v, _t) in enumerate(entries) if str(v) == str(selected)), 0)))
            else:
                control = Chip(str(label))
                control.setChecked(str(selected) == 'true')
            self.choice_widgets.append((str(ident), control))
            row.addWidget(control)
        if self.mode != 'save':
            row.addStretch()
        row.addWidget(PillButton('close', 'Cancelar', self.close, variant='tonal', height=40))
        accept = str(options.get('accept_label') or ('Guardar' if self.mode != 'open' else 'Seleccionar'))
        self.accept_button = PillButton('check', accept, self.accept_selection, variant='filled', height=40)
        row.addWidget(self.accept_button)
        column.addLayout(row)
        self.files_layout.insertWidget(self.files_layout.count() - 1, footer)

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen().availableGeometry()
        self.move(max(screen.left(), min(screen.right() - self.width(), screen.center().x() - self.width() // 2)),
                  max(screen.top(), min(screen.bottom() - self.height(), screen.center().y() - self.height() // 2)))

    def window_title(self, folder):
        return getattr(self, 'chooser_title', folder)

    def change_filter(self, index):
        self.proxy.rules = list(self.filters[index][1])
        self.proxy.invalidateFilter()

    def context_menu(self, point):
        pass

    def more_menu(self):
        pass

    def properties(self):
        pass

    def open_path(self, path):
        if Path(path).is_dir():
            self.navigate(path)
        else:
            self.accept_selection([path])

    def open_selected(self):
        paths = self.current().selected_paths()
        if len(paths) == 1 and Path(paths[0]).is_dir():
            self.navigate(paths[0])
        else:
            self.accept_selection()

    def accept_selection(self, paths=None):
        self.error.clear()
        if isinstance(paths, bool):
            paths = None
        paths = paths or self.current().selected_paths()
        folder = Path(self.current().path)
        if self.mode == 'save':
            name = self.filename.text().strip()
            if not name or Path(name).name != name or name in ('.', '..'):
                self.error.setText('Escribe un nombre de archivo válido.')
                return
            targets = [folder / name]
            if targets[0].is_dir():
                self.error.setText('El nombre corresponde a una carpeta.')
                return
            if not os.access(str(folder), os.W_OK):
                self.error.setText('No puedes guardar archivos en esta carpeta.')
                return
            if targets[0].exists():
                self.sheet.confirm('Reemplazar archivo', 'El archivo ya existe. ¿Quieres reemplazarlo?', 'Reemplazar',
                                   lambda: self.finish(targets))
                return
        elif self.mode == 'savefiles':
            target = local_path(paths[0]) if paths and Path(paths[0]).is_dir() else folder
            targets = []
            for raw in self.options.get('files', []):
                name = Path(byte_path(raw)).name
                if not name or name in ('.', '..'):
                    self.error.setText('Nombre de archivo inválido.')
                    return
                candidate, number = target / name, 1
                while candidate.exists() or candidate in targets:
                    candidate = target / f'{Path(name).stem} ({number}){Path(name).suffix}'
                    number += 1
                targets.append(candidate)
        else:
            if self.directory and not paths:
                paths = [str(folder)]
            if not paths:
                self.error.setText('Selecciona un archivo.')
                return
            targets = [local_path(path) for path in paths]
            if not self.multiple and len(targets) > 1:
                self.error.setText('Selecciona un solo elemento.')
                return
            if any(not p.exists() or p.is_dir() != self.directory or not os.access(p, os.R_OK) for p in targets):
                self.error.setText('La selección ya no está disponible o no es del tipo solicitado.')
                return
        if self.mode != 'open' and not os.access(str(targets[0].parent) if targets else str(folder), os.W_OK):
            self.error.setText('No puedes guardar archivos en esta carpeta.')
            return
        self.finish(targets)

    def finish(self, targets):
        self.result_uris = [p.as_uri() for p in targets]
        self.close()

    def closeEvent(self, event):
        super().closeEvent(event)
        if not event.isAccepted() or self.replied:
            return
        self.replied, result = True, {}
        if self.result_uris:
            result['uris'] = self.result_uris
            if self.filters:
                result['current_filter'] = self.filters[self.filter_box.currentIndex()]
            result['choices'] = [(ident, control.currentData() if isinstance(control, ChoicePicker) else ('true' if control.isChecked() else 'false'))
                                 for ident, control in self.choice_widgets]
        self.completed.emit(0 if self.result_uris else 1, result)
