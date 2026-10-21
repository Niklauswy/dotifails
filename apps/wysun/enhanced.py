"""Shared Qt list delegates and the searchable action menu used by the desktop utilities."""
from theme_tokens import apply_style, color, css, paint_color, on_theme_changed

import colorsys,html,json,os,re,subprocess,time,urllib.parse
from pathlib import Path
from PySide6.QtCore import Qt,QSize,QRectF,QPoint,QTimer,QEvent,QMimeData,QUrl,QProcess
from PySide6.QtGui import QPainter,QPen,QColor,QFont,QPixmap,QImage,QIcon,QKeySequence,QShortcut,QTextCharFormat,QTextCursor
from PySide6.QtWidgets import (QApplication,QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QListWidget,QListWidgetItem,QListView,QStyledItemDelegate,QStyle,QTextEdit,QFormLayout,QComboBox,QDialogButtonBox,QMessageBox,QFileDialog,QInputDialog,QSlider,QCalendarWidget)
from orbit import ROOT,STYLE,run,label,divider
from core import HOME,sensitive
from icons import glyph,icon,emoji_pixmap,badge
from ui_motion import MotionButton as QPushButton, WindowMotion
from ui_theme import paint_surface


class ModernDelegate(QStyledItemDelegate):
 def sizeHint(self,opt,index):return QSize(82,82) if (index.data(Qt.UserRole) or {}).get('kind')=='emoji' else QSize(200,57)
 def paint(self,p,opt,index):
  d=index.data(Qt.UserRole) or {};r=opt.rect.adjusted(3,2,-3,-2);selected=bool(opt.state & QStyle.State_Selected);p.save();p.setRenderHint(QPainter.Antialiasing)
  if d.get('kind')=='emoji':
   p.setPen(QPen(color('glyph_muted'),1) if selected else Qt.NoPen);p.setBrush(color('tint',26 if selected else 8));p.drawRoundedRect(r,9,9);pm=emoji_pixmap(d['text'],42);p.drawPixmap(r.center().x()-21,r.center().y()-21,pm)
   if d.get('pinned'):p.drawPixmap(r.right()-17,r.y()+5,glyph('pin',12,'glyph'))
   p.restore();return
  if selected:
   p.setPen(QPen(color('selection_line'),1));p.setBrush(color('selection'));p.drawRoundedRect(r,10,10)
   p.setPen(Qt.NoPen);p.setBrush(color('accent'));p.drawRoundedRect(QRectF(r.x()+1,r.y()+12,3,r.height()-24),1.5,1.5)
  elif opt.state & QStyle.State_MouseOver:p.setPen(Qt.NoPen);p.setBrush(color('row_hover'));p.drawRoundedRect(r,10,10)
  box=QRectF(r.x()+12,r.y()+11,32,32);pm=d.get('thumbnail')
  if isinstance(pm,QPixmap) and not pm.isNull():
   p.drawPixmap(box.toRect(),pm.scaled(32,32,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation))
  elif d.get('clip_kind')=='color' or d.get('color_value'):
   c=paint_color(d.get('color_value') or color_value(d.get('text','')),'muted');p.setBrush(c);p.setPen(QPen(c.lighter(125),1));p.drawRoundedRect(box.adjusted(4,4,-4,-4),6,6)
  else:
   themed=QIcon(d.get('icon','')) if d.get('icon','').startswith('/') else QIcon.fromTheme(d.get('icon',''))
   if d.get('kind')=='app' and not themed.isNull():themed.paint(p,box.toRect())
   else:p.drawPixmap(box.x()+1,box.y()+1,badge(d.get('mode',d.get('clip_kind',d.get('key',d.get('icon',d.get('kind','file'))))),30))
  tag=d.get('tag','') if r.width()>500 else '';p.setFont(QFont('Inter',10));p.setPen(color('text'));tw=p.fontMetrics().horizontalAdvance(tag)+20 if tag else 0
  p.drawText(r.x()+56,r.y()+24,p.fontMetrics().elidedText(d.get('title',''),Qt.ElideRight,r.width()-66-tw))
  p.setFont(QFont('Inter',8));p.setPen(color('glyph_muted'));p.drawText(r.x()+56,r.y()+42,p.fontMetrics().elidedText(d.get('subtitle','').replace('\n',' '),Qt.ElideRight,r.width()-67))
  if tag:p.drawText(r.right()-tw,r.y()+25,tag)
  if d.get('pinned'):p.drawPixmap(r.right()-16,r.y()+5,glyph('pin',11))
  p.restore()

