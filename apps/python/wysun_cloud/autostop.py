"""Automatic power-off for VMs: the rules, the guard installed on the VM and what it reports.

Everything runs on the VM so it works for every rule the same way and needs no IAM change:
``autostop_guard.sh`` is installed as ``/usr/local/libexec/wysun-autostop`` and a systemd timer
runs it every minute as root. Wysun Cloud only writes ``/etc/wysun-autostop.conf`` (validated
here: the guard sources it) and reads back:

* every second, through the probe's ``auto=`` field (:func:`parse_live`), the next power-off,
  its reason, since when the VM is quiet and the one-off ``shutdown -h +N`` if there is one;
* on demand, the rules themselves (:data:`STATUS_COMMAND`, :func:`parse_status`).

The one-off power-off ("una vez") is plain ``shutdown -h +N`` / ``shutdown -c``; it does not
need the guard. Every change travels as one ``sudo -n sh -s`` script on stdin
(:func:`apply_script`, :func:`postpone_script`), never as a command line.

Times are shown in this computer's timezone, and a schedule is saved with that timezone so
«02:00» means 02:00 here, whatever the VM's clock says.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:                      # pragma: no cover - Python 3.9+ always has it
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

__all__ = ['Rules', 'Live', 'Status', 'Once', 'STATUS_COMMAND', 'DAY_PRESETS', 'parse_conf',
           'render_conf', 'parse_live', 'parse_status', 'apply_script', 'postpone_script',
           'next_stop', 'next_schedule', 'local_tz', 'fmt_duration', 'fmt_when',
           'describe_days', 'describe_rules', 'busy_text', 'REASON_TEXT', 'step']

GUARD_SOURCE = Path(__file__).resolve().with_name('autostop_guard.sh')
GUARD_PATH = '/usr/local/libexec/wysun-autostop'
CONF_PATH = '/etc/wysun-autostop.conf'
STATE_DIR = '/var/lib/wysun-autostop'
UNIT = 'wysun-autostop'
OK_MARK = 'WYSUN_AUTOSTOP_OK'

DEFAULT_PROCS = ('claude', 'codex', 'opencode')
DAY_LETTERS = 'LMXJVSD'
DAY_NAMES = ('lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom')
DAY_PRESETS = (('1234567', 'todos los días'), ('12345', 'de lunes a viernes'),
               ('67', 'sábados y domingos'))

# The values the editor steps through with ← →.
MAX_STEPS = (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 24, 48)
IDLE_STEPS = (10, 15, 20, 30, 45, 60, 90, 120, 180, 240)
CPU_STEPS = (2, 5, 10, 15, 20, 30, 50)
ONCE_STEPS = (15, 30, 60, 90, 120, 180, 240, 300, 360, 480, 600, 720, 1440)   # minutes

REASON_TEXT = {'schedule': 'por horario fijo', 'max': 'por tiempo máximo',
               'idle': 'por inactividad', 'once': 'programado una vez'}

_TIME_RE = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
_TZ_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+)*$')
_PROC_RE = re.compile(r'^[A-Za-z0-9._+\-]{1,15}$')
_DAYS_RE = re.compile(r'^[1-7]{1,7}$')

STATUS_COMMAND = (
    f'cat {CONF_PATH} 2>/dev/null; echo @@state; cat {STATE_DIR}/state 2>/dev/null; '
    f'echo @@postpone; cat {STATE_DIR}/postpone 2>/dev/null; echo; '
    'echo @@once; cat /run/systemd/shutdown/scheduled 2>/dev/null; '
    f'echo @@timer; systemctl is-active {UNIT}.timer 2>/dev/null; true'
)


# -- rules ----------------------------------------------------------------
@dataclass(frozen=True)
class Rules:
    """The guard's rules; a value of ``0``/``None`` turns that rule off."""

    schedule_at: str | None = None        # 'HH:MM'
    days: str = '1234567'                 # date +%u digits, 1 = Monday
    tz: str = 'UTC'
    schedule_from: int = 0                # epoch the schedule rule was saved
    max_hours: int = 0
    max_from: int = 0
    idle_minutes: int = 0
    idle_cpu: int = 10
    idle_ssh: bool = True
    idle_procs: tuple[str, ...] = DEFAULT_PROCS
    warn_minutes: int = 5

    @property
    def any(self) -> bool:
        return bool(self.schedule_at and self.days) or self.max_hours > 0 or self.idle_minutes > 0


