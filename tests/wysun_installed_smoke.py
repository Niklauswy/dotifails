#!/usr/bin/env python3
"""Exercise installed public commands outside the checkout, with disposable data.

No graphical session, portal request, recording, audio or package installation.
Optional extracted runtime proves executable preflight, not physical login.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, action='append', default=[])
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='wysun-installed-') as temporary:
        home = Path(temporary)
        env = dict(os.environ, HOME=str(home), QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1')
        for variable, relative in (('XDG_CONFIG_HOME', '.xdg/config'), ('XDG_DATA_HOME', '.xdg/data'),
                                   ('XDG_STATE_HOME', '.xdg/state'), ('XDG_CACHE_HOME', '.xdg/cache'),
                                   ('XDG_RUNTIME_DIR', 'runtime')):
            path = home / relative; path.mkdir(parents=True, mode=0o700); env[variable] = str(path)
        for variable in ('DISPLAY', 'WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'HYPRLAND_INSTANCE_SIGNATURE',
                         'SWAYSOCK', 'PYTHONPATH', 'QT_PLUGIN_PATH', 'QML_IMPORT_PATH'):
            env.pop(variable, None)
        env['XDG_SESSION_TYPE'] = 'x11'
        env['DBUS_SYSTEM_BUS_ADDRESS'] = 'unix:path=' + str(home / 'no-system-bus')
        env['PATH'] = ':'.join([str(home / '.local/bin'), *[str(p / 'usr/bin') for p in args.runtime_root], '/usr/bin', '/bin'])
        env['LD_LIBRARY_PATH'] = ':'.join(str(p / 'usr/lib/x86_64-linux-gnu') for p in args.runtime_root)
        started = time.monotonic()
        install = subprocess.run(['/usr/bin/python3', str(ROOT / 'installer/main.py'), 'install',
            '--source', str(ROOT), '--target-home', str(home), '--components', 'wayland', '--config-only'],
            env=env, cwd='/', text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        if install.returncode:raise RuntimeError(install.stdout)
        timings = {}
        checks = [(('wysun', '--help'), 'Wysun'),
                  (('wysun', 'recorder', '--version'), 'Wysun Recorder'),
                  (('wysun', 'screenshot', '--version'), 'Wysun Screenshot'),
                  (('loomrec', '--version'), 'Wysun Recorder'),
                  (('wybie-screenshot', '--version'), 'Wysun Screenshot'),
                  (('wysun', 'recorder', '--help'), '--quick-record'),
                  (('wysun', 'screenshot', '--help'), '--library')]
        if args.runtime_root:checks.append((('wysun', 'session-check'), 'WYSUN_SESSION_PREFLIGHT_OK'))
        for argv, expected in checks:
            before = time.monotonic()
            result = subprocess.run(list(argv), env=env, cwd='/', text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=15)
            if result.returncode or expected not in result.stdout:
                raise AssertionError((argv, result.returncode, result.stdout))
            timings[' '.join(argv)] = round((time.monotonic() - before) * 1000, 1)
        # Repeated application-only updates must leave the session config intact.
        config = home / '.config/wysun/hyprland.lua'
        config.write_text('-- synthetic personal binding fixture\n')
        update = subprocess.run(['/usr/bin/python3', str(ROOT / 'installer/main.py'), 'install',
            '--source', str(ROOT), '--target-home', str(home), '--wysun-only'], env=env, cwd='/',
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
        if update.returncode:raise RuntimeError(update.stdout)
        assert config.read_text() == '-- synthetic personal binding fixture\n'
        assert not (home / '.config/bspwm').exists()
        assert not (home / '.config/sxhkd').exists()
        print(json.dumps({'result': 'WYSUN_INSTALLED_SMOKE_OK', 'cwd': '/', 'commands_ms': timings,
                          'elapsed_s': round(time.monotonic() - started, 3),
                          'scope': 'real temporary HOME deployment and executable preflight; no login or media'}, indent=2))


if __name__ == '__main__':
    main()
