"""Single-material floating capture launcher, bounded to the active screen."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget,QHBoxLayout,QApplication,QMenu
from .components import button,apply_material


class QuickBar(QWidget):
    def __init__(self, owner):
        super().__init__(None,Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.owner=owner;self.setObjectName('shotQuick');self.setWindowTitle('Wysun Screenshot · Captura rápida')
        self.row=QHBoxLayout(self);self.row.setContentsMargins(20,16,20,16);self.row.setSpacing(8)
        self.mode=button('Región ⌄',self.sources,'region');self.mode.setMinimumWidth(130)
        self.library=button('Biblioteca',owner.show_library,'library')
        self.settings=button('',owner.show_settings,'settings',compact=True);self.settings.setAccessibleName('Ajustes');self.settings.setToolTip('Ajustes')
        self.start=button('Capturar',owner.begin_capture,'region',primary=True);self.start.setMinimumWidth(138)
        self.dismiss=button('',owner.close,'close',compact=True);self.dismiss.setAccessibleName('Cerrar barra');self.dismiss.setToolTip('Cerrar · Esc')
        for b in (self.mode,self.library,self.settings,self.start,self.dismiss):self.row.addWidget(b);b.setFixedHeight(52);b.setIconSize(QSize(24,24))
        self.setStyleSheet('#shotQuick QPushButton {border-radius:24px;padding:8px 12px;background:transparent;border:1px solid transparent;} #shotQuick QPushButton:hover {background:rgba(255,255,255,110);} #shotQuick QPushButton:focus {border:2px solid #2165D5;} #shotQuick QPushButton[primary="true"] {background:#2165D5;color:white;} #shotQuick QPushButton[primary="true"]:hover {background:#1958BE;}')
        apply_material(self,kind='quick',radius=44)
        QShortcut(QKeySequence('Escape'),self,activated=owner.close)

    def sources(self):
        menu=QMenu(self)
        for text,mode in [('Región ajustable','region'),('Monitor','monitor'),('Todo el escritorio','desktop'),('Ventana (portal en Wayland)…','window')]:
            action=menu.addAction(text);action.setCheckable(True);action.setChecked(self.owner.capture_mode==mode)
            action.triggered.connect(lambda checked=False,m=mode,t=text:self.choose(m,t))
        menu.exec(self.mode.mapToGlobal(self.mode.rect().topLeft()))

    def choose(self,mode,text):
        self.owner.capture_mode=mode;self.mode.setText(text+' ⌄')

    def present(self):
        screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();geo=screen.availableGeometry()
        width=min(720,max(300,geo.width()-32));self.library.setVisible(width>=580)
        self.mode.setMinimumWidth(100 if width<580 else 130);self.start.setMinimumWidth(100 if width<580 else 138)
        self.row.setContentsMargins(12 if width<580 else 20,16,12 if width<580 else 20,16)
        self.setFixedSize(width,88);self.move(geo.center().x()-width//2,geo.bottom()-self.height()-28)
        self.show();self.raise_();self.activateWindow();self.start.setFocus()
