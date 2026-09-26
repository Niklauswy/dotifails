#!/usr/bin/env python3
"""Órbita: resident native command palette for BSPWM/X11."""
import argparse, ctypes, ctypes.util, datetime as dt, json, os, re, socket, subprocess, sys, time
from pathlib import Path
from urllib.parse import quote
from PySide6.QtCore import Qt, QTimer, QSize, QRectF, QBuffer, QByteArray, QIODevice, QThread, Signal, QUrl, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QIcon, QPixmap, QImage, QCursor, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QStyledItemDelegate, QStyle, QFrame, QPlainTextEdit, QComboBox, QMenu, QDialog, QDialogButtonBox, QFormLayout, QMessageBox)

from core import Store, STATE, HOME, calculate, applications, file_index, sensitive, expand_snippet

ROOT=Path(__file__).resolve().parent
SOCKET=str(Path(os.environ.get('XDG_RUNTIME_DIR','/tmp'))/f'orbit-{os.getuid()}.sock')
MODES={'home':('Órbita','Buscar aplicaciones, comandos o calcular…'),'clipboard':('Portapapeles','Buscar en el historial…'),'files':('Archivos','Buscar por nombre o ruta…'),'snippets':('Snippets','Buscar fragmentos o abreviaturas…'),'calculator':('Calculadora','24 × 8 / 16 · 15% de 80 · 10 km a mi'),'windows':('Ventanas','Buscar ventanas abiertas…'),'emoji':('Emoji','Buscar emoji…')}
STYLE='''
QWidget { color: #eeeef2; font-family: "Inter", "Noto Sans"; font-size: 13px; }
QLineEdit { background: transparent; border: none; padding: 8px 4px; font-size: 17px; selection-background-color: #68578e; }
QListWidget { background: transparent; border: none; outline: none; padding: 3px; }
QPushButton { background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 7px 10px; color: #a4a4af; }
QPushButton:hover { background: #34343e; color: #fff; }
QPushButton:checked { background: #393441; color: #ece2ff; border-color: #51475f; }
QPushButton#primary { background: #e7ddf5; color: #211b2b; font-weight: 600; }
QPushButton#primary:hover { background: #f4edff; }
QLabel#muted { color: #9d9da8; font-size: 12px; }
QLabel#section { color: #a4a4af; font-size: 12px; font-weight: 600; }
QLabel#previewTitle { font-size: 16px; font-weight: 600; }
QPlainTextEdit { background: transparent; border: none; font-size: 13px; selection-background-color: #554767; }
QComboBox { background: #202026; border: 1px solid #41414a; padding: 5px 10px; border-radius: 6px; min-width: 92px; }
QComboBox QAbstractItemView { background: #24242b; selection-background-color: #46404e; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 4px 0; }
QScrollBar::handle:vertical { background: #555560; border-radius: 2px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: #25252d; border: 1px solid #484852; border-radius: 9px; padding: 6px; }
QMenu::item { padding: 9px 30px 9px 12px; border-radius: 5px; }
QMenu::item:selected { background: #41404b; }
QMenu::separator { height: 1px; background: #40404a; margin: 5px; }
QDialog { background: #202027; }
QDialog QLineEdit, QDialog QPlainTextEdit { background: #17171d; border: 1px solid #42424c; border-radius: 6px; padding: 9px; }
QToolTip { background: #2b2b34; color: #eee; border: 1px solid #50505d; padding: 5px; }
'''

