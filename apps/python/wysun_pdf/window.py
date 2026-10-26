"""Wysun PDF: one window per document, a continuous virtualized view and native PDF annotations.

The window composes kit widgets (wysun_core.ui) and the reader's own pieces (pdf_chrome, pdf_sidebar,
pdf_view). All PDF work happens in the engine process behind pdf_worker; pdf_source asks it only for
what is on screen.
"""
from pathlib import Path
import json
import math
from datetime import datetime, timezone

from PySide6.QtCore import QEvent, QProcess, QProcessEnvironment, Qt, QTimer, QUrl
from PySide6.QtGui import QActionGroup, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QColorDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QPlainTextEdit,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QStackedLayout, QVBoxLayout, QWidget)

from wysun_core.ui_theme import paint_surface
from wysun_core.ui.frameless import FramelessResize
from wysun_core.ui.motion import WindowMotion
from wysun_core.ui.panels import Panel, SearchField
from wysun_core.ui.style import apply_kit_style, metric
from wysun_core.ui.toast import Toast
from wysun_core.ui.widgets import ElidedLabel, IconButton, PillButton
from wysun_pdf.chrome import (CONTROL, EmptyState, NoteDialog, PageIndicator, SelectionBar, ViewModeSwitch, ZoomControl,
                        ink_colours, ink_menu)
from wysun_pdf.sidebar import Sidebar
from wysun_pdf.source import PageSource
from wysun_pdf.state import Positions, Preferences, clamp
from wysun_pdf.theme import shared as shared_mode
from wysun_pdf.view import DocumentView
from wysun_pdf.worker import PdfWorker
from wysun_pdf.study import StudyStore
from wysun_pdf.study_ui import LibraryView, Notebook, STORAGE_ERRORS, control_height, reveal, navigate, StudySettings
from wysun_core import jsonio
from wysun_pdf.focus import shared_focus
from wysun_pdf.focus_ui import FocusPanel
from wysun_pdf.lookup_ui import LookupPanel
from wysun_core.ui.style import clock

