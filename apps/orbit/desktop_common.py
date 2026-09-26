"""Shared native surfaces and safe editor/terminal launchers."""
import os, shutil, subprocess, tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
from icons import icon

def launch(args):
    return subprocess.Popen([str(a) for a in args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

def terminal_args(command, title='Órbita · Terminal'):
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

PANEL_STYLE='''
QWidget { background: transparent; color: #E8EAF0; font-family: Inter; font-size: 13px; }
QWidget#page { background: transparent; }
QLabel#title { font-size: 20px; font-weight: 600; }
QLabel#subtitle { color: #9396A4; font-size: 12px; }
QPushButton { padding: 8px 12px; border-radius: 7px; background: transparent; border: 1px solid transparent; color:#B7BBC8; }
QPushButton:hover { background: #30323C; color:#F4F5F8; }
QPushButton:focus { border-color:#788CB9; }
QPushButton:checked { background: #343642; color: #EFF0F7; border:1px solid #454853; }
QPushButton#primary { background:#BEC9E5; color:#181B24; font-weight:600; }
QPushButton#danger { color:#EC9BA2; }
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background:#1C1E26; border:1px solid #3A3D48; border-radius:7px; padding:8px; selection-background-color:#444D68; }
QComboBox QAbstractItemView { background:#242731; selection-background-color:#3B4258; }
QListWidget, QTableWidget, QScrollArea { background:transparent; border:none; outline:0; }
QListWidget::item { padding:10px; border-radius:7px; }
QListWidget::item:selected { background:#343742; }
QHeaderView::section { background:#20222B; color:#969BAA; border:0; padding:9px; text-align:left; }
QTableWidget { gridline-color:#32353F; selection-background-color:#363B4C; }
QCheckBox { spacing:10px; padding:7px 0; }
QCheckBox::indicator { width:17px; height:17px; border:1px solid #5A6070; border-radius:5px; background:#20222B; }
QCheckBox::indicator:checked { background:#AABADF; border-color:#C3CDEA; }
QDialog { background:#20222B; }
QSlider::groove:horizontal {height:4px; background:#343B4D; border-radius:2px;}
QSlider::sub-page:horizontal {background:#B8C7E6; border-radius:2px;}
QSlider::handle:horizontal {background:#D3DCF0; width:12px; margin:-4px 0; border-radius:6px;}
QScrollBar:vertical { background:transparent; width:5px; }
QScrollBar::handle:vertical { background:#4A4D59; border-radius:2px; min-height:25px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
'''

def text_label(text,style=''):
    w=QLabel(text);w.setTextFormat(Qt.PlainText);w.setWordWrap(True)
    if style:w.setObjectName(style)
    return w

def button(text,fn,name='',symbol=None):
    b=QPushButton(text);b.setObjectName(name);b.clicked.connect(lambda checked=False:fn())
    if symbol:b.setIcon(icon(symbol));b.setIconSize(QSize(17,17))
    return b

class Surface(QWidget):
    def __init__(self,title,subtitle='',width=760,height=530,parent=None):
        super().__init__(parent,Qt.Window|Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground);self.setWindowTitle(title);self.setStyleSheet(PANEL_STYLE);self.resize(width,height)
        self.outer=QVBoxLayout(self);self.outer.setContentsMargins(22,20,22,16);self.outer.setSpacing(18)
        header=QHBoxLayout();titles=QVBoxLayout();titles.setSpacing(4);titles.addWidget(text_label(title,'title'))
        if subtitle:titles.addWidget(text_label(subtitle,'subtitle'))
        header.addLayout(titles,1);close=button('',self.close,symbol='x');close.setFixedSize(30,30);header.addWidget(close,0,Qt.AlignTop);self.outer.addLayout(header)
        QShortcut(QKeySequence('Escape'),self).activated.connect(self.close)
        self.drag_start=None
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor(139,147,172,65),1));p.setBrush(QColor(22,24,31,242));p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),15,15)
    def present(self):
        screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();r=screen.availableGeometry()
        self.move(r.x()+(r.width()-self.width())//2,r.y()+max(24,(r.height()-self.height())//3));self.show();self.raise_();self.activateWindow()
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton and e.position().y()<75:self.drag_start=e.globalPosition().toPoint()-self.pos()
    def mouseMoveEvent(self,e):
        if self.drag_start is not None and e.buttons()&Qt.LeftButton:self.move(e.globalPosition().toPoint()-self.drag_start)
    def mouseReleaseEvent(self,e):self.drag_start=None
