"""Samples every process in /proc: CPU, memory, disk I/O, GPU (DRM fdinfo, own processes), the application it
belongs to (its systemd app scope) and smoothed values used to order rows without jitter. Nothing is stored."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import time

from wysun_services.process_data import STATES, username

EMA = 0.15          # weight of the newest sample in the smoothed values that order the rows
SMOOTHED = ('cpu', 'gpu', 'io')
RESCAN = 10        # samples between full scans of a process' descriptors for DRM clients


def application_group(cgroup, fallback):
    """The app of a process from its cgroup (`app-<name>-<id>.scope`), else `fallback`."""
    match = re.search(r'(?:^|/)app-([^/\n]+)\.(?:scope|service)', cgroup)
    if not match:
        return fallback
    name = re.sub(r'-(?:[0-9]+|[0-9a-f]{8,})$', '', match[1])
    name = re.sub(r'^(?:gnome|kde|dbus|flatpak)-', '', name, flags=re.I)
    return name.replace('\\x2d', '-') or fallback


def _slurp(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        return os.read(fd, 8192)
    finally:
        os.close(fd)


@dataclass
class Snapshot:
    rows: list
    system: dict
    time: float = field(default_factory=time.monotonic)


class Sampler:
    def __init__(self, proc_root='/proc', sys_root='/sys'):
        from .system import System
        self.proc = Path(proc_root)
        self.real = str(proc_root) == '/proc'
        self.system = System(proc_root, sys_root)
        self.clock = os.sysconf('SC_CLK_TCK')
        self.page = os.sysconf('SC_PAGE_SIZE')
        self.uid = os.getuid()
        self.previous = {}          # key -> (ticks, read, write, monotonic, drm ns)
        self.smoothed = {}          # key -> {cpu, gpu, io}
        self.identity = {}          # key -> (uid, user, app)
        self.rows = []
        self.drm_fds = {}           # key -> (tick of the last full scan, DRM descriptor names)
        self.tick = 0

    def _drm(self, pid, key):
        """Total DRM engine time (ns) of the process' distinct clients, or None without DRM clients. Which
        descriptors are DRM clients is learnt by a full scan every RESCAN samples; between scans only those
        descriptors are read, so processes without a GPU client cost one dictionary lookup."""
        folder = f'{self.proc}/{pid}/fdinfo'
        known = self.drm_fds.get(key)
        if known is None or (self.tick + pid) % RESCAN == 0:       # staggered: a tenth of them per sample
            try:
                names = os.listdir(folder)
            except OSError:
                self.drm_fds[key] = (self.tick, ())
                return None
            texts = {}
            for name in names:
                try:
                    text = _slurp(f'{folder}/{name}')
                except OSError:
                    continue
                if b'drm-client-id' in text:
                    texts[name] = text
            self.drm_fds[key] = (self.tick, tuple(texts))
        else:
            if not known[1]:
                return None
            texts = {}
            for name in known[1]:
                try:
                    texts[name] = _slurp(f'{folder}/{name}')
                except OSError:
                    pass
        clients = {}
        for text in texts.values():
            data = dict(line.split(':', 1) for line in text.decode('utf-8', 'replace').splitlines() if ':' in line)
            if 'drm-client-id' not in data:
                continue
            client = (data.get('drm-pdev', '').strip(), data['drm-client-id'].strip())
            try:
                clients[client] = sum(int(v.split()[0]) for k, v in data.items()
                                      if k.startswith('drm-engine-') and not k.startswith('drm-engine-capacity-'))
            except ValueError:
                pass
        return sum(clients.values()) if clients else None

    def sample(self):
        now = time.monotonic()
        self.tick += 1
        rows, current, smoothed, identity = [], {}, {}, {}
        try:
            entries = os.listdir(self.proc)
        except OSError:
            entries = []
        for name in entries:
            if not name.isdigit():
                continue
            folder = f'{self.proc}/{name}'
            try:
                raw = _slurp(folder + '/stat').decode('utf-8', 'replace')
                head, _, rest = raw.rpartition(') ')
                fields = rest.split()
                pid = int(name)
                start = fields[19]
                key = (pid, start)
                ticks = int(fields[11]) + int(fields[12])
                known = self.identity.get(key)
                if known is None:
                    uid = os.stat(folder).st_uid
                    try:
                        with open(folder + '/cgroup') as handle:
                            app = application_group(handle.read(), head.split('(', 1)[1])
                    except OSError:
                        app = head.split('(', 1)[1]
                    known = (uid, username(uid), app)
                identity[key] = known
                row = dict(pid=pid, name=head.split('(', 1)[1], state=fields[0], ppid=int(fields[1]),
                           nice=int(fields[16]), threads=int(fields[17]), start=start,
                           mem=int(fields[21]) * self.page, uid=known[0], user=known[1], app=known[2], key=key)
            except (OSError, ValueError, IndexError):
                continue
            try:
                io = _slurp(folder + '/io')
                at = io.index(b'read_bytes:') + 11
                read = int(io[at:io.index(b'\n', at)])
                at = io.index(b'write_bytes:') + 12
                write = int(io[at:io.index(b'\n', at)])
            except (OSError, ValueError, KeyError):
                read = write = None
            drm = self._drm(pid, key) if self.real and known[0] == self.uid else None
            old = self.previous.get(key)
            span = now - old[3] if old else 0
            if old and span > 0:
                row['cpu'] = max(0.0, (ticks - old[0]) / self.clock / span * 100)
                row['read_rate'] = max(0.0, (read - old[1]) / span) if read is not None and old[1] is not None else None
                row['write_rate'] = max(0.0, (write - old[2]) / span) if write is not None and old[2] is not None else None
                row['gpu'] = max(0.0, (drm - old[4]) / 1e9 / span * 100) if drm is not None and old[4] is not None else None
            else:
                row.update(cpu=0.0, read_rate=None, write_rate=None, gpu=None)
            row['io'] = (row['read_rate'] or 0) + (row['write_rate'] or 0)
            row['state_label'] = STATES.get(row['state'], row['state'])
            before = self.smoothed.get(key)
            ema = {}
            for k in SMOOTHED:
                value = row[k] or 0.0
                ema[k] = value if before is None else before[k] * (1 - EMA) + value * EMA
            row['ema'] = ema
            smoothed[key] = ema
            current[key] = (ticks, read, write, now, drm)
            rows.append(row)
        self.previous, self.smoothed, self.identity, self.rows = current, smoothed, identity, rows
        self.drm_fds = {k: v for k, v in self.drm_fds.items() if k in current}
        gpus = [r['gpu'] for r in rows if r['gpu'] is not None]
        system = self.system.read(rows, min(100.0, max(gpus)) if gpus else None)
        return Snapshot(rows, system, now)
