"""Wysun's local reader: bounded page rendering and native PDF annotations."""
import base64
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Signal, QPoint
from PySide6.QtGui import QImage, QPainter, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QScrollArea, QSplitter, QLineEdit, QSpinBox, QComboBox,
    QListWidget, QListWidgetItem, QTabWidget, QFileDialog, QMessageBox, QInputDialog, QColorDialog, QStackedWidget, QFrame)
from pdf_worker import PdfWorker
from pdf_material import ReaderTheme, Panel, Text, Action, M, reader_list, thumbnail_view, Emblem, NoteDialog


class PageCanvas(QWidget):
    selected = Signal()
    selectionFinished = Signal()
    noteRequested = Signal(object)

    def __init__(self, theme):
        super().__init__()
        self.theme=theme
        self.image = QImage()
        self.words = []
        self.selection = []
        self.hits = []
        self.start = None
        self.note_mode = False
        self.page_width = 1
        self.page_height = 1
        self.setCursor(Qt.IBeamCursor)
        self.setAccessibleName('Página PDF; arrastra sobre el texto para seleccionarlo')

    def set_page(self, result, display_width):
        self.image = QImage.fromData(base64.b64decode(result['png']))
        self.words = result['words']
        self.page_width, self.page_height = result['width'], result['height']
        self.selection = []
        self.hits = []
        self.start = None
        self.setFixedSize(display_width, round(display_width * self.page_height / self.page_width))
        self.update()
        self.selected.emit()

    def point(self, position):
        return QPointF(position.x() * self.page_width / self.width(),
                       position.y() * self.page_height / self.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(self.rect(), self.image)
        painter.scale(self.width() / self.page_width, self.height() / self.page_height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.theme.color('primary', 65))
        for r in self.hits:
            painter.drawRect(QRectF(r[0], r[1], r[2] - r[0], r[3] - r[1]))
        painter.setBrush(self.theme.color('primary', 95))
        for index in self.selection:
            w = self.words[index]
            painter.drawRect(QRectF(w[0], w[1], w[2] - w[0], w[3] - w[1]))

    def nearest(self, position):
        if not self.words:
            return None
        p = self.point(position)
        return min(range(len(self.words)), key=lambda i:
            max(self.words[i][0] - p.x(), 0, p.x() - self.words[i][2]) ** 2 +
            max(self.words[i][1] - p.y(), 0, p.y() - self.words[i][3]) ** 2)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self.note_mode:
            self.noteRequested.emit(self.point(event.position()))
            return
        self.start = self.nearest(event.position())
        self.selection = [] if self.start is None else [self.start]
        self.selected.emit()
        self.update()

    def mouseMoveEvent(self, event):
        if self.start is not None and event.buttons() & Qt.LeftButton:
            end = self.nearest(event.position())
            self.selection = list(range(min(self.start, end), max(self.start, end) + 1))
            self.selected.emit()
            self.update()

    def mouseReleaseEvent(self, event):
        self.start = None
        self.selectionFinished.emit()

    def text(self):
        return ' '.join(self.words[i][4] for i in self.selection)


class PdfWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.setWindowTitle('Wysun PDF')
        self.resize(1280, 860)
        self.path = None
        self.pages = 0
        self.page = 0
        self.dirty = False
        self.editable = False
        self.ink = None
        self.busy = False
        self.generation = 0
        self.search_generation = 0
        self.search_hits = {}
        self.render_serial = 0
        self.displayed_page = None
        self.pending_markup = None
        self.thumbnail_pending = False
        self.reader_theme = ReaderTheme(self)
        self.worker = PdfWorker(self)
        self.worker.failed.connect(self.worker_failed)
        t = self.reader_theme
        root = Panel(t, 'canvas', None)
        self.setCentralWidget(root)
        shell = QHBoxLayout(root); shell.setContentsMargins(0, 0, M['space_l'], M['space_l']); shell.setSpacing(0)
        rail = Panel(t, 'canvas', None); rail.setFixedWidth(M['rail'])
        rail_layout = QVBoxLayout(rail); rail_layout.setContentsMargins(M['space_m'], M['space_xl'], M['space_m'], M['space_l'])
        rail_layout.setSpacing(M['space_m'])
        brand = Emblem(t)
        brand.setToolTip('Wysun PDF'); brand.setFocusPolicy(Qt.NoFocus)
        rail_layout.addWidget(brand)
        rail_layout.addSpacing(M['space_xl'])
        self.nav_buttons = []
        for index, symbol, label in ((0,'list','Índice'), (1,'search','Buscar'), (2,'notes','Anotaciones')):
            control = Action(t, icon=symbol, callback=lambda i=index:self.navigate(i), size=M['control']+M['space_m'])
            control.setCheckable(True); control.setChecked(index==0)
            control.setToolTip(label); control.setAccessibleName(label)
            rail_layout.addWidget(control); self.nav_buttons.append(control)
        rail_layout.addStretch()
        self.theme_button = Action(t, icon='sun', callback=self.toggle_mode, size=M['control']+M['space_m'])
        self.theme_button.setToolTip('Cambiar entre claro y oscuro');self.theme_button.setAccessibleName('Cambiar modo claro u oscuro')
        rail_layout.addWidget(self.theme_button)
        shell.addWidget(rail)
        main = QVBoxLayout(); main.setContentsMargins(0,0,0,0);main.setSpacing(M['space_l']);shell.addLayout(main,1)
        header = QHBoxLayout();header.setContentsMargins(M['space_s'],M['space_l'],M['space_s'],0);header.setSpacing(M['space_m'])
        title_block=QVBoxLayout();title_block.setSpacing(0)
        title_block.addWidget(Text(t,'Wysun PDF','small','muted',500))
        self.title=Text(t,'Tu espacio de lectura','heading','text',500);title_block.addWidget(self.title)
        header.addLayout(title_block,1)
        self.open_button=Action(t,'Abrir',icon='folder-open',callback=self.choose,kind='tonal')
        self.save_button=Action(t,'Guardar',icon='saved',callback=self.save,kind='filled')
        self.copy_button=Action(t,icon='more',callback=lambda:self.save(copy=True))
        self.copy_button.setToolTip('Guardar una copia · Ctrl Shift S');self.copy_button.setAccessibleName('Guardar una copia')
        header.addWidget(self.open_button);header.addWidget(self.save_button);header.addWidget(self.copy_button)
        main.addLayout(header)
        self.split = QSplitter();self.split.setChildrenCollapsible(False);self.split.setHandleWidth(M['space_l'])
        self.sidebar_panel=Panel(t,'surface_low','radius_l')
        side=QVBoxLayout(self.sidebar_panel);side.setContentsMargins(M['space_l'],M['space_xl'],M['space_l'],M['space_l']);side.setSpacing(M['space_s'])
        self.side_title=Text(t,'Documento','heading','text',500);side.addWidget(self.side_title)
        self.side_meta=Text(t,'Todo empieza con una página','small','muted');side.addWidget(self.side_meta)
        side.addSpacing(M['space_m'])
        self.tabs=QStackedWidget();side.addWidget(self.tabs,1)
        document_panel=QWidget();document_layout=QVBoxLayout(document_panel);document_layout.setContentsMargins(0,0,0,0);document_layout.setSpacing(M['space_m'])
        sections=QHBoxLayout();sections.setSpacing(M['space_xs'])
        self.pages_tab=Action(t,'Páginas',callback=lambda:self.document_section(0));self.pages_tab.setCheckable(True);self.pages_tab.setChecked(True)
        self.outline_tab=Action(t,'Índice',callback=lambda:self.document_section(1));self.outline_tab.setCheckable(True)
        sections.addWidget(self.pages_tab);sections.addWidget(self.outline_tab);document_layout.addLayout(sections)
        self.document_stack=QStackedWidget();document_layout.addWidget(self.document_stack,1)
        self.thumbnails,self.page_model=thumbnail_view(t);self.document_stack.addWidget(self.thumbnails)
        self.thumbnails.clicked.connect(lambda index:self.go(index.row()))
        self.thumbnails.activated.connect(lambda index:self.go(index.row()))
        self.thumbnails.verticalScrollBar().valueChanged.connect(self.load_thumbnails)
        self.outline=reader_list(t);self.outline.itemClicked.connect(self.outline_go);self.outline.itemActivated.connect(self.outline_go)
        self.document_stack.addWidget(self.outline)
        self.tabs.addWidget(document_panel)
        search_panel=QWidget();search_layout=QVBoxLayout(search_panel);search_layout.setContentsMargins(0,0,0,0);search_layout.setSpacing(M['space_m'])
        self.search=QLineEdit();self.search.setPlaceholderText('Buscar una idea…');self.search.setAccessibleName('Buscar en el documento')
        self.search.returnPressed.connect(self.find);self.search.textChanged.connect(self.cancel_search)
        search_layout.addWidget(self.search)
        search_layout.addWidget(Action(t,'Buscar',icon='search',callback=self.find,kind='tonal'))
        self.search_status=Text(t,'Enter para buscar','small','muted');search_layout.addWidget(self.search_status)
        self.results=reader_list(t);self.results.itemClicked.connect(self.search_go);self.results.itemActivated.connect(self.search_go)
        search_layout.addWidget(self.results,1);self.tabs.addWidget(search_panel)
        notes_panel=QWidget();notes_layout=QVBoxLayout(notes_panel);notes_layout.setContentsMargins(0,0,0,0);notes_layout.setSpacing(M['space_m'])
        self.annotations=reader_list(t);notes_layout.addWidget(self.annotations,1)
        self.delete_button=Action(t,'Eliminar',icon='trash',callback=self.delete_annotation,kind='tonal');notes_layout.addWidget(self.delete_button)
        self.annotations.currentRowChanged.connect(self.controls)
        self.annotations.itemActivated.connect(self.edit_note)
        self.tabs.addWidget(notes_panel)
        self.split.addWidget(self.sidebar_panel)
        self.stage=Panel(t,'surface','radius_xl');stage_layout=QVBoxLayout(self.stage)
        stage_layout.setContentsMargins(M['space_l'],M['space_l'],M['space_l'],M['space_m']);stage_layout.setSpacing(M['space_l'])
        tools_row=QHBoxLayout();tools_row.setSpacing(M['space_s'])
        self.sidebar_button=Action(t,icon='sidebar',callback=self.toggle_sidebar)
        self.sidebar_button.setToolTip('Mostrar u ocultar navegación · F9');tools_row.addWidget(self.sidebar_button)
        tools_row.addStretch()
        tool_group=Panel(t,'surface_high','radius_xl');tool_layout=QHBoxLayout(tool_group)
        tool_layout.setContentsMargins(M['space_xs'],M['space_xs'],M['space_xs'],M['space_xs']);tool_layout.setSpacing(M['space_xs'])
        self.select_button=Action(t,icon='select',callback=self.select_mode);self.select_button.setCheckable(True);self.select_button.setChecked(True);self.select_button.setToolTip('Seleccionar texto')
        self.highlight=Action(t,icon='highlight',callback=lambda:self.mark('highlight'));self.highlight.setCheckable(True);self.highlight.setToolTip('Resaltar · Ctrl H')
        self.underline=Action(t,icon='underline',callback=lambda:self.mark('underline'));self.underline.setCheckable(True);self.underline.setToolTip('Subrayar · Ctrl U')
        self.note=Action(t,icon='notes',callback=self.note_mode);self.note.setCheckable(True);self.note.setToolTip('Añadir nota')
        self.ink_button=Action(t,icon='palette',callback=self.choose_ink);self.ink_button.setToolTip('Color de anotación')
        for action in (self.select_button,self.highlight,self.underline,self.note,self.ink_button):tool_layout.addWidget(action)
        tools_row.addWidget(tool_group);tools_row.addStretch()
        self.zoom=QComboBox();self.zoom.addItems(['Ajustar','75%','100%','125%','150%','200%']);self.zoom.setAccessibleName('Zoom')
        self.zoom.currentIndexChanged.connect(self.schedule_render);tools_row.addWidget(self.zoom)
        stage_layout.addLayout(tools_row)
        self.scroll=QScrollArea();self.scroll.setFrameShape(QFrame.NoFrame);self.scroll.setAlignment(Qt.AlignHCenter|Qt.AlignTop)
        self.scroll.viewport().setAutoFillBackground(False)
        self.canvas=PageCanvas(t);self.canvas.hide();self.scroll.setWidget(self.canvas)
        self.canvas.selected.connect(self.controls);self.canvas.noteRequested.connect(self.add_note)
        self.canvas.selectionFinished.connect(self.finish_selection)
        stage_layout.addWidget(self.scroll,1)
        bottom=QHBoxLayout();bottom.addStretch()
        navigation=Panel(t,'surface_high','radius_xl');navigation_layout=QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(M['space_xs'],M['space_xs'],M['space_xs'],M['space_xs']);navigation_layout.setSpacing(M['space_s'])
        self.previous=Action(t,icon='back',callback=lambda:self.go(self.page-1));self.previous.setToolTip('Página anterior · Alt ←')
        self.page_input=QSpinBox();self.page_input.setRange(1,1);self.page_input.setButtonSymbols(QSpinBox.NoButtons)
        self.page_input.setKeyboardTracking(False);self.page_input.setAccessibleName('Número de página');self.page_input.setFixedWidth(M['control']+M['space_m'])
        self.page_input.valueChanged.connect(lambda n:self.go(n-1))
        self.page_count=Text(t,'/ —','small','muted');self.page_count.setFixedWidth(M['control'])
        self.next=Action(t,icon='forward',callback=lambda:self.go(self.page+1));self.next.setToolTip('Página siguiente · Alt →')
        for widget in (self.previous,self.page_input,self.page_count,self.next):navigation_layout.addWidget(widget)
        bottom.addWidget(navigation);bottom.addStretch();stage_layout.addLayout(bottom)
        self.split.addWidget(self.stage);self.split.setSizes([M['sidebar'],900]);main.addWidget(self.split,1)
        self.empty=Panel(t,'surface','radius_xl');empty_layout=QVBoxLayout(self.empty)
        empty_layout.setContentsMargins(M['space_xxl']*2,M['space_xxl'],M['space_xxl']*2,M['space_xxl']);empty_layout.addStretch()
        emblem=Emblem(t,size=M['rail']);emblem.setFocusPolicy(Qt.NoFocus)
        empty_layout.addWidget(emblem,0,Qt.AlignHCenter);empty_layout.addSpacing(M['space_xl'])
        intro=Text(t,'Menos ruido. Más lectura.','title','text',500);intro.setFixedHeight(M['font_title']+M['space_xl']);empty_layout.addWidget(intro)
        empty_layout.addWidget(Text(t,'Abre un documento, marca lo importante y guarda tus ideas.','body','muted'))
        empty_layout.addSpacing(M['space_xl'])
        empty_layout.addWidget(Action(t,'Abrir un PDF',icon='plus',callback=self.choose,kind='filled'),0,Qt.AlignLeft)
        empty_layout.addStretch();empty_layout.addWidget(Text(t,'En tu equipo. Sin cuentas, sin subir archivos.','small','muted'))
        main.addWidget(self.empty,1);self.split.hide()
        self.status=Text(t,'Local · Tus documentos se quedan contigo','small','muted');main.addWidget(self.status)
        self.resize_timer=QTimer(self);self.resize_timer.setSingleShot(True);self.resize_timer.setInterval(150);self.resize_timer.timeout.connect(self.render)
        for keys,action in [('Ctrl+O',self.choose),('Ctrl+S',self.save),('Ctrl+Shift+S',lambda:self.save(copy=True)),
                            ('Ctrl+F',self.focus_search),('Ctrl+C',self.copy_text),('Alt+Right',lambda:self.go(self.page+1)),
                            ('Alt+Left',lambda:self.go(self.page-1)),('F9',self.toggle_sidebar),
                            ('Ctrl+H',lambda:self.mark('highlight')),('Ctrl+U',lambda:self.mark('underline'))]:
            QShortcut(QKeySequence(keys),self).activated.connect(action)
        t.changed.connect(self.theme_changed);self.theme_changed()
        self.setAcceptDrops(True);self.controls()
        if path:QTimer.singleShot(0,lambda:self.open_path(path))

    def document_section(self, index):
        self.document_stack.setCurrentIndex(index)
        self.pages_tab.setChecked(index==0);self.outline_tab.setChecked(index==1)
        if index==0:self.load_thumbnails()

    def load_thumbnails(self, *_):
        if not self.path or self.busy or self.thumbnail_pending or not self.thumbnails.isVisible():
            return
        first=self.thumbnails.indexAt(QPoint(1,1)).row()
        first=max(0,first)
        count=max(2,self.thumbnails.viewport().height()//(M['rail']*3)+2)
        missing=next((p for p in range(first,min(self.pages,first+count)) if p not in self.page_model.images),None)
        if missing is None:return
        self.thumbnail_pending=True;generation=self.generation
        def loaded(reply):
            self.thumbnail_pending=False
            if generation!=self.generation:return
            if 'result' in reply:
                self.page_model.put(missing,QImage.fromData(base64.b64decode(reply['result']['png'])))
                QTimer.singleShot(0,self.load_thumbnails)
        self.worker.request('thumbnail',loaded,page=missing)

    def toggle_mode(self):
        self.reader_theme.set_mode('light' if self.reader_theme.mode=='dark' else 'dark',persist=True)
        self.theme_button.symbol='moon' if self.reader_theme.mode=='light' else 'sun'
        self.theme_button.update()

    def navigate(self, index):
        self.sidebar_panel.show();self.tabs.setCurrentIndex(index)
        self.side_title.setText(('Documento','Buscar','Anotaciones')[index])
        self.side_meta.setText(f'{self.pages} páginas' if index!=2 else f'Página {self.page+1}')
        for i,control in enumerate(self.nav_buttons):control.setChecked(i==index)
        if index==1:self.search.setFocus()
        self.load_thumbnails();self.schedule_render()

    def select_mode(self):
        self.pending_markup=None;self.canvas.note_mode=False
        self.note.setChecked(False);self.highlight.setChecked(False);self.underline.setChecked(False);self.select_button.setChecked(True)
        self.canvas.setCursor(Qt.IBeamCursor)
        self.status.setText('Selecciona texto · Ctrl C para copiar')

    def finish_selection(self):
        if self.pending_markup and self.canvas.selection:self.mark(self.pending_markup)

    def theme_changed(self):
        self.theme_button.symbol='moon' if self.reader_theme.mode=='light' else 'sun'
        self.theme_button.update()
        self.setPalette(self.reader_theme.palette())
        self.setStyleSheet(self.reader_theme.inputs())
        self.canvas.update()
        self.update()

    def controls(self, *_):
        ready = bool(self.path) and not self.busy
        displayed = ready and self.displayed_page == self.page
        self.open_button.setEnabled(not self.busy)
        self.save_button.setEnabled(ready and self.dirty)
        self.copy_button.setEnabled(ready)
        self.page_input.setEnabled(ready); self.zoom.setEnabled(ready)
        self.previous.setEnabled(ready and self.page > 0)
        self.next.setEnabled(ready and self.page + 1 < self.pages)
        selection = displayed and self.editable
        self.highlight.setEnabled(selection); self.underline.setEnabled(selection)
        self.note.setEnabled(displayed and self.editable)
        self.canvas.setEnabled(displayed)
        self.delete_button.setEnabled(displayed and self.editable and self.annotations.currentItem() is not None)
        self.title.setText((Path(self.path).name + (' •' if self.dirty else '')) if self.path else 'Un espacio para leer')
        self.setWindowTitle((Path(self.path).name + (' *' if self.dirty else '') + ' — Wysun PDF') if self.path else 'Wysun PDF')

    def error(self, reply):
        if 'error' not in reply:
            return False
        self.status.setText(reply['error'])
        QMessageBox.warning(self, 'Wysun PDF', reply['error'])
        return True

    def worker_failed(self, message):
        self.busy = True
        self.controls()
        self.status.setText(message)

    def confirm_discard(self):
        return not self.dirty or QMessageBox.question(self, 'Cambios sin guardar',
            'Hay anotaciones sin guardar. ¿Descartarlas?', QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Cancel) == QMessageBox.Discard

    def choose(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir documento', '', 'PDF (*.pdf)')
        if path:
            self.open_path(path)

    def open_path(self, path, password='', confirmed=False):
        if self.busy or (not confirmed and not self.confirm_discard()):
            return
        self.busy = True; self.search_generation += 1
        self.controls(); self.status.setText('Abriendo documento…')
        def opened(reply):
            self.busy = False
            if self.error(reply):
                self.controls(); return
            result = reply['result']
            if result.get('password_required'):
                secret, ok = QInputDialog.getText(self, 'PDF protegido', 'Contraseña:', QLineEdit.Password)
                if ok:
                    self.open_path(path, secret, True)
                self.controls(); return
            self.generation += 1
            self.path, self.pages = result['path'], result['pages']
            self.page_model.reset(self.pages)
            self.thumbnails.setCurrentIndex(self.page_model.index(0,0))
            self.dirty, self.editable = False, result['editable']
            self.page = 0; self.displayed_page = None
            self.outline.clear(); self.results.clear(); self.annotations.clear(); self.search.clear()
            self.page_input.setRange(1, self.pages); self.page_input.setValue(1)
            self.page_count.setText(f'/ {self.pages}')
            self.side_meta.setText(f'{self.pages} páginas')
            for level, title, page in result['outline']:
                item = QListWidgetItem('  ' * min(level - 1, 6) + title)
                item.setData(Qt.UserRole, page - 1); self.outline.addItem(item)
            if not self.outline.count():
                item = QListWidgetItem('Este PDF no tiene índice.\nUsa el número de página o la búsqueda.')
                item.setFlags(Qt.NoItemFlags); self.outline.addItem(item)
            self.empty.hide(); self.split.show(); self.canvas.show()
            self.status.setText('Selecciona texto para resaltar o subrayar · Ctrl S para guardar' if self.editable else 'Documento de solo lectura')
            self.controls(); self.render(); self.load_thumbnails()
        self.worker.request('open', opened, path=str(path), password=password)

    def go(self, page):
        if not self.path or self.busy or not 0 <= page < self.pages:
            return
        self.page = page; self.displayed_page = None
        self.thumbnails.setCurrentIndex(self.page_model.index(page,0))
        self.thumbnails.scrollTo(self.page_model.index(page,0))
        if self.tabs.currentIndex()==2:self.side_meta.setText(f'Página {page+1}')
        self.page_input.blockSignals(True); self.page_input.setValue(page + 1); self.page_input.blockSignals(False)
        self.scroll.verticalScrollBar().setValue(0)
        self.controls(); self.render()

    def outline_go(self, item):
        page = item.data(Qt.UserRole)
        if page is not None:
            self.go(page)

    def schedule_render(self, *_):
        if hasattr(self, 'resize_timer'):
            self.resize_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event); self.schedule_render()

    def render(self):
        if not self.path or self.busy:
            return
        width = max(200, self.scroll.viewport().width() - M['space_xl'] * 2)
        if self.zoom.currentIndex():
            width = round(800 * int(self.zoom.currentText().rstrip('%')) / 100)
        self.render_serial += 1
        serial, generation, page = self.render_serial, self.generation, self.page
        def rendered(reply):
            if serial != self.render_serial or generation != self.generation or page != self.page:
                return
            if self.error(reply):
                return
            self.canvas.set_page(reply['result'], width)
            self.displayed_page = page
            self.canvas.hits = self.search_hits.get(page, [])
            self.canvas.update()
            self.annotations.clear()
            for a in reply['result']['annotations']:
                item = QListWidgetItem(a['type'] + ' · ' + a['text'])
                item.setData(Qt.UserRole, a['xref']); item.setData(Qt.UserRole+1,a); self.annotations.addItem(item)
            self.controls();self.load_thumbnails()
        self.worker.request('render', rendered, page=page, width=round(width * self.devicePixelRatioF()))

    def mark(self, kind):
        if not self.highlight.isEnabled():
            return
        self.pending_markup=kind
        self.highlight.setChecked(kind=='highlight');self.underline.setChecked(kind=='underline')
        self.select_button.setChecked(False);self.note.setChecked(False);self.canvas.note_mode=False
        if not self.canvas.selection:
            self.status.setText('Arrastra sobre el texto para '+('resaltar' if kind=='highlight' else 'subrayar'))
            return
        self.edit('annotate', kind=kind, rects=[self.canvas.words[i][:4] for i in self.canvas.selection],
                  text=self.canvas.text(), colour=self.annotation_colour())

    def choose_ink(self):
        chosen = QColorDialog.getColor(self.ink or self.reader_theme.color('primary'), self, 'Color de las anotaciones')
        if chosen.isValid():
            self.ink = chosen

    def annotation_colour(self):
        c = self.ink or self.reader_theme.color('primary')
        return [c.redF(), c.greenF(), c.blueF()]

    def note_mode(self):
        self.pending_markup=None
        self.highlight.setChecked(False);self.underline.setChecked(False);self.select_button.setChecked(not self.note.isChecked())
        self.canvas.note_mode = self.note.isChecked()
        self.canvas.setCursor(Qt.CrossCursor if self.canvas.note_mode else Qt.IBeamCursor)
        self.status.setText('Haz clic en la página para colocar una nota.' if self.canvas.note_mode else 'Arrastra sobre el texto para seleccionarlo.')

    def add_note(self, point):
        if not self.note.isEnabled():
            return
        dialog=NoteDialog(self.reader_theme,self)
        if dialog.exec():
            self.edit('annotate', kind='note', point=[point.x(), point.y()], text=dialog.editor.toPlainText(),
                      colour=self.annotation_colour())
        self.note.setChecked(False); self.note_mode()

    def edit(self, operation, **args):
        self.busy = True; self.controls()
        def edited(reply):
            self.busy = False
            if not self.error(reply):
                self.dirty = True
                self.page_model.images.pop(self.page,None)
                self.status.setText('Anotaciones sin guardar · Ctrl S')
                self.render()
            self.controls()
        self.worker.request(operation, edited, page=self.page, **args)

    def edit_note(self, item):
        if self.busy or not self.editable or self.displayed_page!=self.page:return
        annotation=item.data(Qt.UserRole+1)
        dialog=NoteDialog(self.reader_theme,self,text=annotation['text'],title='Editar anotación')
        if dialog.exec():
            self.edit('update_note',xref=annotation['xref'],text=dialog.editor.toPlainText())

    def delete_annotation(self):
        item = self.annotations.currentItem()
        if item and self.delete_button.isEnabled():
            self.edit('delete', xref=item.data(Qt.UserRole))

    def save(self, copy=False):
        if not self.path or self.busy:
            return
        target = self.path
        expected = None
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
                s = Path(target).stat(); expected = [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]
        self.busy = True; self.controls(); self.status.setText('Guardando PDF…')
        def saved(reply):
            self.busy = False
            if not self.error(reply):
                self.path = reply['result']['path']; self.dirty = False
                self.status.setText('PDF guardado · Anotaciones compatibles con otros lectores')
            self.controls()
        self.worker.request('save', saved, path=target, expected=expected)

    def focus_search(self):
        self.navigate(1); self.search.selectAll()

    def cancel_search(self):
        self.search_generation += 1
        self.search_hits.clear()
        self.results.clear()
        self.canvas.hits = []
        self.canvas.update()
        self.search_status.setText('Enter para buscar')

    def find(self):
        if not self.path or self.busy:
            return
        text = self.search.text().strip()
        self.search_generation += 1
        token, document = self.search_generation, self.generation
        self.results.clear()
        if not text:
            self.canvas.hits = []; self.canvas.update(); return
        def search_page(page):
            if token != self.search_generation or document != self.generation or self.busy:
                return
            def found(reply):
                if token != self.search_generation or document != self.generation:
                    return
                if self.error(reply):
                    return
                hits = reply['result']['hits']
                self.search_hits[page] = hits
                if self.displayed_page == page:
                    self.canvas.hits = hits; self.canvas.update()
                if hits:
                    item = QListWidgetItem(f'Página {page + 1} · {len(hits)} coincidencias')
                    item.setData(Qt.UserRole, (page, hits)); self.results.addItem(item)
                self.search_status.setText(f'{self.results.count()} páginas encontradas · {page + 1}/{self.pages}')
                if page + 1 < self.pages:
                    QTimer.singleShot(0, lambda: search_page(page + 1))
            self.worker.request('search', found, page=page, text=text)
        search_page(0)

    def search_go(self, item):
        if self.busy:
            return
        page, hits = item.data(Qt.UserRole)
        self.go(page)
        serial = self.render_serial
        # Queue after the page render, using a tiny search response as a barrier.
        def show(reply):
            if serial == self.render_serial and not self.busy and 'result' in reply:
                self.canvas.hits = hits; self.canvas.update()
                if hits:
                    self.scroll.ensureVisible(0, round(hits[0][1] * self.canvas.height() / self.canvas.page_height))
        self.worker.request('search', show, page=page, text=self.search.text())

    def copy_text(self):
        if self.search.hasFocus():
            self.search.copy()
        elif self.canvas.selection:
            QApplication.clipboard().setText(self.canvas.text())

    def toggle_sidebar(self):
        self.sidebar_panel.setVisible(not self.sidebar_panel.isVisible()); self.schedule_render()

    def dragEnterEvent(self, event):
        if not self.busy and any(u.isLocalFile() and u.toLocalFile().lower().endswith('.pdf') for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'):
                self.open_path(url.toLocalFile()); event.acceptProposedAction(); break

    def closeEvent(self, event):
        if self.busy and self.worker.process.state() != self.worker.process.NotRunning:
            self.status.setText('Espera a que termine la operación antes de cerrar.'); event.ignore(); return
        if not self.confirm_discard():
            event.ignore(); return
        self.worker.stop(); event.accept()
