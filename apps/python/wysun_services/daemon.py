#!/usr/bin/env python3
"""Wysun resident (`wysun daemon`): records the clipboard history the launcher shows.

`wysun reload` makes the running resident start again with the installed code, or starts one in the
background when none is running. Its only requests are `ping` and `reload`.
"""
from wysun_core.qt_theme import apply_style

import argparse, os, re, subprocess, sys
from pathlib import Path
from PySide6.QtCore import Qt, QObject, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from wysun_core.desktop import Desktop, wayland
from wysun_services.store import HOME, sensitive
from wysun_core.instance import SingleInstance, send
from wysun_core.qt_instance import InstanceNotifier
from wysun_core import launch

ROOT=Path(__file__).resolve().parent
from wysun_core.ui_theme import PALETTE_STYLE as STYLE


class ClipboardDaemon(QObject):
    """Headless resident that records the clipboard history (the launcher itself is the shell widget)."""
    def __init__(self,store=None,test=False):
        super().__init__()
        from wysun_services.data_v2 import StoreV2
        self.store=store or StoreV2();self.test=test;self.ignore_clip=False;self._external_clipboard=None
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

def owner():
    return SingleInstance(f'wysun-daemon-{os.getuid()}')

def start_detached():
    """Start the resident in its own session, logging to the Wysun state directory."""
    from wysun_core import paths
    state=paths.state('wysun');state.mkdir(parents=True,exist_ok=True)
    with (state/'daemon.log').open('a') as log:
        subprocess.Popen(launch.argv('wysun_services.daemon'),env=launch.environment(),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)

def re_exec(ipc,resident,window):
    """Replace this resident with the installed code; its wl-paste watcher would survive execve."""
    if window.wayland_clipboard is not None:window.wayland_clipboard.stop()
    ipc.close();resident.close()
    os.execve(sys.executable,launch.argv('wysun_services.daemon'),launch.environment())

def main(argv=None):
    parser=argparse.ArgumentParser(prog='wysun daemon');parser.add_argument('mode',nargs='?',choices=('daemon','reload'),default='daemon')
    # parse_known_args: a resident of an earlier version re-executes itself with options this one no longer has.
    args,_=parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    resident=owner()
    if args.mode=='reload':
        if not send(resident.endpoint,b'reload',timeout=.5):start_detached()
        return 0
    if send(resident.endpoint,b'ping',timeout=.5):return 0   # already running
    os.umask(0o077)
    if not resident.claim():return 0                          # another resident is starting
    app=QApplication(['wysun','--name','wysun']);app.setApplicationName('Wysun');app.setApplicationDisplayName('Wysun');app.setDesktopFileName('wysun');app.setWindowIcon(QIcon(str(ROOT/'wysun.png')));app.setQuitOnLastWindowClosed(False);app.setStyle('Fusion');apply_style(app,STYLE);QIcon.setThemeSearchPaths([str(HOME/'.local/share/icons'),str(HOME/'.icons'),'/usr/share/icons']);QIcon.setThemeName('Win11-Dark');QIcon.setFallbackThemeName('Adwaita')
    from wysun_core.qt_theme import watch_theme
    watch_theme()
    resident_window=ClipboardDaemon()  # noqa: F841 (kept alive for the whole session)
    def request(line):
        mode=line.decode('utf-8',errors='ignore').strip()
        if mode=='ping':return b'pong'
        if mode=='reload':QTimer.singleShot(0,lambda:re_exec(ipc,resident,resident_window))
    ipc=InstanceNotifier(resident,request,app,limit=256,timeout=.5)
    return app.exec()

if __name__=='__main__':sys.exit(main())
