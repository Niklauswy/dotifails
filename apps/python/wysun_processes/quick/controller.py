"""The bridge between Wysun Processes' Qt-free core and its QML window (`procs` in QML): sampling on a worker
thread, the table model, selection, histories for the charts, actions with confirmation, Hyprland windows by
workspace, user services with their live journal, and the session startup. QML only presents."""
from collections import deque
import os
from pathlib import Path

from PySide6.QtCore import (QObject, QProcess, QRunnable, QThread, QThreadPool, QTimer, Property, Signal, Slot)
from PySide6.QtGui import QGuiApplication

from wysun_processes.core import actions, views
from wysun_processes.core.hypr import windows_by_app
from .models import KeyedModel

HISTORY = 60
ROW_ROLES = ('key', 'title', 'name', 'app', 'pid', 'ppid', 'depth', 'group', 'kids', 'expanded', 'appRow', 'cpu',
             'mem', 'gpu', 'io', 'threads', 'nice', 'state', 'stateLabel', 'user', 'mine', 'icon', 'tint')
DISPLAY = {'quickshell': 'Wysun Shell', 'Hyprland': 'Hyprland', 'pipewire': 'PipeWire', 'wireplumber': 'WirePlumber'}
SYSTEM_KEYS = ('cpu', 'mem', 'gpu', 'disk', 'net')


class _Relay(QObject):
    done = Signal(object, object)


class _Job(QRunnable):
    def __init__(self, fn, relay, callback):
        super().__init__()
        self.fn, self.relay, self.callback = fn, relay, callback

    def run(self):
        try:
            result = self.fn()
        except Exception as error:          # reported in the window, never raised in a pool thread
            result = error
        self.relay.done.emit(self.callback, result)


class _Worker(QObject):
    sampled = Signal(object)

    def __init__(self, sampler, interval):
        super().__init__()
        self.sampler = sampler
        self.interval = interval
        self.timer = None

    @Slot()
    def start(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sample)
        self.timer.start(self.interval)
        self.sample()

    @Slot()
    def sample(self):
        try:
            self.sampled.emit(self.sampler.sample())
        except Exception:
            pass

    @Slot(int)
    def setInterval(self, ms):
        self.interval = ms
        if self.timer:
            self.timer.setInterval(ms)

    @Slot()
    def stop(self):
        if self.timer:
            self.timer.stop()


def connections(pid):
    """Open TCP/UDP sockets of a process as `[(protocol, local, remote, state)]` (no traffic: that needs privileges)."""
    inodes = set()
    try:
        for fd in os.listdir(f'/proc/{pid}/fd'):
            try:
                target = os.readlink(f'/proc/{pid}/fd/{fd}')
            except OSError:
                continue
            if target.startswith('socket:['):
                inodes.add(target[8:-1])
    except OSError:
        return []
    states = {'01': 'ESTABLISHED', '02': 'SYN_SENT', '06': 'TIME_WAIT', '08': 'CLOSE_WAIT', '0A': 'LISTEN', '07': ''}

    def address(text, six):
        host, port = text.split(':')
        if six:
            raw = bytes.fromhex(host)
            words = [raw[i:i + 4][::-1] for i in range(0, 16, 4)]
            import ipaddress
            ip = str(ipaddress.IPv6Address(b''.join(words)))
            return f'[{ip}]:{int(port, 16)}'
        return '.'.join(str(b) for b in bytes.fromhex(host)[::-1]) + f':{int(port, 16)}'
    out = []
    for proto in ('tcp', 'tcp6', 'udp', 'udp6'):
        try:
            lines = Path(f'/proc/net/{proto}').read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            f = line.split()
            if len(f) > 9 and f[9] in inodes:
                six = proto.endswith('6')
                out.append((proto.rstrip('6').upper(), address(f[1], six), address(f[2], six),
                            states.get(f[3], '') if proto.startswith('tcp') else ''))
    return out[:100]