ZOOM_STEP = 1.2
LINK_SCHEMES = ('http', 'https', 'mailto')
SHORTCUTS = '''Ctrl+O abrir · Ctrl+S guardar · Ctrl+Shift+S guardar una copia
Ctrl+F buscar · Enter / Shift+Enter (o F3 / Shift+F3) siguiente / anterior coincidencia · Esc limpiar
Ctrl+C copiar · Ctrl+H resaltar · Ctrl+U subrayar · doble clic selecciona una palabra
Ctrl+G ir a una página · Alt+← / Alt+→ página anterior / siguiente · RePág / AvPág, Espacio desplazan una pantalla · Inicio / Fin
Ctrl+rueda, Ctrl++ y Ctrl+− zoom · Ctrl+0 ajustar al ancho · Ctrl+9 ajustar a la página
Ctrl+2 una o dos páginas · F9 panel lateral · F1 atajos · Ctrl+W / Ctrl+Q cerrar'''


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
        self.saving = False
        self.generation = 0
        self.pending_markup = None
        self.thumbnail_pending = False
        self.search_term, self.search_generation, self.search_done = '', 0, True
        self.hits, self.matches, self.match = {}, [], -1
        self.preferences = Preferences()
        self.positions = Positions()
        self.study_document = None
        self.lookup_context = None
        self.focus_session = shared_focus(self)
        self.study_error = ''
        try:
            self.study = StudyStore()
        except STORAGE_ERRORS as error:
            self.study = None
            self.study_error = str(error)
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
        self.focus_session.message.connect(self.say)
        self.focus_session.changed.connect(self.focus_updated)
        self.focus_updated()
        self._shortcuts()
        self.setAcceptDrops(True)
        self.set_sidebar(self.preferences.get('sidebar', True) is not False, persist=False)
        self.controls()
        self.library.refresh()
        self.workspace.setCurrentWidget(self.library)
        self.library.open_button.setFocus()
        if self.study_error:
            QTimer.singleShot(0, lambda: self.say('Biblioteca no disponible: ' + self.study_error))
        if path:
            QTimer.singleShot(0, lambda: self.open_path(path))

    # ------------------------------------------------------------------ build
    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        margin = metric('spacing.small')
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(margin)
        self.workspace = QStackedLayout()
        outer.addLayout(self.workspace)
        self.reader = QWidget()
        reader_layout = QVBoxLayout(self.reader)
        reader_layout.setContentsMargins(0, 0, 0, 0)
        reader_layout.setSpacing(margin)
        reader_layout.addLayout(self._top_bar())
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
        inset = metric('spacing.small')
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
        self.notebook = Notebook(self.study)
        self.notebook.hide()
        self.notebook.closed.connect(self.toggle_notebook)
        self.notebook.jump.connect(self.return_to_passage)
        self.notebook.message.connect(self.say)
        self.notebook.export_requested.connect(self.export_notebook)
        self.notebook.new_requested.connect(self.study_note)
        self.notebook.reference_open.connect(lambda url: self.follow_link({'uri': url}))
        body.addWidget(self.notebook)
        self.focus_panel = FocusPanel(self.focus_session)
        self.focus_panel.hide()
        self.focus_panel.closed.connect(self.toggle_focus)
        self.focus_panel.reflection_requested.connect(self.study_note)
        body.addWidget(self.focus_panel)
        self.lookup_panel = LookupPanel(self.preferences)
        self.lookup_panel.hide()
        self.lookup_panel.closed.connect(self.hide_lookup)
        self.lookup_panel.open_url.connect(lambda url: self.follow_link({'uri': url}))
        self.lookup_panel.save_requested.connect(self.save_reference)
        body.addWidget(self.lookup_panel)
        reader_layout.addLayout(body, 1)
        self.workspace.addWidget(self.reader)
        self.library = LibraryView(self.study)
        self.library.choose_requested.connect(self.choose)
        self.library.open_requested.connect(self.open_recent)
        self.library.settings_requested.connect(self.study_settings)
        self.library.message.connect(self.say)
        self.workspace.addWidget(self.library)

    def _top_bar(self):
        bar = QHBoxLayout()
        bar.setContentsMargins(metric('spacing.extraSmall'), metric('spacing.extraSmall'), metric('spacing.extraSmall'), 0)
        bar.setSpacing(metric('spacing.small'))
        self.close_button = IconButton('close', 'Cerrar · Ctrl+W', self.close, size=34)
        self.sidebar_button = IconButton('left_panel_close', 'Panel lateral · F9', self.toggle_sidebar, size=CONTROL)
        self.sidebar_button.outline = True
        bar.addWidget(self.close_button)
        self.home_button = IconButton('home', 'Biblioteca', self.show_library, size=control_height())
        bar.addWidget(self.home_button)
        bar.addWidget(self.sidebar_button)
        title = QVBoxLayout()
        title.setSpacing(0)
        self.title = ElidedLabel('Wysun PDF', 'title.medium', 650)
        self.subtitle = ElidedLabel('Lector local', 'body.small', 450, tint='muted')
        title.addWidget(self.title)
        title.addWidget(self.subtitle)
        bar.addLayout(title, 1)
        self.search = SearchField('Buscar en el documento', 'kitSearch')
        self.search.setPlaceholderText('Buscar en el documento')
        self.search.setToolTip('Buscar · Ctrl+F · Enter siguiente, Shift+Enter anterior')
        self.search.setMinimumWidth(metric('spacing.extraExtraLarge', 3))
        self.search.setMaximumWidth(metric('spacing.extraExtraLarge', 5))
        self.search.textChanged.connect(lambda _: self.search_timer.start())
        self.search.returnPressed.connect(lambda: self.next_match(1))
        self.search.installEventFilter(self)
        bar.addWidget(self.search)
        self.search.hide()
        self.search_button = IconButton('search', 'Buscar en el documento · Ctrl+F', self.focus_search, size=control_height())
        bar.addWidget(self.search_button)
        self.hit_count = QLabel('')
        self.hit_count.setObjectName('muted')
        self.hit_count.setAccessibleName('Coincidencias')
        bar.addWidget(self.hit_count)
        self.previous_hit = IconButton('keyboard_arrow_up', 'Coincidencia anterior · Shift+Enter', lambda: self.next_match(-1), size=CONTROL - 4)
        self.next_hit = IconButton('keyboard_arrow_down', 'Siguiente coincidencia · Enter', lambda: self.next_match(1), size=CONTROL - 4)
        bar.addWidget(self.previous_hit)
        bar.addWidget(self.next_hit)
        bar.addSpacing(metric('spacing.small'))
        self.zoom = ZoomControl()
        self.zoom.zoom_in.connect(self.zoom_in)
        self.zoom.zoom_out.connect(self.zoom_out)
        self.zoom.fit.connect(self.fit)
        self.zoom.percent.connect(lambda value: self.view.set_zoom(value))
        self.zoom.setParent(self.reader)
        self.zoom.hide()
        self.view_switch = ViewModeSwitch()
        self.view_switch.changed.connect(self.set_view_mode)
        self.view_switch.setParent(self.reader)
        self.view_switch.hide()
        self.reading_button = PillButton('auto_stories', 'Lectura', self.reading_menu, 'tonal', control_height())
        bar.addWidget(self.reading_button)
        self.note_button = IconButton('edit_note', 'Nota: haz clic en la página para colocarla', self.toggle_note_tool,
                                      variant='tonal', size=CONTROL, checkable=True)
        self.note_button.setParent(self.reader)
        self.note_button.hide()
        self.save_button = PillButton('save', 'Guardar', self.save, height=CONTROL)
        self.save_button.setToolTip('Guardar · Ctrl+S')
        bar.addWidget(self.save_button)
        self.more_button = IconButton('more_vert', 'Más opciones', self.more_menu, size=CONTROL)
        self.notebook_button = IconButton('edit_note', 'Cuaderno de estudio', self.toggle_notebook,
                                         variant='tonal', size=control_height(), checkable=True)
        bar.addWidget(self.notebook_button)
        self.focus_button = PillButton('timer', 'Sesión', self.toggle_focus, 'tonal', control_height())
        bar.addWidget(self.focus_button)
        bar.addWidget(self.more_button)
        return bar

    def reading_menu(self):
        menu = QMenu(self)
        for title, action in (('Acercar · Ctrl++', self.zoom_in), ('Alejar · Ctrl+−', self.zoom_out),
                              ('Ajustar al ancho · Ctrl+0', lambda: self.fit('width')),
                              ('Ajustar a la página · Ctrl+9', lambda: self.fit('page')),
                              ('Una / dos páginas · Ctrl+2', self.toggle_view_mode)):
            menu.addAction(title, action)
        menu.addSeparator()
        menu.addAction('Nota dentro del PDF', lambda: (self.note_button.setChecked(True), self.toggle_note_tool()))
        menu.addAction('Reflexión en cuaderno · Ctrl+Shift+N', self.study_note)
        menu.addAction('Consultar palabra o concepto', self.consult_selection)
        menu.exec(self.reading_button.mapToGlobal(self.reading_button.rect().bottomLeft()))

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
        QShortcut(QKeySequence('Ctrl+Shift+N'), self).activated.connect(self.study_note)
        QShortcut(QKeySequence('Alt+Home'), self).activated.connect(self.show_library)

    # --------------------------------------------------------------- study
    def hide_lookup(self):
        self.lookup_panel.cancel()
        self.lookup_panel.hide()
        self.lookup_context = None
        self.adapt_panels()

    def consult_selection(self):
        if not self.path or self.busy or not self.notebook.can_leave():
            return
        page = self.view.selection[0]
        page = self.view.current_page() if page is None else page
        quote = self.view.selected_text()
        anchor = {'rects': self.view.selected_rects()}
        try:
            info = Path(self.path).stat()
            anchor['file'] = [info.st_size, info.st_mtime_ns]
        except OSError:
            pass
        self.lookup_context = dict(generation=self.generation, document=self.study_document,
                                   page=page, quote=quote, anchor=anchor)
        self.notebook.hide()
        self.notebook_button.setChecked(False)
        self.focus_panel.hide()
        self.set_sidebar(False, persist=False)
        self.lookup_panel.set_term(quote)
        self.lookup_panel.show()
        self.adapt_panels()
        self.selection_bar.hide()
        reveal(self.lookup_panel)
        self.lookup_panel.term.setFocus()

    def save_reference(self, reference):
        context = self.lookup_context
        if not context or context['generation'] != self.generation or not context['document'] or not self.study:
            self.say('Abre una consulta en el documento actual para guardar su referencia.')
            return
        reference = dict(reference, date=datetime.now(timezone.utc).isoformat())
        anchor = dict(context['anchor'], reference=reference)
        body = '\n\n'.join((reference['title'], reference['body'],
                            reference['source'] + ' · ' + reference['language'].upper(),
                            reference['url'], reference['attribution'], 'Consultado: ' + reference['date']))
        try:
            self.study.save_entry(context['document']['id'], context['page'], context['quote'], anchor, body)
        except STORAGE_ERRORS as error:
            self.say('No se pudo guardar la referencia: ' + str(error))
            return
        self.notebook.refresh()
        self.say('Referencia guardada en el cuaderno, junto al pasaje original.')

    def open_recent(self, path):
        if not Path(path).is_file():
            self.say('No se encuentra el archivo. Ábrelo desde su nueva ubicación; tus notas se conservan.')
            return
        if path == self.path:
            navigate(self.workspace, self.reader)
            return
        self.open_path(path)

    def show_library(self):
        if self.busy or not self.notebook.can_leave():
            return
        # Keep the open PDF (and any unsaved annotations) alive behind the library.
        self.remember()
        self.library.refresh()
        self.hide_lookup()
        navigate(self.workspace, self.library)
        self.library.open_button.setFocus()

    def toggle_notebook(self):
        if not self.path or not self.study_document:
            self.say('Abre un PDF para escribir en su cuaderno.')
            return
        visible = not self.notebook.isVisible()
        if not visible and not self.notebook.can_leave():
            self.notebook_button.setChecked(True)
            return
        if visible:
            self.hide_lookup()
            self.focus_panel.hide()
            self.set_sidebar(False, persist=False)
        self.notebook.setVisible(visible)
        self.adapt_panels()
        self.notebook_button.setChecked(visible)
        if visible:
            self.notebook.refresh()
            reveal(self.notebook)
        else:
            self.view.setFocus()

    def toggle_focus(self):
        if not self.path:
            return
        visible = not self.focus_panel.isVisible()
        if visible:
            if not self.notebook.can_leave():
                return
            self.hide_lookup()
            self.notebook.hide()
            self.notebook_button.setChecked(False)
            self.set_sidebar(False, persist=False)
        self.focus_panel.setVisible(visible)
        self.adapt_panels()
        if visible:
            reveal(self.focus_panel)
        else:
            self.view.setFocus()

    def focus_updated(self):
        session = self.focus_session.clock
        text = clock(math.ceil(session.remaining)) if session.state != 'idle' else 'Sesión'
        symbol = 'pause' if session.state == 'paused' else 'timer'
        self.focus_button.set_content(symbol, text)
        self.focus_button.setAccessibleName('Sesión de concentración: ' + text)
        self.adapt_header()

    def study_note(self):
        if not self.path or not self.study_document:
            return
        page = self.view.selection[0]
        page = self.view.current_page() if page is None else page
        quote = self.view.selected_text()
        anchor = {'rects': self.view.selected_rects()}
        try:
            info = Path(self.path).stat()
            anchor['file'] = [info.st_size, info.st_mtime_ns]
        except OSError:
            pass
        if not self.notebook.new(page, quote, anchor):
            return
        if not self.notebook.isVisible():
            self.toggle_notebook()
        self.notebook.editor.setFocus()
        self.selection_bar.hide()

    def return_to_passage(self, entry):
        if not self.path or not 0 <= entry['page'] < self.pages:
            self.say('La página original ya no está disponible. La nota se conserva en el cuaderno.')
            return
        try:
            anchor = json.loads(entry['anchor'])
            info = Path(self.path).stat()
            expected = anchor.get('file')
            if expected and expected != [info.st_size, info.st_mtime_ns]:
                if QMessageBox.question(self, 'El archivo ha cambiado',
                        'El pasaje podría haberse movido. ¿Ir a la página guardada para localizarlo?',
                        QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
                    return
            rects = anchor.get('rects', [])
            y = rects[0][1] if rects else None
        except (OSError, ValueError, TypeError, IndexError):
            self.say('No se pudo localizar el pasaje. Tu nota sigue guardada.')
            return
        self.view.go(entry['page'], y)
        self.view.setFocus()

    def export_notebook(self):
        if not self.study_document or not self.notebook.can_leave():
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar el cuaderno', 'cuaderno.md', 'Markdown (*.md)')
        if path:
            try:
                jsonio.atomic_write_text(path, self.study.export(self.study_document['id']))
            except STORAGE_ERRORS as error:
                self.say(str(error))
            else:
                self.say('Cuaderno exportado')

    def study_settings(self):
        StudySettings(self.preferences, self.study, self).exec()
        self.hide_lookup()
        self.library.refresh()

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
        self.save_button.setVisible(self.dirty)
        self.note_button.setEnabled(ready and self.editable)
        for widget in (self.zoom, self.view_switch, self.search, self.indicator, self.sidebar_button):
            widget.setEnabled(open_)
        self.reading_button.setEnabled(open_)
        self.focus_button.setEnabled(open_)
        self.search_button.setEnabled(open_)
        self.notebook_button.setEnabled(bool(self.study_document))
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
        self.adapt_header()

    def adapt_panels(self):
        if not hasattr(self, 'lookup_panel'):
            return
        compact = self.width() < metric('spacing.extraExtraLarge', 20)
        panels = (self.notebook, self.focus_panel, self.lookup_panel)
        active = any(not panel.isHidden() for panel in panels)
        # In narrow windows, the study panel gets the canvas; closing it restores
        # the passage instead of shrinking a PDF to an unreadable sliver.
        self.stage.setVisible(not (compact and active))
        for panel in panels:
            panel.setMaximumWidth(self.width() if compact else metric('spacing.extraExtraLarge', 8))

    def adapt_header(self):
        self.adapt_panels()
        compact = self.width() < metric('spacing.extraExtraLarge', 20)
        self.reading_button.set_content('auto_stories', '' if compact else 'Lectura')
        self.reading_button.setAccessibleName('Opciones de lectura')
        self.reading_button.setToolTip('Zoom, vista y anotaciones')
        self.sidebar_button.setVisible(not (compact and not self.search.isHidden()))
        self.save_button.set_content('save', '' if compact else 'Guardar PDF')
        self.save_button.setAccessibleName('Guardar PDF')
        if self.focus_session.clock.state == 'idle':
            self.focus_button.set_content('timer', '' if compact else 'Sesión')
            self.focus_button.setAccessibleName('Sesión de concentración')

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
        if self.busy or (not confirmed and (not self.notebook.can_leave() or not self.confirm_discard())):
            return
        self.hide_lookup()
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
            self.search.clear()
            self.clear_search()
            self.stage_stack.setCurrentWidget(self.view)
            navigate(self.workspace, self.reader)
            self.indicator.show()
            self.set_sidebar(self.preferences.get('sidebar', True) is not False, persist=False)
            self.view.set_document(self.sizes)
            saved = self.positions.load(self.path)
            if saved:
                self.view.restore(clamp(saved, self.pages))
            else:
                self.view.set_fit('width')
            self.view_switch.set_mode(self.view.mode)
            self.study_document = None
            if self.study:
                try:
                    self.study_document = self.study.opened(self.path, self.pages, self.view.current_page(),
                        remember=self.preferences.get('remember_recent', True) is not False)
                except STORAGE_ERRORS as error:
                    self.say('Biblioteca: ' + str(error))
            self.notebook.bind(self.study_document)
            self.notebook.hide()
            self.focus_panel.hide()
            self.notebook_button.setChecked(False)
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
            if self.study_document:
                try:
                    self.study.position(self.study_document['id'], self.view.current_page())
                except STORAGE_ERRORS as error:
                    self.say('No se pudo guardar la posición en la biblioteca: ' + str(error))

    def remember_sidebar(self):
        if self.path:
            self.preferences.set(sidebar=self.sidebar.isVisible())

    def set_sidebar(self, visible, persist=True):
        if visible and hasattr(self, 'lookup_panel'):
            self.hide_lookup()
        if visible and hasattr(self, 'focus_panel'):
            self.focus_panel.hide()
        if visible and hasattr(self, 'notebook') and self.notebook.isVisible():
            if not self.notebook.can_leave():
                return
            self.notebook.hide()
            self.notebook_button.setChecked(False)
        self.sidebar.setVisible(visible and bool(self.path))
        self.adapt_panels()
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
        if action == 'lookup':
            self.consult_selection()
        elif action == 'study':
            self.study_note()
        elif action == 'copy':
            self.copy_text()
        elif action == 'ink':
            ink_menu(self, self.set_ink, self.choose_ink).exec(
                self.selection_bar.ink.mapToGlobal(self.selection_bar.ink.rect().bottomLeft()))
        else:
            self.mark(action)

    def copy_text(self):
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QPlainTextEdit)):
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
        if copy and not self.notebook.can_leave():
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
        self.saving = True
        self.controls()

        def saved(reply):
            self.busy = False
            self.saving = False
            if not self.error(reply):
                previous_path = self.path
                self.path = reply['result']['path']
                self.dirty = False
                if self.path != previous_path:
                    self.hide_lookup()
                if self.path != previous_path and self.study:
                    try:
                        self.study_document = self.study.opened(self.path, self.pages, self.view.current_page(),
                        remember=self.preferences.get('remember_recent', True) is not False)
                        self.notebook.bind(self.study_document)
                    except STORAGE_ERRORS as error:
                        self.study_document = None
                        self.notebook.bind(None)
                        self.say('PDF guardado; biblioteca: ' + str(error))
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
            self.search.show()
            self.search_button.hide()
            self.search.setFocus(Qt.ShortcutFocusReason)
            self.search.selectAll()
            self.adapt_header()

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
        self.search.show()
        self.search_button.hide()
        self.controls()
        token, document = self.search_generation, self.generation
        failures = []
        origin = max(0, self.view.current_page())
        if self.sidebar.isVisible():
            self.sidebar.set_tab(3)

        def search_page(page):
            def found(reply):
                if token != self.search_generation or document != self.generation:
                    return
                if 'error' in reply:
                    failures.append(page)
                result = reply.get('result', {'hits': [], 'contexts': []})
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
                if failures:
                    self.sidebar.results_meta += f' · {len(failures)} páginas sin buscar'
                    self.say('Búsqueda incompleta: no se pudieron consultar algunas páginas.')
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
        if self.notebook.editor.hasFocus():
            self.view.setFocus()
            return
        # The window's Escape shortcut wins over the search field's key filter, so clear it here too.
        if self.search.hasFocus():
            self.search.clear()
            self.search.hide()
            self.search_button.show()
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'reading_button'):
            self.adapt_header()

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
        if not self.notebook.can_leave():
            event.ignore()
            return
        if self.busy and self.worker.process.state() != QProcess.NotRunning:
            if self.saving:
                self.say('Guardando el PDF. Espera antes de cerrar.')
                event.ignore()
                return
            if QMessageBox.question(self, 'Interrumpir operación',
                    'El motor está ocupado. ¿Interrumpir la operación y cerrar?',
                    QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Discard:
                event.ignore()
                return
        if not self.confirm_discard():
            event.ignore()
            return
        self.remember()
        self.lookup_panel.client.cancel()
        self.worker.stop()
        self.focus_session.detach(self)
        event.accept()
