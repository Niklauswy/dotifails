"""One Wysun Processes window per user: a second `wysun processes [query]` hands its query to the open window
through a local socket in $XDG_RUNTIME_DIR and exits."""
import os

from PySide6.QtNetwork import QLocalServer, QLocalSocket


def default_name():
    runtime = os.environ.get('XDG_RUNTIME_DIR') or '/tmp'
    return os.path.join(runtime, 'wysun-processes-%d' % os.getuid())


class Instance:
    def __init__(self, name=None):
        self.name = name or default_name()
        self.server = None

    def forward(self, query, timeout=800):
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(timeout):
            return False
        socket.write((query or '').encode() + b'\n')
        socket.flush()
        socket.waitForBytesWritten(timeout)
        socket.disconnectFromServer()
        return True

    def listen(self, on_query):
        QLocalServer.removeServer(self.name)
        self.server = QLocalServer()
        self.server.setSocketOptions(QLocalServer.UserAccessOption)

        def accept():
            while self.server.hasPendingConnections():
                socket = self.server.nextPendingConnection()
                buffer = bytearray()

                def read(socket=socket, buffer=buffer):
                    buffer.extend(bytes(socket.readAll()))
                    if b'\n' in buffer:
                        on_query(buffer.split(b'\n', 1)[0].decode(errors='replace'))
                        socket.disconnectFromServer()
                socket.readyRead.connect(read)
        self.server.newConnection.connect(accept)
        return self.server.listen(self.name)

    def close(self):
        if self.server is not None:
            self.server.close()
            self.server = None
