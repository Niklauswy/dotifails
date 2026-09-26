"""Órbita 2: visual media, searchable actions and native desktop controls."""
import colorsys,html,json,os,re,subprocess,time,urllib.parse
from pathlib import Path
from PySide6.QtCore import Qt,QSize,QRectF,QPoint,QTimer,QEvent,QMimeData,QUrl,QProcess
from PySide6.QtGui import QPainter,QPen,QColor,QFont,QPixmap,QImage,QIcon,QKeySequence,QShortcut,QTextCharFormat,QTextCursor
from PySide6.QtWidgets import (QApplication,QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QListWidget,QListWidgetItem,QListView,QStyledItemDelegate,QStyle,QTextEdit,QFormLayout,QComboBox,QDialogButtonBox,QMessageBox,QFileDialog,QInputDialog,QSlider,QCalendarWidget)
from orbit import Orbit,MODES,ROOT,STYLE,run,label,divider
from core import HOME,sensitive
from data_v2 import StoreV2,color_value,color_formats,template
from icons import glyph,icon,emoji_pixmap,badge
from media import OCRJob,FaviconJob,png_bytes
from system_panels import NetworkScan,StatusScan,power_rows,split_nm

MODES.update(system=('Sistema','Recursos, memoria y almacenamiento…'),audio=('Sonido','Seleccionar salida de audio…'),notifications=('Notificaciones','Buscar avisos recientes…'),calendar=('Calendario','Calendario local'),network=('Conexiones','Buscar redes, dispositivos o VPN…'),power=('Sesión y energía','Bloquear, suspender, reiniciar…'))

class ModernDelegate(QStyledItemDelegate):
 def sizeHint(self,opt,index):return QSize(82,82) if (index.data(Qt.UserRole) or {}).get('kind')=='emoji' else QSize(200,49)
 def paint(self,p,opt,index):
  d=index.data(Qt.UserRole) or {};r=opt.rect.adjusted(3,2,-3,-2);selected=bool(opt.state & QStyle.State_Selected);p.save();p.setRenderHint(QPainter.Antialiasing)
  if d.get('kind')=='emoji':
   p.setPen(QPen(QColor('#b6b3c2'),1) if selected else Qt.NoPen);p.setBrush(QColor(255,255,255,26 if selected else 8));p.drawRoundedRect(r,9,9);pm=emoji_pixmap(d['text'],42);p.drawPixmap(r.center().x()-21,r.center().y()-21,pm)
   if d.get('pinned'):p.drawPixmap(r.right()-17,r.y()+5,glyph('pin',12,'#c5c3cf'))
   p.restore();return
  if selected:p.setPen(Qt.NoPen);p.setBrush(QColor(220,220,232,29));p.drawRoundedRect(r,7,7)
  box=QRectF(r.x()+9,r.y()+7,32,32);pm=d.get('thumbnail')
  if isinstance(pm,QPixmap) and not pm.isNull():
   p.drawPixmap(box.toRect(),pm.scaled(32,32,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation))
  elif d.get('clip_kind')=='color' or d.get('color_value'):
   c=QColor(d.get('color_value') or color_value(d.get('text','')) or '#aaaaaa');p.setBrush(c);p.setPen(QPen(c.lighter(125),1));p.drawRoundedRect(box.adjusted(4,4,-4,-4),6,6)
  else:
   themed=QIcon(d.get('icon','')) if d.get('icon','').startswith('/') else QIcon.fromTheme(d.get('icon',''))
   if d.get('kind')=='app' and not themed.isNull():themed.paint(p,box.toRect())
   else:p.drawPixmap(box.x()+1,box.y()+1,badge(d.get('mode',d.get('clip_kind',d.get('key',d.get('icon',d.get('kind','file'))))),30))
  tag=d.get('tag','') if r.width()>500 else '';p.setFont(QFont('Inter',10));p.setPen(QColor('#ededf2'));tw=p.fontMetrics().horizontalAdvance(tag)+20 if tag else 0
  p.drawText(r.x()+51,r.y()+20,p.fontMetrics().elidedText(d.get('title',''),Qt.ElideRight,r.width()-66-tw))
  p.setFont(QFont('Inter',8));p.setPen(QColor('#a5a5b1'));p.drawText(r.x()+51,r.y()+36,p.fontMetrics().elidedText(d.get('subtitle','').replace('\n',' '),Qt.ElideRight,r.width()-67))
  if tag:p.drawText(r.right()-tw,r.y()+25,tag)
  if d.get('pinned'):p.drawPixmap(r.right()-16,r.y()+5,glyph('pin',11))
  p.restore()

