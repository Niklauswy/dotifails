#!/usr/bin/env python3
"""Wysun resident: hosts the Qt utility windows and clipboard history. The launcher is the shell widget."""
from theme_tokens import apply_style, color, paint_color

import argparse, os, re, socket, subprocess, sys
from pathlib import Path
from PySide6.QtCore import Qt, QObject, QTimer, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QFrame

from desktop_backend import Desktop, wayland
from core import STATE, HOME, sensitive

ROOT=Path(__file__).resolve().parent
SOCKET=str(Path(os.environ.get('XDG_RUNTIME_DIR','/tmp'))/f'orbit-{os.getuid()}.sock')
from ui_theme import PALETTE_STYLE as STYLE

def run(args):
    subprocess.Popen([str(a) for a in args],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

def divider():
    w=QFrame();w.setFixedHeight(1);apply_style(w,'background: @divider;');return w

def label(text='',name=''):
    x=QLabel(text);x.setTextFormat(Qt.PlainText)
    if name:x.setObjectName(name)
    return x

class OrbitDaemon(QObject):
    """Headless resident: hosts the Qt utility windows and records clipboard history.

    The launcher itself is the shell widget (apps/shell/modules/launcher); no
    Qt launcher palette exists any more.
    """
    UTILITIES=('network','notes','processes','color','tools','music','settings')
    def __init__(self,store=None,test=False):
        super().__init__()
        from data_v2 import StoreV2
        self.store=store or StoreV2();self.test=test;self.utilities={};self.ignore_clip=False;self._external_clipboard=None
        self.clipboard=QApplication.clipboard()
        if not test:self.clipboard.dataChanged.connect(self.capture_clip)
        self.wayland_clipboard=None
        if not test and wayland():
            from wayland_clipboard import ClipboardWatch
            self.wayland_clipboard=ClipboardWatch(self)
        self.prune_timer=QTimer(self);self.prune_timer.timeout.connect(self.store.prune);self.prune_timer.start(3600000)
    @property
    def paused(self):return self.store.get('paused')=='1'
    def update_private(self):pass
    def capture_clip(self):
        if self.ignore_clip or self.paused:return
        mime=self._external_clipboard or self.clipboard.mimeData()
        if not mime or sensitive('',mime.formats()):return
        source=''
        if not self.test:
            try:source=Desktop().focused_app()
            except (OSError,RuntimeError,ValueError,subprocess.SubprocessError):pass
        from clipboard_mime import encode
        from data_v2 import color_value
        from media import png_bytes
        try:rich=encode(mime) if not mime.hasImage() else None
        except ValueError:return
        if mime.hasUrls() and all(u.isLocalFile() for u in mime.urls()):
            paths=[u.toLocalFile() for u in mime.urls()];self.store.clip('files','\n'.join(paths),blob=rich,source=source,meta={'paths':paths,'mime_envelope':True})
        elif mime.hasImage():
            img=mime.imageData() if self._external_clipboard is not None else self.clipboard.image()
            if img.isNull() or img.width()*img.height()>25_000_000:return
            blob=png_bytes(img);thumb=png_bytes(img.scaled(320,240,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            self.store.clip('image',f'Imagen · {img.width()} × {img.height()}',blob,source,{'width':img.width(),'height':img.height(),'bytes':len(blob)},thumb)
        elif mime.hasText():
            text=mime.text()
            if not text.strip() or sensitive(text,mime.formats()):return
            kind='color' if color_value(text) else 'url' if re.fullmatch(r'https?://\S+',text.strip()) else 'text'
            self.store.clip(kind,text,blob=rich,source=source,meta={'mime_envelope':True})
    def show_utility(self,mode):
        if mode in ('settings','music') and not self.test:
            run([str(Path(__file__).with_name('orbit-client')),mode]);return
        if mode not in self.utilities:
            if mode=='tools':
                from tools_window import ToolsWindow
                window=ToolsWindow(test=self.test)
            elif mode=='music':
                from music_app_window import MusicAppWindow
                window=MusicAppWindow(test=self.test)
            elif mode=='settings':
                from settings_hub import SettingsHub
                window=SettingsHub(test=self.test)
            elif mode in ('notes','processes','color'):
                from utilities import NotesWindow,ProcessesWindow,ColorWindow
                window={'notes':NotesWindow,'processes':ProcessesWindow,'color':ColorWindow}[mode]()
            else:
                from connections_window import ConnectionsWindow
                window=ConnectionsWindow()
            self.utilities[mode]=window
        window=self.utilities[mode]
        if window.isVisible() and not getattr(window,'_motion_exiting',False):window.close();return
        window.present()
        if mode=='network':window.load()
    def show_mode(self,mode='home'):
        if mode=='power':run([str(HOME/'.local/bin/wysun-shell'),'session']);return
        if mode in self.UTILITIES:self.show_utility(mode);return
        if mode in ('toggle','home','daemon'):return
        print(f'Wysun: «{mode}» ya no es un menú Qt; usa el lanzador del shell.',file=sys.stderr)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',nargs='?',default='toggle');parser.add_argument('--daemon',action='store_true');args=parser.parse_args()
    os.umask(0o077)
    app=QApplication(['Orbit','--name','Orbit']);app.setApplicationName('Orbit');app.setApplicationDisplayName('Wysun');app.setDesktopFileName('orbit');app.setWindowIcon(QIcon(str(ROOT/'orbit.png')));app.setQuitOnLastWindowClosed(False);app.setStyle('Fusion');apply_style(app,STYLE);QIcon.setThemeSearchPaths([str(HOME/'.local/share/icons'),str(HOME/'.icons'),'/usr/share/icons']);QIcon.setThemeName('Win11-Dark');QIcon.setFallbackThemeName('Adwaita')
    from theme_tokens import watch_theme
    watch_theme()
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
    win=OrbitDaemon()
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
    def receive(mode):
        if mode=='reload':
            # Preserve pending notes, and refuse reload if an external edit conflicts.
            for window in win.utilities.values():
                if hasattr(window,'save') and window.save() is False:
                    window.present();return
            for window in win.utilities.values():
                if hasattr(window,'shutdown_jobs'):window.shutdown_jobs()
            server.close();Path(SOCKET).unlink(missing_ok=True)
            os.execv(sys.executable,[sys.executable,str(ROOT/'orbit.py'),'daemon','--daemon'])
        else:win.show_mode(mode)
    app.aboutToQuit.connect(lambda:[w.shutdown_jobs() for w in win.utilities.values() if hasattr(w,'shutdown_jobs')])
    ipc=IPC();ipc.received.connect(receive);ipc.start()
    if not args.daemon:QTimer.singleShot(0,lambda:win.show_mode(args.mode))
    sys.exit(app.exec())
if __name__=='__main__':main()
