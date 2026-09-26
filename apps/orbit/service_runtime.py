"""Own only the processes started by this desktop, scoped to the X display."""
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path


def identity(pid):
    try:
        fields = Path(f'/proc/{int(pid)}/stat').read_text().rsplit(') ', 1)[1].split()
        return fields[19] if fields[0] != 'Z' else None
    except (OSError, ValueError, IndexError):
        return None


class Services:
    def __init__(self):
        base = Path(os.environ.get('XDG_RUNTIME_DIR', str(Path.home()/'.cache')))
        display = hashlib.sha256(os.environ.get('DISPLAY', '').encode()).hexdigest()[:12]
        self.root = base/f'dotifails-{os.getuid()}-{display}'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, name):
        if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
            raise ValueError('Nombre de servicio inválido')
        return self.root/(name+'.json')

    def running(self, name):
        try:
            item = json.loads(self.path(name).read_text())
            if item.get('start') is not None and identity(item['pid']) == item['start']:
                return item['pid']
        except (OSError, ValueError, KeyError):
            pass
        return None

    def stop(self, name):
        pid = self.running(name)
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for _ in range(40):
            if not self.running(name):
                break
            time.sleep(.05)
        if self.running(name):
            raise RuntimeError(f'{name} no se detuvo; no se iniciará un duplicado')
        self.path(name).unlink(missing_ok=True)

    def start(self, name, argv, env=None):
        with self.path(name).with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            pid = self.running(name)
            if pid:
                return pid
            state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))/'dotifails'
            state.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (state/(name+'.log')).open('ab') as log:
                process = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=log, start_new_session=True)
            self.path(name).write_text(json.dumps({'pid': process.pid, 'start': identity(process.pid)}))
            return process.pid
