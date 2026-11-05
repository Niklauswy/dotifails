"""What was uploaded and its links: ``~/.local/share/wysun/drive/history.json`` (private, newest first)."""
import time

from wysun_core import paths
from wysun_core.jsonio import atomic_write_json, read_json

LIMIT = 200
FIELDS = ('name', 'local', 'remote', 'size', 'is_dir', 'url', 'share_id', 'password')


def history_path():
    return paths.data('wysun', 'drive', 'history.json')


def load():
    data = read_json(history_path(), [])
    return [entry for entry in data if isinstance(entry, dict) and entry.get('remote')] if isinstance(data, list) else []


def _save(entries):
    paths.private_dir(history_path().parent)
    atomic_write_json(history_path(), entries[:LIMIT], mode=0o600)


def add(results, server='', now=None):
    """Prepend the successful ``results`` (upload.Result) to the history."""
    now = time.time() if now is None else now
    fresh = [dict({key: getattr(result, key) for key in FIELDS}, at=now, server=server)
             for result in results if result.ok]
    if fresh:
        _save(fresh + load())


def set_link(remote, url, share_id, password=None):
    entries = load()
    for entry in entries:
        if entry.get('remote') == remote:
            entry.update(url=url, share_id=share_id, password=password)
            break
    _save(entries)
