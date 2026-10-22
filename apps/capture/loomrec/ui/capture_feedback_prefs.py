"""Countdown preference without importing Qt (the shell reads it too)."""
import json
import os
from pathlib import Path


def preference_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))/'loomrec'/'capture-ui.json'


def load_countdown():
    try:return max(0, min(30, int(json.loads(preference_path().read_text()).get('countdown', 3))))
    except (OSError, ValueError, TypeError, AttributeError):return 3


def save_countdown(value):
    path = preference_path();path.parent.mkdir(parents=True, exist_ok=True)
    try:data = json.loads(path.read_text())
    except (OSError, ValueError):data = {}
    if not isinstance(data, dict):data = {}
    data['countdown'] = max(0, min(30, int(value)))
    temp = path.with_suffix('.tmp');temp.write_text(json.dumps(data));os.replace(temp, path)
