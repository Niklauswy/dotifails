#!/usr/bin/env python3
"""Live process telemetry for the Wysun shell. No persistent process data."""
import json
import os
from pathlib import Path
import select
import re
import shutil
import subprocess
import sys
import time

source = Path(__file__).resolve().parents[3] / 'wysun'
if not (source / 'process_data.py').exists():
    source = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'orbit/app'
sys.path.insert(0, str(source))
from process_data import Processes, matched  # noqa: E402

STATES = {'R': 'Running', 'S': 'Sleeping', 'D': 'I/O wait', 'T': 'Stopped', 't': 'Tracing', 'Z': 'Zombie', 'I': 'Idle', 'X': 'Exited'}


def view(rows, control):
    selected = [r for r in rows if (control.get('owner') != 'mine' or r['uid'] == os.getuid())
                and matched(r, re.sub(r'state:(running|sleeping|stopped|idle|zombie)',
                                     lambda m: 'state:' + {'running':'R', 'sleeping':'S', 'stopped':'T', 'idle':'I', 'zombie':'Z'}[m[1].lower()],
                                     control.get('query', ''), flags=re.I))]
    key = control.get('sort', 'cpu')
    if key not in ('name', 'pid', 'cpu', 'memory', 'gpu', 'read_rate', 'write_rate', 'threads', 'nice'):
        key = 'cpu'
    def order(r):
        return r['name'].casefold() if key == 'name' else (r.get(key) or 0)
    reverse = bool(control.get('descending', True))
    selected.sort(key=order, reverse=reverse)
    mode = control.get('mode', 'list')
    collapsed = set(control.get('collapsed', []))
    if mode == 'apps':
        groups = {}
        for row in selected:
            groups.setdefault(row['app'], []).append(row)
        result = []
        totals = []
        for name, children in groups.items():
            group = dict(name=name, app=name, pid=0, start=name, group=True, count=len(children), depth=0)
            for field in ('cpu', 'memory', 'read_rate', 'write_rate', 'threads', 'gpu'):
                values = [r[field] for r in children if r.get(field) is not None]
                group[field] = sum(values) if values else None
            totals.append((group, children))
        for group, children in sorted(totals, key=lambda pair: order(pair[0]), reverse=reverse):
            result.append(group)
            if group['app'] not in collapsed:
                result.extend(dict(r, depth=1) for r in children)
    elif mode == 'tree':
        by_pid = {r['pid']: r for r in rows}
        included = {r['pid']: r for r in selected}
        for row in selected:
            parent, seen = row['ppid'], {row['pid']}
            while parent in by_pid and parent not in seen:
                seen.add(parent)
                included[parent] = by_pid[parent]
                parent = by_pid[parent]['ppid']
        children = {}
        for row in included.values():
            parent = row['ppid'] if row['ppid'] in included and row['ppid'] != row['pid'] else 0
            children.setdefault(parent, []).append(row)
        result, seen = [], set()
        # Iterative traversal also handles chains deeper than Python's recursion limit.
        def walk(roots):
            stack = [(r, 0) for r in reversed(sorted(roots, key=order, reverse=reverse))]
            while stack:
                row, depth = stack.pop()
                if row['pid'] in seen:
                    continue
                seen.add(row['pid'])
                kids = children.get(row['pid'], [])
                result.append(dict(row, depth=depth, hasChildren=bool(kids)))
                if row['pid'] not in collapsed:
                    stack.extend((r, depth+1) for r in reversed(sorted(kids, key=order, reverse=reverse)))
                else:
                    pending = list(kids)
                    while pending:
                        child = pending.pop()
                        if child['pid'] not in seen:
                            seen.add(child['pid'])
                            pending.extend(children.get(child['pid'], []))
        walk(children.get(0, []))
        for row in included.values():
            if row['pid'] not in seen:
                walk([row])
    else:
        result = [dict(r, depth=0) for r in selected]
    return result, len(selected)


