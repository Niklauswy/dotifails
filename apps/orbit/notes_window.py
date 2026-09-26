"""A focused Markdown library, using the same surfaces and actions as Órbita."""
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QLineEdit, QComboBox, QListWidget, QListWidgetItem, QPlainTextEdit,
    QTextBrowser, QSplitter, QFileDialog)
from desktop_common import Surface, button, text_label, open_vim
from icons import icon
from utility_data import Notes, digest


class NotesWindow(Surface):
    def __init__(self, root=None):
        super().__init__('Notas', 'ÓRBITA  /  Tu espacio para pensar', 940, 640)
        self.store = Notes(root)
        if root is None:
            self.store.import_legacy(Path.home() / 'Documents/QuickNotes/notes.md')
        self.key = self.expected = None
        self.dirty = self.loading = False
        self.setStyleSheet(self.styleSheet() + '''
            QPlainTextEdit, QTextBrowser { background:transparent; border:0; padding:12px; font-size:14px; }
            QListWidget::item { padding:0; margin:2px 0; }
            QWidget#notePane { border-left:1px solid #30333D; }
            QLabel#noteTitle {font-size:17px; font-weight:600;}
            QSplitter::handle { background:transparent; width:1px; }
        ''')
        split = QSplitter()
        left = QWidget(); sidebar = QVBoxLayout(left); sidebar.setContentsMargins(0, 0, 14, 0)
        self.search = QLineEdit(); self.search.setPlaceholderText('Buscar notas…'); sidebar.addWidget(self.search)
        self.folder = QComboBox(); self.folder.addItems(['Todas las notas', 'Favoritas', 'Papelera']); sidebar.addWidget(self.folder)
        self.list = QListWidget(); self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); sidebar.addWidget(self.list, 1)
        sidebar.addWidget(button('Nueva nota   Ctrl N', self.new, 'primary', 'plus'))
        split.addWidget(left)
        right = QWidget(); right.setObjectName('notePane'); layout = QVBoxLayout(right); layout.setContentsMargins(20, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.edit_button = button('Escribir', lambda: self.set_preview(False), symbol='pencil'); self.edit_button.setCheckable(True)
        self.preview_button = button('Leer', lambda: self.set_preview(True), symbol='eye'); self.preview_button.setCheckable(True)
        toolbar.addWidget(self.edit_button); toolbar.addWidget(self.preview_button); toolbar.addStretch()
        self.star = button('', self.favorite, symbol='pin'); self.star.setCheckable(True); self.star.setToolTip('Fijar en favoritas'); toolbar.addWidget(self.star)
        self.more = button('', self.actions, symbol='ellipsis'); self.more.setToolTip('Acciones · Alt K'); toolbar.addWidget(self.more); layout.addLayout(toolbar)
        self.heading = text_label('Una idea empieza aquí', 'noteTitle'); layout.addWidget(self.heading)
        self.editor = QPlainTextEdit(); self.editor.setPlaceholderText('Crea una nota o importa tus archivos Markdown.'); layout.addWidget(self.editor, 1)
        self.preview = QTextBrowser(); self.preview.setOpenExternalLinks(False); self.preview.document().setDefaultStyleSheet('body {line-height:1.6;} h1,h2 {color:#E8EAF0;} code {color:#BEC9E5;}'); layout.addWidget(self.preview, 1)
        self.meta = text_label('', 'subtitle'); layout.addWidget(self.meta); split.addWidget(right); split.setSizes([270, 620]); self.outer.addWidget(split, 1)
        footer = QHBoxLayout(); self.status = text_label('Guardado local', 'subtitle'); footer.addWidget(self.status, 1)
        footer.addWidget(button('Abrir en Vim', self.vim, symbol='terminal')); footer.addWidget(button('Acciones  Alt K', self.actions)); self.outer.addLayout(footer)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(650); self.timer.timeout.connect(self.save)
        self.search.textChanged.connect(self.refresh); self.folder.currentIndexChanged.connect(self.refresh)
        self.list.currentItemChanged.connect(self.selected); self.editor.textChanged.connect(self.changed)
        for key, fn in [('Ctrl+N', self.new), ('Ctrl+S', self.save), ('Ctrl+E', self.vim), ('Ctrl+F', self.search.setFocus), ('Alt+K', self.actions), ('Ctrl+Shift+P', self.toggle_preview)]:
            QShortcut(QKeySequence(key), self).activated.connect(fn)
        self.set_preview(False); self.refresh()

    def is_trash(self): return self.folder.currentIndex() == 2

    def row_widget(self, row):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 10, 12, 10); v.setSpacing(4)
        title = text_label(('★  ' if row['favorite'] else '') + row['title'][:34]); title.setWordWrap(False); v.addWidget(title)
        lines = [s.strip() for s in row['body'].splitlines()[1:] if s.strip()]
        excerpt = text_label((' '.join(lines)[:38] or 'Sin contenido'), 'subtitle'); excerpt.setWordWrap(False); v.addWidget(excerpt)
        v.addWidget(text_label(datetime.fromtimestamp(row['stamp']).strftime('%d %b · %H:%M'), 'subtitle'))
        w.setAttribute(Qt.WA_TransparentForMouseEvents)
        return w

    def refresh(self, *_):
        if not self.save(): return
        key = self.key; self.list.blockSignals(True); self.list.clear()
        rows = self.store.all(self.search.text(), self.is_trash())
        if self.folder.currentIndex() == 1: rows = [r for r in rows if r['favorite']]
        for r in rows:
            item = QListWidgetItem(); item.setData(Qt.UserRole, r); item.setSizeHint(QSize(230, 91)); self.list.addItem(item); self.list.setItemWidget(item, self.row_widget(r))
            if r['key'] == key: self.list.setCurrentItem(item)
        if not self.list.currentItem() and self.list.count(): self.list.setCurrentRow(0)
        self.list.blockSignals(False); self.selected(self.list.currentItem())

    def selected(self, item, previous=None):
        if not self.save():
            self.list.blockSignals(True); self.list.setCurrentItem(previous); self.list.blockSignals(False); return
        self.loading = True; row = item.data(Qt.UserRole) if item else None
        self.key = row['key'] if row else None; body = row['body'] if row else ''
        self.editor.setPlainText(body); self.expected = digest(body); self.preview.setMarkdown(body)
        self.editor.setReadOnly(self.is_trash() or not row); self.heading.setText(row['title'][:65] if row else 'Una idea empieza aquí')
        self.star.setEnabled(bool(row) and not self.is_trash()); self.star.setChecked(bool(row and row['favorite']))
        self.loading = False; self.update_meta()

    def update_meta(self):
        body = self.editor.toPlainText()
        self.meta.setText(f'{len(body.split())} palabras  ·  {len(body)} caracteres  ·  Markdown' if self.key else 'Ctrl N para crear · Acciones para importar')

    def changed(self):
        if self.loading: return
        self.dirty = True; self.status.setText('Guardando…'); self.update_meta(); self.timer.start()

    def save(self):
        if not self.dirty or not self.key: return True
        try: self.expected = self.store.save(self.key, self.editor.toPlainText(), self.expected)
        except (OSError, RuntimeError) as e: self.status.setText(str(e)); return False
        self.dirty = False; body = self.editor.toPlainText(); self.preview.setMarkdown(body); self.status.setText('Guardado · en este equipo')
        title = next((s.strip('# ').strip() for s in body.splitlines() if s.strip()), 'Sin título'); self.heading.setText(title[:65])
        for i in range(self.list.count()):
            item = self.list.item(i); row = item.data(Qt.UserRole)
            if row['key'] == self.key:
                row.update(body=body, title=title, stamp=self.store.path(self.key).stat().st_mtime); item.setData(Qt.UserRole, row); self.list.setItemWidget(item, self.row_widget(row))
        return True

    def new(self):
        if not self.save(): return
        self.folder.setCurrentIndex(0); self.search.clear(); self.key = self.store.create(); self.refresh(); self.set_preview(False); self.editor.setFocus()

    def copy_note(self):
        body = self.editor.toPlainText(); self.dirty = False; self.timer.stop()
        self.folder.blockSignals(True); self.search.blockSignals(True); self.folder.setCurrentIndex(0); self.search.clear(); self.folder.blockSignals(False); self.search.blockSignals(False)
        self.key = self.store.create(body); self.refresh(); self.set_preview(False)

    def set_preview(self, preview):
        self.preview.setVisible(preview); self.editor.setVisible(not preview); self.preview.setMarkdown(self.editor.toPlainText())
        self.edit_button.setChecked(not preview); self.preview_button.setChecked(preview)

    def toggle_preview(self): self.set_preview(self.preview.isHidden())

    def favorite(self):
        if self.key and self.save(): self.store.toggle_favorite(self.key); self.refresh()

    def delete(self):
        if self.key and self.save(): self.store.move(self.key, self.is_trash()); self.key = None; self.refresh()

    def vim(self):
        if self.key and self.save():
            try: open_vim(self.store.path(self.key, self.is_trash()))
            except (OSError, RuntimeError) as e: self.status.setText(str(e))

    def import_notes(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Importar notas', '', 'Markdown y texto (*.md *.txt)')
        for path in paths:
            try: self.store.create(Path(path).read_text())
            except (OSError, UnicodeError) as e: self.status.setText(str(e))
        self.refresh()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar nota', 'nota.md', 'Markdown (*.md)')
        if path:
            try: Path(path).write_text(self.editor.toPlainText())
            except OSError as e: self.status.setText(str(e))

    def from_clipboard(self):
        if not self.save(): return
        text = QApplication.clipboard().text()
        if not text: self.status.setText('El portapapeles no contiene texto'); return
        self.folder.setCurrentIndex(0); self.search.clear(); self.key = self.store.create(text); self.refresh(); self.set_preview(False)

    def actions(self):
        from enhanced import SearchMenu
        entries = [('Nueva desde el portapapeles', '', self.from_clipboard), ('Importar Markdown…', '', self.import_notes)]
        if self.key:
            entries = [('Copiar contenido', '', lambda: QApplication.clipboard().setText(self.editor.toPlainText())), ('Guardar copia', '', self.copy_note), ('Exportar Markdown…', '', self.export), ('Restaurar nota' if self.is_trash() else 'Mover a la papelera', '', self.delete)] + entries
        self.popup = SearchMenu(self, entries); self.popup.present(self.more)

    def closeEvent(self, event):
        if self.save(): event.accept()
        else: event.ignore()

    def present(self): self.refresh(); super().present()
