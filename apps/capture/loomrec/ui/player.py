"""mpv embedded playback via a private IPC socket (no QtMultimedia dependency)."""
import json
import socket
import tempfile
from pathlib import Path
from PySide6.QtCore import QProcess, QTimer, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class Player(QWidget):
    positionChanged = Signal(float)
    failed = Signal(str)
    durationChanged = Signal(float)
    stateChanged = Signal()
    def __init__(self):
        super().__init__(); self.setMinimumSize(320,180)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        self.surface=QWidget(); self.surface.setStyleSheet('background:#18263A; border-radius:10px;'); layout.addWidget(self.surface)
        self._closing=False;self._failure_reported=False
        self.process=QProcess(self); self.process.errorOccurred.connect(lambda _:self.report_failure(self.tr('No se pudo iniciar mpv. Comprueba su instalación.')))
        self.process.finished.connect(lambda code,_:self.report_failure(self.tr('mpv no pudo reproducir el video. Comprueba el archivo.')) if code else None)
        self.temp=tempfile.TemporaryDirectory(prefix='loom-player-')
        self.ipc=str(Path(self.temp.name)/'ipc.sock')
        self.timer=QTimer(self); self.timer.setInterval(300); self.timer.timeout.connect(self.poll)
        self.paused=True;self.volume=80;self.muted=False;self.speed=1.;self.duration=0.;self.position=0.
        self.client=None
        self.buffer=bytearray();self.request_id=0;self.requests={}
    def connected(self):
        for name in ('time-pos','duration','pause','volume','mute','speed'):
            self.command('observe_property',('time-pos','duration','pause','volume','mute','speed').index(name)+1,name)
        for name,value in [('volume',self.volume),('mute',self.muted),('speed',self.speed)]:self.command('set_property',name,value)
    def read_messages(self):
        if not self.client:return
        try:
            for _ in range(16):
                chunk=self.client.recv(8192)
                if not chunk:self.client.close();self.client=None;return
                self.buffer.extend(chunk)
        except BlockingIOError:pass
        except OSError:self.client.close();self.client=None;return
        while b'\n' in self.buffer:
            raw,_,rest=self.buffer.partition(b'\n');self.buffer=bytearray(rest)
            try:data=json.loads(raw)
            except ValueError:continue
            if data.get('event')!='property-change':continue
            name,value=data.get('name'),data.get('data')
            if value is None:continue
            if name=='time-pos':self.position=float(value);self.positionChanged.emit(self.position)
            elif name=='duration':self.duration=float(value);self.durationChanged.emit(self.duration)
            elif name=='pause':self.paused=bool(value)
            elif name=='volume':self.volume=max(0,min(100,int(value)))
            elif name=='mute':self.muted=bool(value)
            elif name=='speed':self.speed=float(value)
            self.stateChanged.emit()
    def command(self,*args):
        if self.client:
            try:self.client.sendall((json.dumps({'command':list(args)})+'\n').encode())
            except OSError:pass
    def set_volume(self,value):
        self.volume=max(0,min(100,int(value)));self.command('set_property','volume',self.volume);self.stateChanged.emit()
    def set_speed(self,value):
        self.speed=max(.5,min(2.,float(value)));self.command('set_property','speed',self.speed);self.stateChanged.emit()
    def toggle_mute(self):
        self.muted=not self.muted;self.command('set_property','mute',self.muted);self.stateChanged.emit()
    def load(self,path):
        self.close_media()
        self._failure_reported=False
        if not Path(path).is_file():
            self.report_failure(self.tr('No se encuentra el archivo de video.'));return
        self.process.start('mpv',['--no-config','--idle=no','--pause','--keep-open=yes',
            '--hwdec=no','--vo=gpu,x11','--input-default-bindings=no','--input-vo-keyboard=no',
            '--osc=no',f'--wid={int(self.surface.winId())}',f'--input-ipc-server={self.ipc}',str(path)])
        self.paused=True;self.duration=0.;self.position=0.;self.stateChanged.emit();self.timer.start()
    def report_failure(self,message):
        if self._closing or self._failure_reported:return
        self._failure_reported=True;self.timer.stop();self.failed.emit(message)
    def toggle(self):
        self.paused=not self.paused; self.command('set_property','pause',self.paused);self.stateChanged.emit()
    def seek(self,seconds): self.command('seek',seconds,'absolute+exact')
    def poll(self):
        if self.client is None and Path(self.ipc).exists():
            client=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);client.setblocking(False)
            try:client.connect(self.ipc)
            except OSError:client.close();return
            self.client=client;self.connected()
        self.read_messages()
    def close_media(self):
        self.timer.stop()
        if self.client:self.client.close();self.client=None
        self.buffer.clear()
        self._closing=True
        if self.process.state()!=QProcess.NotRunning:
            self.command('quit'); self.process.terminate()
            if not self.process.waitForFinished(500): self.process.kill(); self.process.waitForFinished(500)
        self._closing=False
    def shutdown(self): self.close_media(); self.temp.cleanup()
