#!/usr/bin/env python3
"""Independent settings app with local IPC using Python and QtCore only."""
import fcntl
import os
import socket
import sys
from pathlib import Path
from PySide6.QtCore import QObject,QSocketNotifier,QTimer,Signal
from PySide6.QtWidgets import QApplication

class LocalSettingsServer(QObject):
    requested=Signal(str)

    def __init__(self,endpoint,parent=None):
        super().__init__(parent)
        self.endpoint=Path(endpoint);self.clients={}
        self.server=socket.socket(socket.AF_UNIX)
        try:
            self.server.bind(str(self.endpoint));self.endpoint.chmod(0o600)
            self.server.listen(8);self.server.setblocking(False)
        except Exception:self.server.close();raise
        self.notifier=QSocketNotifier(self.server.fileno(),QSocketNotifier.Read,self)
        self.notifier.activated.connect(self.accept)

    def accept(self,*_):
        while True:
            try:connection,_=self.server.accept()
            except BlockingIOError:return
            connection.setblocking(False)
            notifier=QSocketNotifier(connection.fileno(),QSocketNotifier.Read,self)
            self.clients[connection]=[notifier,b'']
            notifier.activated.connect(lambda *_,c=connection:self.read(c))
            QTimer.singleShot(2000,self,lambda c=connection:self.drop(c))
            self.read(connection)

    def read(self,connection):
        if connection not in self.clients:return
        try:data=connection.recv(128)
        except BlockingIOError:return
        except OSError:self.drop(connection);return
        if not data:self.drop(connection);return
        state=self.clients[connection];state[1]+=data
        if b'\n' in state[1]:
            route=state[1].split(b'\n',1)[0].decode(errors='replace').strip()
            self.drop(connection);self.requested.emit(route)
        elif len(state[1])>128:self.drop(connection)

    def drop(self,connection):
        if connection not in self.clients:return
        notifier,_=self.clients.pop(connection);notifier.setEnabled(False);notifier.deleteLater();connection.close()

    def close(self):
        self.notifier.setEnabled(False)
        for connection in list(self.clients):self.drop(connection)
        self.server.close();self.endpoint.unlink(missing_ok=True)

def main():
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.cache/orbit')))
    runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
    endpoint=runtime/f'orbit-settings-{os.getuid()}.sock'
    page=sys.argv[1] if len(sys.argv)>1 else 'home'
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(.3);client.connect(str(endpoint));client.sendall((page+'\n').encode());return 0
    except OSError:pass
    lock=(runtime/f'orbit-settings-{os.getuid()}.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    if endpoint.exists():
        if not endpoint.is_socket():raise RuntimeError('La ruta de comunicación está ocupada por otro archivo.')
        endpoint.unlink()
    app=QApplication(['Orbit','-name','Orbit']);app.setStyle('Fusion');app.setApplicationName('Orbit');app.setDesktopFileName('orbit-settings');app.setQuitOnLastWindowClosed(False)
    server=LocalSettingsServer(endpoint,app)
    from settings_hub import SettingsHub
    window=SettingsHub()
    def present(route):
        window.go(route if route in window.routes else 'home');window.present()
    server.requested.connect(present);QTimer.singleShot(0,lambda:present(page))
    def finish():
        for job in list(window.jobs):job.wait(15000)
        server.close()
    app.aboutToQuit.connect(finish)
    return app.exec()

if __name__=='__main__':sys.exit(main())
