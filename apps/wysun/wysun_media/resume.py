"""Remembered playback positions for long files, in the user's state directory."""
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

MIN_DURATION = 300.0         # shorter files always start over
MAX_ENTRIES = 200
EDGE = 10.0                  # near either end there is nothing worth resuming
LIMIT = 256 * 1024


def state_file():
    base = os.environ.get('XDG_STATE_HOME') or str(Path.home() / '.local/state')
    return Path(base) / 'wysun/player/positions.json'


def key(source):
    """Stable per file content identity: path, size and modification time."""
    return hashlib.sha256(source.fingerprint.encode()).hexdigest()[:24]


class Positions:
    def __init__(self, path=None):
        self.path = Path(path) if path else state_file()
        self._data = None

    def _load(self):
        if self._data is None:
            try:
                if self.path.stat().st_size > LIMIT:
                    raise ValueError('state file too large')
                loaded = json.loads(self.path.read_text())
                self._data = loaded if isinstance(loaded, dict) else {}
            except (OSError, ValueError):
                self._data = {}
        return self._data

    def get(self, source):
        entry = self._load().get(key(source))
        try:
            return float(entry['position'])
        except (TypeError, KeyError, ValueError):
            return None

    def put(self, source, position, duration):
        """Remember ``position``; forget the file when it is too short, barely started or finished."""
        data, name = self._load(), key(source)
        if duration < MIN_DURATION or position < EDGE or position > duration - EDGE:
            if data.pop(name, None) is not None:
                self._write()
            return
        data[name] = {'position': round(position, 1), 'seen': int(time.time())}
        for stale in sorted(data, key=lambda k: data[k].get('seen', 0))[:max(0, len(data) - MAX_ENTRIES)]:
            del data[stale]
        self._write()

    def _write(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='.positions')
            with os.fdopen(handle, 'w') as out:
                json.dump(self._data, out)
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        except OSError:
            pass                  # remembering is a convenience; never interrupt playback for it
