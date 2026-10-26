"""Local single GUI instance per user/display; recorder service remains independent."""
import hashlib
import json
import os

from wysun_core import paths
from wysun_core.instance import SingleInstance, send

ACTIONS = ('setup', 'focus', 'status', 'quick', 'hide_controls')


class Instance:
    def __init__(self, directory=None, name="gui"):
        if name not in ("gui", "controller", "job"):
            raise ValueError("Invalid instance namespace")
        display = os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY', 'default')
        tag = hashlib.sha256(display.encode()).hexdigest()[:12]
        self._instance = SingleInstance(f'{name}-{tag}', directory or paths.runtime(f'wysun-recorder-{os.getuid()}'))
        self.path = self._instance.endpoint
        self.lock_path = self._instance.lock_path

    def claim(self):
        return self._instance.claim()

    def request(self, action='setup', timeout=3):
        reply = send(self.path, json.dumps({'action': action}).encode(), timeout=timeout, reply=True, retry=timeout)
        if not reply:
            raise RuntimeError('La ventana de Wysun Recorder está iniciando o no está disponible')
        return json.loads(reply)

    def poll(self, callback):
        def handle(line):
            try:
                action = json.loads(line)['action']
            except (ValueError, KeyError, TypeError):
                return None
            if action not in ACTIONS:
                return None
            return json.dumps(callback(action)).encode()
        self._instance.poll(handle, limit=1024, timeout=3)

    def close(self):
        self._instance.close()
