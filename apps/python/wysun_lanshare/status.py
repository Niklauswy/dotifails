"""Who is using a LANShare, when it shuts itself down, and what the bar reads.

Contract with the shell (apps/shell/services/LanShare.qml): every server keeps
``$XDG_RUNTIME_DIR/wysun-lanshare/<pid>.json`` (private directory, atomic writes, at most about
once a second plus a heartbeat every HEARTBEAT seconds) and deletes it on exit. A file whose
``updated`` is older than three heartbeats belongs to a dead server.
"""
import itertools
import json
import os
from pathlib import Path
import signal
import threading
import time

from wysun_core.jsonio import atomic_path

HEARTBEAT = 10
RECENT = 300          # seconds a client counts as connected after its last request


def device_of(agent):
    agent = agent or ''
    for needle, name in (('iPhone', 'iPhone'), ('iPad', 'iPad'), ('Android', 'Android'), ('Windows', 'Windows'),
                         ('Macintosh', 'Mac'), ('Mac OS X', 'Mac'), ('CrOS', 'Chromebook'), ('Linux', 'Linux')):
        if needle in agent:
            return name
    return 'Navegador'


class Activity:
    """Requests and transfers of clients that are in (with a password: only those who entered)."""

    def __init__(self, idle, clock=time.time):
        self.idle = idle
        self.clock = clock
        self.last = clock()
        self.version = 0
        self._seen = {}
        self._transfers = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def _changed(self):
        self.version += 1

    def touch(self, ip, agent):
        with self._lock:
            self.last = self.clock()
            self._seen[ip] = (device_of(agent), self.last)
            self._changed()

    def begin(self, ip, agent, name, total, direction):
        with self._lock:
            tid = next(self._ids)
            self.last = self.clock()
            self._seen[ip] = (device_of(agent), self.last)
            self._transfers[tid] = {'ip': ip, 'device': device_of(agent), 'name': name, 'done': 0,
                                    'total': total, 'direction': direction}
            self._changed()
            return tid

    def advance(self, tid, count):
        with self._lock:
            if tid in self._transfers:
                self._transfers[tid]['done'] += count
                self._changed()

    def end(self, tid):
        with self._lock:
            self._transfers.pop(tid, None)
            self.last = self.clock()
            self._changed()

    def busy(self):
        return bool(self._transfers)

    def deadline(self):
        return None if self.idle is None else self.last + self.idle

    def expired(self):
        deadline = self.deadline()
        return deadline is not None and not self.busy() and self.clock() > deadline

    def clients(self):
        now = self.clock()
        with self._lock:
            return [{'ip': ip, 'device': device, 'seen': seen} for ip, (device, seen) in sorted(self._seen.items())
                    if now - seen <= RECENT or any(t['ip'] == ip for t in self._transfers.values())]

    def transfers(self):
        with self._lock:
            return [dict(t) for t in self._transfers.values()]


def status_dir(environ=None):
    environ = os.environ if environ is None else environ
    runtime = environ.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}'
    return Path(runtime) / 'wysun-lanshare'


class StatusFile:
    def __init__(self, pid, info, environ=None, clock=time.time):
        self.pid = pid
        self.info = dict(info)
        self.clock = clock
        self.path = status_dir(environ) / f'{pid}.json'
        self._written = None
        self._at = float('-inf')

    def write(self, activity, force=False):
        """Write when something changed (at most once a second) or the heartbeat is due; True if written."""
        now = self.clock()
        key = activity.version
        due = now - self._at >= HEARTBEAT
        if not force and not due and (key == self._written or now - self._at < 1):
            return False
        data = dict(self.info, pid=self.pid, clients=activity.clients(), transfers=activity.transfers(),
                    shutdownAt=activity.deadline(), updated=now)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        with atomic_path(self.path, mode=0o600) as tmp:
            tmp.write_text(json.dumps(data, ensure_ascii=False))
        self._written, self._at = key, now
        return True

    def remove(self):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def _is_lanshare(pid):
    """True when pid is a process of this user running `python3 … -m wysun_lanshare`."""
    proc = Path(f'/proc/{pid}')
    try:
        if proc.stat().st_uid != os.getuid():
            return False
        argv = (proc / 'cmdline').read_bytes().split(b'\0')
    except OSError:
        return False
    return any(a == b'-m' and b == b'wysun_lanshare' for a, b in zip(argv, argv[1:]))


def stop(pid):
    """SIGTERM to a LANShare of this user; False (and nothing sent) for any other process."""
    if pid <= 1 or pid == os.getpid() or not _is_lanshare(pid):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    return True


def prune(environ=None):
    """Delete the status files of servers that are no longer running."""
    directory = status_dir(environ)
    try:
        files = list(directory.glob('*.json'))
    except OSError:
        return
    for path in files:
        if path.stem.isdigit() and not Path(f'/proc/{path.stem}').exists():
            path.unlink(missing_ok=True)
