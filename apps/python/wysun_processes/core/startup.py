"""What starts with the Wysun session, when it started and how much it weighs: the session itself, the
`exec-once` commands of hyprland.lua (read only: the app never writes that file), enabled systemd --user services
and, when the session runs it, XDG autostart. Disabling or delaying an autostart entry writes an override in
~/.config/autostart (the original is never touched); a systemd service is delayed with a drop-in."""
import os
from pathlib import Path
import re
import shlex

ONCE = re.compile(r'hl\.on\(\s*"hyprland\.start"\s*,\s*function\s*\(\)\s*hl\.exec_cmd\(\s*"([^"]+)"\s*\)')
FIELD_CODES = re.compile(r'\s*%[a-zA-Z]')
MARK = 'X-Wysun-Override'


def impact(duration):
    if duration is None:
        return 1
    return 1 if duration < 0.3 else 2 if duration < 1.0 else 3


def read_desktop(path):
    entry, inside = {}, False
    try:
        lines = Path(path).read_text(errors='replace').splitlines()
    except OSError:
        return {}
    for line in lines:
        if line.startswith('['):
            inside = line.strip() == '[Desktop Entry]'
            continue
        if inside and '=' in line and not line.startswith('#'):
            key, _, value = line.partition('=')
            entry.setdefault(key.strip(), value.strip())
    return entry


def write_desktop(path, entry):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text('[Desktop Entry]\n' + ''.join(f'{k}={v}\n' for k, v in entry.items()))
    temp.replace(path)


