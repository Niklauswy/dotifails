"""Keyboard-first clipboard controls with native button and menu semantics."""
from PySide6.QtCore import Qt,QSize,QRectF,Signal
from PySide6.QtGui import QPainter,QColor,QPen,QFont,QIcon
from PySide6.QtWidgets import QMenu,QStyle,QStyleOptionButton
from ui_motion import MotionButton
from icons import icon

class ActionMenu(QMenu):
    def command(self,symbol,title,callback,shortcut=''):
        action=self.addAction(icon(symbol,18,'#d9dce3'),title+('\t'+shortcut if shortcut else ''),callback)
        action.setIconVisibleInMenu(True);return action
    def section(self,title):
        action=self.addSection(title);return action

class CopyButton(MotionButton):
    menuRequested=Signal()
    def __init__(self,callback,parent=None):
        super().__init__('Copiar',parent);self.clicked.connect(callback);self.setIcon(icon('copy',18));self.setIconSize(QSize(18,18));self.setMinimumHeight(34);self._menu_press=False;self.setObjectName('clipCopy')
        self.setAccessibleName('Copiar. Ctrl+Shift+C abre los formatos');self.setToolTip('Copiar · Ctrl+C\nFormatos · Ctrl+Shift+C')
    def sizeHint(self):return super().sizeHint()+QSize(34,0)
    def _content_rect(self,option):return super()._content_rect(option).adjusted(0,0,-26,0)
    def _paint_label(self,painter,option):
        super()._paint_label(painter,option);x=self.width()-28
        painter.setPen(QPen(QColor(255,255,255,28),1));painter.drawLine(x,8,x,self.height()-8)
        icon('chevron-down',14,'#b9bdc8').paint(painter,x+6,(self.height()-14)//2,14,14)
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and event.position().x()>=self.width()-28:
            self._menu_press=True;self.setDown(True);self.pressed.emit();event.accept();return
        super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        if self._menu_press:
            self._menu_press=False;self.setDown(False);self.released.emit();event.accept()
            if self.rect().contains(event.position().toPoint()):self.menuRequested.emit()
            return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Down and event.modifiers()&Qt.AltModifier:self.menuRequested.emit();event.accept();return
        super().keyPressEvent(event)

class ColorValueRow(MotionButton):
    def __init__(self,name,number,callback,parent=None):
        super().__init__('',parent);self.name=name;self.number=number;self.value='';self.shortcut_prefix='Alt+';self.setObjectName('clipColorRow');self.setMinimumHeight(32);self.setFocusPolicy(Qt.StrongFocus);self.clicked.connect(callback)
    def set_value(self,value):
        self.value=value;self.setText(self.name+' '+value);self.setAccessibleName(f'Copiar {self.name}: {value}. {self.shortcut_prefix}{self.number}');self.setToolTip(f'Copiar {self.name} · {self.shortcut_prefix}{self.number}');self.update()
    def _paint_label(self,painter,option):
        rect=self._content_rect(option);painter.setFont(self.font());painter.setPen(QColor('#9da1ac'));painter.drawText(rect.adjusted(0,0,-1,0),Qt.AlignLeft|Qt.AlignVCenter,self.name)
        font=QFont('DejaVu Sans Mono');font.setPixelSize(11 if rect.width()<360 else 12);painter.setFont(font);painter.setPen(QColor('#eceef3'));painter.drawText(rect.adjusted(44 if rect.width()<360 else 56,0,-64 if rect.width()>=360 else 0,0),Qt.AlignLeft|Qt.AlignVCenter,self.value)
        painter.setFont(self.font());painter.setPen(QColor('#80858f'));
        if rect.width()>=360:painter.drawText(rect,Qt.AlignRight|Qt.AlignVCenter,f'{self.shortcut_prefix}{self.number}')
