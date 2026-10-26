"""Wysun PDF: one window per document, a continuous virtualized view and native PDF annotations.

The window composes kit widgets (wysun_core.ui) and the reader's own pieces (pdf_chrome, pdf_sidebar,
pdf_view). All PDF work happens in the engine process behind pdf_worker; pdf_source asks it only for
what is on screen.
"""
from pathlib import Path

from PySide6.QtCore import QEvent, QProcess, QProcessEnvironment, Qt, QTimer, QUrl
from PySide6.QtGui import QActionGroup, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QColorDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QStackedLayout, QVBoxLayout, QWidget)

from ui_theme import paint_surface
from wysun_core.ui.frameless import FramelessResize
from wysun_core.ui.motion import WindowMotion
from wysun_core.ui.panels import Panel, SearchField
from wysun_core.ui.style import apply_kit_style, metric
from wysun_core.ui.toast import Toast
from wysun_core.ui.widgets import ElidedLabel, IconButton, PillButton
from pdf_chrome import (CONTROL, EmptyState, NoteDialog, PageIndicator, SelectionBar, ViewModeSwitch, ZoomControl,
                        ink_colours, ink_menu)
from pdf_sidebar import Sidebar
from pdf_source import PageSource
from pdf_state import Positions, Preferences, clamp
from pdf_theme import shared as shared_mode
from pdf_view import DocumentView
from pdf_worker import PdfWorker

ZOOM_STEP = 1.2
LINK_SCHEMES = ('http', 'https', 'mailto')
SHORTCUTS = '''Ctrl+O abrir · Ctrl+S guardar · Ctrl+Shift+S guardar una copia
Ctrl+F buscar · Enter / Shift+Enter (o F3 / Shift+F3) siguiente / anterior coincidencia · Esc limpiar
Ctrl+C copiar · Ctrl+H resaltar · Ctrl+U subrayar · doble clic selecciona una palabra
Ctrl+G ir a una página · Alt+← / Alt+→ o RePág / AvPág página anterior / siguiente · Inicio / Fin
Ctrl+rueda, Ctrl++ y Ctrl+− zoom · Ctrl+0 ajustar al ancho · Ctrl+9 ajustar a la página
Ctrl+2 una o dos páginas · F9 panel lateral · Ctrl+W cerrar'''


class Stage(Panel):
    """The raised surface that holds the document; floating pieces follow its size."""

    def __init__(self, on_resize):
        super().__init__()
        self.on_resize = on_resize

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.on_resize()


