"""What the bar reads while Wysun Drive uploads, and how it cancels one.

Contract with the shell (apps/shell/services/Drive.qml): every uploading process keeps
``<session runtime dir>/wysun-drive/<pid>.json`` (private directory, atomic writes, at most
once a second plus a heartbeat every HEARTBEAT seconds from a thread) and deletes it on
exit. ``{pid, started, updated, title, items: [{name, done, total}], done, total}``; a file
older than three heartbeats belongs to a dead process.
"""
import json
import os
import signal
import threading
import time
from pathlib import Path

from wysun_core import paths
from wysun_core.jsonio import atomic_path

HEARTBEAT = 10


def status_dir(base=None):
    return Path(base if base is not None else paths.runtime_dir()) / 'wysun-drive'


class StatusFile:
    def __init__(self, pid, title, base=None, clock=time.time):
        self.pid = pid
        self.title = title
        self.clock = clock
        self.path = status_dir(base) / f'{pid}.json'
        self.started = clock()
        self.items = {}
        self.done = 0
        self.total = 0
        self._at = float('-inf')
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def progress(self, name, done, total, all_done, all_total):
        with self._lock:
            self.items[name] = {'name': name, 'done': done, 'total': total}
            self.done, self.total = all_done, all_total
        self.write(force=all_done >= all_total)

    def write(self, force=False):
        now = self.clock()
        if not force and now - self._at < 1:
            return False
        with self._lock:
            data = {'pid': self.pid, 'started': self.started, 'updated': now, 'title': self.title,
                    'items': list(self.items.values()), 'done': self.done, 'total': self.total}
            self._at = now
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        with atomic_path(self.path, mode=0o600) as tmp:
            tmp.write_text(json.dumps(data, ensure_ascii=False))
        return True

    def start(self):
        self.write(force=True)
        self._thread = threading.Thread(target=self._beat, daemon=True)
        self._thread.start()

    def _beat(self):
        while not self._stop.wait(HEARTBEAT):
            try:
                self.write(force=True)
            except OSError:
                pass

    def remove(self):
        self._stop.set()
        self.path.unlink(missing_ok=True)


def _is_drive(pid):
    proc = Path(f'/proc/{pid}')
    try:
        if proc.stat().st_uid != os.getuid():
            return False
        argv = (proc / 'cmdline').read_bytes().split(b'\0')
    except OSError:
        return False
    return any(a == b'-m' and b == b'wysun_drive' for a, b in zip(argv, argv[1:]))


def stop(pid):
    """SIGTERM to an uploading Wysun Drive of this user; False (nothing sent) for any other process."""
    if pid <= 1 or pid == os.getpid() or not _is_drive(pid):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    return True