class ActionDelegate(QStyledItemDelegate):
 def sizeHint(self,opt,index):return QSize(300,23 if (index.data(Qt.UserRole) or {}).get('kind')=='section' else 36)
 def paint(self,p,opt,index):
  d=index.data(Qt.UserRole) or {};r=opt.rect.adjusted(2,1,-2,-1);p.save();p.setRenderHint(QPainter.Antialiasing)
  if opt.state & QStyle.State_Selected:p.setPen(Qt.NoPen);p.setBrush(color('tint',26));p.drawRoundedRect(r,6,6)
  if d.get('kind')=='section':
   p.setFont(QFont('Inter',8));p.setPen(color('subtle'));p.drawText(r.x()+9,r.y()+17,d.get('title',''));p.restore();return
  danger=d.get('icon')=='trash';tone='danger' if danger else 'glyph';p.drawPixmap(r.x()+9,r.y()+8,glyph(d.get('icon','arrow-right'),16,tone));p.setFont(QFont('Inter',9));p.setPen(color(tone));key=d.get('subtitle','').replace('Ctrl + ','Ctrl ').replace('Alt + ','Alt ');w=p.fontMetrics().horizontalAdvance(key)+14 if key else 0;p.drawText(r.x()+35,r.y()+22,p.fontMetrics().elidedText(d.get('title',''),Qt.ElideRight,r.width()-46-w))
  if key:
   x=r.right()-w-7;p.setPen(QPen(color('line_strong'),1));p.setBrush(color('tint',5));p.drawRoundedRect(QRectF(x,r.y()+7,w,20),4,4);p.setPen(color('muted'));p.setFont(QFont('Inter',8));p.drawText(QRectF(x,r.y()+7,w,20),Qt.AlignCenter,key)
  p.restore()

class SearchMenu(WindowMotion,QDialog):
 def __init__(self,parent,entries,title='Buscar acciones…'):
  super().__init__(parent,Qt.Popup|Qt.FramelessWindowHint);self.setAttribute(Qt.WA_TranslucentBackground);self.setFixedWidth(350);self.entries=entries
  layout=QVBoxLayout(self);layout.setContentsMargins(7,7,7,7);layout.setSpacing(4);self.search=QLineEdit();self.search.setPlaceholderText(title);self.search.setFixedHeight(32);apply_style(self.search,'font-size:12px; background:transparent; border:none; padding:4px 8px;');layout.addWidget(self.search);self.search.setVisible(len(entries)>7 or title!='Buscar acciones…');self.list=QListWidget();apply_style(self.list,'QListWidget {padding:0; background:transparent;}');self.list.setItemDelegate(ActionDelegate());self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);layout.addWidget(self.list);self.search.textChanged.connect(self.render);self.search.returnPressed.connect(self.choose);self.list.itemClicked.connect(self.choose);self.list.itemActivated.connect(self.choose);self.render();self.search.installEventFilter(self)
 def paintEvent(self,event):paint_surface(self,14)
 def render(self):
  q=self.search.text().casefold();self.list.clear()
  for title,key,fn in self.entries:
   if key=='section':
    if not q:
     i=QListWidgetItem();i.setData(Qt.UserRole,dict(title=title,kind='section'));i.setFlags(Qt.NoItemFlags);self.list.addItem(i)
    continue
   if q in title.casefold():
    name=next((symbol for word,symbol in [('eliminar','trash'),('olvidar','trash'),('borrar','trash'),('fij','pin'),('copiar','copy'),('pegar','clipboard'),('vim','terminal'),('editar','pencil'),('imagen','image'),('abrir','external-link'),('guardar','download'),('rgb','palette'),('hex','palette'),('hsl','palette'),('actualizar','refresh-cw'),('ajustes','settings'),('detalles','eye'),('pausar','circle-pause'),('reanudar','circle-play'),('más','ellipsis'),('favoritos','pin')] if word in title.casefold()),'arrow-right')
    i=QListWidgetItem();i.setData(Qt.UserRole,dict(title=title,subtitle=key,kind='action',icon=name,callback=fn));self.list.addItem(i)
  self.list.setCurrentRow(next((i for i in range(self.list.count()) if self.list.item(i).flags() & Qt.ItemIsEnabled),-1));self.setFixedHeight(min(430,18+sum(23 if self.list.item(i).data(Qt.UserRole).get('kind')=='section' else 36 for i in range(self.list.count()))+(36 if not self.search.isHidden() else 0)))
 def choose(self,*_):
  i=self.list.currentItem()
  if i and callable(i.data(Qt.UserRole).get('callback')):fn=i.data(Qt.UserRole)['callback'];self.accept();QTimer.singleShot(0,fn)
 def eventFilter(self,o,e):
  if e.type()==QEvent.KeyPress and e.key() in (Qt.Key_Down,Qt.Key_Up):
   direction=1 if e.key()==Qt.Key_Down else -1;row=self.list.currentRow()+direction
   while 0<=row<self.list.count() and not self.list.item(row).flags() & Qt.ItemIsEnabled:row+=direction
   if 0<=row<self.list.count():self.list.setCurrentRow(row)
   return True
  return super().eventFilter(o,e)
 def present(self,anchor):
  screen=anchor.screen().availableGeometry();point=anchor.mapToGlobal(QPoint(anchor.width()-self.width(),anchor.height()+5))
  if point.y()+self.height()>screen.bottom():point.setY(anchor.mapToGlobal(QPoint()).y()-self.height()-5)
  point.setX(max(screen.left()+8,min(point.x(),screen.right()-self.width()-8)));self.move(point);self.show();(self.list if self.search.isHidden() else self.search).setFocus()
