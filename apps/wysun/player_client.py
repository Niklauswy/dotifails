"""Starting Wysun Player from anywhere: reuse the running instance when there is one, otherwise start it.

Standard library only, so the common case (an instance is already up) costs one socket round trip and
no Qt import. The wire format is one JSON line; the server answers ``ok`` once it has queued the request.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from wysun_core.instance import SingleInstance, send

LIMIT = 1 << 20


def instance():
    """The user's player instance (not claimed: the server claims it, clients only read its endpoint)."""
    return SingleInstance(f'wysun-player-{os.getuid()}')


def endpoint():
    return instance().endpoint


def request(files, *, paused=False, fullscreen=False, start=None):
    """The request for ``files`` (paths made absolute here, relative to the caller's directory)."""
    return {'files': [os.path.abspath(str(f)) for f in files], 'paused': bool(paused), 'fullscreen': bool(fullscreen),
            'start': None if start is None else float(start)}


def forward(payload, timeout=1.0):
    """Hand ``payload`` to a running player. True only when it acknowledged the request."""
    data = (json.dumps(payload) + '\n').encode()
    if len(data) > LIMIT:
        raise ValueError('Demasiados archivos en una sola petición')
    return (send(endpoint(), data.rstrip(b'\n'), timeout=timeout, reply=True) or b'').startswith(b'ok')


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
