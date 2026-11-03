"""Hyprland windows for Wysun Processes and the shell calls that need the compositor: focus, close (gracefully),
window thumbnails and locate-on-screen. Thumbnails and locating come from the shell (`wysun-shell thumbs|locate`);
without it they degrade to nothing and the window keeps working."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ADDRESS = re.compile(r'^0x[0-9a-fA-F]+$')
MIN_THUMB_WIDTH = 160
MAX_THUMB_WIDTH = 1920


def _checked(address):
    if not ADDRESS.match(str(address)):
        raise ValueError('Dirección de ventana no válida')
    return address


def capture_width(width):
    """A requested capture width in device pixels, clamped to what the shell accepts; `None` keeps its default
    (480 px). Junk is treated as `None` instead of asking the shell for an impossible image."""
    if width is None:
        return None
    try:
        value = int(round(float(width)))
    except (TypeError, ValueError):
        return None
    return max(MIN_THUMB_WIDTH, min(MAX_THUMB_WIDTH, value))


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

    def monitors(self):
        """The active outputs with their physical position, active workspace and DPMS state; disabled ones are not
        columns and do not keep the window visible."""
        out = []
        for m in self._json('monitors') or []:
            if m.get('disabled'):
                continue
            active = m.get('activeWorkspace') or 0
            out.append(dict(id=m.get('id', 0), name=m.get('name', ''), make=m.get('make', ''),
                            model=m.get('model', ''), x=m.get('x', 0), y=m.get('y', 0),
                            activeWorkspace=active.get('id', 0) if isinstance(active, dict) else active,
                            dpms=bool(m.get('dpmsStatus', True))))
        return out

    def windows(self):
        out = []
        for c in self._json('clients') or []:
            if not c.get('mapped', True) or c.get('hidden') or c.get('workspace', {}).get('id', -1) < 0:
                continue
            out.append(dict(address=c['address'], pid=c.get('pid', 0), app_id=c.get('class', ''),
                            title=c.get('title', ''), workspace=c['workspace']['id'],
                            active=c.get('focusHistoryID') == 0, monitor=c.get('monitor', 0),
                            size=c.get('size') or [0, 0]))
        return out

    def active_workspace(self):
        data = self._json('activeworkspace') or {}
        return data.get('id', 0)

    def _dispatch(self, lua, legacy):
        """Hyprland with a Lua config takes `hl.dsp…` expressions; a classic config, dispatcher words."""
        done = self._call(['hyprctl', 'dispatch', lua])
        if done is not None and done.stdout.strip() == 'ok':
            return True
        done = self._call(['hyprctl', 'dispatch', *legacy])
        return done is not None and done.stdout.strip() == 'ok'

    def focus(self, address):
        a = _checked(address)
        return self._dispatch(f'hl.dsp.focus({{window="address:{a}"}})', ['focuswindow', 'address:' + a])

    def close(self, address):
        a = _checked(address)
        return self._dispatch(f'hl.dsp.window.close({{window="address:{a}"}})', ['closewindow', 'address:' + a])

    @staticmethod
    def thumbs_dir():
        from wysun_core.paths import runtime_dir
        return Path(runtime_dir()) / 'wysun-processes' / 'thumbs'

    def cleanup(self):
        """Forget the thumbnails: they only live while the window is open."""
        shutil.rmtree(self.thumbs_dir(), ignore_errors=True)

    def thumbnails(self, addresses, width=None):
        """`{address: path}` of the shell's captures at `width` device pixels (its 480 px default when omitted)."""
        wanted = [_checked(a) for a in addresses]
        if not wanted:
            return {}
        try:
            os.makedirs(self.thumbs_dir(), mode=0o700, exist_ok=True)
        except OSError:
            return {}
        command = ['wysun-shell', 'thumbs', ','.join(wanted)]
        pixels = capture_width(width)
        if pixels is not None:
            command.append(str(pixels))
        done = self._call(command)
        try:
            data = json.loads(done.stdout.strip() or '{}') if done else {}
        except ValueError:
            return {}
        # The shell keeps the paths it wrote in memory; a restart of the app may have removed the files, so a path
        # only counts while the file is there (otherwise the row keeps its drawn preview and Qt logs no warning).
        return {k: v for k, v in data.items() if k in wanted and isinstance(v, str) and os.path.isfile(v)}

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
