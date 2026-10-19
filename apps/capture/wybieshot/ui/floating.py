"""In-place annotations on frozen desktop pixels with one floating tool palette."""
from dataclasses import replace
from PySide6.QtCore import Qt,QRect,QRectF,QPoint,Signal,QEvent
from PySide6.QtGui import QColor,QPainter,QPen,QShortcut,QKeySequence
from PySide6.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QSpinBox,QColorDialog,QPlainTextEdit,QWidget,QApplication,QFileDialog
from .selection import SelectionOverlay
from .canvas import Canvas
from .components import button,label
from .localization import install_translations,prepare_color_picker
from wybieshot.document import Document

TOOLS=[('select','Objeto','V'),('arrow','Flecha','A'),('rectangle','Rectángulo','R'),('ellipse','Elipse','E'),('pen','Lápiz','P'),('highlight','Resaltar','H'),('text','Texto','T'),('number','Paso','N'),('mask','Máscara opaca','M'),('blur','Desenfoque visual','B')]

class ControlSurface(QFrame):
    """Palette whitespace is a control surface, never a selection/drawing target."""
    def mousePressEvent(self,event):event.accept()
    def mouseMoveEvent(self,event):event.accept()
    def mouseReleaseEvent(self,event):event.accept()

class RegionCanvas(Canvas):
    def __init__(self,parent):
        super().__init__(parent);self.setMinimumSize(1,1)
    def image_rect(self):
        return QRectF(self.rect())

