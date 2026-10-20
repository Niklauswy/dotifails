"""Opt-in session data-control watcher; Qt alone cannot read global Wayland clips.

wl-clipboard owns the privileged compositor protocol. No uinput daemon is used.
Pasting only injects with wtype on a compositor that exposes virtual-keyboard,
and only after the selected destination has been re-focused and re-checked.
"""
import base64
import json
import os
import selectors
import time
from pathlib import Path
import shutil
import subprocess
import sys
from desktop_backend import Desktop

LIMIT=4*1024*1024


def paste_to(target, desktop=None, runner=subprocess.run):
    desktop=desktop or Desktop()
    if desktop.backend!='hyprland' and not shutil.which('wtype'):
        return False,'Copiado. Pega con Ctrl+V en el destino (falta wtype).'
    try:
        desktop.activate(target)
        if desktop.focused()!=target:return False,'Copiado. El destino no aceptó el foco; pega manualmente.'
        if desktop.backend=='hyprland':
            desktop.dispatch('send_shortcut',mods='CTRL',key='V',window='address:'+desktop._id(target))
            return True,''
        result=runner(['wtype','-M','ctrl','-P','v','-p','v','-m','ctrl'],capture_output=True,timeout=2)
        if result.returncode:return False,'Copiado. El compositor no permite inyección; pega con Ctrl+V.'
        return True,''
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError):
        return False,'Copiado. No se pudo verificar el destino; pega manualmente.'


def read_offer(mime,timeout=2):
    proc=subprocess.Popen(['wl-paste','--no-newline','--type',mime],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    data=bytearray();deadline=time.monotonic()+timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout,selectors.EVENT_READ)
            while True:
                if not selector.select(max(0,deadline-time.monotonic())):raise TimeoutError('clipboard read timeout')
                block=os.read(proc.stdout.fileno(),min(65536,LIMIT+1-len(data)))
                if not block:break
                data.extend(block)
                if len(data)>LIMIT:raise ValueError('Clipboard offer too large')
        if proc.wait(timeout=max(.01,deadline-time.monotonic())):raise ValueError('Clipboard offer unavailable')
        return bytes(data)
    finally:
        if proc.poll() is None:proc.kill()
        proc.wait(timeout=2);proc.stdout.close()


def drain_watch_offer(fd=0,timeout=2):
    """Consume the actual watch offer before asking its owner for rich formats.

    wl-paste waits for this child; ignoring stdin can block the source while it
    writes a large image, preventing it from answering our subsequent reads.
    """
    import stat
    if not stat.S_ISFIFO(os.fstat(fd).st_mode):return
    total=0;deadline=time.monotonic()+timeout
    with selectors.DefaultSelector() as selector:
        selector.register(fd,selectors.EVENT_READ)
        while True:
            if not selector.select(max(0,deadline-time.monotonic())):raise TimeoutError('clipboard watch offer timeout')
            block=os.read(fd,min(65536,LIMIT+1-total))
            if not block:return
            total+=len(block)
            if total>LIMIT:raise ValueError('Clipboard offer too large')


def snapshot():
    if os.environ.get('CLIPBOARD_STATE') in ('sensitive','nil','clear'):return
    drain_watch_offer()
    types=subprocess.check_output(['wl-paste','--list-types'],timeout=1,text=True).splitlines()
    from core import sensitive
    if sensitive('',types):return
    supported=('text/uri-list','image/png','text/plain;charset=utf-8','text/plain','text/html','x-special/gnome-copied-files','application/x-kde-cutselection')
    formats={};total=0;first=None
    for mime in supported:
        if mime not in types:continue
        data=read_offer(mime);total+=len(data)
        if total>LIMIT:return
        if mime!='image/png' and sensitive(data.decode('utf8',errors='replace')):return
        if first is None:first=(mime,data)
        formats[mime]=base64.b64encode(data).decode()
    if first is None or read_offer(first[0])!=first[1]:return
    print(json.dumps({'formats':formats}),flush=True)


if __name__=='__main__' and sys.argv[1:]==['--snapshot']:
    try:snapshot()
    except (OSError,ValueError,TimeoutError,subprocess.SubprocessError):pass
    raise SystemExit(0)


from PySide6.QtCore import QObject,QProcess,QMimeData,QUrl
from PySide6.QtGui import QImage

class ClipboardWatch(QObject):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.buffer=bytearray();self.state='focus-only'
        self.process=QProcess(self)
        if not shutil.which('wl-paste'):return
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(lambda *_:self.set_state('focus-only'))
        self.process.errorOccurred.connect(lambda *_:self.set_state('focus-only'))
        if not owner.paused:self.start()
        else:self.state='paused'
        from PySide6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(self.stop)
    def set_state(self,state):
        self.state=state
        if getattr(self.owner,'wayland_clipboard',None) is self:self.owner.update_private()
    def start(self):
        if not shutil.which('wl-paste'):return
        self.buffer.clear();self.process.start('wl-paste',['--watch',sys.executable,str(Path(__file__).resolve()),'--snapshot']);self.set_state('data-control-requested')
    def set_paused(self,paused):
        if paused:self.stop();self.set_state('paused')
        else:self.start()
    def read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        if len(self.buffer)>LIMIT*2:self.buffer.clear();return
        while b'\n' in self.buffer:
            line,_,remaining=self.buffer.partition(b'\n');self.buffer=bytearray(remaining)
            try:
                from clipboard_mime import from_packet
                mime=from_packet(json.loads(line))
                self.owner._external_clipboard=mime
                try:self.owner.capture_clip()
                finally:self.owner._external_clipboard=None
                self.set_state('native-data-control')
            except (KeyError,ValueError,UnicodeError):continue
    def stop(self):
        self.process.terminate()
        if not self.process.waitForFinished(500):self.process.kill();self.process.waitForFinished(500)
