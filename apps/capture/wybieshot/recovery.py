"""Cooperative recovery scoped to a private runtime directory and compositor.

Never signal a process: a library or clipboard owner has nothing to recover.
The GUI acknowledges only after preserving annotations and releasing overlays.
"""
import hashlib
import os
from pathlib import Path
import socket
import tempfile


def runtime_directory():
    from .instance import CaptureLease
    directory = CaptureLease().directory
    if directory.is_symlink():
        raise RuntimeError('Unsafe screenshot runtime directory')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('Screenshot runtime directory must be private')
    return directory


def session_key():
    identity = '\0'.join(os.environ.get(name, '') for name in
                         ('HYPRLAND_INSTANCE_SIGNATURE', 'WAYLAND_DISPLAY', 'DISPLAY'))
    return hashlib.sha256(identity.encode()).hexdigest()[:16]


class RecoveryServer:
    def __init__(self, app):
        from PySide6.QtCore import QSocketNotifier
        self.app = app
        self.path = runtime_directory() / f'recover-{session_key()}-{os.getpid()}.sock'
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            self.socket.bind(str(self.path))
        except Exception:
            self.socket.close()
            raise
        self.socket.setblocking(False)
        self.notifier = QSocketNotifier(self.socket.fileno(), QSocketNotifier.Read, app)
        self.notifier.activated.connect(self.receive)

    def receive(self, *_):
        try:
            message, sender = self.socket.recvfrom(64)
        except BlockingIOError:
            return
        if message != b'cancel-selection' or not sender:
            return
        window = getattr(self.app, '_wybieshot_window', None)
        try:
            result = window.recover_capture() if window is not None else False
            reply = b'closed' if result else b'idle'
        except Exception:
            # Leave the document/overlay available if persistence failed.
            reply = b'error'
        try:
            self.socket.sendto(reply, sender)
        except OSError:
            pass

    def close(self):
        if self.socket.fileno() == -1:return
        self.notifier.setEnabled(False)
        self.notifier.deleteLater()
        self.socket.close()
        self.path.unlink(missing_ok=True)


def request_recovery():
    directory = runtime_directory()
    closed = failed = 0
    # Private reply socket; only endpoints for this compositor are contacted.
    with tempfile.TemporaryDirectory(prefix='reply-', dir=directory) as temporary:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.bind(str(Path(temporary) / 's'))
            client.settimeout(1)
            for path in directory.glob(f'recover-{session_key()}-*.sock'):
                try:
                    client.connect(str(path))
                    client.send(b'cancel-selection')
                    response = client.recv(64)
                    if response == b'closed':closed += 1
                    elif response != b'idle':failed += 1
                except ConnectionRefusedError:
                    # Stale socket from a crashed app. Never touch a PID.
                    continue
                except OSError:
                    failed += 1
    return closed, failed
