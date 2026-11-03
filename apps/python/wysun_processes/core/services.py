"""systemd --user services and timers for Wysun Processes: list with state, resources and errors, actions, and the
journal. Every call has a time limit; without systemctl or journalctl the lists are empty and `available` is
False, so the window explains it instead of blocking."""
import json
import subprocess

KINDS = ('service', 'timer')
ACTIONS = ('start', 'stop', 'restart', 'enable', 'disable', 'run')
PROPERTIES = ('Id', 'MemoryCurrent', 'CPUUsageNSec', 'TasksCurrent', 'MainPID', 'UnitFileState', 'Result',
              'ExecMainStatus', 'ActiveEnterTimestampMonotonic', 'InactiveExitTimestampMonotonic')
LEVELS = {'0': 'err', '1': 'err', '2': 'err', '3': 'err', '4': 'warn'}
RESULTS = {'exit-code': 'terminó con código de salida', 'signal': 'lo detuvo una señal', 'timeout': 'tardó demasiado',
           'core-dump': 'falló y volcó memoria', 'start-limit-hit': 'se reinició demasiadas veces',
           'resources': 'le faltaron recursos', 'oom-kill': 'se quedó sin memoria'}


def _number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class Services:
    def __init__(self, run=subprocess.run, timeout=3):
        self.run = run
        self.timeout = timeout
        self.available = True

    def _call(self, cmd):
        try:
            done = self.run(cmd, capture_output=True, text=True, timeout=self.timeout, check=False)
        except FileNotFoundError:
            self.available = False
            return None
        except (subprocess.SubprocessError, OSError):
            return None
        return done

    def _show(self, units):
        done = self._call(['systemctl', '--user', 'show', '-p', ','.join(PROPERTIES), '--', *units]) if units else None
        blocks, current = {}, {}
        for line in (done.stdout if done else '').splitlines() + ['']:
            if not line.strip():
                if current.get('Id'):
                    blocks[current['Id']] = current
                current = {}
                continue
            name, _, value = line.partition('=')
            current[name] = value
        return blocks

    def list(self):
        done = self._call(['systemctl', '--user', 'list-units', '--all', '--type=service,timer', '-o', 'json',
                           '--no-pager'])
        if not done or done.returncode != 0:
            return []
        try:
            units = [u for u in json.loads(done.stdout or '[]') if u.get('unit', '').rsplit('.', 1)[-1] in KINDS]
        except ValueError:
            return []
        details = self._show([u['unit'] for u in units])
        timers = {}
        listed = self._call(['systemctl', '--user', 'list-timers', '--all', '-o', 'json', '--no-pager'])
        try:
            timers = {t['unit']: t for t in json.loads(listed.stdout or '[]')} if listed else {}
        except ValueError:
            pass
        out = []
        for unit in units:
            name = unit['unit']
            info = details.get(name, {})
            active = unit.get('active', 'inactive')
            state = 'failed' if active == 'failed' else 'active' if active in ('active', 'reloading', 'activating') else 'inactive'
            error = ''
            if state == 'failed':
                result = info.get('Result', '')
                error = RESULTS.get(result, result or 'falló')
                status = info.get('ExecMainStatus', '0')
                if result == 'exit-code' and status not in ('', '0'):
                    error += ' ' + status
            timer = timers.get(name, {})
            out.append(dict(unit=name, description=unit.get('description', ''), kind=name.rsplit('.', 1)[-1],
                            state=state, sub=unit.get('sub', ''), enabled=info.get('UnitFileState') == 'enabled',
                            memory=_number(info.get('MemoryCurrent')), cpu_ns=_number(info.get('CPUUsageNSec')),
                            tasks=_number(info.get('TasksCurrent')), main_pid=_number(info.get('MainPID')) or 0,
                            active_since_us=_number(info.get('ActiveEnterTimestampMonotonic')) or 0,
                            started_us=_number(info.get('InactiveExitTimestampMonotonic')) or 0,
                            error=error, next_us=_number(timer.get('next')) or 0, last_us=_number(timer.get('last')) or 0,
                            activates=timer.get('activates', '')))
        return out

    def action(self, unit, action):
        if action not in ACTIONS:
            raise ValueError('Acción no admitida')
        if action == 'run':
            target = unit[:-len('.timer')] + '.service' if unit.endswith('.timer') else unit
            cmd = ['systemctl', '--user', 'start', '--', target]
        else:
            cmd = ['systemctl', '--user', action, '--', unit]
        done = self._call(cmd)
        if done is None:
            raise RuntimeError('No se pudo hablar con systemd.')
        if done.returncode != 0:
            raise RuntimeError((done.stderr or '').strip().splitlines()[-1] if done.stderr.strip() else 'systemd lo rechazó.')
        return True

    @staticmethod
    def parse_entry(line):
        try:
            entry = json.loads(line)
        except ValueError:
            return None
        message = entry.get('MESSAGE', '')
        if isinstance(message, list):
            message = bytes(message).decode('utf-8', 'replace')
        stamp = _number(entry.get('__REALTIME_TIMESTAMP')) or 0
        return LEVELS.get(str(entry.get('PRIORITY', '6')), 'info'), stamp, str(message)

    def journal(self, unit, lines=200):
        done = self._call(['journalctl', '--user', '-u', unit, '-n', str(lines), '-o', 'json', '--no-pager'])
        if not done:
            return []
        return [e for e in map(self.parse_entry, done.stdout.splitlines()) if e]

    def follow(self, unit):
        """A `journalctl -f` process for the live log; the caller reads its stdout and terminates it."""
        try:
            return subprocess.Popen(['journalctl', '--user', '-u', unit, '-f', '-n', '0', '-o', 'json', '--no-pager'],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        except OSError:
            return None