def _int(text, default=0, low=0, high=10 ** 12):
    try:
        value = int(str(text).strip())
    except (TypeError, ValueError):
        return default
    return value if low <= value <= high else default


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
        return value[1:-1]
    return value


def parse_conf(text: str) -> Rules:
    """Read ``/etc/wysun-autostop.conf``; anything invalid falls back to the rule being off."""
    values = {}
    for raw in (text or '').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        values[key.strip()] = _unquote(value.split(' #', 1)[0])
    at = values.get('SCHEDULE_AT', '')
    days = ''.join(sorted(set(values.get('SCHEDULE_DAYS', '1234567'))))
    tz = values.get('SCHEDULE_TZ', 'UTC')
    procs = tuple(name for name in values.get('IDLE_PROCS', ' '.join(DEFAULT_PROCS)).split()
                  if _PROC_RE.match(name))
    return Rules(
        schedule_at=at if _TIME_RE.match(at) else None,
        days=days if _DAYS_RE.match(days) else '1234567',
        tz=tz if _TZ_RE.match(tz) else 'UTC',
        schedule_from=_int(values.get('SCHEDULE_FROM')),
        max_hours=_int(values.get('MAX_HOURS'), high=24 * 365),
        max_from=_int(values.get('MAX_FROM')),
        idle_minutes=_int(values.get('IDLE_MINUTES'), high=60 * 24 * 30),
        idle_cpu=_int(values.get('IDLE_CPU'), 10, 1, 100),
        idle_ssh=values.get('IDLE_SSH', '1') != '0',
        idle_procs=procs,
        warn_minutes=_int(values.get('WARN_MINUTES'), 5, 0, 120),
    )


def _check(rules: Rules) -> None:
    """Refuse anything the root shell that sources the file could misread."""
    if rules.schedule_at is not None and not _TIME_RE.match(rules.schedule_at):
        raise ValueError(f'hora inválida: {rules.schedule_at!r}')
    if not _DAYS_RE.match(rules.days or ''):
        raise ValueError(f'días inválidos: {rules.days!r}')
    if not _TZ_RE.match(rules.tz or ''):
        raise ValueError(f'zona horaria inválida: {rules.tz!r}')
    for name in rules.idle_procs:
        if not _PROC_RE.match(name):
            raise ValueError(f'nombre de proceso inválido: {name!r}')
    for name in ('schedule_from', 'max_hours', 'max_from', 'idle_minutes', 'idle_cpu', 'warn_minutes'):
        value = getattr(rules, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f'{name} inválido: {value!r}')


def render_conf(rules: Rules) -> str:
    """The conf file for ``rules`` (validated first: it is sourced by root)."""
    _check(rules)
    lines = [
        '# Apagado automático de Wysun Cloud. Lo escribe Wysun Cloud (wysun cloud › Apagado).',
        f'SCHEDULE_AT={rules.schedule_at or ""}',
        f'SCHEDULE_DAYS={rules.days}',
        f'SCHEDULE_TZ={rules.tz}',
        f'SCHEDULE_FROM={rules.schedule_from}',
        f'MAX_HOURS={rules.max_hours}',
        f'MAX_FROM={rules.max_from}',
        f'IDLE_MINUTES={rules.idle_minutes}',
        f'IDLE_CPU={rules.idle_cpu}',
        f'IDLE_SSH={1 if rules.idle_ssh else 0}',
        f'IDLE_PROCS="{" ".join(rules.idle_procs)}"',
        f'WARN_MINUTES={rules.warn_minutes}',
    ]
    return '\n'.join(lines) + '\n'