class ProcessesController(QObject):
    selectionChanged = Signal()
    summaryChanged = Signal()
    stateChanged = Signal()
    appsChanged = Signal()
    statsChanged = Signal()
    servicesChanged = Signal()
    startupChanged = Signal()
    detailsChanged = Signal()
    logChanged = Signal()
    logLine = Signal('QVariantMap')
    confirmNeeded = Signal(str, str, int, int)       # action, label, number of processes, current nice
    message = Signal(str, bool)                      # text, offers undo

    def __init__(self, sampler=None, hypr=None, services=None, startup=None, catalog=None, auto=True, parent=None):
        super().__init__(parent)
        if sampler is None:
            from wysun_processes.core.sampler import Sampler
            sampler = Sampler()
        if hypr is None:
            from wysun_processes.core.hypr import Hypr
            hypr = Hypr()
        if catalog is None:
            from .icons import Catalog
            catalog = Catalog()
        self.sampler, self.hypr, self.services_core, self.startup_core, self.catalog = sampler, hypr, services, startup, catalog
        self._rowsm = KeyedModel(ROW_ROLES, self)
        self.uid = os.getuid()
        self._mode, self._query, self._sort, self._descending = 'apps', '', 'cpu', True
        self._mine, self._interval, self._frozen, self._page = True, 1000, False, 'procs'
        self._expanded, self._selected_key, self._last_index, self._matched = set(), '', 0, 0
        self._snapshot = None
        self._history, self._app_history = {}, {}
        self._system = {k: deque(maxlen=HISTORY) for k in SYSTEM_KEYS}
        self._system_top = deque(maxlen=HISTORY)
        self._summary, self._stats, self._details = {}, {}, {}
        self._workspaces, self._background, self._windows, self._thumbs = [], [], [], {}
        self._services, self._service_unit, self._log, self._journal = [], '', [], None
        self._startup, self._ready = [], 0.0
        self._undo = None
        self._ticks = 0
        self._relay = _Relay(self)
        self._relay.done.connect(lambda callback, result: callback(result))
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self._thread = None
        if auto:
            self._thread = QThread(self)
            self._worker = _Worker(sampler, self._interval)
            self._worker.moveToThread(self._thread)
            self._worker.sampled.connect(self._on_snapshot)
            self._thread.started.connect(self._worker.start)
            self._thread.start()
            self._service_timer = QTimer(self, interval=5000)
            self._service_timer.timeout.connect(self._periodic)
            self._service_timer.start()
            QTimer.singleShot(200, self.refreshServices)
            QTimer.singleShot(400, self.refreshStartup)

    # ------------------------------------------------------------------ plumbing
    def _async(self, fn, callback):
        self._pool.start(_Job(fn, self._relay, callback))

    def close(self):
        if self._journal is not None:
            self._journal.kill()
            self._journal.waitForFinished(500)
            self._journal = None
        if self._thread is not None:
            from PySide6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(self._worker, 'stop', Qt.BlockingQueuedConnection)
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None
        self._pool.waitForDone(2000)

    def _periodic(self):
        if self._page == 'services':
            self.refreshServices()

    @Slot()
    def tick(self):
        """One synchronous sample (tests and `auto=False`)."""
        self._on_snapshot(self.sampler.sample())

    # ------------------------------------------------------------------ sampling
    def title_of(self, row):
        app = row.get('app', '')
        if row.get('group') or row.get('appRow'):
            return DISPLAY.get(app) or self.catalog.name(app)
        return row.get('name', '')

    def _on_snapshot(self, snapshot):
        self._ticks += 1
        alive = set()
        for row in snapshot.rows:
            key = views.key_of(row)
            alive.add(key)
            hist = self._history.get(key)
            if hist is None:
                hist = self._history[key] = {k: deque(maxlen=HISTORY) for k in ('cpu', 'mem', 'gpu', 'io')}
            for k in hist:
                hist[k].append(row.get(k) or 0)
        for key in list(self._history):
            if key not in alive:
                del self._history[key]
        system = snapshot.system
        self._system['cpu'].append(system.get('cpu') or 0)
        self._system['mem'].append(system.get('memory') or 0)
        self._system['gpu'].append(system.get('gpu') or 0)
        self._system['disk'].append((system.get('disk_read') or 0) + (system.get('disk_write') or 0))
        self._system['net'].append((system.get('net_rx') or 0) + (system.get('net_tx') or 0))
        apps = {}
        for row in snapshot.rows:
            if self._mine and row['uid'] != self.uid:
                continue
            a = apps.setdefault(row['app'], dict(cpu=0.0, mem=0, gpu=0.0, io=0.0, count=0))
            a['cpu'] += row['cpu']
            a['mem'] += row['mem']
            a['gpu'] += row['gpu'] or 0
            a['io'] += row['io']
            a['count'] += 1
        for app, a in apps.items():
            h = self._app_history.setdefault(app, deque(maxlen=HISTORY))
            h.append(a['cpu'])
            a.update(app=app, name=DISPLAY.get(app) or self.catalog.name(app), icon=self.catalog.icon(app),
                     tint=self.catalog.tint(app), history=list(h), thumb=self._thumbs.get(app, ''))
        for app in list(self._app_history):
            if app not in apps:
                del self._app_history[app]
        self._system_top.append(max(apps, key=lambda k: apps[k]['cpu']) if apps else '')
        self._stats = apps
        self._summary = dict(system, processes=len(snapshot.rows),
                             io=sum(r['io'] for r in snapshot.rows), cores_count=len(system.get('cores') or []))
        self._snapshot = snapshot
        if self._ticks == 1 or self._ticks % 3 == 0:
            self._refresh_windows()
        if self._frozen:
            return
        self._rebuild()
        self.summaryChanged.emit()
        self.statsChanged.emit()
        if self._ticks % 3 == 0 and self._selected_key:
            self._load_details()

    def _rebuild(self):
        if self._snapshot is None:
            return
        query = views.parse_query(self._query)
        out, self._matched = views.build(self._snapshot.rows, self._mode, query, self._sort, self._descending,
                                         self._expanded, self._mine, self.uid)
        items = []
        for row in out:
            items.append({**{k: row.get(k) for k in ROW_ROLES if k in row}, 'key': row['key'],
                          'title': self.title_of(row), 'name': row.get('name', ''), 'app': row.get('app', ''),
                          'pid': row.get('pid', 0), 'ppid': row.get('ppid', 0), 'depth': row.get('depth', 0),
                          'group': bool(row.get('group')), 'kids': row.get('kids', 0),
                          'expanded': bool(row.get('expanded')), 'appRow': bool(row.get('appRow')),
                          'cpu': row.get('cpu') or 0.0, 'mem': row.get('mem') or 0,
                          'gpu': -1.0 if row.get('gpu') is None else row['gpu'], 'io': row.get('io') or 0.0,
                          'threads': row.get('threads', 0), 'nice': row.get('nice', 0), 'state': row.get('state', ''),
                          'stateLabel': row.get('state_label', ''), 'user': row.get('user', ''),
                          'mine': row.get('uid') == self.uid, 'icon': self.catalog.icon(row.get('app', '')),
                          'tint': self.catalog.tint(row.get('app', ''))})
        self._rowsm.replace(items)
        keys = self._rowsm.keys()
        if self._selected_key not in keys:
            if keys:
                index = min(self._last_index, len(keys) - 1)
                self._set_selected(keys[index], details=True)
            else:
                self._set_selected('', details=False)
        else:
            self._last_index = keys.index(self._selected_key)
            self.selectionChanged.emit()
        self.stateChanged.emit()

    # ------------------------------------------------------------------ windows
    def _refresh_windows(self):
        windows = self.hypr.windows()
        current = self.hypr.active_workspace()
        rows = self._snapshot.rows if self._snapshot else []
        by_app = windows_by_app(windows, rows)
        app_of = {w['address']: app for app, ws in by_app.items() for w in ws}
        spaces = {}
        for w in windows:
            app = app_of.get(w['address'], w['app_id'])
            spaces.setdefault(w['workspace'], []).append(dict(
                address=w['address'], app=app, appId=w['app_id'], title=w['title'], name=self.catalog.name(app),
                icon=self.catalog.icon(app) or self.catalog.icon(w['app_id']),
                tint=self.catalog.tint(app) or self.catalog.tint(w['app_id']), active=w['active']))
        workspaces = [dict(id=k, current=k == current, windows=v) for k, v in sorted(spaces.items())]
        windowed = set(app_of.values())
        background = sorted({r['app'] for r in rows if r['uid'] == self.uid and r['app'] not in windowed
                             and r['app'] in self._stats and r['app'] not in ('systemd', 'Hyprland')})
        background = [dict(app=a, name=DISPLAY.get(a) or self.catalog.name(a), icon=self.catalog.icon(a),
                           tint=self.catalog.tint(a)) for a in background]
        self._windows = windows
        if self._page == 'apps':
            thumbs = self.hypr.thumbnails([w['address'] for w in windows])
            for space in workspaces:
                for w in space['windows']:
                    w['thumb'] = ('file://' + thumbs[w['address']] + '?t=%d' % self._ticks) if w['address'] in thumbs else ''
        else:
            for space in workspaces:
                for w in space['windows']:
                    w['thumb'] = ''
        if workspaces != self._workspaces or background != self._background:
            self._workspaces, self._background = workspaces, background
            self.appsChanged.emit()

    def _address_for(self, app):
        for space in self._workspaces:
            for w in space['windows']:
                if w['app'] == app:
                    return w['address']
        return ''

    # ------------------------------------------------------------------ selection
    def _set_selected(self, key, details=True):
        changed = key != self._selected_key
        self._selected_key = key
        keys = self._rowsm.keys()
        if key in keys:
            self._last_index = keys.index(key)
        if changed:
            self._details = {}
            self.detailsChanged.emit()
        self.selectionChanged.emit()
        if changed and details and key:
            self._load_details()

    def _row(self, key):
        index = self._rowsm.indexOf(key)
        return self._rowsm.get(index) if index >= 0 else {}

    def _children(self, app):
        return [r for r in (self._snapshot.rows if self._snapshot else []) if r['app'] == app
                and (not self._mine or r['uid'] == self.uid)]

    def _load_details(self):
        key = self._selected_key
        if not key:
            return
        if key.startswith('g:'):
            kids = sorted(self._children(key[2:]), key=lambda r: -r['cpu'])
            self._details = dict(key=key, children=[dict(key=views.key_of(r), name=r['name'], pid=r['pid'],
                                                          cpu=r['cpu'], mem=r['mem'], state=r['state'])
                                                     for r in kids[:80]])
            self.detailsChanged.emit()
            return
        _, pid, start = key.split(':', 2)

        def work():
            from wysun_processes.core.actions import guard
            data = guard().details(dict(pid=int(pid), start=start))
            data['connections'] = connections(int(pid))
            data.pop('key', None)
            data['files'] = [list(f) for f in data.get('files', [])]
            data['connections'] = [list(c) for c in data['connections']]
            return data

        def finish(result):
            if self._selected_key != key:
                return
            self._details = {'key': key, 'error': str(result)} if isinstance(result, Exception) else dict(result, key=key)
            self.detailsChanged.emit()
        self._async(work, finish)

    @Property(QObject, constant=True)
    def rows(self):
        return self._rowsm

    @Property(str, notify=selectionChanged)
    def selectedKey(self):
        return self._selected_key

    @Property(int, notify=selectionChanged)
    def selectedIndex(self):
        return self._rowsm.indexOf(self._selected_key)

    @Property('QVariantMap', notify=selectionChanged)
    def selected(self):
        row = self._row(self._selected_key)
        if not row:
            return {}
        row['windowAddress'] = self._address_for(row.get('app', ''))
        return row

    @Property('QVariantMap', notify=selectionChanged)
    def history(self):
        key = self._selected_key
        if key.startswith('g:'):
            kids = [self._history.get(views.key_of(r)) for r in self._children(key[2:])]
            kids = [k for k in kids if k]
            out, top = {}, []
            for metric in ('cpu', 'mem', 'gpu', 'io'):
                n = max((len(k[metric]) for k in kids), default=0)
                series = []
                for i in range(n):
                    series.append(sum(k[metric][i - (n - len(k[metric]))] for k in kids if i >= n - len(k[metric])))
                out[metric] = series
            names = {views.key_of(r): r['name'] for r in self._children(key[2:])}
            n = len(out.get('cpu', []))
            for i in range(n):
                best, value = '', -1
                for k, hist in ((k, self._history.get(k)) for k in names):
                    if hist and i >= n - len(hist['cpu']):
                        v = hist['cpu'][i - (n - len(hist['cpu']))]
                        if v > value:
                            best, value = names[k], v
                top.append(best)
            out['top'] = top
            return out
        hist = self._history.get(key)
        return {k: list(v) for k, v in hist.items()} if hist else {}

    @Property('QVariantMap', notify=detailsChanged)
    def details(self):
        return self._details

    @Slot(str)
    def select(self, key):
        self._set_selected(key)

    @Slot(int)
    def move(self, delta):
        keys = self._rowsm.keys()
        if not keys:
            return
        index = keys.index(self._selected_key) if self._selected_key in keys else 0
        self._set_selected(keys[max(0, min(len(keys) - 1, index + delta))])

    @Slot(str)
    def toggle(self, key):
        row = self._row(key)
        if not row or not (row.get('group') or row.get('kids')):
            return
        if row.get('expanded'):
            self._expanded.discard(key)
        else:
            self._expanded.add(key)
        self._rebuild()

    @Slot(str, bool, result=bool)
    def setExpanded(self, key, value):
        row = self._row(key)
        if not row or not (row.get('group') or row.get('kids')) or bool(row.get('expanded')) == value:
            return False
        self.toggle(key)
        return True

    @Slot()
    def selectParent(self):
        keys = self._rowsm.keys()
        if self._selected_key not in keys:
            return
        index = keys.index(self._selected_key)
        depth = self._rowsm.get(index).get('depth', 0)
        for i in range(index - 1, -1, -1):
            if self._rowsm.get(i).get('depth', 0) < depth:
                self._set_selected(keys[i])
                return

    # ------------------------------------------------------------------ view state
    def _changed(self):
        self._rebuild()
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def mode(self):
        return self._mode

    @Slot(str)
    def setMode(self, mode):
        if mode in ('apps', 'tree', 'list') and mode != self._mode:
            if mode == 'tree' and self._selected_key.startswith('p:'):
                by_pid = {r['pid']: r for r in self._snapshot.rows} if self._snapshot else {}
                pid = int(self._selected_key.split(':')[1])
                while pid in by_pid and by_pid[pid]['ppid'] in by_pid:
                    pid = by_pid[pid]['ppid']
                    self._expanded.add(views.key_of(by_pid[pid]))
            if mode != 'apps' and self._selected_key.startswith('g:'):
                kids = sorted(self._children(self._selected_key[2:]), key=lambda r: -r['cpu'])
                if kids:
                    self._selected_key = views.key_of(kids[0])
            self._mode = mode
            self._changed()

    @Slot()
    def cycleMode(self):
        self.setMode({'apps': 'tree', 'tree': 'list', 'list': 'apps'}[self._mode])

    @Property(str, notify=stateChanged)
    def query(self):
        return self._query

    @Property('QVariantList', notify=stateChanged)
    def tokens(self):
        return views.parse_query(self._query).tokens

    @Property(str, notify=stateChanged)
    def words(self):
        return ' '.join(views.parse_query(self._query).words)

    @Slot(str)
    def setQuery(self, text):
        if text != self._query:
            self._query = text
            self._changed()

    @Slot(str)
    def removeToken(self, token):
        self.setQuery(' '.join(t for t in self._query.split() if t != token))

    @Property(str, notify=stateChanged)
    def sort(self):
        return self._sort

    @Property(bool, notify=stateChanged)
    def descending(self):
        return self._descending

    @Slot(str)
    def sortBy(self, key):
        if key == self._sort:
            self._descending = not self._descending
        else:
            self._sort, self._descending = key, key != 'name'
        self._changed()

    @Slot()
    def cycleSort(self):
        order = list(views.SORTS[1:]) + ['name']
        self.sortBy(order[(order.index(self._sort) + 1) % len(order)] if self._sort in order else 'cpu')

    @Property(bool, notify=stateChanged)
    def mine(self):
        return self._mine

    @Slot(bool)
    def setMine(self, value):
        if value != self._mine:
            self._mine = value
            self._changed()

    @Property(int, notify=stateChanged)
    def interval(self):
        return self._interval

    @Slot(int)
    def setInterval(self, ms):
        if ms in (1000, 2000) and ms != self._interval:
            self._interval = ms
            if self._thread is not None:
                from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                QMetaObject.invokeMethod(self._worker, 'setInterval', Qt.QueuedConnection, Q_ARG(int, ms))
            self.stateChanged.emit()

    @Property(bool, notify=stateChanged)
    def frozen(self):
        return self._frozen

    @Slot(bool)
    def setFrozen(self, value):
        if value != self._frozen:
            self._frozen = value
            if not value:
                self._rebuild()
            self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def page(self):
        return self._page

    @Slot(str)
    def setPage(self, page):
        if page != self._page:
            self._page = page
            if page == 'apps':
                self._refresh_windows()
            if page == 'services':
                self.refreshServices()
            if page == 'startup':
                self.refreshStartup()
            self.stateChanged.emit()

    @Property(int, notify=stateChanged)
    def matched(self):
        return self._matched

    # ------------------------------------------------------------------ system figures
    @Property('QVariantMap', notify=summaryChanged)
    def summary(self):
        return self._summary

    @Property('QVariantMap', notify=summaryChanged)
    def systemHistory(self):
        out = {k: list(v) for k, v in self._system.items()}
        out['top'] = list(self._system_top)
        return out

    @Property('QVariantMap', notify=statsChanged)
    def stats(self):
        return self._stats

    @Slot(str, result='QVariantList')
    def topApps(self, resource):
        field = {'cpu': 'cpu', 'mem': 'mem', 'gpu': 'gpu', 'disk': 'io'}.get(resource, 'cpu')
        ranked = sorted(self._stats.values(), key=lambda a: -a[field])[:6]
        return [dict(app=a['app'], name=a['name'], icon=a['icon'], tint=a['tint'], value=a[field]) for a in ranked]

    # ------------------------------------------------------------------ actions
    def _label(self):
        row = self._row(self._selected_key)
        return row.get('title') or row.get('name') or ''

    def _count(self):
        return len(self._children(self._selected_key[2:])) if self._selected_key.startswith('g:') else 1

    @Slot(str)
    def act(self, action):
        key = self._selected_key
        if not key:
            return
        if action in ('terminate', 'kill'):
            self.confirmNeeded.emit(action, self._label(), self._count(), 0)
            return
        if action == 'priority':
            self.confirmNeeded.emit('priority', self._label(), self._count(), int(self._row(key).get('nice', 0) or 0))
            return
        if action in ('pause', 'toggle-pause'):
            targets = self._children(key[2:]) if key.startswith('g:') else [r for r in (self._snapshot.rows if self._snapshot else []) if views.key_of(r) == key]
            resume = bool(targets) and all(r['state'] in ('T', 't') for r in targets)
            verb = 'resume' if resume else 'pause'
            try:
                actions.act(self.sampler, key, verb)
            except (RuntimeError, PermissionError, ValueError, OSError) as error:
                self.message.emit(str(error), False)
                return
            self._undo = (key, 'pause' if resume else 'resume')
            self.message.emit(f"{self._label()} {'reanudado' if resume else 'pausado'}", True)
            QTimer.singleShot(150, self.tick if self._thread is None else (lambda: None))

    @Slot(str, int)
    def confirm(self, action, nice):
        key = self._selected_key
        label = self._label()
        try:
            if action == 'priority':
                actions.set_priority(self.sampler, key, nice)
                self.message.emit(f'Prioridad de {label}: {nice:+d}' if nice else f'Prioridad de {label}: normal', False)
            else:
                count = actions.act(self.sampler, key, action)
                text = 'cerrado a la fuerza' if action == 'kill' else 'terminado'
                self.message.emit(f'{label} {text}' + (f' · {count} procesos' if count > 1 else ''), False)
        except (RuntimeError, PermissionError, ValueError, OSError) as error:
            self.message.emit(str(error), False)

    @Slot()
    def undo(self):
        if not self._undo:
            return
        key, verb = self._undo
        self._undo = None
        try:
            actions.act(self.sampler, key, verb)
        except (RuntimeError, PermissionError, ValueError, OSError) as error:
            self.message.emit(str(error), False)

    @Slot()
    def copyPid(self):
        key = self._selected_key
        if not key:
            return
        pids = [str(r['pid']) for r in self._children(key[2:])] if key.startswith('g:') else [key.split(':')[1]]
        QGuiApplication.clipboard().setText(' '.join(pids))
        self.message.emit('PID copiado: ' + ' '.join(pids[:6]) + (' …' if len(pids) > 6 else ''), False)

    @Slot()
    def focusWindow(self):
        self.focusApp(self._row(self._selected_key).get('app', ''))

    @Slot()
    def locate(self):
        self.locateApp(self._row(self._selected_key).get('app', ''))

    @Slot(str)
    def focusApp(self, app):
        address = self._address_for(app)
        if not address:
            self.message.emit('No tiene ventana abierta.', False)
        elif not self.hypr.focus(address):
            self.message.emit('Hyprland no respondió.', False)

    @Slot(str)
    def locateApp(self, app):
        address = self._address_for(app)
        if not address:
            self.message.emit('No tiene ventana abierta.', False)
        elif not self.hypr.locate(address):
            self.message.emit('No se pudo localizar: el shell no responde.', False)

    @Slot(str)
    def selectApp(self, app):
        self.setMode('apps')
        kids = self._children(app)
        self._rebuild()
        self._set_selected('g:' + app if len(kids) > 1 else (views.key_of(kids[0]) if kids else ''))

    @Slot(str)
    def openContext(self, query):
        """`wysun processes <query>`: filter and select the first match (its app group when there is one)."""
        self.setMode('apps')
        self.setQuery(query)
        keys = self._rowsm.keys()
        groups = [k for k in keys if k.startswith('g:')]
        if keys:
            self._set_selected(groups[0] if groups else keys[0])

    # ------------------------------------------------------------------ apps page
    @Property('QVariantList', notify=appsChanged)
    def workspaces(self):
        return self._workspaces

    @Property('QVariantList', notify=appsChanged)
    def background(self):
        return self._background

    @Slot(str, bool)
    def closeApp(self, app, force):
        self.selectApp(app)
        self.act('kill' if force else 'terminate')

    # ------------------------------------------------------------------ services
    @Property('QVariantList', notify=servicesChanged)
    def services(self):
        return self._services

    @Property(bool, notify=servicesChanged)
    def servicesAvailable(self):
        return self.services_core is not None and self.services_core.available

    @Property(int, notify=servicesChanged)
    def failedCount(self):
        return sum(1 for s in self._services if s['state'] == 'failed')

    @Slot()
    def refreshServices(self):
        if self.services_core is None:
            return

        def finish(result):
            if isinstance(result, Exception):
                return
            result = sorted(result, key=lambda s: ({'failed': 0, 'active': 1}.get(s['state'], 2) if s['kind'] == 'service'
                                                   else 1.5, s['unit']))
            if result != self._services:
                self._services = result
                self.servicesChanged.emit()
        self._async(self.services_core.list, finish)

    @Slot(str, str)
    def serviceAction(self, unit, action):
        if self.services_core is None:
            return

        def finish(result):
            if isinstance(result, Exception):
                self.message.emit(str(result), False)
            else:
                verbs = {'start': 'iniciado', 'stop': 'parado', 'restart': 'reiniciado', 'enable': 'se iniciará con la sesión',
                         'disable': 'ya no se iniciará con la sesión', 'run': 'ejecutándose'}
                self.message.emit(f'{unit.rsplit(".", 1)[0]} {verbs.get(action, action)}', False)
            self.refreshServices()
        self._async(lambda: self.services_core.action(unit, action), finish)

    @Property(str, notify=logChanged)
    def serviceUnit(self):
        return self._service_unit

    @Property('QVariantList', notify=logChanged)
    def log(self):
        return self._log

    @Slot(str)
    def watchService(self, unit):
        if unit == self._service_unit or self.services_core is None:
            return
        self._service_unit, self._log = unit, []
        if self._journal is not None:
            self._journal.kill()
            self._journal = None
        self.logChanged.emit()

        def finish(result):
            if self._service_unit != unit or isinstance(result, Exception):
                return
            self._log = [self._log_entry(e) for e in result]
            self.logChanged.emit()
            process = QProcess(self)
            process.setProgram('journalctl')
            process.setArguments(['--user', '-u', unit, '-f', '-n', '0', '-o', 'json', '--no-pager'])
            buffer = bytearray()

            def read():
                buffer.extend(bytes(process.readAllStandardOutput()))
                while b'\n' in buffer:
                    line, _, rest = bytes(buffer).partition(b'\n')
                    buffer[:] = rest
                    entry = self.services_core.parse_entry(line.decode(errors='replace'))
                    if entry and self._service_unit == unit:
                        item = self._log_entry(entry)
                        self._log = (self._log + [item])[-500:]
                        self.logLine.emit(item)
            process.readyReadStandardOutput.connect(read)
            process.start()
            self._journal = process
        self._async(lambda: self.services_core.journal(unit), finish)

    @staticmethod
    def _log_entry(entry):
        import time
        level, stamp, text = entry
        clock = time.strftime('%H:%M:%S', time.localtime(stamp / 1e6)) if stamp else '—'
        return dict(level=level, time=clock, text=text)

    # ------------------------------------------------------------------ startup
    @Property('QVariantList', notify=startupChanged)
    def startupItems(self):
        return self._startup

    @Property(float, notify=startupChanged)
    def readyAt(self):
        return self._ready

    @Slot()
    def refreshStartup(self):
        if self.startup_core is None:
            return

        def work():
            items = self.startup_core.items()
            times = [i['ready_s'] for i in items if i['enabled'] and not i['delay'] and i['ready_s'] is not None]
            return items, (max(times) if times else 0.0)

        def finish(result):
            if isinstance(result, Exception):
                return
            items, ready = result
            for item in items:
                item['icon'] = self.catalog.icon(item.get('app', ''))
                item['tint'] = self.catalog.tint(item.get('app', ''))
            self._startup, self._ready = items, ready
            self.startupChanged.emit()
        self._async(work, finish)

    @Slot(str, bool)
    def setStartupEnabled(self, item_id, enabled):
        self._startup_change(lambda: self.startup_core.set_enabled(item_id, enabled))

    @Slot(str, int)
    def setStartupDelay(self, item_id, seconds):
        self._startup_change(lambda: self.startup_core.set_delay(item_id, seconds))

    def _startup_change(self, fn):
        if self.startup_core is None:
            return

        def finish(result):
            if isinstance(result, Exception):
                self.message.emit(str(result), False)
            self.refreshStartup()
        self._async(fn, finish)
