"""Appearance preferences every Wysun program honours: window opacity and reduced motion."""
import json
import os
import time
from pathlib import Path

from . import paths
from .jsonio import atomic_write_json

DEFAULTS = {'opacity': 80, 'reduced_motion': False}
_cache = {}


def preference_path(home=None):
    root = paths.config_home() if home is None or Path(home) == Path.home() else Path(home) / '.config'
    return root / 'wysun/appearance.json'


def read_appearance(home=None):
    path = preference_path(home)
    now = time.monotonic()
    cached = _cache.get(path)
    if cached and now - cached[0] < .5:
        return dict(cached[1])
    values = dict(DEFAULTS)
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            opacity = data.get('opacity', 80)
            if isinstance(opacity, (float, int)):
                values['opacity'] = max(65, min(100, round(opacity)))
            values['reduced_motion'] = data.get('reduced_motion') is True
    except (OSError, ValueError, TypeError, OverflowError):
        pass
    _cache[path] = (now, values)
    return dict(values)


def save_appearance(values, home=None):
    """Store opacity and reduced motion, keeping any other key of the file."""
    path = preference_path(home)
    data = {}
    if path.exists():
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError('El archivo de apariencia no contiene un objeto JSON.')
    data.update(opacity=max(65, min(100, int(values['opacity']))), reduced_motion=bool(values['reduced_motion']))
    atomic_write_json(path, data)
    _cache.pop(path, None)


def reduced_motion(home=None):
    if os.environ.get('WYSUN_REDUCED_MOTION', '').lower() in ('1', 'true', 'yes'):
        return True
    return read_appearance(home)['reduced_motion']