def stamp(new: Rules, old: Rules | None, now: int) -> Rules:
    """``new`` with ``*_from`` set to ``now`` for rules that changed (kept for the others).

    A rule counts from when it was saved, so turning on «2 h encendida» on a VM that has been
    up for 5 h, or «a las 02:00» at 09:00, never powers it off on the spot.
    """
    old = old or Rules()
    schedule_same = (new.schedule_at, new.days, new.tz) == (old.schedule_at, old.days, old.tz)
    max_same = new.max_hours == old.max_hours
    return replace(new,
                   schedule_from=old.schedule_from if schedule_same and new.schedule_at else (
                       int(now) if new.schedule_at else 0),
                   max_from=old.max_from if max_same and new.max_hours else (
                       int(now) if new.max_hours else 0))


# -- what the VM reports --------------------------------------------------
@dataclass(frozen=True)
class Live:
    """The probe's ``auto=`` field: ``installed next reason idle_since busy once``."""

    installed: bool = False
    next_at: int = 0
    reason: str = ''
    idle_since: int = 0
    busy: str = ''
    once_at: int = 0


def parse_live(text: str | None) -> Live | None:
    if not text:
        return None
    parts = text.split()
    if len(parts) != 6:
        return None
    clean = [('' if part == '-' else part) for part in parts]
    return Live(installed=clean[0] == '1', next_at=_int(clean[1]), reason=clean[2],
                idle_since=_int(clean[3]), busy=clean[4], once_at=_int(clean[5]))


@dataclass(frozen=True)
class Status:
    """Everything the Apagado tab and the editor read from the VM."""

    installed: bool = False
    active: bool = False
    rules: Rules = field(default_factory=Rules)
    next_at: int = 0
    reason: str = ''
    idle_since: int = 0
    busy: str = ''
    cpu: int | None = None
    checked: int = 0
    postpone: int = 0
    once_at: int = 0

    @property
    def live(self) -> Live:
        return Live(installed=self.installed, next_at=self.next_at, reason=self.reason,
                    idle_since=self.idle_since, busy=self.busy, once_at=self.once_at)


def _keyvalues(lines):
    found = {}
    for line in lines:
        key, sep, value = line.partition('=')
        if sep:
            found[key.strip()] = value.strip()
    return found


def parse_status(lines) -> Status:
    """Parse :data:`STATUS_COMMAND`'s output."""
    sections = {'conf': []}
    current = 'conf'
    for raw in lines or []:
        line = str(raw).rstrip('\r')
        if line.startswith('@@'):
            current = line[2:].strip()
            sections[current] = []
            continue
        sections.setdefault(current, []).append(line)
    conf = '\n'.join(sections.get('conf', []))
    state = _keyvalues(sections.get('state', []))
    once = _keyvalues(sections.get('once', []))
    once_at = 0
    if once.get('MODE', 'poweroff') in ('poweroff', 'halt') and once.get('USEC'):
        once_at = _int(once['USEC'], high=10 ** 18) // 1_000_000
    timer = ' '.join(sections.get('timer', [])).strip()
    cpu = state.get('CPU')
    return Status(
        installed=bool(conf.strip()),
        active=timer == 'active',
        rules=parse_conf(conf) if conf.strip() else Rules(),
        next_at=_int(state.get('NEXT_AT')),
        reason=state.get('NEXT_REASON', ''),
        idle_since=_int(state.get('IDLE_SINCE')),
        busy=state.get('BUSY', ''),
        cpu=_int(cpu, None, 0, 100) if cpu not in (None, '') else None,
        checked=_int(state.get('CHECKED')),
        postpone=_int(' '.join(sections.get('postpone', [])).strip()),
        once_at=once_at,
    )


def next_stop(live: Live | None, now: float | None = None) -> tuple[int, str] | None:
    """The soonest power-off (guard or one-off) still ahead: ``(epoch, reason)``."""
    if live is None:
        return None
    now = time.time() if now is None else now
    options = []
    if live.installed and live.next_at > 0:
        options.append((live.next_at, live.reason or 'schedule'))
    if live.once_at > 0:
        options.append((live.once_at, 'once'))
    options = [option for option in options if option[0] >= now - 90]
    return min(options) if options else None


# -- the scripts that go to the VM ----------------------------------------
@dataclass(frozen=True)
class Once:
    """The one-off power-off: keep whatever is there, cancel it, or set it ``minutes`` ahead."""

    action: str = 'keep'                  # 'keep' | 'cancel' | 'set'
    minutes: int = 0