class FloatingSelection(SelectionOverlay):
    finished=Signal(object,str)
    def __init__(self,image,geometry,parent=None):
        install_translations(QApplication.instance())
        super().__init__(image,geometry,parent)
        self.setWindowFlag(Qt.X11BypassWindowManagerHint,not __import__('loomrec.portal',fromlist=['is_wayland']).is_wayland())
        self.setWindowTitle('Seleccionar región · Wysun Screenshot')
        self.document=None;self.editing=False;self._popover=None;self._file_dialog=None
        QApplication.instance().installEventFilter(self)
        self.canvas=RegionCanvas(self);self.canvas.hide()
        self.canvas.changed.connect(self.changed);self.canvas.edit_requested.connect(self.edit_layer);self.canvas.selected.connect(self.selection_changed)
        self.toolbar=ControlSurface(self);self.toolbar.setObjectName('capturePalette')
        self.toolbar.setStyleSheet('#capturePalette {background:#FCFDFF;border:1px solid #DDE5EF;border-radius:18px;}')
        layout=QVBoxLayout(self.toolbar);layout.setContentsMargins(12,10,12,10);layout.setSpacing(8)
        tools=QHBoxLayout();tools.setSpacing(3)
        self.area=button('',self.adjust_area,'region',compact=True);self.area.setAccessibleName('Ajustar región');self.area.setToolTip('Ajusta el área antes de anotar. Deshaz los objetos para volver a ajustarla.');tools.addWidget(self.area)
        self.tools={}
        for tool,name,key in TOOLS:
            b=button('',lambda checked=False,t=tool:self.choose(t),tool,compact=True)
            b.setCheckable(True);b.setAccessibleName(name);b.setToolTip(f'{name} · {key}');b.setFixedSize(34,34);tools.addWidget(b);self.tools[tool]=b
            QShortcut(QKeySequence(key),self,activated=lambda t=tool:self.choose(t))
        tools.addStretch();layout.addLayout(tools)
        actions=QHBoxLayout();actions.setSpacing(6)
        self.color=button('',self.pick_color,compact=True);self.color.setAccessibleName('Color');self.color.setToolTip('Color');self.color.setFixedWidth(34);actions.addWidget(self.color)
        self.stroke_spin=QSpinBox();self.stroke_spin.setRange(1,64);self.stroke_spin.setValue(3);self.stroke_spin.setFixedWidth(62);self.stroke_spin.setAccessibleName('Grosor');self.stroke_spin.valueChanged.connect(self.properties);actions.addWidget(self.stroke_spin)
        self.font_spin=QSpinBox();self.font_spin.setRange(6,256);self.font_spin.setValue(24);self.font_spin.setFixedWidth(68);self.font_spin.setAccessibleName('Tamaño de texto');self.font_spin.valueChanged.connect(self.properties);actions.addWidget(self.font_spin)
        self.undo_button=button('',self.undo,'undo',compact=True);self.undo_button.setAccessibleName('Deshacer');self.undo_button.setToolTip('Deshacer · Ctrl+Z');actions.addWidget(self.undo_button)
        self.redo_button=button('',self.redo,'redo',compact=True);self.redo_button.setAccessibleName('Rehacer');self.redo_button.setToolTip('Rehacer · Ctrl+Shift+Z');actions.addWidget(self.redo_button)
        actions.addStretch();self.copy_button=button('Copiar',lambda:self.complete('copy'),'copy',primary=True);self.save_button=button('Guardar',lambda:self.complete('save'),'save');actions.addWidget(self.copy_button);actions.addWidget(self.save_button)
        close=button('',self.cancel,'close',compact=True);close.setAccessibleName('Cancelar captura');close.setToolTip('Cancelar · Esc');actions.addWidget(close)
        layout.addLayout(actions)
        self.message=label('Área lista · elige una herramienta para anotar','subtitle');layout.addWidget(self.message)
        self.font_spin.hide();self.stroke_spin.hide()
        self.toolbar.hide()
        for keys,fn in [('Escape',self.cancel),('Ctrl+C',lambda:self.complete('copy')),('Ctrl+S',lambda:self.complete('save')),('Ctrl+Z',self.undo),('Ctrl+Shift+Z',self.redo)]:QShortcut(QKeySequence(keys),self,activated=fn)
        self.changed()

    def paintEvent(self,event):
        p=QPainter(self);p.drawImage(self.rect(),self.image);p.fillRect(self.rect(),QColor(12,24,40,115))
        r=self.selection.normalized().intersected(self.rect())
        if r.width()>1 and r.height()>1:
            p.save();p.setClipRect(r);p.drawImage(self.rect(),self.image);p.restore()
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#FFFFFF'),1));p.drawRect(QRectF(r).adjusted(.5,.5,-.5,-.5))
            if not self.editing:
                for point in (r.topLeft(),r.topRight(),r.bottomLeft(),r.bottomRight()):p.fillRect(QRect(point-QPoint(3,3),point+QPoint(3,3)),QColor('#FFFFFF'))
        if not self.toolbar.isVisible():
            hint='Arrastra para seleccionar · Esc cancelar';box=QRect(16,max(8,self.height()-54),min(440,self.width()-32),38)
            p.setPen(Qt.NoPen);p.setBrush(QColor('#FCFDFF'));p.drawRoundedRect(box,18,18);p.setPen(QColor('#1C2A3B'));p.drawText(box,Qt.AlignCenter,hint)
        p.end()

    def mousePressEvent(self,event):
        if not self.editing:super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if not self.editing:super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self.editing:return
        super().mouseReleaseEvent(event)
        if event.button()==Qt.LeftButton:self.prepare_selection()

    def prepare_selection(self):
        r=self.selection.normalized().intersected(self.rect())
        if r.width()<2 or r.height()<2:return
        self.selection=r;self.document=Document(self.image.copy(self.source_rect(r)),'Captura')
        self.canvas.set_document(self.document);self.canvas.setGeometry(r)
        self.toolbar.setFixedWidth(min(720,max(1,self.width()-24)))
        self.toolbar.adjustSize();height=self.toolbar.sizeHint().height();self.toolbar.setFixedHeight(height)
        x=max(12,min(self.width()-self.toolbar.width()-12,r.center().x()-self.toolbar.width()//2))
        y=r.bottom()+12
        if y+height>self.height()-12:y=r.top()-height-12
        y=max(12,min(self.height()-height-12,y))
        handles=[QRect(point-QPoint(8,8),point+QPoint(8,8)) for point in (r.topLeft(),r.topRight(),r.bottomLeft(),r.bottomRight())]
        candidates=[QRect(x,y,self.toolbar.width(),height),QRect(x,12,self.toolbar.width(),height),QRect(x,max(12,self.height()-height-12),self.toolbar.width(),height)]
        for candidate in candidates:
            if not any(candidate.intersects(handle) for handle in handles):
                x,y=candidate.x(),candidate.y();break
        self.toolbar.move(x,y);self.toolbar.show();self.toolbar.raise_();self.changed()

    def choose(self,tool):
        if not self.document:return
        self.close_popover()
        self.editing=True;self.canvas.show();self.canvas.set_tool(tool);self.toolbar.raise_()
        for name,b in self.tools.items():b.setChecked(name==tool)
        self.font_spin.setVisible(tool in ('text','number'));self.stroke_spin.setVisible(tool in ('arrow','rectangle','ellipse','pen'))
        self.color.setEnabled(True)
        self.color.setToolTip('Color de las nuevas anotaciones y del objeto seleccionado')
        self.message.setText('Desenfoque visual · para ocultar utiliza Máscara opaca' if tool=='blur' else 'Anota sobre la captura · Ctrl+C copiar · Ctrl+S guardar · Esc cancelar')
        self.update()

    def adjust_area(self):
        if self.document and self.document.layers:return
        self.editing=False;self.canvas.hide();self.setFocus();self.update()
    def selection_changed(self,layer):
        if not layer:return
        for spin,value in ((self.stroke_spin,round(layer.width)),(self.font_spin,layer.font_size)):
            spin.blockSignals(True);spin.setValue(value);spin.blockSignals(False)
        self.canvas.color=layer.color;self.canvas.stroke=layer.width;self.canvas.font_size=layer.font_size
        self.font_spin.setVisible(layer.tool in ('text','number'));self.stroke_spin.setVisible(layer.tool in ('arrow','rectangle','ellipse','pen'))
        self.changed()
    def properties(self):
        self.canvas.stroke=self.stroke_spin.value();self.canvas.font_size=self.font_spin.value()
        layer=self.canvas.current_layer()
        if layer:
            self.document.replace_layer(layer.id,replace(layer,width=self.canvas.stroke,font_size=self.canvas.font_size));self.changed()
    def eventFilter(self,obj,event):
        if event.type()==QEvent.MouseButtonPress and self._popover and isinstance(obj,QWidget):
            if (obj is self or self.isAncestorOf(obj)) and obj is not self._popover and not self._popover.isAncestorOf(obj):
                self.close_popover()
        return super().eventFilter(obj,event)

    def close_popover(self):
        if self._popover:
            popup=self._popover;self._popover=None;popup.hide();popup.deleteLater()
            self.canvas.setFocus()

    def open_popover(self,title,editor,apply):
        self.close_popover();self.canvas.cancel_gesture()
        if QWidget.mouseGrabber() is self.canvas:self.canvas.releaseMouse()
        popup=ControlSurface(self);popup.setObjectName('capturePopover')
        popup.setStyleSheet('#capturePopover {background:#FCFDFF;border:1px solid #DDE5EF;border-radius:18px;}')
        layout=QVBoxLayout(popup);layout.setContentsMargins(12,12,12,12);layout.addWidget(label(title,'section'));layout.addWidget(editor)
        row=QHBoxLayout();row.addStretch()
        def accept():
            apply();self.close_popover()
        row.addWidget(button('Cancelar',self.close_popover));row.addWidget(button('Aplicar',accept,primary=True));layout.addLayout(row)
        self._popover=popup;popup.adjustSize()
        r=self.toolbar.geometry();width=min(popup.sizeHint().width(),max(1,self.width()-24));height=min(popup.sizeHint().height(),max(1,self.height()-24))
        x=max(12,min(self.width()-width-12,r.x()));y=r.bottom()+8
        if y+height>self.height()-12:y=r.top()-height-8
        y=max(12,min(self.height()-height-12,y));popup.setGeometry(x,y,width,height)
        popup.show();popup.raise_();editor.setFocus()
        return popup

    def pick_color(self):
        picker=QColorDialog(QColor(self.canvas.color),self)
        picker.setOption(QColorDialog.DontUseNativeDialog,True);picker.setOption(QColorDialog.NoButtons,True)
        picker.setWindowFlags(Qt.Widget)  # Embedded control, no native/modal window.
        prepare_color_picker(picker)
        def apply():
            color=picker.currentColor()
            if not color.isValid():return
            self.canvas.color=color.name();layer=self.canvas.current_layer()
            if layer:self.document.replace_layer(layer.id,replace(layer,color=color.name()))
            self.changed()
        self.open_popover('Color',picker,apply)

    def changed(self):
        self.undo_button.setEnabled(bool(self.document and self.document.can_undo));self.redo_button.setEnabled(bool(self.document and self.document.can_redo))
        self.area.setEnabled(not self.document or not self.document.layers)
        self.color.setStyleSheet('background:'+self.canvas.color+';border:3px solid #FCFDFF;border-radius:9px;')
        self.canvas.update();self.toolbar.raise_()
        if self._popover:self._popover.raise_()
    def undo(self):
        if self.document:self.document.undo();self.canvas.cancel_gesture();self.changed()
    def redo(self):
        if self.document:self.document.redo();self.canvas.cancel_gesture();self.changed()
    def edit_layer(self,layer):
        if layer.tool=='text':
            editor=QPlainTextEdit(layer.text);editor.setAccessibleName('Texto de la anotación');editor.setMinimumSize(320,100)
            def apply():
                self.document.replace_layer(layer.id,replace(layer,text=editor.toPlainText()));self.changed()
            self.open_popover('Texto',editor,apply);editor.selectAll()
        elif layer.tool=='number':
            editor=QSpinBox();editor.setRange(1,99999);editor.setValue(layer.number);editor.setAccessibleName('Número del paso')
            def apply():
                self.document.replace_layer(layer.id,replace(layer,number=editor.value()));self.changed()
            self.open_popover('Paso numerado',editor,apply)
    def request_save_path(self,default,callback):
        self.close_popover();self.canvas.cancel_gesture()
        if QWidget.mouseGrabber() is self.canvas:self.canvas.releaseMouse()
        if self._file_dialog:self._file_dialog.raise_();self._file_dialog.activateWindow();return
        dialog=QFileDialog(self,'Guardar captura',str(default))
        dialog.setOption(QFileDialog.DontUseNativeDialog,True)
        dialog.setAcceptMode(QFileDialog.AcceptSave);dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setNameFilters(['PNG (*.png)','JPEG (*.jpg *.jpeg)'])
        dialog.setWindowFlags(Qt.Dialog|Qt.WindowStaysOnTopHint|Qt.X11BypassWindowManagerHint)
        dialog.setWindowModality(Qt.NonModal);dialog.setAttribute(Qt.WA_DeleteOnClose)
        self._file_dialog=dialog
        def finished(result):
            files=dialog.selectedFiles();self._file_dialog=None
            if result==QFileDialog.Accepted and files:callback(files[0])
            if self.isVisible():self.raise_();self.activateWindow();self.canvas.setFocus()
        dialog.finished.connect(finished)
        dialog.resize(min(720,self.width()-24),min(480,self.height()-24))
        dialog.move(self.geometry().center()-dialog.rect().center());dialog.show();dialog.raise_();dialog.activateWindow()

    def complete(self,action):
        self.close_popover()
        if self._file_dialog:self._file_dialog.reject()
        if self.document:self.canvas.cancel_gesture();self.finished.emit(self.document,action)
    def show_error(self,message):self.message.setText(message)
    def cancel(self):
        if self._popover:self.close_popover();return
        if self.canvas.start is not None:self.canvas.cancel_gesture();return
        self.hide();self.cancelled.emit()
    def closeEvent(self,event):
        if self._file_dialog:self._file_dialog.reject()
        self.close_popover();self.canvas.cancel_gesture()
        if QWidget.mouseGrabber() is self.canvas:self.canvas.releaseMouse()
        super().closeEvent(event)

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return,Qt.Key_Enter):
            if self.document:self.choose('arrow')
            else:super().keyPressEvent(event);self.prepare_selection()
        elif not self.editing:
            super().keyPressEvent(event)
            if event.key() in (Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down):self.prepare_selection()
        else:super().keyPressEvent(event)
