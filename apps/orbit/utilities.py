"""Three focused native desktop tools sharing Órbita's visual language."""
import os
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QRect,QPoint,Signal,QThread
from PySide6.QtGui import QColor,QKeySequence,QShortcut,QPainter,QPen,QCursor
from PySide6.QtWidgets import (QApplication,QHBoxLayout,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem,
    QPlainTextEdit,QTextBrowser,QSplitter,QComboBox,QMessageBox,QFileDialog,QWidget,QLabel)
from desktop_common import Surface,button,text_label,open_vim
from utility_data import Notes,Colors,Processes,digest


def shortcut(window,key,fn):QShortcut(QKeySequence(key),window).activated.connect(fn)


class NotesWindow(Surface):
    def __init__(self,root=None):
        super().__init__('Notas','Markdown local · Ctrl N nueva · Ctrl E Vim',880,610)
        self.store=Notes(root);self.key=None;self.expected=None;self.dirty=False;self.loading=False
        top=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Buscar en tus notas…');top.addWidget(self.search,1)
        self.folder=QComboBox();self.folder.addItems(['Notas','Papelera']);top.addWidget(self.folder);top.addWidget(button('Nueva',self.new,'primary','plus'));self.outer.addLayout(top)
        split=QSplitter();self.list=QListWidget();split.addWidget(self.list);right=QWidget();layout=QVBoxLayout(right);layout.setContentsMargins(10,0,0,0)
        self.editor=QPlainTextEdit();self.editor.setPlaceholderText('Escribe una nota en Markdown…');self.preview=QTextBrowser();self.preview.setOpenExternalLinks(False);self.preview.hide();layout.addWidget(self.editor,1);layout.addWidget(self.preview,1)
        actions=QHBoxLayout()
        for label,fn in [('Vista previa',self.toggle_preview),('Vim',self.vim),('Favorito',self.favorite),('Papelera / restaurar',self.delete)]:actions.addWidget(button(label,fn))
        layout.addLayout(actions);split.addWidget(right);split.setSizes([260,560]);self.outer.addWidget(split,1)
        footer=QHBoxLayout();self.status=text_label('Guardado local','subtitle');footer.addWidget(self.status,1);footer.addWidget(button('Importar Markdown',self.import_notes));footer.addWidget(button('Guardar copia',self.copy_note));self.outer.addLayout(footer)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(650);self.timer.timeout.connect(self.save)
        self.search.textChanged.connect(self.refresh);self.folder.currentIndexChanged.connect(self.refresh);self.list.currentItemChanged.connect(self.selected);self.editor.textChanged.connect(self.changed)
        shortcut(self,'Ctrl+N',self.new);shortcut(self,'Ctrl+S',self.save);shortcut(self,'Ctrl+E',self.vim);shortcut(self,'Ctrl+F',self.search.setFocus)
        self.refresh()
    def refresh(self,*args):
        if not self.save():return
        key=self.key;self.list.blockSignals(True);self.list.clear()
        for r in self.store.all(self.search.text(),self.folder.currentIndex()==1):
            item=QListWidgetItem(('★  ' if r['favorite'] else '')+r['title']);item.setData(Qt.UserRole,r);self.list.addItem(item)
            if r['key']==key:self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        if not self.list.currentItem() and self.list.count():self.list.setCurrentRow(0)
        elif self.list.currentItem():self.selected(self.list.currentItem())
        else:self.selected(None)
    def selected(self,item,*args):
        if not self.save():return
        self.loading=True;r=item.data(Qt.UserRole) if item else None;self.key=r['key'] if r else None
        body=r['body'] if r else '';self.editor.setPlainText(body);self.expected=digest(body);self.preview.setMarkdown(body);self.editor.setReadOnly(self.folder.currentIndex()==1 or not r);self.loading=False
    def changed(self):
        if self.loading:return
        self.dirty=True;self.status.setText('Guardando…');self.timer.start()
    def save(self):
        if not self.dirty or not self.key:return True
        try:self.expected=self.store.save(self.key,self.editor.toPlainText(),self.expected)
        except (OSError,RuntimeError) as e:self.status.setText(str(e));return False
        self.dirty=False;self.preview.setMarkdown(self.editor.toPlainText());self.status.setText('Guardado')
        for i in range(self.list.count()):
            item=self.list.item(i);row=item.data(Qt.UserRole)
            if row['key']==self.key:
                row['body']=self.editor.toPlainText();row['title']=next((s.strip('# ').strip() for s in row['body'].splitlines() if s.strip()),'Sin título');item.setData(Qt.UserRole,row);item.setText(('★  ' if row['favorite'] else '')+row['title'])
        return True
    def new(self):
        if not self.save():return
        self.folder.setCurrentIndex(0);self.search.clear();self.key=self.store.create();self.refresh();self.editor.setFocus()
    def copy_note(self):
        self.key=self.store.create(self.editor.toPlainText());self.dirty=False;self.folder.setCurrentIndex(0);self.search.clear();self.refresh()
    def toggle_preview(self):self.preview.setVisible(not self.preview.isVisible());self.editor.setVisible(not self.preview.isVisible());self.preview.setMarkdown(self.editor.toPlainText())
    def favorite(self):
        if self.key:self.store.toggle_favorite(self.key);self.refresh()
    def delete(self):
        if self.key and self.save():self.store.move(self.key,self.folder.currentIndex()==1);self.key=None;self.refresh()
    def vim(self):
        if self.key and self.save():open_vim(self.store.path(self.key,self.folder.currentIndex()==1))
    def import_notes(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Importar notas','','Markdown y texto (*.md *.txt)')
        for path in paths:
            try:self.store.create(Path(path).read_text())
            except (OSError,UnicodeError) as e:self.status.setText(str(e))
        self.refresh()
    def closeEvent(self,event):
        if self.save():event.accept()
        else:event.ignore()
    def present(self):self.refresh();super().present()


class ProcessScan(QThread):
    ready=Signal(list)
    def __init__(self,model,parent):super().__init__(parent);self.model=model
    def run(self):self.ready.emit(self.model.scan())


class ProcessesWindow(Surface):
    def __init__(self):
        super().__init__('Procesos','CPU y memoria · selecciona un proceso para inspeccionarlo',820,560)
        self.model=Processes();self.rows=[];self.worker=None
        top=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Buscar nombre o PID…');top.addWidget(self.search,1);self.sort=QComboBox();self.sort.addItems(['Más CPU','Más memoria','Nombre']);top.addWidget(self.sort);self.outer.addLayout(top)
        body=QHBoxLayout();self.list=QListWidget();body.addWidget(self.list,3);detail=QVBoxLayout();self.info=text_label('Selecciona un proceso');detail.addWidget(self.info);detail.addStretch();self.normal=button('Terminar',lambda:self.stop(False));self.force=button('Forzar cierre…',lambda:self.stop(True),'danger');detail.addWidget(self.normal);detail.addWidget(self.force);body.addLayout(detail,2);self.outer.addLayout(body,1)
        self.status=text_label('Actualización cada 2 segundos · CPU por núcleo','subtitle');self.outer.addWidget(self.status)
        self.timer=QTimer(self);self.timer.setInterval(2000);self.timer.timeout.connect(self.scan);self.search.textChanged.connect(self.render);self.sort.currentIndexChanged.connect(self.render);self.list.currentItemChanged.connect(self.inspect)
        shortcut(self,'Ctrl+F',self.search.setFocus);shortcut(self,'F5',self.scan)
    def scan(self):
        if self.worker and self.worker.isRunning():return
        self.worker=ProcessScan(self.model,self);self.worker.ready.connect(self.loaded);self.worker.start()
    def loaded(self,rows):self.rows=rows;self.render()
    def current(self):return self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None
    def render(self,*args):
        selected=self.current();key=(selected['pid'],selected['start']) if selected else None;query=self.search.text().casefold();self.list.blockSignals(True);self.list.clear()
        order=[lambda r:-r['cpu'],lambda r:-r['memory'],lambda r:r['name'].casefold()][self.sort.currentIndex()]
        for r in sorted(self.rows,key=order):
            if query not in (r['name']+' '+str(r['pid'])).casefold():continue
            item=QListWidgetItem(f"{r['name']}   ·   {r['cpu']:.1f}%   ·   {r['memory']/1048576:.0f} MB");item.setData(Qt.UserRole,r);self.list.addItem(item)
            if (r['pid'],r['start'])==key:self.list.setCurrentItem(item)
        self.list.blockSignals(False);self.inspect()
    def inspect(self,*args):
        r=self.current();allowed=bool(r and r['uid']==os.getuid() and r['pid'] not in (1,os.getpid()));self.normal.setEnabled(allowed);self.force.setEnabled(allowed)
        if not r:self.info.setText('Selecciona un proceso');return
        self.info.setText(f"{r['name']}\n\nPID  {r['pid']}\nUsuario  {r['uid']}\nCPU  {r['cpu']:.1f}%\nMemoria  {r['memory']/1048576:.1f} MB\nEstado  {r['state']}")
    def stop(self,force):
        r=self.current()
        if not r:return
        if force and QMessageBox.question(self,'Forzar cierre',f"¿Forzar {r['name']} (PID {r['pid']})? Puede perder cambios sin guardar.",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:self.model.terminate(r,force);self.status.setText('Señal enviada');self.scan()
        except (OSError,RuntimeError) as e:self.status.setText(str(e))
    def present(self):super().present();self.timer.start();self.scan()
    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)


class Picker(QWidget):
    picked=Signal(QColor)
    cancelled=Signal()
    def __init__(self):
        super().__init__(None,Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.screens=[(s.geometry(),s.grabWindow(0).toImage()) for s in QApplication.screens()];rect=QRect()
        for geometry,_ in self.screens:rect=rect.united(geometry)
        self.setGeometry(rect);self.setMouseTracking(True);self.setCursor(Qt.CrossCursor);self.point=QCursor.pos()-rect.topLeft()
    def color(self):
        p=self.point+self.geometry().topLeft()
        for geometry,image in self.screens:
            if geometry.contains(p):
                local=p-geometry.topLeft();return image.pixelColor(min(image.width()-1,int(local.x()*image.width()/geometry.width())),min(image.height()-1,int(local.y()*image.height()/geometry.height())))
        return QColor('#000000')
    def paintEvent(self,event):
        p=QPainter(self)
        for geometry,image in self.screens:p.drawImage(geometry.translated(-self.geometry().topLeft()),image)
        x=min(max(8,self.point.x()+22),self.width()-168);y=min(max(8,self.point.y()+22),self.height()-145)
        p.fillRect(x,y,156,132,QColor('#1c1e26'));globalpoint=self.point+self.geometry().topLeft()
        for geometry,image in self.screens:
            if geometry.contains(globalpoint):
                local=globalpoint-geometry.topLeft();sx=image.width()/geometry.width();sy=image.height()/geometry.height();source=QRect(int(local.x()*sx)-5,int(local.y()*sy)-5,11,11);p.drawImage(QRect(x+4,y+4,148,100),image,source)
        p.setPen(QPen(QColor('white'),1));p.drawRect(x+70,y+49,14,10);p.setPen(QColor('white'));p.drawText(x+12,y+123,self.color().name().upper()+'   Esc cancelar')
    def mouseMoveEvent(self,e):self.point=e.position().toPoint();self.update()
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:self.picked.emit(self.color());self.close()
        else:self.cancelled.emit();self.close()
    def keyPressEvent(self,e):
        if e.key()==Qt.Key_Escape:self.cancelled.emit();self.close()
        elif e.key() in (Qt.Key_Return,Qt.Key_Enter):self.picked.emit(self.color());self.close()
        elif e.key() in (Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down):
            dx,dy={Qt.Key_Left:(-1,0),Qt.Key_Right:(1,0),Qt.Key_Up:(0,-1),Qt.Key_Down:(0,1)}[e.key()];self.point+=QPoint(dx,dy);self.point.setX(max(0,min(self.width()-1,self.point.x())));self.point.setY(max(0,min(self.height()-1,self.point.y())));self.update()


class ColorWindow(Surface):
    def __init__(self,path=None):
        super().__init__('Color','Captura un píxel · HEX, RGB y HSL',640,510);self.store=Colors(path);self.picker=None
        top=QHBoxLayout();self.entry=QLineEdit('#7AA2F7');self.entry.setPlaceholderText('Color HEX o nombre…');top.addWidget(self.entry,1);top.addWidget(button('Capturar pantalla',self.capture,'primary','palette'));self.outer.addLayout(top)
        self.swatch=QLabel();self.swatch.setMinimumHeight(130);self.swatch.setAlignment(Qt.AlignCenter);self.outer.addWidget(self.swatch)
        self.formats=QComboBox();self.outer.addWidget(self.formats);actions=QHBoxLayout();actions.addWidget(button('Copiar',self.copy,'primary'));actions.addWidget(button('Favorito',self.favorite));self.outer.addLayout(actions)
        self.recent=QListWidget();self.recent.setFlow(QListWidget.LeftToRight);self.recent.setWrapping(True);self.outer.addWidget(self.recent,1)
        self.entry.textChanged.connect(self.update_color);self.recent.itemActivated.connect(lambda item:self.entry.setText(item.data(Qt.UserRole)));shortcut(self,'Ctrl+C',self.copy);shortcut(self,'Ctrl+P',self.capture);self.update_color();self.refresh()
    def update_color(self,*args):
        c=QColor(self.entry.text().strip());self.formats.clear()
        if not c.isValid():self.swatch.setText('Introduce un color válido');return
        value=c.name().upper();h,s,l,_=c.getHslF();self.formats.addItems([value,f'rgb({c.red()}, {c.green()}, {c.blue()})',f'hsl({max(0,h)*360:.0f}, {s*100:.0f}%, {l*100:.0f}%)']);self.swatch.setStyleSheet(f'background:{value};border-radius:12px;color:{"#111" if c.lightness()>140 else "#fff"};font-size:26px;');self.swatch.setText(value)
    def refresh(self):
        self.recent.clear();data=self.store.read()
        for value in dict.fromkeys(data.get('favorites',[])+data.get('recent',[])):
            item=QListWidgetItem(('★ ' if value in data.get('favorites',[]) else '')+value);item.setData(Qt.UserRole,value);item.setForeground(QColor(value));self.recent.addItem(item)
    def copy(self):
        if self.formats.count():QApplication.clipboard().setText(self.formats.currentText());self.store.save(QColor(self.entry.text()).name().upper());self.refresh()
    def favorite(self):
        if self.formats.count():self.store.save(QColor(self.entry.text()).name().upper(),True);self.refresh()
    def capture(self):self.hide();QTimer.singleShot(180,self.start_picker)
    def start_picker(self):
        self.picker=Picker();self.picker.picked.connect(self.picked);self.picker.cancelled.connect(self.present);self.picker.show();self.picker.raise_();self.picker.activateWindow()
    def picked(self,color):self.entry.setText(color.name().upper());self.store.save(color.name().upper());self.refresh();self.present()