def run(args):
    subprocess.Popen([str(a) for a in args],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

def divider():
    w=QFrame();w.setFixedHeight(1);w.setStyleSheet('background: rgba(190,190,210,22);');return w

def label(text='',name=''):
    x=QLabel(text);x.setTextFormat(Qt.PlainText)
    if name:x.setObjectName(name)
    return x

class Indexer(QThread):
    ready=Signal(object)
    def run(self):self.ready.emit(file_index())

class PreviewJob(QThread):
    ready=Signal(str,object)
    def __init__(self,path):super().__init__();self.path=path
    def run(self):
        p=Path(self.path); result={}
        try:
            st=p.stat();result['meta']=f'{p.parent}\n\n{st.st_size/1024:,.1f} KB  ·  Modificado {dt.datetime.fromtimestamp(st.st_mtime):%d/%m/%Y %H:%M}'
            ext=p.suffix.lower()
            if ext in ('.png','.jpg','.jpeg','.webp','.gif','.bmp','.svg'):
                from PySide6.QtGui import QImageReader
                reader=QImageReader(str(p));sz=reader.size()
                if sz.width()>0: reader.setScaledSize(sz.scaled(720,480,Qt.KeepAspectRatio))
                result['image']=reader.read()
            elif ext=='.pdf':
                r=subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','650','-png',str(p)],capture_output=True,timeout=4)
                if r.returncode==0: result['image']=QImage.fromData(r.stdout)
            elif ext in ('.mp4','.mkv','.webm','.mov'):
                r=subprocess.run(['ffmpeg','-v','error','-i',str(p),'-frames:v','1','-vf','scale=640:-1','-f','image2pipe','-vcodec','png','-'],capture_output=True,timeout=4)
                if r.returncode==0: result['image']=QImage.fromData(r.stdout)
            elif st.st_size<2*1024*1024:
                with p.open('rb') as f:data=f.read(20000)
                if b'\0' not in data: result['text']=data.decode('utf-8',errors='replace')
        except (OSError,subprocess.SubprocessError):result['text']='Vista previa no disponible. Pulsa Enter para abrir.'
        self.ready.emit(str(p),result)

class RowDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(220,55)
    def paint(self,p,option,index):
        item=index.data(Qt.UserRole) or {};rect=option.rect.adjusted(3,2,-3,-2)
        p.save();p.setRenderHint(QPainter.Antialiasing)
        if option.state & QStyle.State_Selected:
            p.setPen(Qt.NoPen);p.setBrush(QColor(230,220,255,26));p.drawRoundedRect(rect,7,7)
        icon=QIcon.fromTheme(item.get('icon',''))
        if not icon.isNull():icon.paint(p,rect.x()+12,rect.y()+13,25,25)
        else:
            p.setPen(Qt.NoPen);p.setBrush(QColor(item.get('color','#b4a0dc')));p.drawRoundedRect(QRectF(rect.x()+12,rect.y()+13,25,25),6,6)
            p.setPen(QColor('#17131e'));p.setFont(QFont('Noto Sans',12,QFont.Bold));p.drawText(QRectF(rect.x()+12,rect.y()+12,25,26),Qt.AlignCenter,item.get('glyph','⌘'))
        width=rect.width()-65;tag=item.get('tag','') if rect.width()>470 else ''
        p.setFont(QFont('Inter',10));tw=p.fontMetrics().horizontalAdvance(tag)+22 if tag else 0
        p.setPen(QColor('#efeff4'));p.drawText(rect.x()+49,rect.y()+23,p.fontMetrics().elidedText(item.get('title',''),Qt.ElideRight,width-tw))
        p.setFont(QFont('Inter',9));p.setPen(QColor('#a4a4b0'));p.drawText(rect.x()+49,rect.y()+40,p.fontMetrics().elidedText(item.get('subtitle','').replace('\n',' '),Qt.ElideRight,width))
        if tag:p.drawText(rect.right()-tw,rect.y()+25,tag)
        p.restore()

class SnippetDialog(QDialog):
    def __init__(self,parent,item=None):
        super().__init__(parent);self.setWindowTitle('Editar snippet' if item else 'Nuevo snippet');self.resize(560,420)
        item=item or {};layout=QVBoxLayout(self);form=QFormLayout();self.title=QLineEdit(item.get('title',''));self.shortcut=QLineEdit(item.get('shortcut',''));self.body=QPlainTextEdit(item.get('body',''))
        form.addRow('Nombre',self.title);form.addRow('Abreviatura',self.shortcut);layout.addLayout(form);layout.addWidget(self.body)
        layout.addWidget(label('Variables: {date}, {time}, {datetime}. Busca la abreviatura en Órbita.','muted'))
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('Guardar');buttons.button(QDialogButtonBox.Cancel).setText('Cancelar');buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def save(self):
        if not self.title.text().strip() or not self.body.toPlainText().strip():self.title.setFocus();return
        self.accept()

class Orbit(QWidget):
    def __init__(self,store=None,test=False):
        super().__init__(None,Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.setWindowTitle('Órbita');self.setAttribute(Qt.WA_TranslucentBackground);self.resize(860,550)
        self.store=store or Store();self.test=test;self.mode='home';self.apps=applications();self.files=[];self.indexer=None;self.jobs=[];self.preview_path='';self.ignore_clip=False;self.source_window='';self.socket_buffers={}
        self.emojis=[]
        emoji_file=ROOT/'assets/emojis.txt'
        if emoji_file.exists():
            self.emojis=[tuple(line.split(' ',1)) for line in emoji_file.read_text().splitlines() if ' ' in line]
        self.paused=self.store.get('paused')=='1';self.usage=self.store.usages();self.build_ui();self.commands=self.make_commands();self.render()
        self.clipboard=QApplication.clipboard()
        if not test:self.clipboard.dataChanged.connect(self.capture_clip)
        self.prune_timer=QTimer(self);self.prune_timer.timeout.connect(self.store.prune);self.prune_timer.start(3600000)
        self.installEventFilter(self);self.search.installEventFilter(self);self.results.installEventFilter(self)
        for seq,fn in [('Ctrl+Return',self.paste_selected),('Escape',self.escape),('Ctrl+K',self.actions),('Ctrl+N',self.new_snippet),('Alt+1',lambda:self.set_mode('home')),('Alt+2',lambda:self.set_mode('clipboard')),('Alt+3',lambda:self.set_mode('files')),('Alt+4',lambda:self.set_mode('snippets')),('Alt+5',lambda:self.set_mode('calculator')),('Ctrl+Backspace',lambda:self.set_mode('home'))]:
            sc=QShortcut(QKeySequence(seq),self);sc.activated.connect(fn)
        self.debounce=QTimer(self);self.debounce.setSingleShot(True);self.debounce.setInterval(65);self.debounce.timeout.connect(self.render);self.search.textChanged.connect(lambda:self.debounce.start())
        if not test:QTimer.singleShot(2000,self.start_index)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor(170,164,185,70),1));p.setBrush(QColor(22,22,28,226));p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),15,15)
    def build_ui(self):
        outer=QVBoxLayout(self);outer.setContentsMargins(1,8,1,1);outer.setSpacing(0)
        top=QHBoxLayout();top.setContentsMargins(17,7,17,12);top.setSpacing(10)
        self.back=QPushButton('⌘');self.back.setFixedSize(31,31);self.back.clicked.connect(lambda:self.set_mode('home'));top.addWidget(self.back)
        self.search=QLineEdit();self.search.setPlaceholderText(MODES['home'][1]);self.search.setClearButtonEnabled(True);top.addWidget(self.search,1)
        self.filter=QComboBox();self.filter.addItems(['Todos','Texto','Imagen','Color','Enlace']);self.filter.currentIndexChanged.connect(self.render);self.filter.hide();top.addWidget(self.filter)
        self.new=QPushButton('+ Nuevo');self.new.clicked.connect(self.new_snippet);self.new.hide();top.addWidget(self.new)
        outer.addLayout(top);outer.addWidget(divider())
        content=QHBoxLayout();content.setContentsMargins(8,0,8,0);content.setSpacing(0)
        left=QWidget();self.left=left;ll=QVBoxLayout(left);ll.setContentsMargins(6,12,6,5);ll.setSpacing(6);self.heading=label('Sugerencias','section');ll.addWidget(self.heading)
        self.results=QListWidget();self.results.setItemDelegate(RowDelegate());self.results.setVerticalScrollMode(QListWidget.ScrollPerPixel);self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.results.currentRowChanged.connect(self.preview);self.results.itemActivated.connect(self.activate);self.results.itemClicked.connect(self.preview);ll.addWidget(self.results,1)
        self.empty=label('');self.empty.setAlignment(Qt.AlignCenter);self.empty.setWordWrap(True);self.empty.setStyleSheet('color:#a4a4b0; padding:35px;');self.empty.hide();ll.addWidget(self.empty,1);content.addWidget(left,1)
        self.inspector=QWidget();self.inspector.setMinimumWidth(440);self.inspector.setStyleSheet('QWidget#inspector { border-left: 1px solid rgba(190,190,210,22); }');self.inspector.setObjectName('inspector')
        pr=QVBoxLayout(self.inspector);pr.setContentsMargins(23,22,18,18);pr.setSpacing(12);self.preview_title=label('','previewTitle');self.preview_title.setWordWrap(True);pr.addWidget(self.preview_title)
        self.picture=QLabel();self.picture.setAlignment(Qt.AlignCenter);self.picture.setMinimumHeight(160);self.picture.hide();pr.addWidget(self.picture,1)
        self.calc_result=label('');self.calc_result.setAlignment(Qt.AlignCenter);self.calc_result.setWordWrap(True);self.calc_result.setStyleSheet('font-size: 44px; font-weight: 600; color: #eeeaf4;');self.calc_result.hide();pr.addWidget(self.calc_result,1)
        self.body=QPlainTextEdit();self.body.setReadOnly(True);pr.addWidget(self.body,1)
        self.metadata=label('','muted');self.metadata.setWordWrap(True);pr.addWidget(divider());pr.addWidget(self.metadata);content.addWidget(self.inspector,1);self.inspector.hide();outer.addLayout(content,1)
        outer.addWidget(divider());footer=QHBoxLayout();footer.setContentsMargins(16,7,12,7);self.status=label('Órbita · Local','muted');footer.addWidget(self.status,1);self.go=QPushButton('Abrir  ↵');self.go.clicked.connect(self.activate);footer.addWidget(self.go);self.action_button=QPushButton('Acciones  ⌃ K');self.action_button.clicked.connect(self.actions);footer.addWidget(self.action_button);outer.addLayout(footer)
        outer.addWidget(divider());dock=QHBoxLayout();dock.setContentsMargins(14,7,14,9);dock.setSpacing(4);self.tabs={}
        for i,(key,title) in enumerate([('home','⌘  Inicio'),('clipboard','▣  Historial'),('files','⌕  Archivos'),('snippets','{ }  Snippets'),('calculator','=  Calcular')]):
            b=QPushButton(title);b.setCheckable(True);b.setToolTip(f'Alt + {i+1}');b.clicked.connect(lambda checked=False,k=key:self.set_mode(k));dock.addWidget(b);self.tabs[key]=b
        dock.addStretch();self.private=QPushButton('Historial activo');self.private.setToolTip('Pausar o reanudar la captura del portapapeles');self.private.clicked.connect(self.toggle_capture);dock.addWidget(self.private);outer.addLayout(dock);self.update_private()
    def make_commands(self):
        defs=[('clipboard','Historial del portapapeles','Texto, imágenes, colores y enlaces','edit-paste','▣'),('files','Buscar archivos','Vista previa de imágenes, documentos y vídeo','system-search','⌕'),('snippets','Buscar snippets','Tus fragmentos de texto, siempre a mano','text-x-generic','{}'),('calculator','Calculadora','Operaciones, porcentajes y conversiones','accessories-calculator','='),('windows','Cambiar de ventana','Busca entre tus ventanas abiertas','preferences-system-windows','▤'),('emoji','Buscar emoji','Encuentra y copia un emoji','face-smile','☺')]
        rows=[dict(kind='mode',mode=k,title=t,subtitle=s,icon=ic,glyph=g,tag='Comando',key=k) for k,t,s,ic,g in defs]
        scripts=HOME/'.local/bin'
        for key,title,subtitle,cmd,icon in [
            ('terminal','Nueva terminal','Ghostty · inicio rápido',[str(HOME/'.local/bin/desktop-terminal')],'utilities-terminal'),
            ('screenshot','Capturar pantalla','Seleccionar una región',['flameshot','gui'],'camera-photo'),
            ('network','Conexiones de red','Wi-Fi, Ethernet y VPN',[str(scripts/'orbit'),'network'],'network-wireless'),
            ('notes','Notas rápidas','Abrir tus notas locales',[str(scripts/'orbit'),'notes'],'accessories-text-editor'),
            ('wallpaper','Cambiar fondo de pantalla','Personaliza tu escritorio',[str(scripts/'orbit'),'settings','wallpaper'],'preferences-desktop-wallpaper'),
            ('color','Elegir un color','Tomar un color de la pantalla',[str(scripts/'orbit'),'color'],'applications-graphics'),
            ('audio','Ajustes de sonido','Volumen y dispositivos',['pavucontrol'],'audio-volume-high'),
            ('mute','Silenciar / activar sonido','Salida de audio actual',['pactl','set-sink-mute','@DEFAULT_SINK@','toggle'],'audio-volume-muted'),
            ('notifications','Pausar / reanudar notificaciones','Modo concentración',['dunstctl','set-paused','toggle'],'preferences-desktop-notification'),
            ('compositor','Alternar transparencia y animaciones','Picom',[str(scripts/'desktop-compositor'),'toggle'],'preferences-desktop'),
            ('settings','Configuración de Órbita','Abrir configuración y guía',['xdg-open',str(ROOT/'README.md')],'preferences-system')]:
            if Path(cmd[0]).exists() or __import__('shutil').which(cmd[0]):rows.append(dict(kind='command',title=title,subtitle=subtitle,cmd=cmd,icon=icon,key=key,tag='Comando'))
        return rows
    def start_index(self):
        if self.indexer and self.indexer.isRunning():return
        self.indexer=Indexer();self.indexer.ready.connect(self.index_ready);self.indexer.start()
    def index_ready(self,files):self.files=files;self.indexed_at=time.monotonic();self.render() if self.mode=='files' else None
    def set_mode(self,mode):
        if mode not in MODES:mode='home'
        self.mode=mode;self.search.clear();self.filter.setCurrentIndex(0);self.search.setPlaceholderText(MODES[mode][1]);self.back.setText('⌘' if mode=='home' else '←');self.filter.setVisible(mode=='clipboard');self.new.setVisible(mode=='snippets');self.inspector.setVisible(mode in ('clipboard','files','snippets','calculator'));self.left.setMaximumWidth(355 if self.inspector.isVisible() else 16777215)
        for k,b in self.tabs.items():b.setChecked(k==mode)
        if mode=='files' and time.monotonic()-getattr(self,'indexed_at',0)>300:self.start_index()
        self.render();self.search.setFocus()
    def show_mode(self,mode='home'):
        if mode=='toggle' and self.isVisible():self.hide();return
        if not self.isVisible() and not self.test:
            try:self.source_window=subprocess.check_output(['bspc','query','-N','-n','focused'],text=True,timeout=.3).strip()
            except subprocess.SubprocessError:self.source_window=''
        self.set_mode('home' if mode=='toggle' else mode)
        screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();r=screen.availableGeometry();w=min(860,r.width()-48);h=min(550,r.height()-60);self.resize(w,h);self.move(r.x()+(r.width()-w)//2,r.y()+max(25,int((r.height()-h)*.35)))
        self.show();self.raise_();self.activateWindow();self.search.setFocus()
    def escape(self):
        if self.search.text():self.search.clear()
        elif self.mode!='home':self.set_mode('home')
        else:self.hide()
    def eventFilter(self,obj,event):
        if obj==self and event.type()==QEvent.WindowDeactivate and not self.test:
            QTimer.singleShot(100,self.hide_if_inactive)
        if event.type()==QEvent.KeyPress:
            if event.key() in (Qt.Key_Down,Qt.Key_Up) and obj==self.search:
                self.results.setCurrentRow(max(0,min(self.results.count()-1,self.results.currentRow()+(1 if event.key()==Qt.Key_Down else -1))));return True
            if event.key() in (Qt.Key_Return,Qt.Key_Enter) and obj==self.search:self.activate();return True
        return super().eventFilter(obj,event)
    def hide_if_inactive(self):
        if self.isVisible() and not self.isActiveWindow() and not QApplication.activePopupWidget() and not QApplication.activeModalWidget():self.hide()
    def render(self):
        q=self.search.text().strip();fold=q.casefold();rows=[];heading=MODES[self.mode][0]
        if self.mode=='home':
            rows=self.commands+self.apps
            if fold:
                words=fold.split();rows=[r for r in rows if all(w in (r['title']+' '+r.get('subtitle','')).casefold() for w in words)]
                rows.sort(key=lambda r:(not r['title'].casefold().startswith(fold),-self.usage.get(r.get('key',''),0)))
                for s in self.store.snippets():
                    if fold in (s['title']+' '+s['shortcut']).casefold():rows.append(dict(s,kind='snippet',subtitle=s['shortcut'],tag='Snippet',glyph='{}'))
                answer=calculate(q)
                if answer is not None:rows.insert(0,dict(title=answer,subtitle=q+'  →  Copiar resultado',kind='calc',query=q,result=answer,glyph='=',tag='Calculadora',color='#b9d7b2'))
                if not rows:rows=[dict(title='Buscar en DuckDuckGo',subtitle=q,kind='web',query=q,glyph='⌕',tag='Web')]
                heading='Resultados'
            else:
                rows=sorted(self.commands,key=lambda r:-self.usage.get(r['key'],0))[:6]+sorted(self.apps,key=lambda r:-self.usage.get(r['key'],0))[:12];heading='Sugerencias'
        elif self.mode=='clipboard':
            choice=self.filter.currentText();kinds={'Texto':'text','Imagen':'image','Color':'color','Enlace':'url'}
            for r in self.store.clips():
                if fold not in r['text'].casefold() or (choice in kinds and r['kind']!=kinds[choice]):continue
                kind=r['kind'];rows.append(dict(r,clip_kind=kind,kind='clip',title=r['text'].split('\n')[0][:110] if kind!='image' else r['text'],subtitle=dt.datetime.fromtimestamp(r['stamp']).strftime('%d %b · %H:%M'),glyph={'image':'▧','color':'●','url':'↗','text':'▤'}.get(kind,'▤'),color=r['text'] if kind=='color' else '#b4a0dc',tag=kind))
            heading='Últimos 7 días'
        elif self.mode=='snippets':
            rows=[dict(r,kind='snippet',subtitle=r['shortcut'] or 'Fragmento de texto',glyph='{}') for r in self.store.snippets() if fold in (r['title']+' '+r['shortcut']+' '+r['body']).casefold()];heading='Tus fragmentos'
        elif self.mode=='files':
            terms=fold.split()
            if terms:
                matches=[x for x in self.files if all(t in x[2] for t in terms)];matches.sort(key=lambda x:(not x[0].startswith(fold),len(x[2])))
            else:matches=sorted(self.files,key=lambda x:(not x[1].startswith(str(HOME/'Downloads')),len(x[2])))[:80]
            rows=[dict(kind='file',title=Path(p).name,subtitle=str(Path(p).parent).replace(str(HOME),'~'),path=p,icon='text-x-generic',tag='Archivo') for _,p,_ in matches[:150]];heading=f'{len(self.files):,} archivos · por nombre' if self.files else 'Preparando índice…'
        elif self.mode=='calculator':
            answer=calculate(q)
            if answer is not None:rows=[dict(kind='calc',title=answer,subtitle=q,query=q,result=answer,glyph='=',color='#b9d7b2')]
            elif not q:rows=[dict(kind='calc',title=r['result'],subtitle=r['query'],query=r['query'],result=r['result'],glyph='=') for r in self.store.calcs()]
            heading='Resultado' if q else 'Historial de cálculos'
        elif self.mode=='windows':
            try:
                tree=json.loads(subprocess.check_output(['bspc','wm','-d'],timeout=1))
                def visit(n):
                    if not n:return
                    if n.get('client'):
                        c=n['client'];title=c.get('className','Ventana');wid=hex(n['id'])
                        try:
                            title=subprocess.check_output(['xprop','-id',wid,'_NET_WM_NAME'],text=True,timeout=.2).split(' = ',1)[-1].strip().strip('"')
                        except subprocess.SubprocessError:pass
                        if 'Órbita' not in title and fold in (title+' '+c.get('className','')).casefold():rows.append(dict(kind='window',title=title,subtitle=c.get('className',''),wid=wid,glyph='▤'))
                    visit(n.get('firstChild'));visit(n.get('secondChild'))
                for m in tree['monitors']:
                    for d in m['desktops']:visit(d.get('root'))
            except (subprocess.SubprocessError,ValueError,KeyError):pass
        elif self.mode=='emoji':
            defaults=[('😀','sonrisa feliz'),('😂','risa lágrimas'),('❤️','amor corazón'),('✨','brillos magia'),('👍','bien pulgar'),('🙏','gracias manos'),('🎉','fiesta celebración'),('🔥','fuego'),('🚀','cohete lanzar'),('💡','idea luz'),('✅','listo correcto'),('👀','ojos mirar'),('💻','computadora trabajo'),('☕','café'),('🌙','luna noche'),('🫶','corazón manos'),('🤔','pensar duda'),('😎','genial gafas'),('🥹','emoción'),('💜','corazón morado')]
            for emoji,name in defaults+self.emojis:
                if fold in name.casefold():rows.append(dict(kind='emoji',title=emoji+'  '+name,subtitle='Copiar emoji',text=emoji,glyph=emoji))
        if self.mode=='emoji':
            seen=set();rows=[r for r in rows if not (r['text'] in seen or seen.add(r['text']))]
        self.heading.setText(heading);self.results.blockSignals(True);self.results.clear()
        for row in rows[:150]:
            item=QListWidgetItem();item.setData(Qt.UserRole,row);self.results.addItem(item)
        self.results.blockSignals(False);self.results.setVisible(bool(rows));self.empty.setVisible(not rows)
        self.empty.setText({'clipboard':'El historial empieza con tu próxima copia.\n\nTexto, imágenes, enlaces y colores.\nPuedes pausarlo en cualquier momento.','snippets':'Tus respuestas y fragmentos, a un atajo.\n\nPulsa + Nuevo o Ctrl + N.','calculator':'Escribe una operación.\n\n24 × 8 / 16\n15% de 80\n10 km a mi'}.get(self.mode,'No hay resultados. Prueba otra búsqueda.'))
        if rows:self.results.setCurrentRow(0)
        else:self.preview()
        self.status.setText(f'{MODES[self.mode][0]}  ·  {len(rows)} resultados' if rows else MODES[self.mode][0])
        self.go.setText('Copiar  ↵' if self.mode in ('clipboard','snippets','calculator','emoji') else 'Abrir  ↵')
    def current(self):return self.results.currentItem().data(Qt.UserRole) if self.results.currentItem() else None
    def preview(self,*args):
        if not self.inspector.isVisible():return
        r=self.current();self.preview_path='';self.picture.clear();self.picture.hide();self.calc_result.hide();self.body.show();self.body.clear();self.preview_title.setText('');self.metadata.clear()
        if not r:return
        self.preview_title.setText(r['title'][:100]);kind=r['kind']
        if kind=='clip':
            if r['clip_kind']=='image':self.show_image(QImage.fromData(self.store.blob(r['id']) or b''))
            elif r['clip_kind']=='color':
                pix=QPixmap(220,165);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor(r['text']).darker(140),5));p.setBrush(QColor(r['text']));p.drawEllipse(58,24,104,104);p.end();self.picture.setPixmap(pix);self.picture.show();self.body.hide()
            else:self.body.setPlainText(r['text'])
            self.metadata.setText(f"Tipo  ·  {r['clip_kind']}\nCopiado  ·  {dt.datetime.fromtimestamp(r['stamp']):%d/%m/%Y %H:%M}\n{len(r['text']):,} caracteres  ·  {len(r['text'].split()):,} palabras")
        elif kind=='snippet':self.body.setPlainText(expand_snippet(r['body']));self.metadata.setText(f"Abreviatura  ·  {r['shortcut'] or '—'}\n{len(r['body'])} caracteres · Ctrl + K para editar")
        elif kind=='calc':
            self.preview_title.setText(r['query']);self.body.hide();self.calc_result.setText(r['result']);self.calc_result.show();self.metadata.setText('Enter para copiar el resultado\nCálculo local · sin enviar datos')
        elif kind=='file':
            self.preview_path=r['path'];self.metadata.setText(r['path']);self.body.setFont(QFont('Noto Sans',10));self.body.setPlainText('Cargando vista previa…');QTimer.singleShot(100,lambda path=r['path']:self.start_preview(path))
        if kind!='calc':self.body.setFont(QFont('Noto Sans',10))
    def start_preview(self,path):
        if path!=self.preview_path or not path or len(self.jobs)>=2 or any(j.path==path for j in self.jobs):return
        job=PreviewJob(path);self.jobs.append(job);job.ready.connect(self.preview_ready);job.finished.connect(lambda j=job:self.finish_job(j));job.start()
    def finish_job(self,job):
        if job in self.jobs:self.jobs.remove(job)
        job.deleteLater()
        if self.preview_path and self.body.toPlainText()=='Cargando vista previa…':self.start_preview(self.preview_path)
    def preview_ready(self,path,data):
        if path!=self.preview_path:return
        self.body.setPlainText(data.get('text','Pulsa Enter para abrir con tu aplicación.'));self.metadata.setText(data.get('meta',path))
        if 'image' in data:self.show_image(data['image'])
    def show_image(self,img):
        if img.isNull():return
        self.picture.setPixmap(QPixmap.fromImage(img).scaled(380,270,Qt.KeepAspectRatio,Qt.SmoothTransformation));self.picture.show();self.body.hide()
    def capture_clip(self):
        if self.ignore_clip or self.paused:return
        mime=self.clipboard.mimeData()
        if not mime:return
        formats=mime.formats()
        if sensitive('',formats):return
        if mime.hasImage():
            image=self.clipboard.image()
            if image.isNull() or image.width()*image.height()>25_000_000:return
            data=QByteArray();buf=QBuffer(data);buf.open(QIODevice.WriteOnly);image.save(buf,'PNG');self.store.clip('image',f'Imagen · {image.width()} × {image.height()}',bytes(data))
        elif mime.hasText():
            text=mime.text()
            if not text.strip() or sensitive(text,formats):return
            kind='color' if re.fullmatch(r'#[\da-fA-F]{6}',text.strip()) else 'url' if re.fullmatch(r'https?://\S+',text.strip()) else 'text'
            self.store.clip(kind,text)
        if self.isVisible() and self.mode=='clipboard':self.render()
    def copy(self,text=None,image=None):
        self.ignore_clip=True
        if image is not None:self.clipboard.setImage(image)
        else:self.clipboard.setText(text or '')
        QTimer.singleShot(150,lambda:setattr(self,'ignore_clip',False))
        self.hide()
    def activate(self,*args):
        r=self.current()
        if not r:return
        kind=r['kind']
        if r.get('key'):self.store.use(r['key']);self.usage=self.store.usages()
        if kind=='mode':self.set_mode(r['mode'])
        elif kind=='app':run(['gio','launch',r['path']]);self.hide()
        elif kind=='command':self.hide();run(r['cmd'])
        elif kind=='file':QDesktopServices.openUrl(QUrl.fromLocalFile(r['path']));self.hide()
        elif kind=='web':QDesktopServices.openUrl(QUrl('https://duckduckgo.com/?q='+quote(r['query'])));self.hide()
        elif kind=='window':self.hide();run(['bspc','node',r['wid'],'-f'])
        elif kind=='clip':
            if r['clip_kind']=='image':self.copy(image=QImage.fromData(self.store.blob(r['id']) or b''))
            else:self.copy(r['text'])
        elif kind=='snippet':self.copy(expand_snippet(r['body']))
        elif kind=='calc':self.store.record_calc(r['query'],r['result']);self.copy(r['result'])
        elif kind=='emoji':self.copy(r['text'])
    def paste_selected(self):
        r=self.current()
        if not r or r['kind'] not in ('clip','snippet','calc','emoji'):return
        target=self.source_window;self.activate()
        if not self.test and target:QTimer.singleShot(120,lambda:self.paste_to(target))
    def paste_to(self,target):
        try:
            current=subprocess.check_output(['bspc','query','-N','-n','focused'],text=True,timeout=.3).strip()
            if current.lower()!=target.lower():return
            x=ctypes.CDLL(ctypes.util.find_library('X11'));xt=ctypes.CDLL(ctypes.util.find_library('Xtst'))
            x.XOpenDisplay.restype=ctypes.c_void_p;d=x.XOpenDisplay(None)
            if not d:return
            x.XKeysymToKeycode.argtypes=[ctypes.c_void_p,ctypes.c_ulong];x.XKeysymToKeycode.restype=ctypes.c_uint
            xt.XTestFakeKeyEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
            ctrl=x.XKeysymToKeycode(d,0xffe3);v=x.XKeysymToKeycode(d,0x76)
            for key,down in [(ctrl,1),(v,1),(v,0),(ctrl,0)]:xt.XTestFakeKeyEvent(d,key,down,0)
            x.XFlush.argtypes=[ctypes.c_void_p];x.XFlush(d);x.XCloseDisplay.argtypes=[ctypes.c_void_p];x.XCloseDisplay(d)
        except (OSError,subprocess.SubprocessError):pass
    def new_snippet(self):
        self.edit_snippet(None)
    def edit_snippet(self,r):
        dialog=SnippetDialog(self,r)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.store.save_snippet(dialog.title.text().strip(),dialog.shortcut.text().strip(),dialog.body.toPlainText(),r.get('id') if r else None);self.set_mode('snippets')
    def toggle_capture(self):self.paused=not self.paused;self.store.set('paused','1' if self.paused else '0');self.update_private()
    def update_private(self):
        if hasattr(self,'private'):self.private.setText('◌  Historial pausado' if self.paused else '●  Historial activo')
    def actions(self):
        menu=QMenu(self);r=self.current()
        if r:
            menu.addAction('Copiar' if r['kind'] in ('clip','snippet','calc','emoji') else 'Abrir',self.activate)
            if r['kind'] in ('clip','snippet','calc','emoji'):menu.addAction('Pegar en la ventana anterior  Ctrl+Enter',self.paste_selected)
            if r['kind']=='snippet':
                menu.addAction('Editar snippet',lambda:self.edit_snippet(r));menu.addAction('Eliminar snippet',lambda:self.delete_item(r))
            if r['kind']=='clip':menu.addAction('Eliminar del historial',lambda:self.delete_item(r))
            if r['kind']=='file':
                menu.addAction('Copiar ruta',lambda:self.copy(r['path']));menu.addAction('Abrir carpeta',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(r['path']).parent))))
        menu.addSeparator();menu.addAction('Nuevo snippet',self.new_snippet);menu.addAction('Actualizar aplicaciones e índice',self.refresh_sources)
        menu.addAction('Reanudar historial' if self.paused else 'Pausar historial',self.toggle_capture);menu.addAction('Borrar historial del portapapeles…',self.clear_history)
        menu.addSeparator();menu.addAction('Volver al inicio',lambda:self.set_mode('home'));menu.popup(self.action_button.mapToGlobal(self.action_button.rect().topLeft())-__import__('PySide6').QtCore.QPoint(120,220));self.menu=menu
    def delete_item(self,r):
        if r['kind']=='clip':self.store.delete_clip(r['id'])
        else:self.store.delete_snippet(r['id'])
        self.render()
    def clear_history(self):
        if QMessageBox.question(self,'Borrar historial','¿Eliminar todo el historial local del portapapeles?',QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:self.store.clear_clips();self.render()
    def refresh_sources(self):self.apps=applications();self.start_index();self.render()
    def closeEvent(self,event):event.ignore();self.hide()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',nargs='?',default='toggle');parser.add_argument('--daemon',action='store_true');args=parser.parse_args()
    os.umask(0o077)
    app=QApplication(['Orbit','--name','Orbit']);app.setApplicationName('Orbit');app.setDesktopFileName('orbit');app.setWindowIcon(QIcon(str(ROOT/'orbit.png')));app.setQuitOnLastWindowClosed(False);app.setStyle('Fusion');app.setStyleSheet(STYLE);QIcon.setThemeSearchPaths([str(HOME/'.local/share/icons'),str(HOME/'.icons'),'/usr/share/icons']);QIcon.setThemeName('Win11-Dark');QIcon.setFallbackThemeName('Adwaita')
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        server.bind(SOCKET)
    except OSError:
        try:
            with socket.socket(socket.AF_UNIX) as sock:
                sock.settimeout(.5);sock.connect(SOCKET);sock.sendall((args.mode+'\n').encode())
            return
        except OSError:
            Path(SOCKET).unlink(missing_ok=True);server.bind(SOCKET)
    os.chmod(SOCKET,0o600);server.listen(8)
    from desktop_v3 import OrbitV3
    win=OrbitV3()
    class IPC(QThread):
        received=Signal(str)
        def run(self):
            while True:
                try:client,_=server.accept()
                except OSError:return
                with client:
                    client.settimeout(.5)
                    try:
                        data=client.recv(256).decode('utf-8',errors='ignore').strip()
                        if data=='ping':client.sendall(b'pong\n')
                        elif data and data!='daemon':self.received.emit(data)
                    except OSError:pass
    ipc=IPC();ipc.received.connect(win.show_mode);ipc.start()
    if not args.daemon:QTimer.singleShot(0,lambda:win.show_mode(args.mode))
    sys.exit(app.exec())
if __name__=='__main__':main()
