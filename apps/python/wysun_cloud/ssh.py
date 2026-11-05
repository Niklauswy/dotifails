"""The SSH side of Wysun Cloud: persistent probe sessions and on-demand tab commands.

Two routes, never rewriting the user's SSH setup:

* **alias**: the VM has an external IP and ``NAME.ZONE.PROJECT`` is a ``Host``
  line in ``~/.ssh/config``. The alias is used with ``-o HostName=<current IP>``
  so a stop/start that changes the ephemeral IP keeps working.
* **IAP**: everything else goes through ``gcloud compute ssh --tunnel-through-iap``.

The metrics probe is plain POSIX ``sh`` fed on stdin, so the VM needs nothing
installed. ``probe.sh`` prints one line per sample and the client turns pairs of
lines into a :class:`~wysun_cloud.model.Sample`.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

from wysun_cloud.model import Sample, TabData

__all__ = ['BACKOFF', 'ProbeParser', 'ProbeSession', 'SSH_OPTIONS', 'route',
           'run_tab_command', 'ssh_command']

PROBE_PATH = Path(__file__).resolve().with_name('probe.sh')

# ``-o`` options shared by both routes. BatchMode keeps ssh from asking for a
# password; the keepalives detect a dead VM quickly.
SSH_OPTIONS = [
    '-o', 'BatchMode=yes',
    '-o', 'ConnectTimeout=5',
    '-o', 'ServerAliveInterval=5',
    '-o', 'ServerAliveCountMax=2',
]

# Reconnect waits in seconds; the last value repeats forever (Review Focus 3).
BACKOFF = (2, 5, 15, 30)
SIN_SSH_DELAY = 30

IAP_BLOCKED = 'IAP bloqueado: abre el puerto 22 a 35.235.240.0/20'
MISSING_ALIAS = 'falta el alias: ejecuta gcloud compute config-ssh'
PERMISSION_DENIED = 'llave rechazada'
NO_ANSWER = 'sin respuesta'

MB = 1_000_000
KB_PER_GB = 1024 * 1024
SECTOR_BYTES = 512

_REASONS = (
    ('permission denied', PERMISSION_DENIED),
    ('failed to connect to backend', IAP_BLOCKED),
    ('4033', IAP_BLOCKED),
    ('timed out', NO_ANSWER),
    ('timeout', NO_ANSWER),
)


# -- routes ---------------------------------------------------------------
def _alias_configured(inst, ssh_config=None):
    """True when a ``Host`` line in the SSH config lists exactly ``inst.alias``.

    Only the simple token scan from the plan: ``Include`` files are not followed
    and the file is never modified.
    """
    path = Path(ssh_config) if ssh_config is not None else Path.home() / '.ssh' / 'config'
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0].lower() == 'host' and inst.alias in parts[1:]:
            return True
    return False


def route(inst, ssh_config=None):
    """``'alias'`` when the fresh-HostName route applies, else ``'iap'``."""
    if inst.external_ip and _alias_configured(inst, ssh_config):
        return 'alias'
    return 'iap'


def ssh_command(inst, remote, ssh_config=None):
    """The argv to run ``remote`` on ``inst`` (alias route when possible, else IAP)."""
    remote = [str(part) for part in remote]
    if route(inst, ssh_config) == 'alias':
        return ['ssh', *SSH_OPTIONS, '-o', f'HostName={inst.external_ip}', inst.alias, *remote]
    return ['gcloud', 'compute', 'ssh', inst.name, '--zone', inst.zone,
            '--project', inst.project, '--tunnel-through-iap', '--quiet', '--',
            *SSH_OPTIONS, *remote]


# -- probe parsing --------------------------------------------------------
_KEY_RE = re.compile(r'(?:^|\s)(cpu|cores|load|mem|net|disk|df|up|top)=')


def _keyed(line):
    """Split a probe line into ``key -> raw value`` without losing spaces inside values."""
    matches = list(_KEY_RE.finditer(line))
    values = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
        values[match.group(1)] = line[match.end():end].strip()
    return values


def _floats(text):
    return [float(part) for part in text.split()]


def _counters(epoch, fields):
    """Every raw counter of one probe line, or ``None`` when a field is unusable."""
    cpu = _floats(fields['cpu'])
    if len(cpu) != 8:
        return None
    cores = []
    for part in fields.get('cores', '').split(';'):
        part = part.strip()
        if not part:
            continue
        values = [float(item) for item in part.split(',')]
        if len(values) != 2:
            return None
        cores.append((values[0], values[1]))
    load = _floats(fields['load'])
    mem = _floats(fields['mem'])
    net = _floats(fields['net'])
    disk = _floats(fields['disk'])
    if len(load) != 3 or len(mem) != 5 or len(net) != 2 or len(disk) != 2:
        return None
    mounts = []
    for part in fields.get('df', '').split(','):
        part = part.strip()
        if not part:
            continue
        bits = part.rsplit(':', 2)
        if len(bits) != 3:
            return None
        mounts.append((bits[0], float(bits[1]), float(bits[2])))
    top = []
    for part in fields.get('top', '').split('|'):
        part = part.strip()
        if not part:
            continue
        bits = part.split(':', 3)
        if len(bits) != 4:
            return None
        top.append((int(float(bits[0])), float(bits[1]), float(bits[2]), bits[3]))
    return {
        'epoch': float(epoch),
        'cpu': cpu,
        'cores': cores,
        'load': tuple(load),
        'mem': mem,
        'net': net,
        'disk': disk,
        'mounts': mounts,
        'up': int(float(fields['up'])),
        'top': top,
    }


def _fraction(previous, current):
    """Busy share between two ``(total, idle)`` deltas, clamped to 0..1."""
    total = current[0] - previous[0]
    if total <= 0:
        return 0.0
    idle = current[1] - previous[1]
    return min(1.0, max(0.0, (total - idle) / total))


def _rate(new, old, scale, dt):
    return max(0.0, (new - old) * scale / dt)


def _sample(previous, current, dt):
    cpu_total = sum(current['cpu']) - sum(previous['cpu'])
    if cpu_total <= 0:
        cpu = 0.0
    else:
        idle = ((current['cpu'][3] - previous['cpu'][3])
                + (current['cpu'][4] - previous['cpu'][4]))
        cpu = min(1.0, max(0.0, (cpu_total - idle) / cpu_total))
    cores = [_fraction(old, new) for old, new in zip(previous['cores'], current['cores'])]

    mem_total, mem_available, cached, swap_total, swap_free = current['mem']
    return Sample(
        cpu=cpu,
        cores=cores,
        load=current['load'],
        ram_used_gb=(mem_total - mem_available) / KB_PER_GB,
        ram_total_gb=mem_total / KB_PER_GB,
        cache_gb=cached / KB_PER_GB,
        swap_used_gb=(swap_total - swap_free) / KB_PER_GB,
        swap_total_gb=swap_total / KB_PER_GB,
        rx_mbs=_rate(current['net'][0], previous['net'][0], 1 / MB, dt),
        tx_mbs=_rate(current['net'][1], previous['net'][1], 1 / MB, dt),
        read_mbs=_rate(current['disk'][0], previous['disk'][0], SECTOR_BYTES / MB, dt),
        write_mbs=_rate(current['disk'][1], previous['disk'][1], SECTOR_BYTES / MB, dt),
        mounts=[(mount, used / KB_PER_GB, size / KB_PER_GB)
                for mount, used, size in current['mounts']],
        uptime_s=current['up'],
        top=[(pid, pcpu, rss / KB_PER_GB, command)
             for pid, pcpu, rss, command in current['top']],
    )


class ProbeParser:
    """Turn consecutive probe lines into a :class:`Sample`; the first line is a baseline."""

    def __init__(self):
        self._previous = None

    def reset(self):
        self._previous = None

    def feed(self, line):
        """A Sample for the delta since the previous line, or ``None``."""
        if not isinstance(line, str):
            return None
        try:
            parts = line.strip().split(None, 2)
            if len(parts) < 3 or parts[0] != 'S':
                return None
            epoch = float(parts[1])
            current = _counters(epoch, _keyed(line))
            if current is None:
                return None
            previous, self._previous = self._previous, current
            if previous is None:
                return None
            dt = epoch - previous['epoch']
            if dt <= 0:
                return None
            return _sample(previous, current, dt)
        except Exception:
            # A truncated or garbled line is a lost sample, never a crash.
            return None


# -- persistent session ---------------------------------------------------
class ProbeSession:
    """One persistent ``ssh … sh -s`` per running VM, reconnecting with backoff.

    ``on_state(state, reason)`` fires only when the state (or its reason)
    changes: ``conectando`` once at start, ``activo`` on the first Sample,
    ``reconectando`` when a live session drops, and ``sin-ssh`` plus a short
    Spanish reason when stderr names a permanent cause. ``sin-ssh`` keeps
    retrying every 30 s; a successful ``activo`` resets the backoff.
    """

    def __init__(self, app, inst, on_sample, on_state, ssh_config=None, interval=1):
        self.app = app
        self.inst = inst
        self.on_sample = on_sample
        self.on_state = on_state
        self.ssh_config = ssh_config
        self.interval = interval
        self._child = None
        self._timer = None
        self._parser = ProbeParser()
        self._stopped = False
        self._started = False
        self._attempt = 0
        self._reason = ''
        self._used_iap = False
        self._last_state = None

    # -- lifecycle --------------------------------------------------------
    def start(self):
        if self._started or self._stopped:
            return
        self._started = True
        self._emit('conectando', '')
        self._connect()

    def stop(self):
        """Kill the child and any pending reconnect; no callback fires afterwards."""
        self._stopped = True
        if self._timer is not None:
            self.app.cancel(self._timer)
            self._timer = None
        child, self._child = self._child, None
        if child is not None:
            child.kill()

    # -- internals --------------------------------------------------------
    def _emit(self, state, reason=''):
        if self._stopped:
            return
        if (state, reason) == self._last_state:
            return
        self._last_state = (state, reason)
        self.on_state(state, reason)

    def _connect(self):
        if self._stopped:
            return
        self._timer = None
        self._parser = ProbeParser()
        self._used_iap = route(self.inst, self.ssh_config) == 'iap'
        argv = ssh_command(self.inst, ['sh', '-s'], self.ssh_config)
        try:
            script = PROBE_PATH.read_bytes()
        except OSError:
            self._emit('sin-ssh', NO_ANSWER)
            self._reason = NO_ANSWER
            self._schedule_retry()
            return
        # The remote environment cannot be set from outside: the first line of
        # the stdin script sets INTERVAL for the shell that runs it.
        payload = f'INTERVAL={self.interval}\n'.encode('ascii') + script
        self._child = self.app.spawn(
            argv, self._on_line, self._on_exit, stdin=payload, on_err_line=self._on_err,
        )

    def _on_line(self, line):
        if self._stopped:
            return
        sample = self._parser.feed(line)
        if sample is None:
            return
        self._attempt = 0
        self._reason = ''
        self._emit('activo', '')
        self.on_sample(sample)

    def _on_err(self, line):
        if self._stopped:
            return
        reason = self._reason_for(line)
        if reason:
            self._reason = reason
            self._emit('sin-ssh', reason)

    def _reason_for(self, line):
        """A short Spanish reason for a permanent failure, or ``''`` for noise."""
        text = (line or '').strip()
        if not text:
            return ''
        lowered = text.lower()
        for needle, reason in _REASONS:
            if needle in lowered:
                return reason
        # No specific message, but the alias route was unavailable (external IP
        # without a Host line) and IAP failed too: the fix is config-ssh.
        if (self._used_iap and self.inst.external_ip
                and not _alias_configured(self.inst, self.ssh_config)):
            return MISSING_ALIAS
        return ''

    def _on_exit(self, returncode):
        if self._stopped:
            return
        self._child = None
        if not self._reason:
            self._emit('reconectando', '')
        self._schedule_retry()

    def _schedule_retry(self):
        if self._stopped:
            return
        if self._reason:
            delay = SIN_SSH_DELAY
        else:
            delay = BACKOFF[min(self._attempt, len(BACKOFF) - 1)]
            self._attempt += 1
        self._timer = self.app.after(delay, self._connect)


# -- tab commands ---------------------------------------------------------
COMMANDS = {
    'ports': 'ss -tlnp',
    'journal': 'journalctl -p warning --since -1h --no-pager -o short-iso',
    'docker': "docker ps -a --format '{{json .}}'",
    'failed': 'systemctl --failed --no-legend --plain',
    'du': 'du -x -d2 -k / 2>/dev/null | sort -rn | head -12',
}

DOCKER_MISSING = 'docker no está instalado'


def _remote(sudo, command):
    """The remote argv for ``command``.

    ``ssh`` joins the remote arguments with spaces and the login shell parses
    the result again, so the whole command travels as one ``shlex.quote``d
    argument to ``sh -c``; pipes and redirections in ``du`` arrive intact.
    """
    quoting = ['sh', '-c', shlex.quote(command)]
    return ['sudo', '-n', *quoting] if sudo else quoting


def _missing_docker(returncode, stderr_lines):
    if returncode == 127:
        return True
    return any('not found' in line.lower() or 'no se encontró' in line.lower()
               or 'command not found' in line.lower() for line in stderr_lines)


def run_tab_command(app, inst, kind, on_done):
    """Run one detail-tab command over SSH and call ``on_done(TabData)`` once.

    The first try is ``sudo -n`` (never prompting); a failure that mentions
    ``sudo:`` retries without it and marks the result ``limited`` so the UI can
    say «necesita permisos».
    """
    command = COMMANDS.get(kind)
    if command is None:
        on_done(TabData(kind=kind, lines=[], limited=False, error='orden desconocida'))
        return

    lines: list[str] = []
    child = None

    def finish(returncode, limited):
        stderr_lines = [line.strip() for line in (child.stderr_tail if child else []) if line.strip()]
        error = None
        result_lines = lines
        if returncode != 0:
            if kind == 'docker' and _missing_docker(returncode, stderr_lines):
                error = DOCKER_MISSING
                result_lines = []
            else:
                last = stderr_lines[-1][:80] if stderr_lines else ''
                error = f'no se pudo leer: {last}' if last else 'no se pudo leer'
        on_done(TabData(kind=kind, lines=list(result_lines), limited=limited, error=error))

    def run(sudo, limited):
        nonlocal child
        lines.clear()
        child = app.spawn(ssh_command(inst, _remote(sudo, command)),
                          lambda line: lines.append(line),
                          lambda code: on_exit(code, sudo, limited))

    def on_exit(code, sudo, limited):
        if code != 0 and sudo and any('sudo:' in line for line in child.stderr_tail):
            run(False, True)
            return
        finish(code, limited)

    run(True, False)