class ActionDelegate(QStyledItemDelegate):
 def sizeHint(self,opt,index):return QSize(300,23 if (index.data(Qt.UserRole) or {}).get('kind')=='section' else 36)
 def paint(self,p,opt,index):
  d=index.data(Qt.UserRole) or {};r=opt.rect.adjusted(2,1,-2,-1);p.save();p.setRenderHint(QPainter.Antialiasing)
  if opt.state & QStyle.State_Selected:p.setPen(Qt.NoPen);p.setBrush(QColor(201,211,238,26));p.drawRoundedRect(r,6,6)
  if d.get('kind')=='section':
   p.setFont(QFont('Inter',8));p.setPen(QColor('#9097A8'));p.drawText(r.x()+9,r.y()+17,d.get('title',''));p.restore();return
  danger=d.get('icon')=='trash';color='#E39A9F' if danger else '#D1D4DF';p.drawPixmap(r.x()+9,r.y()+8,glyph(d.get('icon','arrow-right'),16,color));p.setFont(QFont('Inter',9));p.setPen(QColor(color));key=d.get('subtitle','').replace('Ctrl + ','Ctrl ').replace('Alt + ','Alt ');w=p.fontMetrics().horizontalAdvance(key)+14 if key else 0;p.drawText(r.x()+35,r.y()+22,p.fontMetrics().elidedText(d.get('title',''),Qt.ElideRight,r.width()-46-w))
  if key:
   x=r.right()-w-7;p.setPen(QPen(QColor('#4B505D'),1));p.setBrush(QColor(255,255,255,5));p.drawRoundedRect(QRectF(x,r.y()+7,w,20),4,4);p.setPen(QColor('#A8AEBE'));p.setFont(QFont('Inter',8));p.drawText(QRectF(x,r.y()+7,w,20),Qt.AlignCenter,key)
  p.restore()

class SearchMenu(QDialog):
 def __init__(self,parent,entries,title='Buscar acciones…'):
  super().__init__(parent,Qt.Popup|Qt.FramelessWindowHint);self.setAttribute(Qt.WA_TranslucentBackground);self.setFixedWidth(350);self.entries=entries
  layout=QVBoxLayout(self);layout.setContentsMargins(7,7,7,7);layout.setSpacing(4);self.search=QLineEdit();self.search.setPlaceholderText(title);self.search.setFixedHeight(32);self.search.setStyleSheet('font-size:12px; background:transparent; border:none; padding:4px 8px;');layout.addWidget(self.search);self.search.setVisible(len(entries)>7 or title!='Buscar acciones…');self.list=QListWidget();self.list.setStyleSheet('QListWidget {padding:0; background:transparent;}');self.list.setItemDelegate(ActionDelegate());self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);layout.addWidget(self.list);self.search.textChanged.connect(self.render);self.search.returnPressed.connect(self.choose);self.list.itemClicked.connect(self.choose);self.list.itemActivated.connect(self.choose);self.render();self.search.installEventFilter(self)
 def paintEvent(self,event):
  p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor(127,137,162,85),1));p.setBrush(QColor(28,30,38,249));p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),10,10)
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

class RichSnippet(QDialog):
 def __init__(self,parent,item=None):
  super().__init__(parent);r=item or {};self.setWindowTitle('Editar snippet' if item else 'Crear snippet');self.resize(720,480)
  outer=QVBoxLayout(self);columns=QHBoxLayout();left=QVBoxLayout();left.addWidget(label('CONTENIDO','section'));self.body=QTextEdit();self.body.setAcceptRichText(True)
  if r.get('html'):self.body.setHtml(r['html'])
  else:self.body.setPlainText(r.get('body',''))
  left.addWidget(self.body);tools=QHBoxLayout()
  for title,attr in [('B','bold'),('I','italic'),('U','underline'),('S̶','strike')]:
   b=QPushButton(title);b.setFixedWidth(38);b.clicked.connect(lambda checked=False,a=attr:self.format(a));tools.addWidget(b)
  tools.addStretch();left.addLayout(tools);columns.addLayout(left,3)
  right=QFormLayout();self.title=QLineEdit(r.get('title',''));self.shortcut=QLineEdit(r.get('shortcut',''));self.icons=QComboBox()
  for k,n in [('snippet','Código'),('file','Documento'),('clipboard','Portapapeles'),('globe','Web'),('clock','Fecha'),('emoji','Personal')]:self.icons.addItem(icon(k),n,k)
  self.icons.setCurrentIndex(max(0,self.icons.findData(r.get('icon','snippet'))));right.addRow('Nombre',self.title);right.addRow('Abreviatura',self.shortcut);right.addRow('Icono',self.icons);columns.addLayout(right,2);outer.addLayout(columns,1)
  hint=label('Variables: {clipboard}, {date}, {date+4}, {time}, {week}.','muted');outer.addWidget(hint);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('Guardar snippet');buttons.button(QDialogButtonBox.Cancel).setText('Cancelar');buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);outer.addWidget(buttons);QShortcut(QKeySequence('Ctrl+Return'),self).activated.connect(self.save)
 def format(self,attr):
  f=self.body.currentCharFormat()
  if attr=='bold':f.setFontWeight(QFont.Normal if f.fontWeight()>=QFont.Bold else QFont.Bold)
  elif attr=='italic':f.setFontItalic(not f.fontItalic())
  elif attr=='underline':f.setFontUnderline(not f.fontUnderline())
  else:f.setFontStrikeOut(not f.fontStrikeOut())
  self.body.mergeCurrentCharFormat(f);self.body.setFocus()
 def save(self):
  if self.title.text().strip() and self.body.toPlainText().strip():self.accept()
  else:self.title.setFocus()

