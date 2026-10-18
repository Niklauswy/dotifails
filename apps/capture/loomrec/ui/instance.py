"""Local single GUI instance per user/display; recorder service remains independent."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import time


class Instance:
    def __init__(self, directory=None, name="gui"):
        if name not in ("gui","controller","job"):raise ValueError("Invalid instance namespace")
        root=Path(directory) if directory else Path(os.environ.get('XDG_RUNTIME_DIR','/tmp'))/f'loomrec-{os.getuid()}'
        if root.is_symlink():raise RuntimeError('Unsafe instance directory')
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        if root.stat().st_uid!=os.getuid() or root.stat().st_mode & 0o077:raise RuntimeError('Instance directory must be private')
        tag=hashlib.sha256(os.environ.get('DISPLAY','default').encode()).hexdigest()[:12]
        self.path=root/f'{name}-{tag}.sock';self.lock_path=root/f'{name}-{tag}.lock'
        self.lock=None;self.server=None;self.clients=[]

    def claim(self):
        if self.lock_path.is_symlink():raise RuntimeError('Unsafe instance lock')
        self.lock=self.lock_path.open('a')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:self.lock.close();self.lock=None;return False
        try:
            self.path.unlink(missing_ok=True)
            self.server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.server.bind(str(self.path));os.chmod(self.path,0o600)
            self.server.listen(8);self.server.setblocking(False)
        except Exception:self.close();raise
        return True

    def request(self,action='setup',timeout=3):
        deadline=time.monotonic()+timeout
        while True:
            try:
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                    client.settimeout(max(.01,deadline-time.monotonic()));client.connect(str(self.path));client.sendall(json.dumps({'action':action}).encode()+b'\n')
                    data=b''
                    while b'\n' not in data and len(data)<4096:
                        part=client.recv(4096)
                        if not part:break
                        data+=part
                    return json.loads(data)
            except (FileNotFoundError,ConnectionRefusedError):
                if time.monotonic()>=deadline:raise RuntimeError('La ventana de Wysun Recorder está iniciando o no está disponible')
                time.sleep(.03)

    def poll(self,callback):
        while True:
            try:client,_=self.server.accept();client.setblocking(False);self.clients.append([client,b'',time.monotonic()])
            except BlockingIOError:break
        for entry in self.clients[:]:
            client,data,created=entry
            try:
                try:
                    chunk=client.recv(1024)
                    if not chunk:raise ConnectionError()
                    entry[1]=data=data+chunk
                except BlockingIOError:pass
                if len(data)>1024 or time.monotonic()-created>3:raise ConnectionError()
                if b'\n' not in data:continue
                action=json.loads(data)['action']
                if action not in ('setup','focus','status','quick','hide_controls'):raise ValueError('Unsupported activation')
                response=callback(action);client.sendall(json.dumps(response).encode()+b'\n')
            except (OSError,ValueError,KeyError):pass
            else:
                if b'\n' not in data:continue
            client.close();self.clients.remove(entry)

    def close(self):
        for client,_,_ in self.clients:client.close()
        self.clients=[]
        if self.server:self.server.close();self.server=None
        if self.lock:
            self.path.unlink(missing_ok=True);self.lock.close();self.lock=None
