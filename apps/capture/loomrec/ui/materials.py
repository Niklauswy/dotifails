"""Opt-in native Acrylic surfaces; never screenshot or blur application content.

Real backdrop blur is owned by the compositor, gated by a verified per-window
configuration. Without that capability, every material paints opaque matte pearl.
Region selection and main-window canvases must never opt in.
"""
import ctypes
import ctypes.util
import json
import os
from pathlib import Path
from PySide6.QtCore import Qt,QEvent,QObject,QRectF,QTimer
from PySide6.QtGui import QPainter,QColor,QPen,QLinearGradient,QPainterPath,QRegion
from PySide6.QtWidgets import QWidget

PROPERTY='_WYBIE_ACRYLIC'


def _x11_property(window=None,enabled=False,radius=None):
    if os.environ.get('QT_QPA_PLATFORM')=='offscreen' or not os.environ.get('DISPLAY'):return False
    try:
        lib=ctypes.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
        lib.XOpenDisplay.argtypes=[ctypes.c_char_p];lib.XOpenDisplay.restype=ctypes.c_void_p
        lib.XCloseDisplay.argtypes=[ctypes.c_void_p]
        lib.XDefaultScreen.argtypes=[ctypes.c_void_p];lib.XDefaultScreen.restype=ctypes.c_int
        lib.XInternAtom.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_int];lib.XInternAtom.restype=ctypes.c_ulong
        lib.XGetSelectionOwner.argtypes=[ctypes.c_void_p,ctypes.c_ulong];lib.XGetSelectionOwner.restype=ctypes.c_ulong
        lib.XChangeProperty.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_int]
        lib.XDeleteProperty.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong]
        lib.XFlush.argtypes=[ctypes.c_void_p]
        display=lib.XOpenDisplay(None)
        if not display:return False
        try:
            screen=lib.XDefaultScreen(display);selection=lib.XInternAtom(display,f'_NET_WM_CM_S{screen}'.encode(),False)
            present=bool(lib.XGetSelectionOwner(display,selection))
            if window is not None:
                atom=lib.XInternAtom(display,PROPERTY.encode(),False)
                cardinal=lib.XInternAtom(display,b'CARDINAL',False);value=ctypes.c_ulong(1 if enabled and present else 0)
                lib.XChangeProperty(display,int(window),atom,cardinal,32,0,ctypes.byref(value),1)
                if radius is not None:
                    radius_atom=lib.XInternAtom(display,b'_WYBIE_RADIUS',False);radius_value=ctypes.c_ulong(int(radius))
                    lib.XChangeProperty(display,int(window),radius_atom,cardinal,32,0,ctypes.byref(radius_value),1)
                lib.XFlush(display)
            return present
        finally:lib.XCloseDisplay(display)
    except (OSError,ValueError):return False


def backdrop_available():
    """Installer enables this only after proving the scoped compositor rule."""
    root=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))
    try:
        settings=json.loads((root/'loomrec/materials.json').read_text())
        return settings.get('backdrop_blur') is True and settings.get('transparency',True) is not False and _x11_property()
    except (OSError,ValueError,TypeError):return False


class MaterialLayer(QWidget):
    def __init__(self,parent,radius=18):
        super().__init__(parent);self.radius=radius;self.acrylic=False
        self.setAttribute(Qt.WA_TransparentForMouseEvents);self.setAttribute(Qt.WA_NoSystemBackground)
        self.setGeometry(parent.rect());self.lower();self.show()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        # Low-contrast tint/light, not an image of the desktop or Qt child blur.
        tint=QLinearGradient(0,0,0,self.height())
        tint.setColorAt(0,QColor(240,248,255,208 if self.acrylic else 255))
        tint.setColorAt(1,QColor(226,239,252,222 if self.acrylic else 255))
        p.setBrush(tint);p.setPen(QPen(QColor(255,255,255,220),1));p.drawRoundedRect(rect,self.radius,self.radius)
        # A single lit edge; no second nested border or shadow.


class _MaterialBinding(QObject):
    def __init__(self,window,panel,radius):
        super().__init__(panel);self.window=window;self.panel=panel;self.radius=radius;self.layer=MaterialLayer(panel,radius)
        panel.installEventFilter(self)
        if panel is not window:window.installEventFilter(self)
        self.refresh()
    def refresh(self):
        enabled=backdrop_available();self.layer.acrylic=enabled;self.layer.update()
        self.window.setProperty('materialMode','acrylic' if enabled else 'matte')
        self.shape()
        if self.window.isVisible():
            _x11_property(self.window.winId(),enabled,self.radius)
            if os.environ.get('QT_QPA_PLATFORM')!='offscreen':
                import subprocess
                try:subprocess.run(['bspc','config','-n',hex(int(self.window.winId())),'border_width','0'],capture_output=True,timeout=.3)
                except (OSError,subprocess.SubprocessError):pass
    def shape(self):
        if self.panel is self.window:
            path=QPainterPath();path.addRoundedRect(QRectF(self.window.rect()),self.radius,self.radius)
            self.window.setMask(QRegion(path.toFillPolygon().toPolygon()))
    def eventFilter(self,obj,event):
        if obj is self.panel and event.type()==QEvent.Resize:self.layer.setGeometry(self.panel.rect());self.layer.lower();self.shape()
        if obj is self.window and event.type()==QEvent.Show:QTimer.singleShot(0,self,self.refresh)
        return False


def apply_material(window,panel=None,*,kind='popup',radius=18):
    """Decorate an explicitly approved surface without changing flags or behavior."""
    if kind not in ('quick','controller','popup','dialog'):raise ValueError('Material is restricted to floating surfaces')
    if getattr(window,'_wybie_material',None):return window._wybie_material
    panel=panel or window
    window.setAttribute(Qt.WA_TranslucentBackground)
    panel.setAutoFillBackground(False)
    if not panel.objectName():panel.setObjectName('wybieMaterialSurface')
    panel.setStyleSheet(panel.styleSheet()+f'\n#{panel.objectName()} {{background:transparent;border:0;}}')
    binding=_MaterialBinding(window,panel,radius);window._wybie_material=binding
    return binding
