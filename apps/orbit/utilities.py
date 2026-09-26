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


from processes_window import ProcessesWindow


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