class OrbitV2(Orbit):
 def __init__(self,store=None,test=False):
  self.v2ready=False;self.ocr_job=None;self.favicon_jobs=[];self.icon_cache={};self.icon_requested=set();self.network_rows=[];self.network_scan=None;self.nm_process=None;self.process_output='';self.capture_source='';self.network_busy=False;self.status_scan=None;self.status_rows=[]
  super().__init__(store or StoreV2(),test)
  self.v2ready=True;self.clip_filter='Todos';self.emoji_category='Todos';self.emoji_pins=json.loads(self.store.get('emoji_pins','["❤️","👋","👍","🚀","🎉","🙏"]'))
  self.results.setItemDelegate(ModernDelegate());self.results.setSpacing(1);self.filter.hide();self.filter_button=QPushButton('Todos  ⌄');self.filter_button.clicked.connect(self.filter_menu);self.layout().itemAt(0).layout().insertWidget(2,self.filter_button);self.filter_button.hide()
  self.back.setText('');self.back.setIcon(icon('back'));self.action_button.setText('Acciones  ⌃ K');self.status.setStyleSheet('font-size:11px; color:#a4a4af;')
  for k,b in self.tabs.items():b.setIcon(icon('search' if k=='home' else k,20));b.setText({'home':'Inicio','clipboard':'Historial','files':'Archivos','snippets':'Snippets','calculator':'Calcular'}[k])
  self.emoji_tab=QPushButton();self.emoji_tab.setIcon(icon('emoji',20));self.emoji_tab.setToolTip('Emoji');self.emoji_tab.clicked.connect(lambda:self.set_mode('emoji'));self.layout().itemAt(self.layout().count()-1).layout().insertWidget(5,self.emoji_tab)
  self.volume_slider=QSlider(Qt.Horizontal);self.volume_slider.setRange(0,100);self.volume_slider.sliderReleased.connect(self.set_volume);self.volume_slider.hide();self.inspector.layout().insertWidget(1,self.volume_slider)
  self.status_timer=QTimer(self);self.status_timer.setInterval(3000);self.status_timer.timeout.connect(lambda:self.scan_status() if self.isVisible() and self.mode=='system' else None);self.status_timer.start()
  self.metadata.setTextFormat(Qt.RichText);self.metadata.setMinimumHeight(76)
  for seq,fn in [('Ctrl+P',self.pin_current),('Ctrl+D',self.delete_current),('Ctrl+Shift+Return',lambda:self.paste_selected(keep=True))]:QShortcut(QKeySequence(seq),self).activated.connect(fn)
  self.set_mode('home')
  if not test:QTimer.singleShot(1200,self.next_ocr)
 def set_mode(self,mode):
  if not self.v2ready:return super().set_mode(mode)
  if mode=='calendar':self.show_calendar();return
  self.clip_filter='Todos';self.emoji_category='Todos';self.filter_button.setText('Todos  ⌄');self.results.setViewMode(QListView.IconMode if mode=='emoji' else QListView.ListMode);self.results.setMovement(QListView.Static);self.results.setResizeMode(QListView.Adjust);self.results.setWrapping(mode=='emoji');self.results.setGridSize(QSize(85,84) if mode=='emoji' else QSize());self.results.setSpacing(3 if mode=='emoji' else 1)
  super().set_mode(mode);self.filter.hide();self.filter_button.setVisible(mode in ('clipboard','emoji'));self.inspector.setVisible(mode in ('clipboard','files','snippets','calculator','network','power','system','audio','notifications'));self.left.setMaximumWidth(325 if self.inspector.isVisible() else 16777215)
  self.back.setText('');self.volume_slider.setVisible(mode=='audio')
  if mode=='network':self.scan_network()
  if mode in ('system','audio','notifications'):self.status_rows=[];self.scan_status()
  self.render()
 def make_commands(self):
  rows=super().make_commands()
  rows=[r for r in rows if r.get('key')!='network']
  rows.extend([dict(kind='mode',mode=k,title=t,subtitle=d,icon=k,key=k,tag='Control') for k,t,d in [('system','Estado del sistema','Memoria, carga y batería'),('audio','Sonido y dispositivos','Volumen y salidas de audio'),('notifications','Centro de notificaciones','Historial y modo concentración'),('calendar','Calendario','Consultar fechas')]])
  rows.insert(6,dict(kind='mode',mode='network',title='Conexiones de red',subtitle='Wi-Fi, dispositivos y VPN',icon='network',key='network',tag='Super + N'))
  rows.insert(7,dict(kind='mode',mode='power',title='Sesión y energía',subtitle='Bloquear, suspender, reiniciar y apagar',icon='power',key='power',tag='Super + X'))
  return rows
 def render(self):
  if not self.v2ready:return super().render()
  if self.mode not in ('clipboard','emoji','network','power','system','audio','notifications'):return super().render()
  q=self.search.text().strip().casefold();rows=[];heading=MODES[self.mode][0]
  selected=self.current();old_id=selected.get('id') if selected else None
  if self.mode=='clipboard':
   types={'Texto':'text','Imágenes':'image','Colores':'color','Enlaces':'url','Archivos':'files'}
   for r in self.store.clips():
    text=r['text'];search=' '.join([text,r.get('ocr',''),r.get('source','')]).casefold()
    if not all(w in search for w in q.split()):continue
    if self.clip_filter in types and r['kind']!=types[self.clip_filter]:continue
    if self.clip_filter=='Fijados' and not r['pinned']:continue
    kind=r['kind'];row=dict(r,clip_kind=kind,kind='clip',title=text.split('\n')[0][:120],subtitle=(r.get('source') or 'Origen anterior')+' · '+__import__('datetime').datetime.fromtimestamp(r['stamp']).strftime('%H:%M'),color_value=color_value(text) if kind=='color' else None)
    if kind=='files':
     paths=json.loads(r['meta']).get('paths',[]);row['title']=Path(paths[0]).name+(f' y {len(paths)-1} más' if len(paths)>1 else '') if paths else 'Archivos'
    if r.get('thumb'):row['thumbnail']=self.thumbnail(r['id'],r['thumb'])
    elif kind=='url':
     host=urllib.parse.urlsplit(text.strip()).hostname or '';key='favicon:'+host
     if key in self.icon_cache:row['thumbnail']=self.icon_cache[key]
     elif not self.test and host not in self.icon_requested and len(self.favicon_jobs)<2:self.request_favicon(text.strip())
    rows.append(row)
   heading='Fijados y recientes' if any(r['pinned'] for r in rows) else 'Recientes · búsqueda en texto e imágenes'
  elif self.mode=='emoji':
   base=[('❤️','corazón amor heart'),('👋','saludo mano wave'),('👍','bien pulgar thumb'),('🚀','cohete rocket'),('🎉','fiesta celebración party'),('🙏','gracias manos pray'),('😀','sonrisa feliz grinning'),('😂','risa lágrimas laugh'),('🥹','emoción emocion'),('💜','corazón morado purple heart')]+self.emojis
   seen=set();categories={'Caras':r'face|smil|grin|laugh|cry|kiss','Personas':r'person|woman|man |people|hand|thumb|finger','Animales':r'cat|dog|bird|animal|bear|lion|tiger|fish|whale','Comida':r'food|fruit|apple|cake|coffee|bread|rice|pizza|drink','Símbolos':r'heart|arrow|symbol|sign|button|flag'}
   for emoji,name in base:
    if emoji in seen:continue
    seen.add(emoji);pin=emoji in self.emoji_pins
    if self.emoji_category=='Favoritos' and not pin:continue
    if self.emoji_category in categories and not re.search(categories[self.emoji_category],name,re.I):continue
    if not all(w in (emoji+' '+name).casefold() for w in q.split()):continue
    rows.append(dict(kind='emoji',title=name.split('|')[0],text=emoji,subtitle='Enter copia · Ctrl+Enter pega · Ctrl+P fija',pinned=pin))
   rows.sort(key=lambda r:not r['pinned']);heading='Favoritos primero · Emoji y símbolos'
  elif self.mode=='network':rows=[r for r in self.network_rows if q in (r['title']+' '+r.get('subtitle','')).casefold()];heading='Actualizando…' if self.network_scan and self.network_scan.isRunning() else 'Wi-Fi · dispositivos · VPN'
  elif self.mode in ('system','audio','notifications'):rows=[r for r in self.status_rows if q in (r['title']+' '+r.get('subtitle','')).casefold()];heading=MODES[self.mode][0]
  elif self.mode=='power':rows=[r for r in power_rows() if q in (r['title']+' '+r['subtitle']).casefold()];heading='Tu sesión'
  self.results.blockSignals(True);self.results.clear()
  for row in rows:
   item=QListWidgetItem();item.setData(Qt.UserRole,row);item.setToolTip(row['title']);self.results.addItem(item)
  self.results.blockSignals(False);self.heading.setText(heading);self.results.setVisible(bool(rows));self.empty.setVisible(not rows);self.empty.setText('No hay resultados para esta búsqueda.' if q else 'No hay elementos todavía.');self.status.setText(f'{MODES[self.mode][0]} · {len(rows)} elementos');self.go.setText('Conectar  ↵' if self.mode=='network' else 'Continuar  ↵' if self.mode=='power' else 'Copiar  ↵')
  index=next((i for i,r in enumerate(rows) if old_id and r.get('id')==old_id),0);self.results.setCurrentRow(index if rows else -1)
  if not rows:self.preview()
 def thumbnail(self,ident,data):
  if ident not in self.icon_cache:self.icon_cache[ident]=QPixmap.fromImage(QImage.fromData(data))
  return self.icon_cache[ident]
 def filter_menu(self):
  choices=['Todos','Fijados','Texto','Imágenes','Archivos','Enlaces','Colores'] if self.mode=='clipboard' else ['Todos','Favoritos','Caras','Personas','Animales','Comida','Símbolos']
  self.popup=SearchMenu(self,[(c,'',lambda value=c:self.choose_filter(value)) for c in choices],'Buscar tipo…');self.popup.present(self.filter_button)
 def choose_filter(self,value):
  if self.mode=='clipboard':self.clip_filter=value
  else:self.emoji_category=value
  self.filter_button.setText(value+'  ⌄');self.render()
 def table(self,rows):
  return '<table width="100%" cellspacing="0" cellpadding="5">'+''.join('<tr><td style="color:#a2a2af">'+html.escape(str(k))+'</td><td align="right" style="color:#e7e7ee">'+html.escape(str(v))+'</td></tr>' for k,v in rows)+'</table>'
 def preview(self,*args):
  if not self.v2ready:return super().preview(*args)
  r=self.current()
  if self.mode=='emoji':
   if r:self.status.setText(r['title'].split('|')[0][:75]);self.go.setText('Copiar emoji  ↵')
   return
  if not r or r['kind'] not in ('clip','snippet','wifi','network_action','network_device','power','info','status_action','notification'):return super().preview(*args)
  self.preview_path='';self.calc_result.hide();self.picture.clear();self.picture.hide();self.body.clear();self.body.show();self.preview_title.show();self.preview_title.setText(r['title'][:80]);self.metadata.clear()
  if r['kind']=='clip':
   kind=r['clip_kind'];meta=json.loads(r.get('meta') or '{}');info=[('Aplicación',r.get('source') or 'No registrada en la versión anterior'),('Tipo',{'text':'Texto','color':'Color','image':'Imagen','url':'Enlace','files':'Archivos'}.get(kind,kind)),('Copiado',__import__('datetime').datetime.fromtimestamp(r['stamp']).strftime('%d/%m/%Y, %H:%M'))]
   if kind=='image':
    self.preview_title.hide();img=QImage.fromData(self.store.blob(r['id']) or b'');self.show_image(img);info.insert(2,('Dimensiones',f'{meta.get("width",img.width())} × {meta.get("height",img.height())}'));info.insert(3,('Tamaño',f'{(r.get("bytes") or 0)/1024:,.1f} KB'));info.append(('Texto reconocido','Disponible' if r.get('ocr') else 'Procesando…' if not r.get('ocr_done') else 'Sin texto legible'))
   elif kind=='color':
    self.preview_title.hide();c=color_value(r['text']);pm=QPixmap(230,230);pm.fill(Qt.transparent);p=QPainter(pm);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor('#eeeeee'),2));p.setBrush(QColor('#ffffff'));p.drawRoundedRect(QRectF(16,8,198,206),9,9);p.setPen(Qt.NoPen);p.setBrush(QColor(c[:7]));p.drawRoundedRect(QRectF(20,12,190,151),6,6);p.setFont(QFont('Inter',11));p.setPen(QColor('#292930'));p.drawText(29,195,c);p.end();self.picture.setPixmap(pm);self.picture.show();self.body.hide();info.append(('RGB',color_formats(r['text'])['RGB']))
   elif kind=='files':self.body.setPlainText('\n'.join(meta.get('paths',[])));info.append(('Archivos',len(meta.get('paths',[]))))
   else:
    self.body.setPlainText(r['text']);info.append(('Caracteres',f'{len(r["text"]):,}'));info.append(('Palabras',f'{len(r["text"].split()):,}'))
   self.metadata.setText(self.table(info))
  elif r['kind']=='snippet':
   self.body.setPlainText(template(r['body'],self.clipboard.text()));self.metadata.setText(self.table([('Abreviatura',r['shortcut'] or '—'),('Tipo','Texto con formato' if r.get('html') else 'Texto'),('Veces copiado',r.get('uses',0)),('Último uso',__import__('datetime').datetime.fromtimestamp(r['lastused']).strftime('%d/%m/%Y %H:%M') if r.get('lastused') else 'Todavía no utilizado')]))
  else:
   self.body.setPlainText(r.get('detail',r.get('subtitle','')));self.metadata.setText(self.table([('Control','Local · '+('NetworkManager' if self.mode=='network' else 'BSPWM / systemd'))]));self.go.setText('Desconectar  ↵' if r.get('connected') else 'Conectar  ↵' if r['kind']=='wifi' else 'Continuar  ↵')
 def capture_clip(self):
  if not self.v2ready:return super().capture_clip()
  if self.ignore_clip or self.paused:return
  mime=self.clipboard.mimeData()
  if not mime or sensitive('',mime.formats()):return
  source=''
  if not self.test:
   try:
    wid=subprocess.check_output(['bspc','query','-N','-n','focused'],text=True,timeout=.3).strip();raw=subprocess.check_output(['xprop','-id',wid,'WM_CLASS'],text=True,timeout=.3);matches=re.findall(r'"([^"]+)"',raw);source=matches[-1] if matches else '';source={'Brave-browser':'Brave','com.mitchellh.ghostty':'Ghostty','Code':'Visual Studio Code','firefox':'Firefox'}.get(source,source)
   except subprocess.SubprocessError:pass
  if mime.hasUrls() and all(u.isLocalFile() for u in mime.urls()):
   paths=[u.toLocalFile() for u in mime.urls()];self.store.clip('files','\n'.join(paths),source=source,meta={'paths':paths})
  elif mime.hasImage():
   img=self.clipboard.image()
   if img.isNull() or img.width()*img.height()>25_000_000:return
   blob=png_bytes(img);thumb=png_bytes(img.scaled(80,80,Qt.KeepAspectRatio,Qt.SmoothTransformation));self.store.clip('image',f'Imagen · {img.width()} × {img.height()}',blob,source,{'width':img.width(),'height':img.height(),'bytes':len(blob)},thumb);self.next_ocr()
  elif mime.hasText():
   text=mime.text()
   if not text.strip() or sensitive(text,mime.formats()):return
   kind='color' if color_value(text) else 'url' if re.fullmatch(r'https?://\S+',text.strip()) else 'text';self.store.clip(kind,text,source=source)
  if self.isVisible() and self.mode=='clipboard':self.render()
 def next_ocr(self):
  if self.test or self.ocr_job:return
  row=self.store.db.execute("SELECT id,blob FROM clips WHERE kind='image' AND ocr_done=0 ORDER BY stamp DESC LIMIT 1").fetchone()
  if not row:return
  job=OCRJob(row['id'],row['blob']);self.ocr_job=job;job.done.connect(self.ocr_finished);job.finished.connect(self.ocr_cleanup);job.start()
 def ocr_finished(self,ident,text,meta,thumb):
  self.store.save_media(ident,text,meta,thumb)
  if self.isVisible() and self.mode=='clipboard':self.render()
 def ocr_cleanup(self):
  old=self.ocr_job;self.ocr_job=None;old.deleteLater();QTimer.singleShot(100,self.next_ocr)
 def request_favicon(self,url):
  host=urllib.parse.urlsplit(url).hostname or '';self.icon_requested.add(host);job=FaviconJob(url,self.store.root);self.favicon_jobs.append(job);job.done.connect(self.favicon_done);job.finished.connect(lambda j=job:self.favicon_cleanup(j));job.start()
 def favicon_done(self,host,path):
  self.icon_cache['favicon:'+host]=QPixmap(path)
  if self.isVisible() and self.mode=='clipboard':self.render()
 def favicon_cleanup(self,job):
  if job in self.favicon_jobs:self.favicon_jobs.remove(job)
  job.deleteLater()
 def pin_current(self):
  r=self.current()
  if not r:return
  if r['kind']=='clip':self.store.pin(r['id'])
  elif r['kind']=='emoji':
   if r['text'] in self.emoji_pins:self.emoji_pins.remove(r['text'])
   else:self.emoji_pins.append(r['text'])
   self.store.set('emoji_pins',json.dumps(self.emoji_pins))
  self.render()
 def delete_current(self):
  r=self.current()
  if r and r['kind'] in ('clip','snippet'):self.delete_item(r)
 def activate(self,*args):
  r=self.current()
  if not self.v2ready or not r:return super().activate(*args)
  if r['kind'] in ('status_action','notification'):run(r['action']);QTimer.singleShot(350,self.scan_status);return
  if r['kind']=='info':return
  if r['kind']=='power':self.power_action(r);return
  if r['kind']=='wifi':
   self.network_command(['nmcli','--ask','--wait','25','device','disconnect',r['device']] if r['connected'] else ['nmcli','--ask','--wait','25','device','wifi','connect',r['ssid'],'ifname',r['device']]);return
  if r['kind']=='network_action':self.network_command(r['action']);return
  if r['kind']=='network_device':return
  if r['kind']=='snippet':
   self.store.used_snippet(r['id']);mime=QMimeData();mime.setText(template(r['body'],self.clipboard.text()))
   if r.get('html'):mime.setHtml(template(r['html'],html.escape(self.clipboard.text())))
   self.ignore_clip=True;self.clipboard.setMimeData(mime);QTimer.singleShot(150,lambda:setattr(self,'ignore_clip',False));self.hide();return
  if r['kind']=='clip' and r['clip_kind']=='files':
   mime=QMimeData();paths=json.loads(r['meta']).get('paths',[]);mime.setUrls([QUrl.fromLocalFile(p) for p in paths]);mime.setData('x-special/gnome-copied-files',('copy\n'+'\n'.join(QUrl.fromLocalFile(p).toString() for p in paths)).encode());self.ignore_clip=True;self.clipboard.setMimeData(mime);QTimer.singleShot(150,lambda:setattr(self,'ignore_clip',False));self.hide();return
  super().activate(*args)
 def paste_selected(self,keep=False):
  r=self.current()
  if not r or r['kind'] not in ('clip','snippet','calc','emoji'):return
  target=self.source_window;mode=self.mode;self.activate()
  if not self.test and target:
   QTimer.singleShot(140,lambda:self.paste_to(target))
   if keep:QTimer.singleShot(330,lambda:self.show_mode(mode))
 def edit_snippet(self,r):
  dialog=RichSnippet(self,r)
  if dialog.exec()==QDialog.DialogCode.Accepted:
   self.store.rich_snippet(dialog.title.text().strip(),dialog.shortcut.text().strip(),dialog.body.toPlainText(),dialog.body.toHtml(),dialog.icons.currentData(),r.get('id') if r else None);self.set_mode('snippets')
 def actions(self):
  if not self.v2ready:return super().actions()
  r=self.current();entries=[]
  if r:
   copyable=r['kind'] in ('clip','snippet','calc','emoji')
   entries.append(('Copiar al portapapeles' if copyable else 'Abrir','Enter',self.activate))
   if copyable:entries.extend([('Pegar en la ventana anterior','Ctrl + Enter',self.paste_selected),('Pegar y mantener Órbita abierta','Ctrl + Shift + Enter',lambda:self.paste_selected(True))])
   if r['kind'] in ('clip','emoji'):entries.append(('Desfijar elemento' if r.get('pinned') else 'Fijar elemento','Ctrl + P',self.pin_current))
   if r['kind']=='clip':
    if r['clip_kind']=='image':entries.extend([('Vista ampliada','',lambda:self.quicklook(r)),('Guardar imagen como…','',lambda:self.save_image(r)),('Abrir en el visor de imágenes','',lambda:self.open_image(r)),('Abrir imagen con…','',lambda:self.open_with(r))])
    if r.get('ocr'):entries.extend([('Copiar texto reconocido (OCR)','',lambda:self.copy(r['ocr'])),('Ver texto reconocido','',lambda:self.show_ocr(r))])
    if r['clip_kind']=='color':
     for key,value in color_formats(r['text']).items():entries.append(('Copiar color como '+key,value,lambda v=value:self.copy(v)))
    if r['clip_kind']=='url':entries.append(('Abrir enlace','',lambda:__import__('PySide6').QtGui.QDesktopServices.openUrl(QUrl(r['text']))))
    if r['clip_kind']=='files':
     paths=json.loads(r['meta']).get('paths',[])
     if paths:entries.append(('Abrir archivo','',lambda:__import__('PySide6').QtGui.QDesktopServices.openUrl(QUrl.fromLocalFile(paths[0]))))
    entries.append(('Eliminar elemento','Ctrl + D',self.delete_current));entries.append(('Eliminar varios…','',self.delete_multiple))
   if r['kind']=='snippet':entries.extend([('Editar snippet','',lambda:self.edit_snippet(r)),('Copiar como texto sin formato','',lambda:self.copy(template(r['body'],self.clipboard.text()))),('Eliminar snippet','Ctrl + D',self.delete_current)])
   if r['kind']=='file':entries.extend([('Copiar ruta','',lambda:self.copy(r['path'])),('Abrir carpeta','',lambda:__import__('PySide6').QtGui.QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(r['path']).parent))))])
  entries.extend([('Nuevo snippet','Ctrl + N',self.new_snippet),('Reanudar historial' if self.paused else 'Pausar historial','',self.toggle_capture),('Borrar historial completo…','',self.clear_history),('Actualizar aplicaciones y archivos','',self.refresh_sources)])
  self.popup=SearchMenu(self,entries);self.popup.present(self.action_button)
 def quicklook(self,r):
  dialog=QDialog(self);dialog.setWindowTitle('Vista ampliada');dialog.resize(1000,700);layout=QVBoxLayout(dialog);image=QImage.fromData(self.store.blob(r['id']) or b'');view=QLabel();view.setAlignment(Qt.AlignCenter);view.setPixmap(QPixmap.fromImage(image).scaled(960,640,Qt.KeepAspectRatio,Qt.SmoothTransformation));layout.addWidget(view);dialog.exec()
 def show_ocr(self,r):
  dialog=QDialog(self);dialog.setWindowTitle('Texto reconocido · OCR local');dialog.resize(640,460);lay=QVBoxLayout(dialog);body=QTextEdit();body.setReadOnly(True);body.setPlainText(r['ocr']);lay.addWidget(body);dialog.exec()
 def save_image(self,r):
  path,_=QFileDialog.getSaveFileName(self,'Guardar imagen',str(HOME/'Pictures/imagen.png'),'PNG (*.png)')
  if path:QImage.fromData(self.store.blob(r['id']) or b'').save(path,'PNG')
 def image_path(self,r):
  folder=HOME/'.cache/orbit/opened';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
  for old in folder.glob('*.png'):
   if time.time()-old.stat().st_mtime>86400:old.unlink(missing_ok=True)
  path=folder/f"clipboard-{r['id']}.png"
  QImage.fromData(self.store.blob(r['id']) or b'').save(str(path),'PNG');path.chmod(0o600);return path
 def open_image(self,r):
  __import__('PySide6').QtGui.QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.image_path(r))));self.hide()
 def open_with(self,r):
  entries=[];path=self.image_path(r)
  try:
   import gi
   gi.require_version('Gio','2.0')
   from gi.repository import Gio
   for app in Gio.AppInfo.get_all_for_type('image/png'):
    ident=app.get_id();desktop=Gio.DesktopAppInfo.new(ident) if ident else None
    if desktop:entries.append((app.get_display_name(),'Abrir imagen',lambda f=desktop.get_filename():run(['gio','launch',f,str(path)])))
  except (ImportError,ValueError):pass
  if not entries:entries=[('Visor predeterminado','',lambda:self.open_image(r))]
  self.popup=SearchMenu(self,entries,'Buscar aplicación…');self.popup.present(self.action_button)
 def delete_multiple(self):
  dialog=QDialog(self);dialog.setWindowTitle('Eliminar del historial');dialog.resize(520,430);lay=QVBoxLayout(dialog);items=QListWidget();lay.addWidget(items)
  for r in self.store.clips():
   item=QListWidgetItem(r['text'].split('\n')[0][:90]);item.setData(Qt.UserRole,r['id']);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);items.addItem(item)
  b=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Ok).setText('Eliminar seleccionados');b.accepted.connect(dialog.accept);b.rejected.connect(dialog.reject);lay.addWidget(b)
  if dialog.exec()==QDialog.DialogCode.Accepted:
   for i in range(items.count()):
    if items.item(i).checkState()==Qt.Checked:self.store.delete_clip(items.item(i).data(Qt.UserRole))
   self.render()
 def scan_network(self):
  if self.network_scan and self.network_scan.isRunning():return
  self.network_scan=NetworkScan();self.network_scan.done.connect(self.network_ready);self.network_scan.finished.connect(lambda:self.render() if self.mode=='network' else None);self.network_scan.start()
 def network_ready(self,rows):self.network_rows=rows;self.render() if self.mode=='network' else None
 def network_command(self,args):
  if self.network_busy:return
  self.network_busy=True;self.process_output='';process=QProcess(self);self.nm_process=process;process.setProcessChannelMode(QProcess.MergedChannels);process.readyReadStandardOutput.connect(self.network_output);process.finished.connect(self.network_finished);process.errorOccurred.connect(lambda *_:self.network_finished(1));process.start(args[0],args[1:]);self.status.setText('Aplicando cambio de red…')
 def network_output(self):
  data=bytes(self.nm_process.readAllStandardOutput()).decode('utf8',errors='replace');self.process_output=(self.process_output+data)[-3000:]
  if re.search(r'password|contrase[ñn]a|psk',data,re.I) and ('?' in data or ':' in data):
   dialog=QInputDialog(self);dialog.setWindowTitle('Conectar a Wi-Fi');dialog.setLabelText('Contraseña de la red');dialog.setTextEchoMode(QLineEdit.Password)
   if dialog.exec()==QDialog.DialogCode.Accepted:self.nm_process.write((dialog.textValue()+'\n').encode())
   else:self.nm_process.kill()
   dialog.setTextValue('');dialog.deleteLater();self.process_output=''
 def network_finished(self,code,*_):
  self.network_busy=False;self.status.setText('Conexión actualizada' if code==0 else 'No se pudo completar el cambio. Revisa la red y vuelve a intentar.');self.process_output='';self.scan_network()
 def power_action(self,r):
  import shutil
  if r['action']=='lock':
   if shutil.which('slock'):run(['slock'])
   elif shutil.which('xflock4'):run(['xflock4'])
   elif shutil.which('i3lock'):run(['i3lock','-c','101015'])
   else:run(['loginctl','lock-session'])
   self.hide();return True
  dialog=QMessageBox(self);dialog.setWindowTitle(r['title']);dialog.setText(r['title']+' el equipo' if r['action'] in ('shutdown','reboot') else r['title']);dialog.setInformativeText('Guarda tu trabajo antes de continuar.' if r['action']!='suspend' else 'Las aplicaciones permanecerán abiertas.');dialog.setStandardButtons(QMessageBox.Yes|QMessageBox.Cancel);dialog.setDefaultButton(QMessageBox.Cancel);dialog.button(QMessageBox.Yes).setText('Confirmar');dialog.button(QMessageBox.Cancel).setText('Cancelar')
  if dialog.exec()==QMessageBox.Yes:
   command={'suspend':['systemctl','suspend'],'logout':['bspc','quit'],'reboot':['systemctl','reboot'],'shutdown':['systemctl','poweroff']}[r['action']];run(command);self.hide();return True
 def scan_status(self):
  if self.mode not in ('system','audio','notifications') or (self.status_scan and self.status_scan.isRunning()):return
  mode=self.mode;self.status_scan=StatusScan(mode);self.status_scan.done.connect(lambda rows,extra,m=mode:self.status_ready(m,rows,extra));self.status_scan.finished.connect(lambda m=mode:QTimer.singleShot(0,self.scan_status) if m!=self.mode else None);self.status_scan.start()
 def status_ready(self,mode,rows,extra):
  if self.mode!=mode:return
  self.status_rows=rows
  if mode=='audio':self.volume_slider.blockSignals(True);self.volume_slider.setValue(extra.get('volume',0));self.volume_slider.blockSignals(False)
  self.render()
 def set_volume(self):
  run(['pactl','set-sink-volume','@DEFAULT_SINK@',str(self.volume_slider.value())+'%']);QTimer.singleShot(300,self.scan_status)
 def show_calendar(self):
  dialog=QDialog(self);dialog.setWindowTitle('Calendario');lay=QVBoxLayout(dialog);calendar=QCalendarWidget();calendar.setGridVisible(False);lay.addWidget(calendar);dialog.resize(480,360);dialog.exec()
 def eventFilter(self,obj,event):
  if getattr(self,'v2ready',False) and self.mode=='emoji' and obj==self.search and event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Down,Qt.Key_Up,Qt.Key_Left,Qt.Key_Right):
   step=max(1,self.results.viewport().width()//85) if event.key() in (Qt.Key_Down,Qt.Key_Up) else 1
   if event.key() in (Qt.Key_Up,Qt.Key_Left):step=-step
   self.results.setCurrentRow(max(0,min(self.results.count()-1,self.results.currentRow()+step)));return True
  return super().eventFilter(obj,event)