class Startup:
    def __init__(self, home=None, hypr_config=None, proc_root='/proc', services=None, env=None, xdg_active=None):
        self.home = Path(home or Path.home())
        self.env = os.environ if env is None else env
        self.config = Path(hypr_config or self.home / '.config/wysun/hyprland.lua')
        self.proc = Path(proc_root)
        self.services = services
        self.clock = os.sysconf('SC_CLK_TCK')
        self.xdg_active = xdg_active

    # --- processes --------------------------------------------------------------------------------------------
    def _processes(self):
        out = []
        try:
            names = [n for n in os.listdir(self.proc) if n.isdigit()]
        except OSError:
            return out
        for name in names:
            try:
                raw = (self.proc / name / 'stat').read_text()
                fields = raw.rpartition(') ')[2].split()
                comm = raw.split('(', 1)[1].rpartition(')')[0]
                try:
                    cmd = (self.proc / name / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace').strip()
                except OSError:
                    cmd = ''
                out.append((int(name), comm, cmd, int(fields[19]) / self.clock))
            except (OSError, ValueError, IndexError):
                continue
        return out

    def _session_start(self, procs):
        starts = [p[3] for p in procs if p[1] == 'Hyprland']
        return min(starts) if starts else None

    @staticmethod
    def _find(procs, command):
        first = command.split()[0] if command.split() else command
        base = os.path.basename(first)
        for pid, comm, cmd, start in sorted(procs, key=lambda p: p[3]):
            if comm == base[:15] or cmd.startswith(command) or cmd.split(' ')[:1] == [first]:
                return start
        return None

    # --- sources ----------------------------------------------------------------------------------------------
    def _autostart_dirs(self):
        dirs = [Path(d) / 'autostart' for d in (self.env.get('XDG_CONFIG_DIRS') or '/etc/xdg').split(':') if d]
        return dirs, self.home / '.config/autostart'

    def _xdg_runs(self):
        """XDG autostart only counts when the session starts it (systemd's xdg-desktop-autostart.target)."""
        if self.xdg_active is not None:
            return self.xdg_active
        if self.services is None:
            return False
        done = self.services._call(['systemctl', '--user', 'is-active', 'xdg-desktop-autostart.target'])
        return bool(done) and done.stdout.strip() == 'active'

    def _autostart(self):
        system, user = self._autostart_dirs()
        entries = {}
        for folder in reversed(system):
            for path in sorted(folder.glob('*.desktop')):
                entries[path.name] = (path, None)
        for path in sorted(user.glob('*.desktop')):
            original = entries.get(path.name, (None, None))[0]
            entries[path.name] = (original, path)
        return entries

    def items(self):
        procs = self._processes()
        zero = self._session_start(procs)
        rel = lambda start: None if start is None or zero is None else max(0.0, start - zero)
        out = []
        for name, comm in (('Hyprland', 'Hyprland'), ('Wysun Shell', 'quickshell')):
            start = self._find(procs, comm)
            out.append(dict(id='session:' + name, name=name, source='session', editable=False, enabled=True,
                            delay=0, started_s=rel(start), ready_s=rel(start), impact=2 if name == 'Hyprland' else 3,
                            app=comm))
        try:
            text = self.config.read_text()
        except OSError:
            text = ''
        for command in ONCE.findall(text):
            start = rel(self._find(procs, command))
            out.append(dict(id='once:' + command, name=command, source='exec-once', editable=False, enabled=True,
                            delay=0, started_s=start, ready_s=start, impact=1, app=command.split()[0]))
        if self.services is not None:
            for unit in self.services.list():
                if unit['kind'] != 'service' or not unit['enabled']:
                    continue
                zero_us = zero * 1e6 if zero is not None else None
                begin = (unit['started_us'] - zero_us) / 1e6 if zero_us and unit['started_us'] else None
                ready = (unit['active_since_us'] - zero_us) / 1e6 if zero_us and unit['active_since_us'] else None
                if begin is None or begin < 0 or ready is None or ready < begin:
                    # Monotonic vs boot clocks drift apart after a suspend: use the main process when there is one.
                    main = next((p[3] for p in procs if p[0] == unit['main_pid']), None)
                    begin = ready = rel(main) if main is not None else None
                delay = self._systemd_delay_of(unit['unit'])
                out.append(dict(id='systemd:' + unit['unit'], name=unit['unit'].removesuffix('.service'),
                                source='systemd', editable=True, enabled=True, delay=delay, started_s=begin,
                                ready_s=ready, impact=impact(None if begin is None or ready is None else ready - begin),
                                app=unit['unit']))
        if self._xdg_runs():
            for filename, (original, override) in self._autostart().items():
                entry = read_desktop(original) if original else {}
                mine = read_desktop(override) if override else {}
                merged = dict(entry, **mine)
                if not merged.get('Name') or merged.get('Type', 'Application') != 'Application':
                    continue
                enabled = merged.get('Hidden', 'false').lower() != 'true' and \
                    merged.get('X-GNOME-Autostart-enabled', 'true').lower() != 'false'
                exec_ = merged.get('X-Wysun-Exec') or merged.get('Exec', '')
                start = rel(self._find(procs, FIELD_CODES.sub('', exec_))) if enabled and exec_ else None
                out.append(dict(id='xdg:' + filename, name=merged['Name'], source='autostart', editable=True,
                                enabled=enabled, delay=int(merged.get('X-Wysun-Delay', 0) or 0), started_s=start,
                                ready_s=start, impact=2, app=Path(exec_.split()[0]).name if exec_ else filename))
        return out

    def ready_at(self):
        times = [i['ready_s'] for i in self.items() if i['enabled'] and not i['delay'] and i['ready_s'] is not None]
        return max(times) if times else 0.0

    # --- changes ----------------------------------------------------------------------------------------------
    def _item(self, item_id):
        for item in self.items():
            if item['id'] == item_id:
                return item
        raise KeyError(item_id)

    def _override(self, filename, hidden=None, delay=None):
        original, override = self._autostart().get(filename, (None, None))
        target = self._autostart_dirs()[1] / filename
        base = read_desktop(original) if original else {}
        mine = read_desktop(override) if override else {}
        ours = mine.get(MARK) == 'true' or not override
        entry = dict(base, **mine) if ours else dict(mine)
        exec_ = entry.get('X-Wysun-Exec') or entry.get('Exec', '')
        hidden = entry.get('Hidden', 'false').lower() == 'true' if hidden is None else hidden
        delay = int(entry.get('X-Wysun-Delay', 0) or 0) if delay is None else delay
        for key in ('Hidden', 'X-Wysun-Delay', 'X-Wysun-Exec'):
            entry.pop(key, None)
        entry['Exec'] = exec_
        if delay:
            inner = 'sleep %d; exec %s' % (delay, FIELD_CODES.sub('', exec_))
            entry['Exec'] = 'sh -c ' + shlex.quote(inner)
            entry['X-Wysun-Exec'] = exec_
            entry['X-Wysun-Delay'] = str(delay)
        if hidden:
            entry['Hidden'] = 'true'
        if ours and not hidden and not delay:
            if target.exists():
                target.unlink()
            return
        if ours:
            entry[MARK] = 'true'
        write_desktop(target, entry)

    def set_enabled(self, item_id, enabled):
        item = self._item(item_id)
        if not item['editable']:
            raise PermissionError('Esta entrada es parte de la configuración de Hyprland o de Wysun.')
        if item['source'] == 'autostart':
            self._override(item_id[len('xdg:'):], hidden=not enabled)
        elif item['source'] == 'systemd' and self.services is not None:
            self.services.action(item_id[len('systemd:'):], 'enable' if enabled else 'disable')

    def set_delay(self, item_id, seconds):
        if seconds not in (0, 5, 10):
            raise ValueError('Retraso no admitido')
        item = self._item(item_id)
        if not item['editable']:
            raise PermissionError('Esta entrada es parte de la configuración de Hyprland o de Wysun.')
        if item['source'] == 'autostart':
            self._override(item_id[len('xdg:'):], delay=seconds)
        elif item['source'] == 'systemd':
            self.systemd_delay(item_id[len('systemd:'):], seconds)

    def _systemd_delay_path(self, unit):
        return self.home / '.config/systemd/user' / (unit + '.d') / 'wysun-delay.conf'

    def _systemd_delay_of(self, unit):
        match = re.search(r'sleep (\d+)', self._systemd_delay_path(unit).read_text()) \
            if self._systemd_delay_path(unit).exists() else None
        return int(match[1]) if match else 0

    def systemd_delay(self, unit, seconds):
        path = self._systemd_delay_path(unit)
        if not seconds:
            if path.exists():
                path.unlink()
                try:
                    path.parent.rmdir()
                except OSError:
                    pass
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'# Wysun Processes: espera antes de iniciar\n[Service]\nExecStartPre=/bin/sleep {seconds}\n')
        if self.services is not None:
            self.services._call(['systemctl', '--user', 'daemon-reload'])
        return path
