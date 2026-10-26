"""What the reader remembers: where each document was left, and the reader's own preferences.

Both are private user state outside the repository. Documents are keyed by a SHA-256 of their path,
so the file never lists what the user reads.
"""
import hashlib
import math
from pathlib import Path
import time

from wysun_core import jsonio, paths
from wysun_pdf.layout import clamp_zoom

LIMIT = 200
VIEWS = ('single', 'spread')
ZOOM_MODES = ('width', 'page', 'custom')


def _key(document):
    return hashlib.sha256(str(Path(document).expanduser().resolve()).encode()).hexdigest()


def clamp(state, pages):
    """A remembered position made valid for the document as it is now."""
    def number(name, default):
        try:
            value = float(state.get(name, default))
            return value if math.isfinite(value) else default
        except (ValueError, TypeError, OverflowError):
            return default
    result = dict(state)
    result['page'] = max(0, min(pages - 1, int(number('page', 0))))
    result['zoom'] = clamp_zoom(number('zoom', 1.0))
    result['view'] = state.get('view') if state.get('view') in VIEWS else 'single'
    result['zoom_mode'] = state.get('zoom_mode') if state.get('zoom_mode') in ZOOM_MODES else 'width'
    for name in ('fx', 'fy'):
        result[name] = max(0.0, min(1.0, number(name, 0.0)))
    return result


class Positions:
    def __init__(self):
        self.path = paths.state('wysun', 'pdf-reader', 'positions.json')

    def _read(self):
        stored = jsonio.read_json(self.path, {})
        return stored if isinstance(stored, dict) else {}

    def load(self, document):
        entry = self._read().get(_key(document))
        return entry if isinstance(entry, dict) else None

    def save(self, document, state):
        stored = self._read()
        stored[_key(document)] = dict(state, t=time.time())
        def timestamp(key):
            entry = stored[key]
            value = entry.get('t', 0) if isinstance(entry, dict) else 0
            return value if isinstance(value, (int, float)) and math.isfinite(value) else 0
        newest = sorted(stored, key=timestamp)
        for key in newest[:-LIMIT]:
            del stored[key]
        jsonio.atomic_write_json(self.path, stored, mode=0o600)


class Preferences:
    """``pdf-reader.json`` in the user's config: mode (sun/moon), sidebar and ink. Unknown keys are kept."""

    def __init__(self):
        self.path = paths.config('wysun', 'pdf-reader.json')

    def _read(self):
        stored = jsonio.read_json(self.path, {})
        return stored if isinstance(stored, dict) else {}

    def get(self, key, default=None):
        return self._read().get(key, default)

    def set(self, **values):
        jsonio.atomic_write_json(self.path, {**self._read(), **values}, mode=0o600)
