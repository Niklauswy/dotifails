"""Shared native surfaces and safe editor/terminal launchers."""
from theme_tokens import apply_style

import os, shutil, subprocess, tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QCursor, QKeySequence, QShortcut, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication, QSizePolicy
from icons import icon, glyph

def launch(args):
    return subprocess.Popen([str(a) for a in args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

def terminal_args(command, title='Wysun · Terminal'):
    terminal=shutil.which('ghostty')
    if terminal:return [terminal, '--title='+title, '-e', *map(str,command)]
    terminal=shutil.which('x-terminal-emulator') or shutil.which('xterm')
    if not terminal:raise RuntimeError('No se encontró una terminal.')
    return [terminal,'-e',*map(str,command)]

def is_text_file(path):
    try:
        p=Path(path)
        if not p.is_file():return False
        with p.open('rb') as f:data=f.read(4096)
        if b'\0' in data:return False
        data.decode('utf8');return True
    except (OSError,UnicodeDecodeError):return False

def vim_args(path):
    editor=shutil.which('nvim') or shutil.which('vim')
    if not editor:raise RuntimeError('Instala Vim o Neovim para editar archivos.')
    p=Path(path).expanduser().absolute()
    return terminal_args([editor,'--',str(p)],'Vim · '+p.name)

def open_vim(path):return launch(vim_args(path))

def edit_text(text):
    root=Path.home()/'.cache/orbit/editor';root.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(prefix='fragmento-',suffix='.txt',dir=root)
    with os.fdopen(fd,'w') as f:f.write(text)
    open_vim(name);return name

from ui_theme import PANEL_STYLE, paint_surface
from ui_motion import WindowMotion, MotionButton as QPushButton

def text_label(text,style=''):
    w=QLabel(text);w.setTextFormat(Qt.PlainText);w.setWordWrap(True)
    if style:w.setObjectName(style)
    return w

def button(text,fn,name='',symbol=None):
    b=QPushButton(text);b.setObjectName(name);b.clicked.connect(lambda checked=False:fn())
    if not symbol and text.strip().lower().startswith('copiar'):symbol='copy'
    if symbol:b.setIcon(icon(symbol,17,'on_accent') if name=='primary' else icon(symbol));b.setIconSize(QSize(17,17))
    return b

class Surface(WindowMotion, QWidget):
    def __init__(self,title,subtitle='',width=760,height=530,parent=None):
        super().__init__(parent,Qt.Window|Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground);self.setWindowTitle(title);apply_style(self,PANEL_STYLE);self.resize(width,height)
        self.outer=QVBoxLayout(self);self.outer.setContentsMargins(26,24,26,20);self.outer.setSpacing(20)
        header=QHBoxLayout();titles=QVBoxLayout();titles.setSpacing(5);titles.addWidget(text_label('W Y S U N', 'eyebrow'));titles.addWidget(text_label(title,'title'))
        if subtitle:titles.addWidget(text_label(subtitle,'subtitle'))
        header.addLayout(titles,1);close=button('',self.close,symbol='x');close.setFixedSize(36,36);close.setToolTip('Cerrar · Esc');close.setAccessibleName('Cerrar panel');header.addWidget(close,0,Qt.AlignTop);self.outer.addLayout(header)
        QShortcut(QKeySequence('Escape'),self).activated.connect(self.close)
        self.drag_start=None
    def paintEvent(self,event):paint_surface(self)
    def closeEvent(self,event):event.ignore();self.dismiss()
    def present(self):
        if getattr(self, '_motion_exiting', False):
            self.show();self.raise_();self.activateWindow();return
        screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();r=screen.availableGeometry()
        self.resize(min(self.width(),r.width()-32),min(self.height(),r.height()-40))
        if not self.isVisible():self.move(r.x()+(r.width()-self.width())//2,r.y()+max(20,(r.height()-self.height())//3))
        self.show();self.raise_();self.activateWindow()
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton and e.position().y()<75:self.drag_start=e.globalPosition().toPoint()-self.pos()
    def mouseMoveEvent(self,e):
        if self.drag_start is not None and e.buttons()&Qt.LeftButton:self.move(e.globalPosition().toPoint()-self.drag_start)
    def mouseReleaseEvent(self,e):self.drag_start=None


class ElidedLabel(QLabel):
    """Single-line native label that keeps its complete text accessible."""
    def __init__(self,text='',parent=None):
        super().__init__('',parent);self._full='';self.setMinimumWidth(0);self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);self.setText(text)
    def setText(self,text):
        self._full=str(text);self.setToolTip(self._full);self.setAccessibleName(self._full);self._elide()
    def _elide(self):QLabel.setText(self,self.fontMetrics().elidedText(self._full,Qt.ElideRight,max(0,self.width())))
    def resizeEvent(self,event):super().resizeEvent(event);self._elide()
