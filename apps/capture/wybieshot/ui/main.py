"""Offline native capture, editable document, library and comparison workflow."""
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from collections import OrderedDict
import os
from PySide6.QtCore import Qt,QRect,QPoint,QTimer,QSize,Signal,QThread
from PySide6.QtGui import QKeySequence,QShortcut,QColor,QPixmap,QIcon,QPainter,QFont
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QStackedWidget,QScrollArea,QListWidget,QListWidgetItem,QAbstractItemView,QLineEdit,QComboBox,QSpinBox,QCheckBox,QDialog,QDialogButtonBox,QFileDialog,QInputDialog,QColorDialog,QSlider,QLabel,QStyledItemDelegate,QStyle)
from wybieshot.schema import Rect,Layer,CaptureRequest
from wybieshot.document import Document
from wybieshot.storage import Storage
from wybieshot.capture import CaptureEngine
from .components import button,tool_button,label,apply_theme,apply_material,apply_style,color as token_color,SpinBox,localize_buttons
from .canvas import Canvas
from .quick import QuickBar
from .selection import SelectionOverlay,SelectionGroup
from .floating import FloatingSelection
from wybieshot.instance import CaptureLease

TOOLS=[('select','Seleccionar','V'),('arrow','Flecha','A'),('rectangle','Rectángulo','R'),('ellipse','Elipse','E'),('pen','Lápiz','P'),('highlight','Resaltar','H'),('text','Texto','T'),('number','Paso numerado','N'),('mask','Máscara opaca','M'),('blur','Desenfoque visual','B'),('crop','Recortar','C')]


class CaptureDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(320,104)
    def paint(self,p,option,index):
        p.save();p.setRenderHint(QPainter.Antialiasing)
        r=option.rect.adjusted(1,2,-1,-2);selected=bool(option.state&QStyle.State_Selected);hover=bool(option.state&QStyle.State_MouseOver)
        p.setPen(Qt.NoPen);p.setBrush(token_color('selection' if selected else 'tile_hover' if hover else 'tile'));p.drawRoundedRect(r,12,12)
        thumb=QRect(r.left()+12,r.top()+10,128,80);p.setBrush(token_color('inset'));p.drawRoundedRect(thumb,6,6)
        preview=index.data(Qt.DecorationRole)
        if preview:preview.paint(p,thumb,Qt.AlignCenter)
        entry=index.data(Qt.UserRole+1) or {};left=thumb.right()+16;available=max(1,r.right()-left-16)
        font=option.font;font.setPixelSize(15);font.setWeight(QFont.Medium);p.setFont(font);p.setPen(token_color('text'))
        p.drawText(QRect(left,r.top()+21,available,26),Qt.AlignVCenter,p.fontMetrics().elidedText(entry.get('title','Captura'),Qt.ElideRight,available))
        font.setPixelSize(12);font.setWeight(QFont.Normal);p.setFont(font);p.setPen(token_color('muted'))
        secondary=f"{entry.get('width',0)} × {entry.get('height',0)} px · "+datetime.fromtimestamp(entry.get('updated',0)).strftime('%d %b · %H:%M')
        p.drawText(QRect(left,r.top()+51,available,24),Qt.AlignVCenter,p.fontMetrics().elidedText(secondary,Qt.ElideRight,available))
        if option.state&QStyle.State_HasFocus:p.setPen(token_color('focus'));p.setBrush(Qt.NoBrush);p.drawRoundedRect(r.adjusted(1,1,-1,-1),11,11)
        p.restore()


class Work(QThread):
    ready=Signal(object);failed=Signal(str)
    def __init__(self,fn,parent):super().__init__(parent);self.fn=fn
    def run(self):
        try:self.ready.emit(self.fn())
        except Exception as exc:self.failed.emit(str(exc))


def selection_parts(frozen):
    """Native per-output crops; one overlay per monitor at its real scale."""
    from loomrec.portal import is_wayland
    g=frozen.geometry;fallback=QRect(g.x,g.y,g.width,g.height)
    if not is_wayland():return [(frozen.image,None,QPoint(0,0),fallback)]
    screens=[screen for screen in QApplication.screens() if not screen.geometry().isEmpty()]
    if not screens:return [(frozen.image,None,QPoint(0,0),fallback)]
    if len(screens)==1:return [(frozen.image,screens[0],QPoint(0,0),screens[0].geometry())]
    bounds=QRect()
    for screen in screens:bounds=bounds.united(screen.geometry())
    if bounds.width()<=0 or bounds.height()<=0:return [(frozen.image,None,QPoint(0,0),fallback)]
    sx=frozen.image.width()/bounds.width();sy=frozen.image.height()/bounds.height()
    ratios={round(screen.devicePixelRatio(),3) for screen in screens}
    if len(ratios)>1 or abs(sx-sy)/max(sx,sy)>0.02:
        # Mixed scales or an image that does not map linearly: do not invent a crop.
        return [(frozen.image,None,QPoint(0,0),fallback)]
    parts=[]
    for screen in screens:
        geometry=screen.geometry()
        crop=QRect(round((geometry.x()-bounds.x())*sx),round((geometry.y()-bounds.y())*sy),
                   round(geometry.width()*sx),round(geometry.height()*sy)).intersected(frozen.image.rect())
        if crop.isEmpty():continue
        parts.append((frozen.image.copy(crop),screen,QPoint(crop.x(),crop.y()),geometry))
    return parts or [(frozen.image,None,QPoint(0,0),fallback)]


