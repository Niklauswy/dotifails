"""Opt-in resource alerts of the Wysun resident: every 5 s it reads `cpu.stat` and `memory.current` of the user's
app scopes (cheap: one file pair per app, no /proc walk) and, when an app stays over the CPU threshold for N minutes
or over the memory limit, sends one notification with actions — Ver (opens Wysun Processes on it), Terminar (asks
once more, then stops its scope) and Silenciar 1 h. Disabled by default; nothing is read or stored while disabled.
Settings: ~/.config/wysun/processes.json = {"alerts": false, "cpu": 90, "minutes": 3, "memory_gb": 0}."""
import json
import os
from pathlib import Path
import subprocess
import time

DEFAULTS = {'alerts': False, 'cpu': 90, 'minutes': 3, 'memory_gb': 0}
MUTE = 3600


def default_root():
    uid = os.getuid()
    return Path(f'/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/app.slice')


def default_config():
    from wysun_core.paths import config
    return config('wysun', 'processes.json')


def app_name(scope):
    from wysun_processes.core.sampler import application_group
    return application_group(scope, scope)


class ProcessWatch:
    def __init__(self, root=None, config=None, notify=None, clock=time.monotonic, run=None):
        self.root = Path(root or default_root())
        self.config_path = Path(config or default_config())
        self.notify = notify or (lambda *a, **k: 0)
        self.clock = clock
        self.run = run or (lambda argv: subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                         stderr=subprocess.DEVNULL, start_new_session=True))
        self.previous = {}          # scope -> (usage_usec, time)
        self.over = {}              # scope -> time the current episode started
        self.alerted = set()        # scopes notified in the current episode
        self.muted = {}             # app -> until
        self.notices = {}           # notification id -> (scope, app)

    def settings(self):
        try:
            data = json.loads(self.config_path.read_text())
        except (OSError, ValueError):
            data = {}
        out = dict(DEFAULTS)
        out.update({k: v for k, v in data.items() if k in DEFAULTS})
        return out

    def _read(self, folder):
        try:
            usage = int(next(l.split()[1] for l in (folder / 'cpu.stat').read_text().splitlines()
                             if l.startswith('usage_usec')))
            memory = int((folder / 'memory.current').read_text().strip())
            return usage, memory
        except (OSError, ValueError, StopIteration, IndexError):
            return None

    def tick(self):
        conf = self.settings()
        if not conf['alerts']:
            self.previous.clear()
            self.over.clear()
            return
        now = self.clock()
        try:
            scopes = [p for p in self.root.iterdir() if p.is_dir() and p.name.endswith(('.scope', '.service'))]
        except OSError:
            return
        seen = set()
        for folder in scopes:
            data = self._read(folder)
            if data is None:
                continue
            scope = folder.name
            seen.add(scope)
            usage, memory = data
            old = self.previous.get(scope)
            self.previous[scope] = (usage, now)
            app = app_name(scope)
            if self.muted.get(app, 0) > now:
                continue
            if conf['memory_gb'] and memory >= conf['memory_gb'] * 1024 ** 3:
                if scope + ':mem' not in self.alerted:
                    self.alerted.add(scope + ':mem')
                    self._notice(scope, app, f'{app} usa {memory / 1024 ** 3:.1f} GB de memoria',
                                 'Wysun Processes · supera el límite que elegiste')
            else:
                self.alerted.discard(scope + ':mem')
            if old is None or now <= old[1]:
                continue
            cpu = (usage - old[0]) / 1e6 / (now - old[1]) * 100
            if cpu >= conf['cpu']:
                started = self.over.setdefault(scope, old[1])
                minutes = conf['minutes']
                if now - started >= minutes * 60 and scope not in self.alerted:
                    self.alerted.add(scope)
                    self._notice(scope, app, f'{app} lleva {minutes} min al {round(cpu)} % de CPU',
                                 'Wysun Processes · de un núcleo; puede calentar el equipo o gastar batería')
            else:
                self.over.pop(scope, None)
                self.alerted.discard(scope)
        for scope in list(self.previous):
            if scope not in seen:
                self.previous.pop(scope, None)
                self.over.pop(scope, None)

    def _notice(self, scope, app, title, body):
        actions = [('ver', 'Ver'), ('terminar', 'Terminar'), ('silenciar', 'Silenciar 1 h')]
        ident = self.notify(title, body, actions)
        if ident:
            self.notices[ident] = (scope, app)

    def action(self, ident, key):
        if ident not in self.notices:
            return
        scope, app = self.notices[ident]
        if key == 'ver':
            self.run(['wysun', 'processes', app])
        elif key == 'silenciar':
            self.muted[app] = self.clock() + MUTE
        elif key == 'terminar':
            again = self.notify(f'¿Terminar {app}?', 'Se cerrarán todos sus procesos; lo que no esté guardado se pierde.',
                                [('terminar-ya', 'Terminar'), ('cancelar', 'Cancelar')])
            if again:
                self.notices[again] = (scope, app)
        elif key == 'terminar-ya':
            self.run(['systemctl', '--user', 'stop', scope])


class DbusNotifier:
    """org.freedesktop.Notifications with actions over QtDBus; calls `on_action(id, key)` when one is chosen."""

    def __init__(self, on_action):
        from PySide6.QtCore import QObject, Slot
        from PySide6.QtDBus import QDBusConnection
        self.bus = QDBusConnection.sessionBus()

        class Receiver(QObject):
            @Slot(int, str)
            def invoked(self, ident, key):
                on_action(ident, key)
        self.receiver = Receiver()
        self.bus.connect('org.freedesktop.Notifications', '/org/freedesktop/Notifications',
                         'org.freedesktop.Notifications', 'ActionInvoked', self.receiver, 'invoked(uint,QString)')

    def __call__(self, title, body, actions, image=None):
        """Notify through gdbus (it types the call from introspection); the id identifies later actions."""
        flat = [part for key, label in actions for part in (key, label)]
        argv = ['gdbus', 'call', '--session', '--dest', 'org.freedesktop.Notifications', '--object-path',
                '/org/freedesktop/Notifications', '--method', 'org.freedesktop.Notifications.Notify', 'Wysun Processes',
                '0', 'utilities-system-monitor', title, body, json.dumps(flat), '{}', '0']
        try:
            out = subprocess.run(argv, capture_output=True, text=True, timeout=3, check=False).stdout
        except (OSError, subprocess.SubprocessError):
            return 0
        import re
        match = re.search(r'uint32 (\d+)', out)
        return int(match[1]) if match else 0
