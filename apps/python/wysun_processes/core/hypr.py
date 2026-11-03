"""Hyprland windows for Wysun Processes and the shell calls that need the compositor: focus, close (gracefully),
window thumbnails and locate-on-screen. Thumbnails and locating come from the shell (`wysun-shell thumbs|locate`);
without it they degrade to nothing and the window keeps working."""
import json
import re
import subprocess

ADDRESS = re.compile(r'^0x[0-9a-fA-F]+$')


def _checked(address):
    if not ADDRESS.match(str(address)):
        raise ValueError('Dirección de ventana no válida')
    return address


class Hypr:
    def __init__(self, run=subprocess.run, timeout=2):
        self.run = run
        self.timeout = timeout

    def _call(self, cmd):
        try:
            done = self.run(cmd, capture_output=True, text=True, timeout=self.timeout, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        return done if done.returncode == 0 else None

    def _json(self, what):
        done = self._call(['hyprctl', '-j', what])
        try:
            return json.loads(done.stdout) if done else None
        except ValueError:
            return None

    def windows(self):
        out = []
        for c in self._json('clients') or []:
            if not c.get('mapped', True) or c.get('hidden') or c.get('workspace', {}).get('id', -1) < 0:
                continue
            out.append(dict(address=c['address'], pid=c.get('pid', 0), app_id=c.get('class', ''),
                            title=c.get('title', ''), workspace=c['workspace']['id'],
                            active=c.get('focusHistoryID') == 0, monitor=c.get('monitor', 0)))
        return out

    def active_workspace(self):
        data = self._json('activeworkspace') or {}
        return data.get('id', 0)

    def focus(self, address):
        return self._call(['hyprctl', 'dispatch', 'focuswindow', 'address:' + _checked(address)]) is not None

    def close(self, address):
        return self._call(['hyprctl', 'dispatch', 'closewindow', 'address:' + _checked(address)]) is not None

    def thumbnails(self, addresses):
        wanted = [_checked(a) for a in addresses]
        if not wanted:
            return {}
        done = self._call(['wysun-shell', 'thumbs', ','.join(wanted)])
        try:
            data = json.loads(done.stdout.strip() or '{}') if done else {}
        except ValueError:
            return {}
        return {k: v for k, v in data.items() if k in wanted and isinstance(v, str)}

    def locate(self, address):
        done = self._call(['wysun-shell', 'locate', _checked(address)])
        return bool(done) and done.stdout.strip() == 'true'


def windows_by_app(windows, rows):
    """`{app: [window, …]}`: each window belongs to the app of its process (or of its nearest known ancestor)."""
    by_pid = {r['pid']: r for r in rows}
    out = {}
    for window in windows:
        pid, seen = window['pid'], set()
        while pid in by_pid and pid not in seen:
            row = by_pid[pid]
            if row.get('app'):
                out.setdefault(row['app'], []).append(window)
                break
            seen.add(pid)
            pid = row.get('ppid', 0)
    return out