class Telemetry:
    def __init__(self):
        self.model = Processes()
        self.previous = None
        self.drm_previous = {}
        self.engine_previous = {}
        self.nvidia = shutil.which('nvidia-smi')

    def counters(self):
        net = 0
        for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
            name, values = line.split(':', 1)
            if name.strip() != 'lo':
                fields = values.split()
                net += int(fields[0]) + int(fields[8])
        disk = 0
        devices = {p.name for p in Path('/sys/block').iterdir() if not p.name.startswith(('loop', 'ram', 'dm-'))}
        for line in Path('/proc/diskstats').read_text().splitlines():
            f = line.split()
            if f[2] in devices:
                disk += (int(f[5]) + int(f[9])) * 512
        return disk, net

    def gpu(self, elapsed):
        utilization, memory, per_pid = None, None, {}
        # Drivers exposing busy percentage need no helper executable or elevated access.
        for path in Path('/sys/class/drm').glob('card[0-9]*/device/gpu_busy_percent'):
            try:
                value = float(path.read_text())
                utilization = max(utilization or 0, value)
            except (OSError, ValueError):
                pass
        if self.nvidia:
            try:
                reply = subprocess.run([self.nvidia, '--query-gpu=utilization.gpu,memory.used', '--format=csv,noheader,nounits'],
                                       capture_output=True, text=True, timeout=0.8, check=True)
                values = [line.split(',') for line in reply.stdout.splitlines()]
                utilization = max(float(v[0]) for v in values)
                memory = sum(float(v[1])*1048576 for v in values)
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        return utilization, memory, per_pid

    def drm(self, row, elapsed):
        # DRM fdinfo reports engine nanoseconds on AMD/Intel. Deduplicate shared DRM clients.
        clients = {}
        try:
            for path in (Path('/proc')/str(row['pid'])/'fdinfo').iterdir():
                data = dict(line.split(':', 1) for line in path.read_text().splitlines() if ':' in line)
                client = data.get('drm-client-id')
                if client:
                    client = (data.get('drm-pdev', ''), client.strip())
                    engines = {k: int(v.split()[0]) for k, v in data.items()
                               if k.startswith('drm-engine-') and not k.startswith('drm-engine-capacity-')}
                    clients[client] = sum(engines.values())
                    for engine, value in engines.items():
                        self.engine_current[(client, engine)] = value
        except (OSError, ValueError):
            pass
        current = sum(clients.values()) if clients else None
        identity = (row['pid'], row['start'])
        old = self.drm_previous.get(identity)
        if current is not None:
            self.drm_current[identity] = current
        return max(0, (current-old)/1e9/elapsed*100) if current is not None and old is not None else None

    def scan(self):
        now = time.monotonic()
        elapsed = max(.01, now-self.previous[0]) if self.previous else 1
        rows = self.model.scan()
        self.drm_current = {}
        self.engine_current = {}
        for row in rows:
            row['stateLabel'] = STATES.get(row['state'], row['state'])
            row['gpu'] = self.drm(row, elapsed) if row['uid'] == os.getuid() else None
            row['app'] = row['name']
            try:
                cgroup = (Path('/proc')/str(row['pid'])/'cgroup').read_text()
                app = re.search(r'app-(?:[^/]*?-)?([^/]+?)(?:-[0-9a-f]+)?\.(?:scope|service)', cgroup)
                if app:
                    row['app'] = app[1].replace('\\x2d', '-')
            except OSError:
                pass
            reason = self.model.action_reason(row)
            row['reason'] = ('Owned by another user' if row['uid'] != os.getuid() else
                             'Protected session process' if reason else '')
        self.drm_previous = self.drm_current
        disk, network = self.counters()
        summary = dict(self.model.summary)
        summary['disk'] = max(0, (disk-self.previous[1])/elapsed) if self.previous else None
        summary['network'] = max(0, (network-self.previous[2])/elapsed) if self.previous else None
        summary['gpu'], summary['gpu_memory'], _ = self.gpu(elapsed)
        summary['gpu_source'] = 'Driver utilization'
        if summary['gpu'] is None:
            engines = {}
            for (client, engine), value in self.engine_current.items():
                old = self.engine_previous.get((client, engine))
                if old is not None:
                    key = (client[0], engine)
                    engines[key] = engines.get(key, 0) + max(0, value-old)/1e9/elapsed*100
            if engines:
                summary['gpu'] = min(100, max(engines.values()))
                summary['gpu_source'] = 'Busiest DRM engine'
        self.engine_previous = self.engine_current
        self.previous = (now, disk, network)
        return rows, summary


def action(args):
    model = Processes()
    row = args['row']
    current = model.checked(row)
    if args['action'] == 'details':
        return model.details(row)
    if not current['uid'] == os.getuid() or model.action_reason(current):
        raise PermissionError('This process is protected or owned by another user.')
    if args['action'] == 'priority':
        nice = int(args['nice'])
        if not -20 <= nice <= 19:
            raise ValueError('Priority must be between -20 and 19.')
        model.checked(row)
        os.setpriority(os.PRIO_PROCESS, current['pid'], nice)
        model.checked(row)
    else:
        model.act(row, args['action'])
    return {}


def stream():
    sampler = Telemetry()
    control = dict(owner='mine', sort='cpu', descending=True, mode='list', query='', interval=2)
    while True:
        rows, summary = sampler.scan()
        shown, count = view(rows, control)
        selected = next((r for r in rows if [r['pid'], r['start']] == control.get('selected')), None)
        print(json.dumps(dict(rows=shown, matched=count, summary=summary, selected=selected)), flush=True)
        deadline = time.monotonic()+max(1, min(10, float(control.get('interval', 2))))
        while True:
            ready, _, _ = select.select([sys.stdin], [], [], max(0, deadline-time.monotonic()))
            if not ready:
                break
            line = sys.stdin.readline()
            if not line:
                return
            try:
                update = json.loads(line)
                if isinstance(update, dict):
                    control.update(update)
            except ValueError:
                pass
            # Reorder existing measurements without distorting sampling intervals.
            shown, count = view(rows, control)
            selected = next((r for r in rows if [r['pid'], r['start']] == control.get('selected')), None)
            print(json.dumps(dict(rows=shown, matched=count, summary=summary, selected=selected, redraw=True)), flush=True)
            if time.monotonic() >= deadline:
                break


if __name__ == '__main__':
    try:
        if len(sys.argv) == 1:
            stream()
        else:
            print(json.dumps(dict(ok=True, data=action(json.loads(sys.argv[1])))), flush=True)
    except BrokenPipeError:
        pass
    except Exception as error:
        print(json.dumps(dict(ok=False, error='Permission denied. Higher priority may require administrator privileges.'
                             if isinstance(error, PermissionError) else
                             'The process exited or changed identity. Select it again.' if isinstance(error, (ProcessLookupError, FileNotFoundError, RuntimeError)) else str(error))), flush=True)
        sys.exit(1)
