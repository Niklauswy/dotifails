"""Countdown preference without importing Qt (the shell reads it too)."""
from wysun_core import paths
from wysun_core.jsonio import atomic_write_json, read_json


def preference_path():
    return paths.config('loomrec', 'capture-ui.json')


def load_countdown():
    try:return max(0, min(30, int(read_json(preference_path(), {}).get('countdown', 3))))
    except (ValueError, TypeError, AttributeError):return 3


def save_countdown(value):
    data = read_json(preference_path(), {})
    if not isinstance(data, dict):data = {}
    data['countdown'] = max(0, min(30, int(value)))
    atomic_write_json(preference_path(), data, indent=None)