class PdfWindow(FramelessResize, WindowMotion, QMainWindow):
    drag_height = 56

    def __init__(self, path=None):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('Wysun PDF')
        self.setMinimumSize(720, 480)
        self.resize(1280, 860)
        self.setMouseTracking(True)
        self.path, self.pages, self.sizes = None, 0, []
        self.dirty = self.editable = self.busy = False
        self.generation = 0
        self.pending_markup = None
        self.thumbnail_pending = False
        self.search_term, self.search_generation, self.search_done = '', 0, True
        self.hits, self.matches, self.match = {}, [], -1
        self.preferences = Preferences()
        self.positions = Positions()
        self.reader_mode = shared_mode(self.preferences)
        saved_ink = self.preferences.get('ink')
        self.ink = None
        if isinstance(saved_ink, list) and len(saved_ink) == 3:
            self.ink = ink_colours()[0][1]
            self.ink.setRgbF(*[max(0.0, min(1.0, float(v))) for v in saved_ink])
        self.worker = PdfWorker(self)
        self.worker.failed.connect(self.worker_failed)
        self.source = PageSource(self.worker, self)
        apply_kit_style(self)
        self.save_timer = QTimer(self, singleShot=True, interval=1000)
        self.save_timer.timeout.connect(self.remember)
        self.search_timer = QTimer(self, singleShot=True, interval=300)
        self.search_timer.timeout.connect(self.start_search)
        self._build()
        self.toast = Toast(self.centralWidget(), duration=3200, bottom=112)
        self._shortcuts()
        self.setAcceptDrops(True)
        self.set_sidebar(self.preferences.get('sidebar', True) is not False, persist=False)
        self.controls()
        self.empty.button.setFocus()
        if path:
            QTimer.singleShot(0, lambda: self.open_path(path))

    # ------------------------------------------------------------------ build
    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        margin = metric('space_s')
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(margin)
        outer.addLayout(self._top_bar())
        body = QHBoxLayout()
        body.setSpacing(margin)
        self.sidebar = Sidebar()
        self.sidebar.page_requested.connect(lambda page: self.view.go(page))
        self.sidebar.result_requested.connect(self.select_match)
        self.sidebar.note_selected.connect(lambda note: self.view.go(note['page']))
        self.sidebar.note_activated.connect(self.edit_note)
        self.sidebar.delete_requested.connect(self.delete_annotation)
        self.sidebar.thumbnails_wanted.connect(self.load_thumbnails)
        self.sidebar.tab_changed.connect(lambda _: self.remember_sidebar())
        body.addWidget(self.sidebar)
        self.stage = Stage(self.place_overlays)
        frame = QVBoxLayout(self.stage)
        inset = metric('space_s')
        frame.setContentsMargins(inset, inset, inset // 2, inset)
        stack = self.stage_stack = QStackedLayout()
        frame.addLayout(stack)
        self.empty = EmptyState()
        self.empty.open_requested.connect(self.choose)
        stack.addWidget(self.empty)
        self.view = DocumentView(self.source)
        self.view.pageChanged.connect(self.page_changed)
        self.view.zoomChanged.connect(lambda _: self.zoom_changed())
        self.view.selectionChanged.connect(self.selection_changed)
        self.view.selectionFinished.connect(self.selection_finished)
        self.view.linkActivated.connect(self.follow_link)
        self.view.noteRequested.connect(self.add_note)
        self.view.scrolled.connect(self.place_selection_bar)
        self.view.scrolled.connect(self.save_timer.start)
        stack.addWidget(self.view)
        self.indicator = PageIndicator(self.stage)
        self.indicator.jump.connect(lambda page: (self.view.go(page), self.view.setFocus()))
        self.selection_bar = SelectionBar(self.view.viewport())
        self.selection_bar.action.connect(self.selection_action)
        if self.ink is not None:
            self.selection_bar.ink.set_ink(self.ink)
        body.addWidget(self.stage, 1)
        outer.addLayout(body, 1)

    def _top_bar(self):
        bar = QHBoxLayout()
        bar.setContentsMargins(metric('space_xs'), metric('space_xs'), metric('space_xs'), 0)
        bar.setSpacing(metric('space_s'))
        self.close_button = IconButton('close', 'Cerrar · Ctrl+W', self.close, size=34)
        self.sidebar_button = IconButton('left_panel_close', 'Panel lateral · F9', self.toggle_sidebar, size=CONTROL)
        self.sidebar_button.outline = True
        bar.addWidget(self.close_button)
        bar.addWidget(self.sidebar_button)
        title = QVBoxLayout()
        title.setSpacing(0)
        self.title = ElidedLabel('Wysun PDF', 'heading', 650)
        self.subtitle = ElidedLabel('Lector local', 'small', 450, tint='muted')
        title.addWidget(self.title)
        title.addWidget(self.subtitle)
        bar.addLayout(title, 1)
        self.search = SearchField('Buscar en el documento', 'kitSearch')
        self.search.setPlaceholderText('Buscar en el documento')
        self.search.setToolTip('Buscar · Ctrl+F · Enter siguiente, Shift+Enter anterior')
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(lambda _: self.search_timer.start())
        self.search.returnPressed.connect(lambda: self.next_match(1))
        self.search.installEventFilter(self)
        bar.addWidget(self.search)
        self.hit_count = QLabel('')
        self.hit_count.setObjectName('muted')
        self.hit_count.setAccessibleName('Coincidencias')
        bar.addWidget(self.hit_count)
        self.previous_hit = IconButton('keyboard_arrow_up', 'Coincidencia anterior · Shift+Enter', lambda: self.next_match(-1), size=CONTROL - 4)
        self.next_hit = IconButton('keyboard_arrow_down', 'Siguiente coincidencia · Enter', lambda: self.next_match(1), size=CONTROL - 4)
        bar.addWidget(self.previous_hit)
        bar.addWidget(self.next_hit)
        bar.addSpacing(metric('space_s'))
        self.zoom = ZoomControl()
        self.zoom.zoom_in.connect(self.zoom_in)
        self.zoom.zoom_out.connect(self.zoom_out)
        self.zoom.fit.connect(self.fit)
        self.zoom.percent.connect(lambda value: self.view.set_zoom(value))
        bar.addWidget(self.zoom)
        self.view_switch = ViewModeSwitch()
        self.view_switch.changed.connect(self.set_view_mode)
        bar.addWidget(self.view_switch)
        self.note_button = IconButton('edit_note', 'Nota: haz clic en la página para colocarla', self.toggle_note_tool,
                                      variant='tonal', size=CONTROL, checkable=True)
        bar.addWidget(self.note_button)
        self.save_button = PillButton('save', 'Guardar', self.save, height=CONTROL)
        self.save_button.setToolTip('Guardar · Ctrl+S')
        bar.addWidget(self.save_button)
        self.more_button = IconButton('more_vert', 'Más opciones', self.more_menu, size=CONTROL)
        bar.addWidget(self.more_button)
        return bar

    def _shortcuts(self):
        def page_step(step):
            return lambda: self.view.go(self.view.current_page() + step * (2 if self.view.mode == 'spread' else 1))
        for keys, action in (('Ctrl+O', self.choose), ('Ctrl+S', self.save), ('Ctrl+Shift+S', lambda: self.save(copy=True)),
                             ('Ctrl+F', self.focus_search), ('Ctrl+C', self.copy_text), ('F3', lambda: self.next_match(1)),
                             ('Shift+F3', lambda: self.next_match(-1)), ('Ctrl+H', lambda: self.mark('highlight')),
                             ('Ctrl+U', lambda: self.mark('underline')), ('Ctrl+G', self.indicator.start_edit),
                             ('Alt+Right', page_step(1)), ('Alt+Left', page_step(-1)), ('Ctrl++', self.zoom_in),
                             ('Ctrl+=', self.zoom_in), ('Ctrl+-', self.zoom_out), ('Ctrl+0', lambda: self.fit('width')),
                             ('Ctrl+9', lambda: self.fit('page')), ('Ctrl+2', self.toggle_view_mode),
                             ('F9', self.toggle_sidebar), ('Ctrl+W', self.close), ('Ctrl+Q', self.close),
                             ('F1', self.show_shortcuts), ('Escape', self.escape)):
            QShortcut(QKeySequence(keys), self).activated.connect(action)

    # --------------------------------------------------------------- feedback
    def say(self, text):
        self.toast.show_message(text)

    def error(self, reply):
        if 'error' not in reply:
            return False
        self.say(reply['error'])
        QMessageBox.warning(self, 'Wysun PDF', reply['error'])
        return True

    def worker_failed(self, message):
        self.busy = True
        self.controls()
        self.say(message)

    def ready(self):
        """A document is open and its first visible page is painted sharp."""
        if not self.path or self.busy:
            return False
        page = max(0, self.view.current_page())
        return self.source.image(page, self.view.pixel_width(page))[1]

    def controls(self):
        open_ = bool(self.path)
        ready = open_ and not self.busy
        self.save_button.setEnabled(ready and self.dirty)
        self.note_button.setEnabled(ready and self.editable)
        for widget in (self.zoom, self.view_switch, self.search, self.indicator, self.sidebar_button):
            widget.setEnabled(open_)
        searching = bool(self.search_term)
        for widget in (self.previous_hit, self.next_hit, self.hit_count):
            widget.setVisible(searching)
        self.previous_hit.setEnabled(bool(self.matches))
        self.next_hit.setEnabled(bool(self.matches))
        self.selection_bar.set_editable(self.editable and not self.busy)
        self.sidebar.editable = self.editable and not self.busy
        self.sidebar._sync_delete()
        name = Path(self.path).name if self.path else 'Wysun PDF'
        self.title.setText(name + (' •' if self.dirty else ''))
        if open_:
            details = [f'{self.pages} páginas'] + ([] if self.editable else ['solo lectura'])
            self.subtitle.setText(' · '.join(details + (['cambios sin guardar'] if self.dirty else [])))
        self.setWindowTitle((name + (' *' if self.dirty else '') + ' — Wysun PDF') if open_ else 'Wysun PDF')

    # ----------------------------------------------------------------- open
    def confirm_discard(self):
        return not self.dirty or QMessageBox.question(
            self, 'Cambios sin guardar', 'Hay anotaciones sin guardar. ¿Descartarlas?',
            QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Discard

    def choose(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir documento', '', 'PDF (*.pdf)')
        if path:
            self.open_path(path)

    def open_path(self, path, password='', confirmed=False):
        if self.busy or (not confirmed and not self.confirm_discard()):
            return
        self.remember()
        self.busy = True
        self.search_generation += 1
        self.controls()

        def opened(reply):
            self.busy = False
            if self.error(reply):
                self.controls()
                return
            result = reply['result']
            if result.get('password_required'):
                secret, ok = QInputDialog.getText(self, 'PDF protegido', 'Contraseña:', QLineEdit.Password)
                if ok:
                    self.open_path(path, secret, True)
                self.controls()
                return
            self.generation += 1
            self.path, self.pages, self.sizes = result['path'], result['pages'], result['sizes']
            self.dirty, self.editable = False, result['editable']
            self.source.reset(self.sizes)
            self.sidebar.reset(self.pages, self.editable)
            self.sidebar.set_outline(result['outline'])
            self.clear_search()
            self.stage_stack.setCurrentWidget(self.view)
            self.indicator.show()
            self.set_sidebar(self.preferences.get('sidebar', True) is not False, persist=False)
            self.view.set_document(self.sizes)
            saved = self.positions.load(self.path)
            if saved:
                self.view.restore(clamp(saved, self.pages))
            else:
                self.view.set_fit('width')
            self.view_switch.set_mode(self.view.mode)
            self.zoom_changed()
            self.page_changed(self.view.current_page())
            self.view.setFocus()
            self.controls()
            self.refresh_annotations()
            self.load_thumbnails()
            if not self.editable:
                self.say('Documento de solo lectura')
        self.worker.request('open', opened, path=str(path), password=password)

    # ------------------------------------------------------------- navigation
    def page_changed(self, page):
        if page < 0:
            return
        self.indicator.set_page(page, self.pages)
        self.sidebar.set_current_page(page)

    def zoom_changed(self):
        self.zoom.set_zoom(self.view.zoom, self.view.zoom_mode)
        self.save_timer.start()

    def zoom_in(self):
        if self.path:
            self.view.zoom_by(ZOOM_STEP)

    def zoom_out(self):
        if self.path:
            self.view.zoom_by(1 / ZOOM_STEP)

    def fit(self, kind):
        if self.path:
            self.view.set_fit(kind)

    def set_view_mode(self, mode):
        if self.path:
            self.view.set_mode(mode)
        self.view_switch.set_mode(self.view.mode)

    def toggle_view_mode(self):
        self.set_view_mode('single' if self.view.mode == 'spread' else 'spread')

    def place_overlays(self):
        self.indicator.place()
        self.place_selection_bar()

    def remember(self):
        if self.path and self.sizes:
            self.positions.save(self.path, self.view.position())

    def remember_sidebar(self):
        if self.path:
            self.preferences.set(sidebar=self.sidebar.isVisible())

    def set_sidebar(self, visible, persist=True):
        self.sidebar.setVisible(visible and bool(self.path))
        self.sidebar_button.set_symbol('left_panel_close' if visible else 'left_panel_open')
        if persist:
            self.remember_sidebar()
        if visible:
            QTimer.singleShot(0, self.load_thumbnails)

    def toggle_sidebar(self):
        self.set_sidebar(not self.sidebar.isVisible())

    # --------------------------------------------------------------- thumbnails
    def load_thumbnails(self):
        if not self.path or self.thumbnail_pending or self.sidebar.current_tab() != 0:
            return
        missing = next((p for p in self.sidebar.visible_thumbnails() if p not in self.sidebar.page_model.images), None)
        if missing is None:
            return
        self.thumbnail_pending = True
        generation = self.generation

        def loaded(reply):
            self.thumbnail_pending = False
            if generation != self.generation:
                # A reply for the previous document: the new one's thumbnails still have to start.
                QTimer.singleShot(0, self.load_thumbnails)
                return
            if 'result' not in reply:
                return
            result = reply['result']
            image = QImage(result['blob'], result['width'], result['height'], result['stride'],
                           QImage.Format_RGB888).copy()
            self.sidebar.page_model.put(missing, image)
            QTimer.singleShot(0, self.load_thumbnails)
        self.worker.request('thumbnail', loaded, priority=1, key=('thumbnail',), page=missing)

    # ------------------------------------------------------------- selection
    def selection_changed(self):
        if self.view.selection[0] is None:
            self.selection_bar.hide()

    def selection_finished(self):
        if self.pending_markup:
            kind, self.pending_markup = self.pending_markup, None
            self.mark(kind)
            return
        self.selection_bar.show()
        self.place_selection_bar()

    def place_selection_bar(self):
        if not self.selection_bar.isVisible():
            return
        rect = self.view.selection_rect()
        if not rect.isValid() or not self.view.viewport().rect().intersects(rect):
            self.selection_bar.hide()
            return
        self.selection_bar.place(rect)

    def selection_action(self, action):
        if action == 'copy':
            self.copy_text()
        elif action == 'ink':
            ink_menu(self, self.set_ink, self.choose_ink).exec(
                self.selection_bar.ink.mapToGlobal(self.selection_bar.ink.rect().bottomLeft()))
        else:
            self.mark(action)

    def copy_text(self):
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit):
            focus.copy()
        elif self.view.selected_text():
            QApplication.clipboard().setText(self.view.selected_text())
            self.say('Texto copiado')

    def set_ink(self, ink):
        self.ink = ink
        self.selection_bar.ink.set_ink(ink)
        self.preferences.set(ink=[ink.redF(), ink.greenF(), ink.blueF()])

    def choose_ink(self):
        chosen = QColorDialog.getColor(self.annotation_ink(), self, 'Color de las anotaciones')
        if chosen.isValid():
            self.set_ink(chosen)

    def annotation_ink(self):
        return self.ink if self.ink is not None else ink_colours()[0][1]

    def annotation_colour(self):
        ink = self.annotation_ink()
        return [ink.redF(), ink.greenF(), ink.blueF()]

    # ------------------------------------------------------------- annotations
    def mark(self, kind):
        if not self.path or self.busy or not self.editable:
            return
        rects = self.view.selected_rects()
        if not rects:
            self.pending_markup = kind
            self.say('Arrastra sobre el texto para ' + ('resaltarlo' if kind == 'highlight' else 'subrayarlo'))
            return
        page = self.view.selection[0]
        self.edit('annotate', page, kind=kind, rects=rects, text=self.view.selected_text(),
                  colour=self.annotation_colour())

    def toggle_note_tool(self):
        self.view.note_mode = self.note_button.isChecked()
        if self.view.note_mode:
            self.say('Haz clic en la página para colocar la nota')

    def add_note(self, page, point):
        self.note_button.setChecked(False)
        self.view.note_mode = False
        if not self.editable or self.busy:
            return
        dialog = NoteDialog(self)
        if dialog.exec():
            self.edit('annotate', page, kind='note', point=[point.x(), point.y()],
                      text=dialog.editor.toPlainText(), colour=self.annotation_colour())

    def edit_note(self, note):
        if self.busy or not self.editable:
            return
        dialog = NoteDialog(self, text=note['text'], title='Editar anotación')
        if dialog.exec():
            self.edit('update_note', note['page'], xref=note['xref'], text=dialog.editor.toPlainText())

    def delete_annotation(self, note):
        if not self.busy and self.editable:
            self.edit('delete', note['page'], xref=note['xref'])

    def edit(self, operation, page, **args):
        self.busy = True
        self.controls()
        generation = self.generation

        def edited(reply):
            self.busy = False
            if generation == self.generation and not self.error(reply):
                self.dirty = True
                self.source.invalidate(page)
                self.sidebar.page_model.forget(page)
                self.view.clear_selection()
                self.view.request()
                self.refresh_annotations()
                self.load_thumbnails()
                self.say('Anotación sin guardar · Ctrl+S')
            self.controls()
        self.worker.request(operation, edited, page=page, **args)

    def refresh_annotations(self):
        generation = self.generation

        def listed(reply):
            if generation == self.generation and 'result' in reply:
                self.sidebar.set_notes(reply['result']['items'])
        self.worker.request('annotations', listed, key=('annotations',))

    # ------------------------------------------------------------------ save
    def save(self, copy=False):
        if not self.path or self.busy or (not copy and not self.dirty):
            return
        target, expected = self.path, None
        if copy:
            dialog = QFileDialog(self, 'Guardar copia anotada')
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            dialog.setNameFilter('PDF (*.pdf)')
            dialog.setDefaultSuffix('pdf')
            dialog.selectFile(str(Path(self.path).with_stem(Path(self.path).stem + ' — anotado')))
            if not dialog.exec():
                return
            target = dialog.selectedFiles()[0]
            if Path(target).exists():
                info = Path(target).stat()
                expected = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]
        self.busy = True
        self.controls()

        def saved(reply):
            self.busy = False
            if not self.error(reply):
                self.path = reply['result']['path']
                self.dirty = False
                self.say('PDF guardado · las anotaciones se ven en cualquier lector')
                self.remember()
            self.controls()
        self.worker.request('save', saved, path=target, expected=expected)

    # ---------------------------------------------------------------- search
    def eventFilter(self, watched, event):
        if watched is self.search and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ShiftModifier:
                self.next_match(-1)
                return True
            if event.key() == Qt.Key_Escape:
                self.search.clear()
                self.view.setFocus()
                return True
        return super().eventFilter(watched, event)

    def focus_search(self):
        if self.path:
            self.search.setFocus(Qt.ShortcutFocusReason)
            self.search.selectAll()

    def clear_search(self):
        self.search_generation += 1
        self.search_term, self.search_done = '', True
        self.hits, self.matches, self.match = {}, [], -1
        self.view.set_hits({})
        self.sidebar.set_results('', [], 'Busca con Ctrl F')
        self.hit_count.setText('')
        self.controls()

    def start_search(self):
        self.search_timer.stop()
        term = self.search.text().strip()
        if not self.path or term == self.search_term:
            return
        self.clear_search()
        if not term:
            return
        self.search_term, self.search_done = term, False
        self.controls()
        token, document = self.search_generation, self.generation
        origin = max(0, self.view.current_page())
        if self.sidebar.isVisible():
            self.sidebar.set_tab(3)

        def search_page(page):
            def found(reply):
                if token != self.search_generation or document != self.generation or self.error(reply):
                    return
                result = reply['result']
                if result['hits']:
                    self.hits[page] = result['hits']
                    start = len(self.matches)
                    self.matches += [(page, index) for index in range(len(result['hits']))]
                    self.sidebar.add_results(term, [(page, context) for context in result['contexts']],
                                             f'Buscando… página {page + 1} de {self.pages}')
                    if self.match < 0 and page >= origin:
                        self.select_match(start)
                    else:
                        self.view.set_hits(self.hits, self.view.current_hit)
                if page + 1 < self.pages:
                    QTimer.singleShot(0, lambda: search_page(page + 1))
                    return
                self.search_done = True
                if self.matches and self.match < 0:
                    self.select_match(0)
                self.sidebar.results_meta = f'{len(self.matches)} coincidencias' if self.matches else 'Sin coincidencias'
                self.sidebar._meta()
                self._count()
            self.worker.request('search', found, priority=2, page=page, text=term)
        search_page(0)

    def _count(self):
        if self.matches:
            self.hit_count.setText(f'{self.match + 1}/{len(self.matches)}')
        else:
            self.hit_count.setText('' if not self.search_done else 'Sin resultados')
        self.controls()

    def select_match(self, index):
        if not 0 <= index < len(self.matches):
            return
        self.match = index
        page, hit = self.matches[index]
        self.view.set_hits(self.hits, (page, hit))
        self.sidebar.select_result(index)
        self._count()

    def next_match(self, step):
        if self.search.text().strip() != self.search_term:
            self.start_search()
            return
        if self.matches:
            self.select_match((self.match + step) % len(self.matches))

    # ----------------------------------------------------------------- links
    def follow_link(self, link):
        if 'page' in link:
            self.view.go(link['page'], link.get('y') or None)
            return
        uri = link.get('uri', '')
        if QUrl(uri).scheme().lower() not in LINK_SCHEMES:
            self.say('Este enlace no se puede abrir desde el lector')
            return
        if self.confirm_link(uri):
            self.launch_url(uri)

    def confirm_link(self, uri):
        box = QMessageBox(QMessageBox.Question, 'Abrir enlace externo',
                          'El documento quiere abrir esta dirección fuera del lector:\n\n' + uri,
                          QMessageBox.Open | QMessageBox.Cancel, self)
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec() == QMessageBox.Open

    def launch_url(self, uri):
        process = QProcess(self)
        environment = QProcessEnvironment()
        for key, value in self.reader_mode.environment().items():
            environment.insert(key, value)
        process.setProcessEnvironment(environment)
        process.setProgram('xdg-open')
        process.setArguments([uri])
        if not process.startDetached()[0]:
            self.say('No se pudo abrir el enlace')

    # ----------------------------------------------------------------- menu
    def more_menu(self):
        menu = QMenu(self)
        menu.addAction('Abrir…  Ctrl+O', self.choose)
        copy = menu.addAction('Guardar una copia…  Ctrl+Shift+S', lambda: self.save(copy=True))
        copy.setEnabled(bool(self.path) and not self.busy)
        menu.addSeparator()
        look = menu.addMenu('Apariencia del lector')
        group = QActionGroup(look)
        for mode, label in ((None, 'Como el escritorio'), ('light', 'Claro'), ('dark', 'Oscuro')):
            action = look.addAction(label, lambda m=mode: self.reader_mode.set(m))
            action.setCheckable(True)
            action.setChecked(self.reader_mode.pinned == mode)
            group.addAction(action)
        menu.addAction('Atajos de teclado  F1', self.show_shortcuts)
        menu.exec(self.more_button.mapToGlobal(self.more_button.rect().bottomLeft()))

    def show_shortcuts(self):
        QMessageBox.information(self, 'Atajos de Wysun PDF', SHORTCUTS)

    def escape(self):
        # The window's Escape shortcut wins over the search field's key filter, so clear it here too.
        if self.search.hasFocus():
            self.search.clear()
            self.view.setFocus()
            return
        if self.view.note_mode:
            self.note_button.setChecked(False)
            self.view.note_mode = False
        self.pending_markup = None
        self.view.clear_selection()

    # ---------------------------------------------------------------- window
    def paintEvent(self, _event):
        paint_surface(self)

    def dragEnterEvent(self, event):
        if not self.busy and any(u.isLocalFile() and u.toLocalFile().lower().endswith('.pdf') for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'):
                self.open_path(url.toLocalFile())
                event.acceptProposedAction()
                break

    def closeEvent(self, event):
        if self.busy and self.worker.process.state() != QProcess.NotRunning:
            self.say('Espera a que termine la operación antes de cerrar.')
            event.ignore()
            return
        if not self.confirm_discard():
            event.ignore()
            return
        self.remember()
        self.worker.stop()
        event.accept()
