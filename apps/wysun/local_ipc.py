"""Small Unix-socket server used by resident Qt apps (Music) to receive one-line requests."""
import socket
from pathlib import Path
from PySide6.QtCore import QObject,QSocketNotifier,QTimer,Signal

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
