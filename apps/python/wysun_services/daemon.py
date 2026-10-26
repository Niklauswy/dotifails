#!/usr/bin/env python3
"""Wysun resident: hosts the Qt utility windows and clipboard history. The launcher is the shell widget."""
from wysun_core.qt_theme import apply_style, color, paint_color

import argparse, os, re, subprocess, sys
from pathlib import Path
from PySide6.QtCore import Qt, QObject, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QFrame

from wysun_core.desktop import Desktop, wayland
from wysun_services.store import STATE, HOME, sensitive
from wysun_core.instance import SingleInstance, send
from wysun_core.qt_instance import InstanceNotifier
from wysun_core import launch

ROOT=Path(__file__).resolve().parent
from wysun_core.ui_theme import PALETTE_STYLE as STYLE

def run(args):
    subprocess.Popen([str(a) for a in args],env=launch.environment(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

def divider():
    w=QFrame();w.setFixedHeight(1);apply_style(w,'background: @divider;');return w

def label(text='',name=''):
    x=QLabel(text);x.setTextFormat(Qt.PlainText)
    if name:x.setObjectName(name)
    return x

class ClipboardDaemon(QObject):
    """Headless resident: hosts the Qt utility windows and records clipboard history.

    The launcher itself is the shell widget (apps/shell/modules/launcher); no
    Qt launcher palette exists any more.
    """
    UTILITIES=('color','music')
    def __init__(self,store=None,test=False):
        super().__init__()
        from wysun_services.data_v2 import StoreV2
        self.store=store or StoreV2();self.test=test;self.utilities={};self.ignore_clip=False;self._external_clipboard=None
        self.clipboard=QApplication.clipboard()
        if not test:self.clipboard.dataChanged.connect(self.capture_clip)
        self.wayland_clipboard=None
        if not test and wayland():
            from wysun_services.wayland_clipboard import ClipboardWatch
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
        from wysun_services.clipboard_mime import encode
        from wysun_services.data_v2 import color_value
        from wysun_services.media import png_bytes
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
        if mode == 'color':
            run([str(HOME/'.local/bin/wysun'), 'colors']);return
        if mode=='music' and not self.test:
            run(launch.argv('wysun_services.client',mode));return
        if mode not in self.utilities:
            from wysun_music.app import build
            self.utilities[mode]=build(test=self.test).window
        window=self.utilities[mode]
        if window.isVisible() and not getattr(window,'_motion_exiting',False):window.close();return
        window.present()
    def show_mode(self,mode='home'):
        if mode=='power':run([str(HOME/'.local/bin/wysun-shell'),'session']);return
        if mode in self.UTILITIES:self.show_utility(mode);return
        if mode in ('toggle','home','daemon'):return
        print(f'Wysun: «{mode}» ya no es un menú Qt; usa el lanzador del shell.',file=sys.stderr)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',nargs='?',default='toggle');parser.add_argument('--daemon',action='store_true');args=parser.parse_args()
    os.umask(0o077)
    app=QApplication(['wysun','--name','wysun']);app.setApplicationName('Wysun');app.setApplicationDisplayName('Wysun');app.setDesktopFileName('wysun');app.setWindowIcon(QIcon(str(ROOT/'wysun.png')));app.setQuitOnLastWindowClosed(False);app.setStyle('Fusion');apply_style(app,STYLE);QIcon.setThemeSearchPaths([str(HOME/'.local/share/icons'),str(HOME/'.icons'),'/usr/share/icons']);QIcon.setThemeName('Win11-Dark');QIcon.setFallbackThemeName('Adwaita')
    from wysun_core.qt_theme import watch_theme
    watch_theme()
    owner=SingleInstance(f'wysun-daemon-{os.getuid()}')
    if send(owner.endpoint,args.mode.encode(),timeout=.5):return
    if not owner.claim():
        send(owner.endpoint,args.mode.encode(),timeout=.5,retry=2.0);return   # another resident is starting
    win=ClipboardDaemon()
    def request(line):
        mode=line.decode('utf-8',errors='ignore').strip()
        if mode=='ping':return b'pong'
        if mode and mode!='daemon':QTimer.singleShot(0,lambda:receive(mode))
    def receive(mode):
        if mode=='reload':
            # Preserve pending notes, and refuse reload if an external edit conflicts.
            for window in win.utilities.values():
                if hasattr(window,'save') and window.save() is False:
                    window.present();return
            for window in win.utilities.values():
                if hasattr(window,'shutdown_jobs'):window.shutdown_jobs()
            ipc.close();owner.close()
            os.execve(sys.executable,launch.argv('wysun_services.daemon','daemon','--daemon'),launch.environment())
        else:win.show_mode(mode)
    app.aboutToQuit.connect(lambda:[w.shutdown_jobs() for w in win.utilities.values() if hasattr(w,'shutdown_jobs')])
    ipc=InstanceNotifier(owner,request,app,limit=256,timeout=.5)
    if not args.daemon:QTimer.singleShot(0,lambda:win.show_mode(args.mode))
    sys.exit(app.exec())
if __name__=='__main__':main()
