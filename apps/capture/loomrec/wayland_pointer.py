"""Scoped mouse effects client. No keyboard observation or device access here.

The separately installed root broker requires explicit policy consent for each
recording. It emits filtered mouse buttons only, never an input FD. Position comes
from the native compositor IPC while a segment is actively sampled.
"""
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import socket
import stat
import struct
import subprocess
import time

HELPER=Path('/usr/libexec/wysun-pointer-helper')


def native_point(position,metadata,source_size,crop):
    origin=metadata.get('position');size=metadata.get('size')
    if not origin or not size or min(size)<=0:raise ValueError('El portal no describe coordenadas para efectos del cursor')
    x,y=position
    if not origin[0]<=x<origin[0]+size[0] or not origin[1]<=y<origin[1]+size[1]:return None
    px=round((x-origin[0])*source_size[0]/size[0])-crop[0];py=round((y-origin[1])*source_size[1]/size[1])-crop[1]
    return (px,py) if 0<=px<crop[2] and 0<=py<crop[3] else None


def cursor_position():
    signature=os.environ.get('HYPRLAND_INSTANCE_SIGNATURE','')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',signature) or signature in ('.','..'):raise RuntimeError('Falta el identificador nativo de Hyprland')
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))
    path=runtime/'hypr'/signature/'.socket.sock'
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(.25);connection.connect(str(path))
        peer=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if peer[1]!=os.getuid():raise PermissionError('El socket no pertenece a la sesión')
        connection.sendall(b'j/cursorpos');data=bytearray()
        while len(data)<4096:
            block=connection.recv(4096-len(data))
            if not block:break
            data.extend(block)
        value=json.loads(data)
        if not all(type(value.get(key)) in (int,float) for key in ('x','y')):raise ValueError('Posición nativa inválida')
        return value['x'],value['y']


class MouseEffects:
    buttons_available=True
    def __init__(self,on_wait=None):
        self.on_wait=on_wait;self.connection=None;self.process=None;self.listener=None;self.path=None;self.buffer=bytearray();self.last_ping=0;self.buttons=[]
    def prepare(self):
        if not HELPER.is_file():raise RuntimeError('Falta el helper de ratón instalado por administrador; se conserva el cursor nativo')
        info=HELPER.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise PermissionError('El helper debe estar instalado y protegido por root')
        runtime=Path('/run/user')/str(os.getuid());folder=runtime/'wysun-pointer'
        actual=runtime.lstat()
        if not stat.S_ISDIR(actual.st_mode) or actual.st_uid!=os.getuid() or stat.S_IMODE(actual.st_mode)!=0o700:raise PermissionError('Runtime de sesión inseguro')
        folder.mkdir(mode=0o700,exist_ok=True);actual=folder.lstat()
        if not stat.S_ISDIR(actual.st_mode) or actual.st_uid!=os.getuid() or stat.S_IMODE(actual.st_mode)!=0o700:raise PermissionError('Directorio de control inseguro')
        nonce=secrets.token_hex(32);self.path=folder/f'{os.getpid()}.{nonce}.sock'
        self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.listener.bind(str(self.path));self.path.chmod(0o600);self.listener.listen(1);self.listener.settimeout(.25)
        self.process=subprocess.Popen(['pkexec',str(HELPER),str(os.getpid()),nonce],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        try:
            deadline=time.monotonic()+120
            while self.connection is None:
                if self.on_wait:self.on_wait()
                if self.process.poll() is not None:raise RuntimeError('No se autorizó la lectura temporal de botones del ratón')
                if time.monotonic()>deadline:raise TimeoutError('Caducó la autorización de efectos del ratón')
                try:self.connection,_=self.listener.accept()
                except socket.timeout:continue
            peer=struct.unpack('3i',self.connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if peer[0]!=self.process.pid or peer[1]!=0:raise PermissionError('El peer no es el helper autorizado')
            self.connection.settimeout(3);ready=bytearray()
            while not ready.endswith(b'\n') and len(ready)<128:
                part=self.connection.recv(1)
                if not part:raise RuntimeError('El helper rechazó la sesión activa')
                ready.extend(part)
            if ready!=b'READY\n':raise RuntimeError('Respuesta de autorización inválida')
            os.set_blocking(self.process.stdout.fileno(),False);self.last_ping=time.monotonic()
        except BaseException:self.close();raise
        finally:
            if self.listener:self.listener.close();self.listener=None
            if self.path:self.path.unlink(missing_ok=True)
        return self
    def control(self,command):
        if self.connection is None:raise RuntimeError('El helper de ratón no está conectado')
        if command not in ('PING','RUN','PAUSE','STOP'):raise ValueError('Control no permitido')
        self.connection.sendall((command+'\n').encode());self.last_ping=time.monotonic()
    def ping(self):
        if self.connection and time.monotonic()-self.last_ping>=.5:self.control('PING')
    def run(self):self.buttons.clear();self.control('RUN')
    def pause(self):
        if self.connection:self.control('PAUSE')
        self.buttons.clear()
    def clicks(self):
        self.ping()
        if not self.process or self.process.poll() is not None:raise RuntimeError('Los efectos de ratón se cerraron; el cursor nativo permanece')
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout,selectors.EVENT_READ)
            while selector.select(0):
                block=os.read(self.process.stdout.fileno(),8192)
                if not block:raise RuntimeError('Se revocó la lectura de botones del ratón')
                self.buffer.extend(block)
                if len(self.buffer)>32768:raise RuntimeError('Demasiados eventos del ratón')
                while b'\n' in self.buffer:
                    line,_,tail=self.buffer.partition(b'\n');self.buffer=bytearray(tail);event=json.loads(line)
                    if set(event)!={'t','button','value'} or type(event['button']) is not int or event['button'] not in (1,2,3) or type(event['value']) is not int or event['value'] not in (0,1):raise RuntimeError('Evento de ratón inválido')
                    if event['value']==1:self.buttons.append(event['button'])
                    if len(self.buttons)>256:raise RuntimeError('Límite de clics alcanzado')
        result=self.buttons;self.buttons=[];return result
    def close(self):
        if self.connection:
            try:self.control('STOP')
            except OSError:pass
            self.connection.close();self.connection=None
        if self.listener:self.listener.close();self.listener=None
        if self.path:self.path.unlink(missing_ok=True)
        if self.process:
            process=self.process;self.process=None
            # Authorization is still an unprivileged pkexec until it has connected.
            if process.poll() is None:
                try:process.terminate()
                except PermissionError:pass
                try:process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    import threading
                    threading.Thread(target=process.wait,daemon=True,name='wysun-mouse-reaper').start()
            for stream in (process.stdout,process.stderr):
                if stream:stream.close()


class PositionEffects:
    buttons_available=False
    """No privilege or button observation when only halo/trail is requested."""
    def prepare(self):return self
    def run(self):pass
    def pause(self):pass
    def ping(self):pass
    def clicks(self):return []
    def close(self):pass


class NativePointerReader:
    def __init__(self,broker,metadata,source_size,crop,position=cursor_position):
        self.broker=broker;self.metadata=metadata;self.source_size=source_size;self.crop=crop;self.get_position=position
        native_point((metadata.get('position') or [0,0]),metadata,source_size,crop)
    def position(self):return native_point(self.get_position(),self.metadata,self.source_size,self.crop)
    def clicks(self):return self.broker.clicks()
    def close(self):
        try:self.broker.pause()
        except (OSError,RuntimeError):pass
