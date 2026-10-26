"""One process per name: a lock decides the owner, a Unix socket carries line requests.

Clients call :func:`send`; the owner claims a :class:`SingleInstance` and calls
``poll`` whenever its socket is readable (``qt_instance`` wires that to Qt).
"""
import fcntl
import signal
import socket
import sys
import time
import traceback
from pathlib import Path

from . import paths

LINE_LIMIT = 4096


class SingleInstance:
    def __init__(self, name, directory=None):
        root = paths.private_dir(directory) if directory is not None else paths.runtime_dir()
        self.endpoint = Path(root) / f'{name}.sock'
        self.lock_path = Path(root) / f'{name}.lock'
        self._lock = None
        self._server = None
        self._clients = []          # [socket, buffer, opened_at]

    def claim(self):
        """True when this process now owns the name; False when another one does."""
        if self.lock_path.is_symlink():
            raise RuntimeError(f'{self.lock_path} es un enlace simbólico')
        lock = self.lock_path.open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            return False
        self._lock = lock
        try:
            if self.endpoint.exists() or self.endpoint.is_symlink():
                if not self.endpoint.is_socket():
                    raise RuntimeError(f'{self.endpoint} está ocupado por otro archivo')
                self.endpoint.unlink()
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(self.endpoint))
            self.endpoint.chmod(0o600)
            server.listen(8)
            server.setblocking(False)
            self._server = server
        except Exception:
            self.close()
            raise
        return True

    def fileno(self):
        return self._server.fileno()

    @property
    def pending(self):
        return bool(self._clients)

    def poll(self, handler, *, limit=LINE_LIMIT, timeout=3.0):
        """Serve every complete request line; ``handler(line)`` may return a reply."""
        if self._server is None:
            return
        while True:
            try:
                client, _ = self._server.accept()
            except (BlockingIOError, InterruptedError):
                break
            client.setblocking(False)
            self._clients.append([client, b'', time.monotonic()])
        for entry in self._clients[:]:
            client, buffer, opened = entry
            finished = False
            try:
                chunk = client.recv(limit + 1)
                if chunk:
                    buffer = entry[1] = buffer + chunk
                else:
                    finished = True
            except BlockingIOError:
                pass
            except OSError:
                finished = True
            if b'\n' in buffer and buffer.index(b'\n') <= limit:
                finished = True             # whatever the handler does, this request is over
                try:
                    reply = handler(buffer.split(b'\n', 1)[0])
                except Exception:
                    traceback.print_exc(file=sys.stderr)
                    reply = None
                if reply is not None:
                    try:
                        client.setblocking(True)
                        client.settimeout(1.0)
                        client.sendall(reply + b'\n')
                    except OSError:
                        pass
            elif len(buffer) > limit or time.monotonic() - opened > timeout:
                finished = True
            if finished:
                client.close()
                self._clients.remove(entry)

    def close(self):
        for client, _, _ in self._clients:
            client.close()
        self._clients = []
        if self._server is not None:
            self._server.close()
            self._server = None
            self.endpoint.unlink(missing_ok=True)
        if self._lock is not None:
            self._lock.close()
            self._lock = None


def release_on_termination(instance):
    """Until the app installs its own handlers, SIGTERM/SIGINT remove the socket and exit cleanly.

    The socket exists as soon as the instance is claimed, often before Qt has started;
    without this a termination in that window would leave a stale endpoint behind.
    """
    def stop(*_):
        instance.close()
        raise SystemExit(0)
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, stop)


def send(endpoint, message, *, timeout=1.0, reply=False, retry=0.0):
    """Deliver one request line. Without ``reply``: True/False. With it: the reply line or None."""
    deadline = time.monotonic() + retry
    while True:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(timeout)
                client.connect(str(endpoint))
                client.sendall(message + b'\n')
                if not reply:
                    return True
                data = b''
                while b'\n' not in data and len(data) <= LINE_LIMIT:
                    part = client.recv(LINE_LIMIT)
                    if not part:
                        break
                    data += part
                return data.split(b'\n', 1)[0]
        except (FileNotFoundError, ConnectionRefusedError):
            if time.monotonic() >= deadline:
                return None if reply else False
            time.sleep(0.03)
        except OSError:
            return None if reply else False
