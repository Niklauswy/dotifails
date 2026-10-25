"""Starting Wysun Player from anywhere: reuse the running instance when there is one, otherwise start it.

Standard library only, so the common case (an instance is already up) costs one socket round trip and
no Qt import. The wire format is one JSON line; the server answers ``ok`` once it has queued the request.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

LIMIT = 1 << 20


def runtime_dir():
    return Path(os.environ.get('XDG_RUNTIME_DIR') or tempfile.gettempdir())


def endpoint():
    return runtime_dir() / f'wysun-player-{os.getuid()}.sock'


def lock_path():
    return runtime_dir() / f'wysun-player-{os.getuid()}.lock'


def request(files, *, paused=False, fullscreen=False, start=None):
    """The request for ``files`` (paths made absolute here, relative to the caller's directory)."""
    return {'files': [os.path.abspath(str(f)) for f in files], 'paused': bool(paused), 'fullscreen': bool(fullscreen),
            'start': None if start is None else float(start)}


def forward(payload, timeout=1.0):
    """Hand ``payload`` to a running player. True only when it acknowledged the request."""
    data = (json.dumps(payload) + '\n').encode()
    if len(data) > LIMIT:
        raise ValueError('Demasiados archivos en una sola petición')
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(timeout)
            client.connect(str(endpoint()))
            client.sendall(data)
            return client.recv(16).startswith(b'ok')
    except OSError:
        return False


def command(payload):
    """argv that starts a new player for ``payload``."""
    argv = [sys.executable, str(Path(__file__).with_name('player_app.py'))]
    if payload.get('paused'):
        argv.append('--paused')
    if payload.get('fullscreen'):
        argv.append('--fullscreen')
    if payload.get('start') is not None:
        argv += ['--start', str(payload['start'])]
    return argv + ['--', *payload['files']]


def launch(files, **options):
    """Show ``files`` in Wysun Player, starting it if needed. Never blocks on the player itself."""
    payload = request(files, **options)
    if not forward(payload):
        subprocess.Popen(command(payload), start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
