"""Disk space of a provider's folder: total, known parts and cleanup ideas. It only measures; nothing is deleted.

Symbolic links are not followed, so a folder shared with another home is not counted twice.
"""
import os
from pathlib import Path

OLD = 90 * 86400
PARTS = {
    'claude': ('projects/', 'shell-snapshots/', 'todos/', 'plans/', 'file-history/'),
    'codex': ('sessions/', 'archived_sessions/', 'log/'),
    'opencode': ('opencode.db', 'storage/', 'snapshot/', 'tool-output/', 'log/'),
}
LOGS = {'claude': ('projects',), 'codex': ('sessions', 'archived_sessions'), 'opencode': ()}


def _walk(path):
    """(size, [(file, size, mtime)]) of a file or folder, without following links."""
    try:
        info = os.lstat(path)
    except OSError:
        return 0, []
    if not os.path.isdir(path) or os.path.islink(path):
        return info.st_size, [(path, info.st_size, info.st_mtime)]
    total, files = 0, []
    for folder, dirs, names in os.walk(path, followlinks=False):
        for name in names:
            try:
                stat = os.lstat(os.path.join(folder, name))
            except OSError:
                continue
            total += stat.st_size
            files.append((os.path.join(folder, name), stat.st_size, stat.st_mtime))
    return total, files


def measure(root, provider, now):
    root = Path(root)
    total, _ = _walk(root)
    parts = []
    for name in PARTS.get(provider, ()):
        path = root / name.rstrip('/')
        if name == 'opencode.db':
            size = sum(_walk(root / (name + suffix))[0] for suffix in ('', '-wal', '-shm'))
        else:
            size = _walk(path)[0] if path.exists() or path.is_symlink() else 0
        if size:
            parts.append({'name': name, 'size': size})
    old = 0
    for folder in LOGS.get(provider, ()):
        _, files = _walk(root / folder)
        old += sum(size for _, size, mtime in files if now - mtime > OLD)
    tips = [{'kind': 'old-logs', 'size': old}] if old else []
    if provider == 'claude':
        history = _walk(root / 'file-history')[0]
        if history:
            tips.append({'kind': 'file-history', 'size': history})
    return {'root': str(root), 'total': total, 'parts': parts, 'tips': tips, 'measuredAt': now}
