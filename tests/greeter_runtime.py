#!/usr/bin/env python3
"""Exercise the real QML greeter in an isolated nested compositor.

Uses synthetic credentials and sessions. Never authenticates a host account or
launches its desktop. Requires access to the current Wayland socket.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import tempfile
import time

SOURCE = Path(__file__).resolve().parents[1]


def stop(process):
    if process and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def main():
    root = Path(tempfile.mkdtemp(prefix='wg-'))
    print(f'Evidence: {root}', flush=True)
    compositor = server = client = None
    try:
        shutil.copytree(SOURCE / 'apps/shell/modules/lockscreen', root / 'modules/lockscreen')
        harness = (SOURCE / 'tests/greeter_harness.qml').read_text()
        (root / 'harness.qml').write_text(harness.replace('../apps/shell/modules/lockscreen', 'modules/lockscreen'))
        (root / 'passwd').write_text('testuser:x:1000:1000:Test:/tmp:/bin/sh\n')
        (root / 'sessions').mkdir()
        marker = root / 'session started.json'
        script = root / 'session command.py'
        script.write_text('import json,sys\nfrom pathlib import Path\n'
                          'Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))\n')
        args = ['/usr/bin/python3', str(script), str(marker), 'argument with spaces', 'literal $HOME']
        command = shlex.join(args)
        (root / 'sessions/test.desktop').write_text(f'[Desktop Entry]\nName=Wysun Test\nExec={command}\n')
        (root / 'hyprland.conf').write_text('monitor = ,1280x720@60,auto,1\n'
            'misc {\n disable_hyprland_logo = true\n disable_splash_rendering = true\n}\n')
        host_socket = str(Path(os.environ['XDG_RUNTIME_DIR']) / os.environ['WAYLAND_DISPLAY'])
        env = dict(os.environ, HOME=str(root), XDG_RUNTIME_DIR=str(root),
                   XDG_CONFIG_HOME=str(root / 'config'), XDG_CACHE_HOME=str(root / 'cache'),
                   XDG_STATE_HOME=str(root / 'state'), XDG_DATA_HOME=str(root / 'data'),
                   AQ_BACKEND='wayland', WAYLAND_DISPLAY=host_socket, HYPRLAND_NO_SD_NOTIFY='1')
        for key in ('DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE', 'DBUS_SESSION_BUS_ADDRESS'):
            env.pop(key, None)
        with (root / 'compositor.log').open('w') as output:
            compositor = subprocess.Popen(['dbus-run-session', '--', 'Hyprland', '--config', str(root / 'hyprland.conf')],
                env=env, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(200):
            sockets = [p for p in root.glob('wayland-*') if not p.name.endswith('.lock')]
            if sockets:
                break
            if compositor.poll() is not None:
                raise RuntimeError((root / 'compositor.log').read_text())
            time.sleep(.05)
        else:
            raise RuntimeError('Nested compositor did not create its socket')
        server = subprocess.Popen(['python3', str(SOURCE / 'tests/fake_greetd.py'),
            str(root / 'greetd.sock'), 'wysun', str(root / 'ipc.jsonl')], start_new_session=True)
        for _ in range(100):
            if (root / 'greetd.sock').exists():
                break
            time.sleep(.02)
        env.update(QT_QPA_PLATFORM='wayland', WAYLAND_DISPLAY=str(sockets[0]),
            GREETD_SOCK=str(root / 'greetd.sock'), WYSUN_GREETER_STATE=str(root / 'saved.json'),
            WYSUN_GREETER_PASSWD=str(root / 'passwd'), WYSUN_GREETER_SESSIONS=str(root / 'sessions'))
        with (root / 'greeter.log').open('w') as output:
            client = subprocess.Popen(['quickshell', '--no-color', '-p', str(root / 'harness.qml')],
                env=env, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        assert client.wait(timeout=35) == 0, (root / 'greeter.log').read_text()
        server.wait(timeout=5)
        requests = [json.loads(line) for line in (root / 'ipc.jsonl').read_text().splitlines()]
        verdicts = [r['accepted'] for r in requests if 'accepted' in r]
        assert verdicts == [False, True], requests
        launches = [r for r in requests if r['type'] == 'start_session']
        assert len(launches) == 1, requests
        # Match greetd/session/worker.rs: cmd is joined, then interpreted by sh.
        subprocess.run(['/bin/sh', '-c', 'exec ' + ' '.join(launches[0]['cmd'])], check=True, timeout=5)
        assert json.loads(marker.read_text()) == args[3:]
        # Demonstrate the former implementation silently exits without execution.
        marker.unlink()
        old = ['/bin/sh', '-c', 'exec ' + command]
        subprocess.run(['/bin/sh', '-c', 'exec ' + ' '.join(old)], check=True, timeout=5)
        assert not marker.exists(), 'Old command unexpectedly executed'
        assert 'XDG_SESSION_TYPE=wayland' in launches[0]['env']
        print('GREETER_RUNTIME_PASSED: rejection, retry, launch, quoted arguments; old launch reproduced')
    finally:
        for process in (client, server, compositor):
            stop(process)


if __name__ == '__main__':
    main()
