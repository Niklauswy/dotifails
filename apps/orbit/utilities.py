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


from notes_window import NotesWindow


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


from color_window import ColorWindow