class Window(QMainWindow):
    capture_settle_ms=180  # Let the compositor unmap our own windows first.
    def __init__(self,storage=None,engine=None):
        super().__init__();self.storage=storage or Storage();self.engine=engine or CaptureEngine()
        self._closing=False;self.thumbnail_cache=OrderedDict();self.thumbnail_pending=False;self.library_generation=0
        os.environ['LOOMREC_REDUCED_MOTION']='1' if self.storage.settings.get('reduced_motion',False) else '0'
        self._capture_lease=None;self._capture_feedback=None;self._capture_job=None
        self._clipboard_hidden=False
        self.capture_mode='region';self.monitor=0;self.document=None;self.overlay=None;self.frozen=None;self.jobs=[];self.busy=False;self.countdown=0
        self.setWindowTitle('Wysun Screenshot');self.resize(1120,760);self.setMinimumSize(520,430)
        self.stack=QStackedWidget();self.setCentralWidget(self.stack)
        self.make_library();self.make_editor();self.quick=QuickBar(self)
        self.thumbnail_timer=QTimer(self);self.thumbnail_timer.setSingleShot(True);self.thumbnail_timer.timeout.connect(self.load_visible_thumbnail)
        self.items.verticalScrollBar().valueChanged.connect(lambda _:self.thumbnail_timer.start(40))
        self.save_timer=QTimer(self);self.save_timer.setSingleShot(True);self.save_timer.setInterval(250);self.save_timer.timeout.connect(self.save_document)
        self.capture_timer=QTimer(self);self.capture_timer.setSingleShot(True);self.capture_timer.timeout.connect(self.capture_tick)
        self.shortcuts=[]
        for keys,fn in [('Ctrl+Z',self.undo),('Ctrl+Shift+Z',self.redo),('Ctrl+Y',self.redo),('Ctrl+S',self.export),('Ctrl+Shift+C',self.copy),('Ctrl+N',self.show_quick),('Escape',self.escape)]:self.shortcut(keys,fn)
        for tool,name,key in TOOLS:
            shortcut=QShortcut(QKeySequence(key),self.canvas);shortcut.setContext(Qt.WidgetWithChildrenShortcut);shortcut.activated.connect(lambda t=tool:self.choose_tool(t));self.shortcuts.append(shortcut)
        self.refresh_library();self.sync()

    def shortcut(self,keys,fn):
        shortcut=QShortcut(QKeySequence(keys),self);shortcut.activated.connect(fn);self.shortcuts.append(shortcut)

    def guard(self,fn):
        try:return fn()
        except Exception as exc:self.notice(str(exc),True)

    def notice(self,text,error=False):
        apply_style(self.statusBar(),'color:@danger;' if error else 'color:@muted;')
        self.statusBar().showMessage(text)
        self.statusBar().setAccessibleName(text)

    def make_library(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(28,24,28,24);layout.setSpacing(16)
        top=QHBoxLayout();top.addWidget(label('Wysun Screenshot','title'));top.addStretch();top.addWidget(button('Ajustes',self.show_settings,'settings'));layout.addLayout(top)
        hint=label('Captura, explica y continúa. Tus imágenes se quedan en este equipo.','subtitle');hint.setWordWrap(True);layout.addWidget(hint)
        row=QHBoxLayout();row.addWidget(button('Nueva captura',self.show_quick,'region',primary=True));row.addWidget(button('Abrir imagen',self.import_image,'folder'));row.addStretch();layout.addLayout(row)
        self.search=QLineEdit();self.search.setPlaceholderText('Buscar capturas…');self.search.setAccessibleName('Buscar capturas');self.search.textChanged.connect(self.filter_library);layout.addWidget(self.search)
        self.items=QListWidget();self.items.setItemDelegate(CaptureDelegate(self.items));self.items.setSpacing(4);self.items.setUniformItemSizes(True);self.items.setMouseTracking(True);self.items.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.items.setSelectionMode(QAbstractItemView.ExtendedSelection);self.items.setAccessibleName('Capturas guardadas. Selecciona dos para comparar o varias para componer.');self.items.itemActivated.connect(lambda _:self.open_selected());self.items.itemSelectionChanged.connect(self.library_state);layout.addWidget(self.items,1)
        self.empty=label('Tu próxima idea empieza con una captura.','section');self.empty.setAlignment(Qt.AlignCenter);layout.addWidget(self.empty)
        actions=QHBoxLayout();self.open_button=button('Abrir',self.open_selected,'folder');self.compose_button=button('Componer',self.compose,'compose');self.compare_button=button('Antes / después',self.compare,'compare')
        for b in (self.open_button,self.compose_button,self.compare_button):actions.addWidget(b)
        actions.addStretch();layout.addLayout(actions);self.library_page=page;self.stack.addWidget(page)

    def make_editor(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(16,12,16,12);layout.setSpacing(10)
        header=QHBoxLayout();header.addWidget(button('Biblioteca',self.show_library,'back'));self.title=QLineEdit();self.title.setAccessibleName('Título de captura');self.title.editingFinished.connect(self.rename);header.addWidget(self.title,1)
        self.copy_button=button('Copiar',self.copy,'copy');self.export_button=button('Guardar',self.export,'save',primary=True);header.addWidget(self.copy_button);header.addWidget(self.export_button);layout.addLayout(header)
        toolbar=QWidget();toolbar.setObjectName('shotTools');tools=QHBoxLayout(toolbar);tools.setContentsMargins(4,2,4,2);tools.setSpacing(2);self.tool_buttons={}
        for key,name,shortcut in TOOLS:
            b=tool_button(name,key,shortcut,lambda checked=False,t=key:self.choose_tool(t));tools.addWidget(b);self.tool_buttons[key]=b
        tools.addStretch();self.undo_button=button('',self.undo,'undo',compact=True);self.undo_button.setAccessibleName('Deshacer');self.undo_button.setToolTip('Deshacer · Ctrl+Z')
        self.redo_button=button('',self.redo,'redo',compact=True);self.redo_button.setAccessibleName('Rehacer');self.redo_button.setToolTip('Rehacer · Ctrl+Shift+Z')
        tools.addWidget(self.undo_button);tools.addWidget(self.redo_button)
        scroll=QScrollArea();scroll.setWidget(toolbar);scroll.setWidgetResizable(True);scroll.setFixedHeight(64);scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);layout.addWidget(scroll)
        properties=QHBoxLayout();self.color_button=button('Color',self.change_color);properties.addWidget(self.color_button)
        self.width_spin=SpinBox();self.width_spin.setRange(1,64);self.width_spin.setValue(3);self.width_spin.setAccessibleName('Grosor');self.width_spin.valueChanged.connect(self.apply_properties);self.width_label=label('Grosor');properties.addWidget(self.width_label);properties.addWidget(self.width_spin)
        self.font_spin=SpinBox();self.font_spin.setRange(6,256);self.font_spin.setValue(24);self.font_spin.setAccessibleName('Tamaño de texto');self.font_spin.valueChanged.connect(self.apply_properties);self.font_label=label('Tamaño texto');properties.addWidget(self.font_label);properties.addWidget(self.font_spin)
        self.width_spin.setFixedWidth(76);self.font_spin.setFixedWidth(76)
        self.edit_button=button('Editar',self.edit_selected);properties.addWidget(self.edit_button);properties.addStretch();layout.addLayout(properties)
        self.canvas=Canvas();self.canvas.changed.connect(self.changed);self.canvas.selected.connect(self.selection_changed);self.canvas.edit_requested.connect(self.edit_layer);layout.addWidget(self.canvas,1)
        footer=QHBoxLayout();self.doc_status=label('','subtitle');footer.addWidget(self.doc_status,1);self.reset_crop=button('Restaurar recorte',lambda:self.guard(self.uncrop));footer.addWidget(self.reset_crop);layout.addLayout(footer)
        self.editor_page=page;self.stack.addWidget(page);self.choose_tool('select')

    def choose_tool(self,tool):
        self.canvas.set_tool(tool)
        for key,b in self.tool_buttons.items():b.setChecked(key==tool)
        messages={'blur':'Desenfoque visual. Para ocultar información utiliza Máscara opaca.','crop':'Arrastra el nuevo recorte. Puedes restaurarlo sin perder el original.','select':'Selecciona un objeto. Flechas para mover; Enter para editar; Suprimir para eliminar.','number':'Haz clic para añadir el siguiente paso. Enter permite cambiar su número.'}
        self.sync_properties()
        self.notice(messages.get(tool,'Arrastra sobre la imagen para anotar.' if tool not in ('text',) else 'Haz clic y escribe tu texto.'))

    def set_document(self,doc):
        if self.document and not self.save_document():return False
        self.document=doc;self.canvas.set_document(doc);self.title.setText(doc.title);self.stack.setCurrentWidget(self.editor_page)
        self.show();self.raise_();self.activateWindow();self.canvas.setFocus();self.changed()

    def changed(self):
        self.save_timer.start();self.canvas.update();self.sync()
        self.doc_status.setText(self.doc_status.text().replace('Guardado automático','Guardando…'))

    def sync(self):
        doc=self.document
        self.undo_button.setEnabled(bool(doc and doc.can_undo));self.redo_button.setEnabled(bool(doc and doc.can_redo));self.copy_button.setEnabled(bool(doc));self.export_button.setEnabled(bool(doc));self.reset_crop.setVisible(bool(doc and doc.crop));self.sync_properties()
        if doc:
            r=doc.crop;w,h=(r.width,r.height) if r else (doc.size.width(),doc.size.height())
            self.doc_status.setText(f'{w} × {h} px · {len(doc.layers)} objetos · Guardado automático')

    def save_document(self):
        if not self.document:return
        self.save_timer.stop()
        try:self.storage.save(self.document);self.doc_status.setText(self.doc_status.text().replace('Guardando…','Guardado automático'));return True
        except Exception as exc:self.notice('No se pudo guardar la captura: '+str(exc),True);return False

    def rename(self):
        if self.document:self.document.title=self.title.text().strip() or 'Captura';self.changed()

    def undo(self):
        if self.document:self.canvas.cancel_gesture();self.document.undo();self.changed();self.selection_changed(self.canvas.current_layer())

    def redo(self):
        if self.document:self.canvas.cancel_gesture();self.document.redo();self.changed();self.selection_changed(self.canvas.current_layer())

    def uncrop(self):
        if self.document:self.document.set_crop(None);self.changed()

    def selection_changed(self,layer):
        self.sync_properties()
        if layer:
            for spin,value in ((self.width_spin,round(layer.width)),(self.font_spin,layer.font_size)):
                spin.blockSignals(True);spin.setValue(value);spin.blockSignals(False)
            self.canvas.color=layer.color;self.canvas.stroke=layer.width;self.canvas.font_size=layer.font_size
        self.sync_properties()

    def sync_properties(self):
        layer=self.canvas.current_layer()
        tool=layer.tool if layer else self.canvas.tool
        has_color=tool not in ('select','crop','blur')
        has_width=tool in ('arrow','rectangle','ellipse','pen')
        has_font=tool in ('text','number')
        self.color_button.setEnabled(has_color)
        self.width_label.setVisible(has_width);self.width_spin.setVisible(has_width)
        self.font_label.setVisible(has_font);self.font_spin.setVisible(has_font)
        self.width_spin.setEnabled(has_width);self.font_spin.setEnabled(has_font)
        self.edit_button.setEnabled(bool(layer and layer.tool in ('text','number')))
        self.edit_button.setVisible(bool(layer and layer.tool in ('text','number')))
        swatch=QPixmap(18,18);swatch.fill(QColor(self.canvas.color));self.color_button.setIcon(QIcon(swatch))
        self.color_button.setAccessibleName('Color '+self.canvas.color);self.color_button.setToolTip('Color del objeto · '+self.canvas.color)

    def apply_properties(self):
        self.canvas.stroke=self.width_spin.value();self.canvas.font_size=self.font_spin.value()
        layer=self.canvas.current_layer()
        if layer:self.document.replace_layer(layer.id,replace(layer,width=self.canvas.stroke,font_size=self.canvas.font_size,color=self.canvas.color));self.changed()

    def change_color(self):
        color=QColorDialog.getColor(QColor(self.canvas.color),self,'Color del objeto')
        if color.isValid():self.canvas.color=color.name();self.apply_properties();self.sync_properties()

    def edit_selected(self):
        layer=self.canvas.current_layer()
        if layer:self.edit_layer(layer)

    def edit_layer(self,layer):
        if layer.tool=='text':
            text,ok=QInputDialog.getMultiLineText(self,'Editar texto','Texto',layer.text)
            if ok:self.document.replace_layer(layer.id,replace(layer,text=text));self.changed()
        elif layer.tool=='number':
            value,ok=QInputDialog.getInt(self,'Editar paso','Número del paso',layer.number,1,99999)
            if ok:self.document.replace_layer(layer.id,replace(layer,number=value));self.changed()
        else:
            self.notice('Ajusta color, grosor o tamaño arriba. Arrastra el objeto para moverlo.');self.width_spin.setFocus()

    def copy(self):
        if not self.document:return
        try:self.storage.copy(self.document);self.notice('Imagen copiada al portapapeles')
        except Exception as exc:self.notice(str(exc),True)

    def prefs(self):return getattr(self.storage,'settings',{})

    def export(self):
        if not self.document:return
        def save():
            fmt=self.prefs().get('format','PNG').lower();suffix='jpg' if fmt in ('jpeg','jpg') else 'png'
            name='Wysun-'+datetime.now().strftime('%Y-%m-%d-%H%M%S-%f')+'.'+suffix
            path=self.storage.export(self.document,self.storage.default_output/name);self.notice('Guardada en '+str(path));return path
        return self.guard(save)

    def show_quick(self):
        self.hide();self.quick.present()

    def show_library(self):
        self.quick.hide()
        if self.document and not self.save_document():
            self.stack.setCurrentWidget(self.editor_page);self.show();return
        self.refresh_library();self.stack.setCurrentWidget(self.library_page);self.show();self.raise_();self.activateWindow();self.library_state();self.thumbnail_timer.start(0)

    def refresh_library(self):
        try:
            self.library_generation+=1;self.items.clear()
            for entry in self.storage.list_sessions():
                date=datetime.fromtimestamp(entry['updated']).strftime('%d %b · %H:%M')
                item=QListWidgetItem(f"{entry['title']}\n{entry['width']} × {entry['height']} px · {date}");item.setData(Qt.UserRole,entry['id']);item.setData(Qt.UserRole+1,entry);self.items.addItem(item)
            self.filter_library()
            if hasattr(self,'thumbnail_timer'):self.thumbnail_timer.start(0)
        except Exception as exc:self.notice(str(exc),True)

    def filter_library(self):
        query=self.search.text().casefold()
        for n in range(self.items.count()):self.items.item(n).setHidden(query not in self.items.item(n).text().casefold())
        self.empty.setVisible(not any(not self.items.item(n).isHidden() for n in range(self.items.count())));self.library_state()
        if hasattr(self,'thumbnail_timer'):self.thumbnail_timer.start(0)

    def selected_ids(self):return [i.data(Qt.UserRole) for i in self.items.selectedItems() if not i.isHidden()]
    def library_state(self):
        count=len(self.selected_ids())
        if self.stack.currentWidget()==self.library_page:
            self.notice(f'{count} capturas seleccionadas · Componer une las imágenes; Comparar necesita dos del mismo tamaño.' if count>1 else 'Enter para abrir · Ctrl+clic para seleccionar varias capturas' if count==1 else 'Elige una captura para abrirla o varias para componer.')
        self.open_button.setEnabled(count==1);self.compose_button.setEnabled(count>=2);self.compare_button.setEnabled(count==2)
    def load_visible_thumbnail(self):
        if self.thumbnail_pending or self.stack.currentWidget()!=self.library_page or not self.isVisible():return
        viewport=self.items.viewport().rect()
        target=None
        for n in range(self.items.count()):
            item=self.items.item(n)
            if item.isHidden() or not self.items.visualItemRect(item).intersects(viewport):continue
            entry=item.data(Qt.UserRole+1);key=(entry['id'],entry['updated'])
            if key in self.thumbnail_cache:
                item.setData(Qt.DecorationRole,QIcon(QPixmap.fromImage(self.thumbnail_cache[key])));continue
            target=(item,entry,key);break
        if target is None:return
        item,entry,key=target;generation=self.library_generation;self.thumbnail_pending=True
        def render():
            doc=self.storage.load(entry['id']);return doc.render().scaled(160,96,Qt.KeepAspectRatio,Qt.SmoothTransformation)
        job=Work(render,QApplication.instance());self.jobs.append(job)
        def ready(image):
            self.thumbnail_cache[key]=image
            while len(self.thumbnail_cache)>32:self.thumbnail_cache.popitem(last=False)
            if generation==self.library_generation:item.setData(Qt.DecorationRole,QIcon(QPixmap.fromImage(image)));self.items.viewport().update()
        def failed(message):
            image=QPixmap(160,96);image.fill(token_color('inset'));self.thumbnail_cache[key]=image.toImage()
            if generation==self.library_generation:item.setToolTip('Vista previa no disponible: '+message)
        def finished():
            self.thumbnail_pending=False
            if job in self.jobs:self.jobs.remove(job)
            job.deleteLater()
            if self._closing and not self.jobs:QTimer.singleShot(0,self.close)
            elif not self._closing:self.thumbnail_timer.start(0)
        job.ready.connect(ready);job.failed.connect(failed);job.finished.connect(finished);job.start()

    def open_selected(self):
        ids=self.selected_ids()
        if len(ids)==1:self.guard(lambda:self.set_document(self.storage.load(ids[0])))

    def import_image(self):
        path,_=QFileDialog.getOpenFileName(self,'Abrir imagen',str(self.storage.default_output),'Imágenes (*.png *.jpg *.jpeg)')
        if path:
            from PySide6.QtGui import QImageReader
            def load():
                reader=QImageReader(path);size=reader.size()
                if size.width()*size.height()>100_000_000:raise ValueError('Imagen demasiado grande')
                self.set_document(Document(reader.read(),Path(path).stem))
            self.guard(load)

    def compose(self):
        ids=self.selected_ids()
        if len(ids)<2:return
        dialog=QDialog(self);dialog.setWindowTitle('Componer capturas');form=QFormLayout(dialog);form.addRow(label('Componer capturas','section'))
        hint=label('Orden de arriba hacia abajo en la biblioteca. Cada original se conserva.','subtitle');hint.setWordWrap(True);form.addRow(hint)
        axis=QComboBox();axis.addItem('Horizontal','horizontal');axis.addItem('Vertical','vertical');form.addRow('Dirección',axis)
        gap=SpinBox();gap.setRange(0,512);gap.setValue(16);form.addRow('Separación en píxeles',gap)
        titles=QCheckBox('Incluir títulos');titles.setChecked(True);form.addRow(titles)
        buttons=localize_buttons(QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel),'Componer');buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec()==QDialog.Accepted:
            def build():
                docs=[self.storage.load(id) for id in ids]
                # Labelled inputs are derived images: sources remain independently editable.
                if titles.isChecked():
                    from PySide6.QtGui import QImage,QPainter,QFont
                    labelled=[]
                    for doc in docs:
                        source=doc.render();image=QImage(source.width(),source.height()+48,QImage.Format_ARGB32);image.fill(QColor('#F3F6FB'))  # theme-exception: exported composition is document content, not UI
                        p=QPainter(image);p.setPen(QColor('#1C2A3B'));font=QFont();font.setPixelSize(18);p.setFont(font)  # theme-exception: exported composition label
                        p.drawText(QRect(12,0,max(1,image.width()-24),48),Qt.AlignVCenter,p.fontMetrics().elidedText(doc.title,Qt.ElideRight,max(1,image.width()-24)));p.drawImage(0,48,source);p.end();labelled.append(Document(image,doc.title))
                    docs=labelled
                self.set_document(Document.compose(docs,axis.currentData(),gap.value()));self.notice('Composición creada. Las capturas originales siguen en la biblioteca.')
            self.guard(build)

    def compare(self):
        ids=self.selected_ids()
        if len(ids)!=2:return
        def open_compare():
            before,after=[self.storage.load(id) for id in ids]
            if before.render().size()!=after.render().size():raise ValueError('El comparador necesita dos capturas del mismo tamaño.')
            dialog=QDialog(self);dialog.setWindowTitle('Antes / después');dialog.resize(900,650);layout=QVBoxLayout(dialog)
            heading=label('Antes: '+before.title+'   /   Después: '+after.title,'section');heading.setWordWrap(True);layout.addWidget(heading)
            view=Canvas();view.setEnabled(False);layout.addWidget(view,1)
            slider=QSlider(Qt.Horizontal);slider.setRange(0,100);slider.setValue(50);slider.setAccessibleName('División antes y después');layout.addWidget(slider)
            def update():view.comparison_split=slider.value()/100;view.set_document(Document.compare(before,after,slider.value()/100))
            slider.valueChanged.connect(update);update()
            row=QHBoxLayout();row.addWidget(label('← Antes · mueve el divisor · Después →','subtitle'));row.addStretch();row.addWidget(button('Invertir',lambda:swap()));row.addWidget(button('Guardar vista',lambda:(self.set_document(Document.compare(before,after,slider.value()/100)),dialog.accept()),'save',primary=True));layout.addLayout(row)
            def swap():
                nonlocal before,after
                before,after=after,before;heading.setText('Antes: '+before.title+'   /   Después: '+after.title);update()
            dialog.exec()
        self.guard(open_compare)

    def show_settings(self):
        restore_quick=self.quick.isVisible();self.quick.hide();dialog=QDialog(self);dialog.setWindowTitle('Ajustes · Wysun Screenshot');dialog.setMinimumWidth(380);form=QFormLayout(dialog);form.addRow(label('Ajustes','title'))
        output=QLineEdit(str(self.storage.default_output));output.setAccessibleName('Carpeta de imágenes');row=QHBoxLayout();row.addWidget(output)
        def browse():
            path=QFileDialog.getExistingDirectory(dialog,'Carpeta de imágenes',output.text())
            if path:output.setText(path)
        row.addWidget(button('Elegir…',browse,'folder'));form.addRow('Guardar imágenes en',row)
        fmt=QComboBox();fmt.addItems(['PNG','JPEG']);fmt.setCurrentText(self.prefs().get('format','PNG'));form.addRow('Formato',fmt)
        delay=QComboBox()
        for seconds in (0,3,5):delay.addItem('Sin espera' if seconds==0 else f'{seconds} segundos',seconds)
        delay.setCurrentIndex(max(0,delay.findData(self.prefs().get('delay',0))));form.addRow('Antes de capturar',delay)
        monitors=QComboBox()
        for n,screen in enumerate(QApplication.screens()):monitors.addItem(f'{screen.name()} · {screen.geometry().width()} × {screen.geometry().height()}',n)
        monitors.setCurrentIndex(min(self.monitor,monitors.count()-1));form.addRow('Monitor',monitors)
        cursor=QCheckBox('Incluir cursor');cursor.setChecked(self.prefs().get('include_cursor',False));form.addRow(cursor)
        reduced=QCheckBox('Reducir movimiento');reduced.setChecked(self.prefs().get('reduced_motion',False));form.addRow(reduced)
        from loomrec.portal import is_wayland
        contract='Wayland: selección y permiso en el portal. Escritorio con cursor pide un permiso por monitor y compone imágenes secuenciales; cancelar descarta el conjunto.' if is_wayland() else 'Captura local X11 a escala 1×. Ventana captura su área visible, incluidas las ventanas que la cubran.'
        hint=label(contract+'\nCtrl+N nueva · Ctrl+S guardar · Ctrl+Shift+C copiar\nSelección: flechas mueven · Shift ajusta · Ctrl acelera\nLos documentos se guardan automáticamente para reabrirlos.','subtitle');hint.setWordWrap(True);form.addRow(hint)
        box=localize_buttons(QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel));box.accepted.connect(dialog.accept);box.rejected.connect(dialog.reject);form.addRow(box)
        if dialog.exec()==QDialog.Accepted:
            def save():
                self.storage.set_output(Path(output.text()));self.monitor=max(0,monitors.currentIndex())
                if hasattr(self.storage,'update_settings'):self.storage.update_settings(format=fmt.currentText(),delay=delay.currentData(),include_cursor=cursor.isChecked(),reduced_motion=reduced.isChecked())
                else:raise RuntimeError('Backend incompatible: no se pudieron guardar los ajustes.')
                os.environ['LOOMREC_REDUCED_MOTION']='1' if reduced.isChecked() else '0';self.notice('Ajustes guardados')
            self.guard(save)
        if restore_quick:self.quick.present()

    def begin_capture(self):
        if self.busy:return
        # Validate the physical coordinate contract before hiding the app.
        try:
            if QApplication.platformName()!='xcb' and not __import__('loomrec.portal',fromlist=['is_wayland']).is_wayland():raise RuntimeError('La captura requiere una sesión X11. Puedes editar imágenes y abrir la biblioteca aquí.')
            if QApplication.platformName()=='xcb' and not __import__('loomrec.portal',fromlist=['is_wayland']).is_wayland() and any(abs(s.devicePixelRatio()-1)>.001 for s in QApplication.screens()):raise RuntimeError('La captura requiere escala de pantalla 1×; esta escala todavía no es compatible.')
        except Exception as exc:self.show_library();self.notice(str(exc),True);return
        if self._capture_lease is None:self._capture_lease=CaptureLease()
        if not self._capture_lease.claim():
            self.notice('Ya hay una captura en curso. Termina o cancela la selección actual.',True);return
        window_id=None
        if self.capture_mode=='window' and not __import__('loomrec.portal',fromlist=['is_wayland']).is_wayland():
            try:entries=self.engine.windows()
            except Exception as exc:self.release_capture();self.show_library();self.notice(str(exc),True);return
            owned={int(w.winId()) for w in QApplication.topLevelWidgets()}
            entries=[w for w in entries if w['id'] not in owned]
            if not entries:self.release_capture();self.notice('No hay ventanas visibles disponibles.',True);self.show_library();return
            dialog=QDialog(self);dialog.setWindowTitle('Elegir ventana visible');dialog.resize(520,440);layout=QVBoxLayout(dialog)
            hint=label('Se captura el área visible: otras ventanas pueden aparecer encima.','subtitle');hint.setWordWrap(True);layout.addWidget(hint)
            items=QListWidget();items.setAccessibleName('Ventanas visibles')
            for entry in entries:
                item=QListWidgetItem(entry['title']);item.setData(Qt.UserRole,entry['id']);items.addItem(item)
            layout.addWidget(items);items.setCurrentRow(0);box=localize_buttons(QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel),'Capturar');box.accepted.connect(dialog.accept);box.rejected.connect(dialog.reject);items.itemActivated.connect(lambda _:dialog.accept());layout.addWidget(box)
            if dialog.exec()!=QDialog.Accepted:self.release_capture();return
            window_id=items.currentItem().data(Qt.UserRole)
        self.pending_request=CaptureRequest(mode=self.capture_mode,monitor=self.monitor,window_id=window_id,include_cursor=self.prefs().get('include_cursor',False))
        self.busy=True;self.countdown=int(self.prefs().get('delay',0));self.hide();self.quick.hide();self.capture_timer.start(self.capture_settle_ms)

    def capture_tick(self):
        if not self.busy:return
        if self.countdown:
            # A cancellable visible countdown is dismissed before the actual frame grab.
            if not hasattr(self,'countdown_window'):
                self.countdown_window=QDialog(None,Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint);self.countdown_window.setWindowTitle('Preparando captura');layout=QHBoxLayout(self.countdown_window);self.count_label=label('','section');layout.addWidget(self.count_label);layout.addWidget(button('Cancelar',self.cancel_capture,'close'));apply_material(self.countdown_window,kind='dialog',radius=20)
                QShortcut(QKeySequence('Escape'),self.countdown_window,activated=self.cancel_capture)
            self.count_label.setText(f'Captura en {self.countdown}…');self.countdown_window.show();self.countdown-=1;self.capture_timer.start(1000);return
        if hasattr(self,'countdown_window') and self.countdown_window.isVisible():self.countdown_window.hide();self.capture_timer.start(180);return
        if __import__('loomrec.portal',fromlist=['is_wayland']).is_wayland():
            request=self.pending_request
            feedback=None
            if request.mode=='desktop' and request.include_cursor:
                from .capture_feedback import CaptureFeedback
                feedback=CaptureFeedback(self);self._capture_feedback=feedback
            elif request.mode=='region':
                from .capture_feedback import CaptureWaitFeedback
                # The cursor branch talks to the ScreenCast picker and must show
                # instructions immediately. The direct Screenshot branch is fast
                # and non-interactive, so its dialog waits and never flashes.
                delay=0 if request.include_cursor else 1200
                feedback=CaptureWaitFeedback(self,delay_ms=delay,screen_cast=request.include_cursor);self._capture_feedback=feedback
            pending=feedback is not None;outcome={}
            def work():
                if pending and request.mode=='region':return self.engine.freeze(request.include_cursor,progress=feedback.report,on_wait=feedback.check)
                if feedback:return self.engine.capture(request,progress=feedback.report,on_wait=feedback.check)
                return self.engine.freeze(request.include_cursor) if request.mode=='region' else self.engine.capture(request)
            job=Work(work,QApplication.instance());self.jobs.append(job);self._capture_job=job
            def ready(result):
                if pending:
                    outcome['result']=result;return
                if not self.busy or (feedback and feedback.cancelled.is_set()):return
                if request.mode=='region':
                    self.frozen=result;self.overlay=self.create_selection(result);self.overlay.present()
                else:self.finish_capture(result)
            def failed(message):
                if pending:
                    outcome['error']=message;return
                if feedback and self._capture_feedback is not feedback:return
                if message=='Selección cancelada en el portal' or (feedback and feedback.cancelled.is_set()):
                    self.cancel_capture();return
                # A failed capture is not the user's Cancel action. In direct
                # mode that override closes the app while this job is active,
                # suppressing the error and quitting as soon as it finishes.
                Window.cancel_capture(self)
                if ('No such interface' in message or 'org.freedesktop.DBus.Error.UnknownInterface' in message) and any(
                        iface in message for iface in ('org.freedesktop.portal.ScreenCast','org.freedesktop.portal.Screenshot')):
                    message='El portal de captura no está disponible en esta sesión. Revisa la configuración del portal y vuelve a intentarlo. Tus capturas guardadas se conservan.'
                if not self._closing:self.show_library();self.notice(message,True)
            def finished():
                cancelled=bool(feedback and feedback.cancelled.is_set())
                if feedback:
                    feedback.close()
                    if self._capture_feedback is feedback:self._capture_feedback=None
                if job in self.jobs:self.jobs.remove(job)
                if self._capture_job is job:self._capture_job=None
                job.deleteLater()
                if pending and not self._closing:
                    message=outcome.get('error')
                    if cancelled or message=='Selección cancelada en el portal':self.cancel_capture()
                    elif message:
                        # Complete teardown before releasing the lease or
                        # offering a retry. An error is still not Cancel.
                        Window.cancel_capture(self)
                        if ('No such interface' in message or 'org.freedesktop.DBus.Error.UnknownInterface' in message) and any(iface in message for iface in ('org.freedesktop.portal.ScreenCast','org.freedesktop.portal.Screenshot')):
                            message='El portal de captura no está disponible en esta sesión. Revisa la configuración del portal y vuelve a intentarlo. Tus capturas guardadas se conservan.'
                        self.show_library();self.notice(message,True)
                    elif 'result' in outcome:
                        if request.mode=='region':
                            self.frozen=outcome['result'];self.overlay=self.create_selection(self.frozen);self.overlay.present()
                        else:self.finish_capture(outcome['result'])
                if self._closing and not self.jobs:QTimer.singleShot(0,self.close)
            job.ready.connect(ready);job.failed.connect(failed);job.finished.connect(finished);job.start();return
        def capture():
            if self.pending_request.mode=='region':
                self.frozen=self.engine.freeze();g=self.frozen.geometry
                self.overlay=self.create_selection(self.frozen)
                self.overlay.present()
            else:self.finish_capture(self.engine.capture(self.pending_request))
        try:capture()
        except Exception as exc:self.cancel_capture();self.notice(str(exc),True);self.show_library()

    def release_capture(self):
        if self._capture_lease:self._capture_lease.release();self._capture_lease=None

    def create_selection(self,frozen):
        overlays=[]
        for image,screen,origin,geometry in selection_parts(frozen):
            overlay=FloatingSelection(image,geometry,screen=screen,image_origin=origin)
            overlay.finished.connect(lambda doc,action,o=overlay:self.complete_floating(doc,action,overlay=o))
            overlay.cancelled.connect(self.cancel_capture)
            overlays.append(overlay)
        if not overlays:raise RuntimeError('No hay una pantalla disponible para la selección')
        return overlays[0] if len(overlays)==1 else SelectionGroup(overlays)

    def complete_floating(self,doc,action,path=None,overlay=None):
        overlay=overlay or (self.overlay.overlays[0] if getattr(self.overlay,'overlays',None) else self.overlay)
        if overlay is None:return
        if action=='save' and path is None:
            name='Wysun-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.png'
            overlay.request_save_path(self.storage.default_output/name,
                                      lambda chosen,o=overlay:self.complete_floating(doc,'save',chosen,overlay=o))
            return
        try:
            self.storage.save(doc)
            if action=='save':self.storage.export(doc,Path(path))
            else:self.storage.copy(doc)
        except Exception as exc:
            overlay.show_error('No se pudo completar: '+str(exc));return
        self.busy=False;self.frozen=None
        self.overlay.hide();self.overlay.deleteLater();self.overlay=None
        self.release_capture()
        if action=='copy':
            self.hide();self.quick.hide()
            self._clipboard_hidden=True
            QApplication.clipboard().dataChanged.connect(self.clipboard_ownership_changed)
        else:self.close()

    def clipboard_ownership_changed(self):
        if self._clipboard_hidden and not QApplication.clipboard().ownsClipboard():
            self._clipboard_hidden=False;self.close()

    def selected_region(self,rect):
        g=self.frozen.geometry
        request=replace(self.pending_request,region=Rect(rect.x()+g.x,rect.y()+g.y,rect.width(),rect.height()))
        try:self.finish_capture(self.engine.capture(request,self.frozen))
        except Exception as exc:self.cancel_capture();self.show_library();self.notice(str(exc),True)

    def finish_capture(self,result):
        self.release_capture()
        self.busy=False;self.frozen=None
        if self.overlay:self.overlay.deleteLater();self.overlay=None
        self.set_document(Document(result.image,'Captura '+datetime.now().strftime('%d %b %H:%M')))
        self.notice(result.warning or 'Captura lista. Anota, copia o guarda.')

    def defer_capture_cancel(self):
        # Request.Close is performed by the worker's portal wait callback.
        # Keep ownership until its session/FD teardown and QThread.finished.
        feedback=self._capture_feedback
        if self._capture_job is not None and feedback:
            feedback.cancel();self.capture_timer.stop();return True
        return False

    def cancel_capture(self):
        if self.defer_capture_cancel():return
        if self._capture_feedback:self._capture_feedback.cancel()
        self.release_capture()
        self.capture_timer.stop();self.busy=False;self.frozen=None
        if self.overlay:self.overlay.hide();self.overlay.deleteLater();self.overlay=None
        if hasattr(self,'countdown_window'):self.countdown_window.hide()
        if not self._closing:self.quick.present()

    def escape(self):
        if self.busy:self.cancel_capture()
        else:self.canvas.cancel_gesture()

    def closeEvent(self,event):
        if self.jobs:
            if self._capture_feedback:self._capture_feedback.cancel()
            self._closing=True;self.hide();self.quick.hide();event.ignore();return
        self.thumbnail_timer.stop()
        if self.document and not self.save_document():
            self._closing=False;self.show();event.ignore();return
        self.release_capture()
        self.quick.hide();self.capture_timer.stop()
        if self.overlay:self.overlay.close()
        if hasattr(self,'countdown_window'):self.countdown_window.close()
        event.accept()
        app=QApplication.instance()
        if getattr(app,'_wybieshot_window',None) is self:app.quit()


def run(app,argv):
    apply_theme(app);app.setQuitOnLastWindowClosed(False)
    window=Window();app._wybieshot_window=window
    if '--library' in argv:window.show_library()
    else:
        window.show_quick()
        if '--region' in argv:QTimer.singleShot(0,window.begin_capture)
    result=app.exec()
    window.quick.close();window.close();window.quick.deleteLater();window.deleteLater()
    from PySide6.QtCore import QEvent
    app.sendPostedEvents(None,QEvent.DeferredDelete);app._wybieshot_window=None
    return result