def _heredoc(path: str, body: str, mode: str, tag: str) -> list[str]:
    if f'\n{tag}\n' in f'\n{body}\n':
        raise ValueError('el contenido contiene el marcador del heredoc')
    return [f"cat > {path}.tmp <<'{tag}'", body.rstrip('\n'), tag,
            f'chmod {mode} {path}.tmp', f'mv -f {path}.tmp {path}']


SERVICE = f"""[Unit]
Description=Wysun Cloud: apagado automático

[Service]
Type=oneshot
ExecStart={GUARD_PATH}
"""

TIMER = """[Unit]
Description=Wysun Cloud: revisa el apagado automático cada minuto

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=5s

[Install]
WantedBy=timers.target
"""


def apply_script(rules: Rules, once: Once = Once(), guard: str | None = None) -> str:
    """The ``sudo -n sh -s`` script that leaves the VM with ``rules`` and ``once``.

    With no rule left on, the guard, its units, conf and state are removed. It prints
    :data:`OK_MARK` last, so a script cut short never looks like a success.
    """
    lines = ['set -eu']
    if rules.any:
        guard = GUARD_SOURCE.read_text(encoding='utf-8') if guard is None else guard
        lines += [f'install -d -m 0755 /usr/local/libexec {STATE_DIR}']
        lines += _heredoc(GUARD_PATH, guard, '0755', 'WYSUN_GUARD_EOF')
        lines += _heredoc(f'/etc/systemd/system/{UNIT}.service', SERVICE, '0644', 'WYSUN_UNIT_EOF')
        lines += _heredoc(f'/etc/systemd/system/{UNIT}.timer', TIMER, '0644', 'WYSUN_UNIT_EOF')
        lines += _heredoc(CONF_PATH, render_conf(rules), '0644', 'WYSUN_CONF_EOF')
        # New rules start from a clean slate: no stale idle time, warning or postponement.
        lines += [f'rm -f {STATE_DIR}/state {STATE_DIR}/postpone',
                  'systemctl daemon-reload',
                  f'systemctl enable {UNIT}.timer >/dev/null 2>&1',
                  f'systemctl restart {UNIT}.timer',
                  f'systemctl start {UNIT}.service || true']
    else:
        lines += [f'systemctl disable --now {UNIT}.timer >/dev/null 2>&1 || true',
                  f'rm -f {GUARD_PATH} {CONF_PATH} /etc/systemd/system/{UNIT}.service '
                  f'/etc/systemd/system/{UNIT}.timer',
                  f'rm -rf {STATE_DIR}',
                  'systemctl daemon-reload']
    if once.action == 'cancel':
        lines.append('shutdown -c >/dev/null 2>&1 || true')
    elif once.action == 'set':
        minutes = int(once.minutes)
        if minutes <= 0:
            raise ValueError('minutos inválidos')
        lines.append(f"shutdown -h +{minutes} 'Wysun Cloud: apagado programado' >/dev/null 2>&1")
    lines.append(f'echo {OK_MARK}')
    return '\n'.join(lines) + '\n'


def postpone_script(until: int, once_minutes: int | None = None) -> str:
    """Delay the guard's power-off until ``until``; with ``once_minutes`` the one-off
    ``shutdown`` moves too (to that many minutes from now)."""
    until = int(until)
    lines = ['set -eu',
             f'if [ -d {STATE_DIR} ]; then',
             f'  echo {until} > {STATE_DIR}/postpone.tmp',
             f'  chmod 0644 {STATE_DIR}/postpone.tmp',
             f'  mv -f {STATE_DIR}/postpone.tmp {STATE_DIR}/postpone',
             'fi']
    if once_minutes is not None:
        minutes = int(once_minutes)
        if minutes <= 0:
            raise ValueError('minutos inválidos')
        lines.append(f"shutdown -h +{minutes} 'Wysun Cloud: apagado programado' >/dev/null 2>&1")
    lines.append(f'echo {OK_MARK}')
    return '\n'.join(lines) + '\n'


# -- time and text --------------------------------------------------------
def local_tz() -> str:
    """This computer's IANA timezone name (``UTC`` when it cannot be told)."""
    name = os.environ.get('TZ', '').lstrip(':')
    if name and _TZ_RE.match(name) and _zone(name) is not None:
        return name
    try:
        target = os.path.realpath('/etc/localtime')
        if 'zoneinfo/' in target:
            name = target.split('zoneinfo/', 1)[1]
            if _TZ_RE.match(name):
                return name
    except OSError:
        pass
    try:
        name = Path('/etc/timezone').read_text(encoding='utf-8').strip()
        if _TZ_RE.match(name):
            return name
    except OSError:
        pass
    return 'UTC'


def _zone(name):
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def next_schedule(rules: Rules, ref: float) -> int:
    """The guard's schedule rule in Python (for previews): first time after ``ref``, or 0."""
    if not rules.schedule_at or not rules.days:
        return 0
    zone = _zone(rules.tz)
    if zone is None:
        return 0
    hour, minute = (int(part) for part in rules.schedule_at.split(':'))
    start = datetime.fromtimestamp(ref, zone).date()
    for offset in range(9):
        day = start + timedelta(days=offset)
        if str(day.isoweekday()) not in rules.days:
            continue
        moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
        # A wall time that does not exist that night (daylight saving) skips the day.
        if datetime.fromtimestamp(moment.timestamp(), zone).replace(tzinfo=None) != moment.replace(tzinfo=None):
            continue
        if moment.timestamp() > ref:
            return int(moment.timestamp())
    return 0


def fmt_duration(seconds: float) -> str:
    """``4 h 12 min`` · ``35 min`` · ``2 d 3 h`` · ``menos de 1 min``."""
    seconds = int(max(0, seconds))
    if seconds < 60:
        return 'menos de 1 min'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes} min'
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f'{hours} h {minutes} min' if minutes else f'{hours} h'
    days, hours = divmod(hours, 24)
    return f'{days} d {hours} h' if hours else f'{days} d'


def fmt_when(epoch: float, now: float | None = None) -> str:
    """``17:42`` today, ``mañana 02:00``, ``mié 02:00`` this week, else ``12 nov 02:00``."""
    now = time.time() if now is None else now
    when = datetime.fromtimestamp(epoch)
    today = datetime.fromtimestamp(now).date()
    clock = when.strftime('%H:%M')
    days = (when.date() - today).days
    if days == 0:
        return clock
    if days == 1:
        return f'mañana {clock}'
    if days == -1:
        return f'ayer {clock}'
    if 1 < days < 7:
        return f'{DAY_NAMES[when.weekday()]} {clock}'
    months = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')
    return f'{when.day} {months[when.month - 1]} {clock}'


def describe_days(days: str) -> str:
    for value, label in DAY_PRESETS:
        if days == value:
            return label
    names = [DAY_NAMES[int(digit) - 1] for digit in sorted(days)]
    if len(names) == 1:
        return f'solo {names[0]}'
    return ', '.join(names[:-1]) + f' y {names[-1]}'


def describe_rules(rules: Rules) -> list[str]:
    """One short phrase per active rule, for the Apagado tab and summaries."""
    parts = []
    if rules.schedule_at:
        parts.append(f'a las {rules.schedule_at}, {describe_days(rules.days)}')
    if rules.max_hours:
        parts.append(f'{rules.max_hours} h después de encenderse')
    if rules.idle_minutes:
        parts.append(f'{rules.idle_minutes} min sin uso')
    return parts


def busy_text(busy: str) -> str:
    if busy == 'cpu':
        return 'la CPU está trabajando'
    if busy == 'ssh':
        return 'hay una sesión SSH abierta'
    if busy.startswith('proc:'):
        return f'{busy[5:]} está corriendo'
    return ''


def step(values, current, direction):
    """The next value of ``values`` from ``current`` in ``direction`` (clamped to the ends)."""
    values = list(values)
    if current not in values:
        bigger = [value for value in values if value > current]
        index = values.index(bigger[0]) if bigger else len(values) - 1
        return values[index] if direction > 0 else values[max(0, index - 1)]
    index = values.index(current) + (1 if direction > 0 else -1)
    return values[max(0, min(len(values) - 1, index))]
