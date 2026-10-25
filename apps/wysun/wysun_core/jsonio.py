"""Atomic file writes and defensive JSON reads.

A write goes to a temporary file in the target's directory, is flushed to disk and
then renamed over the target, so readers see the old or the new content, never a
mix. A rewritten file keeps its permissions; a new one is private (0o600).
"""
import copy
import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path


def _fsync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def atomic_path(path, *, mode=None):
    """Yield a temporary path to write; it replaces ``path`` only if the block finishes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if mode is None:
        try:
            mode = path.stat().st_mode & 0o777
        except FileNotFoundError:
            mode = 0o600
    # Keep the suffix: tools such as ffmpeg and PIL choose the format from it.
    temporary = path.with_name(f'.{path.stem}.{uuid.uuid4().hex}.tmp{path.suffix}')
    try:
        yield temporary
        os.chmod(temporary, mode)
        descriptor = os.open(temporary, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_bytes(path, data, *, mode=None):
    with atomic_path(path, mode=mode) as temporary:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
    return Path(path)


def atomic_write_text(path, text, *, mode=None):
    return atomic_write_bytes(path, text.encode('utf-8'), mode=mode)


def atomic_write_json(path, data, *, mode=None, indent=2):
    text = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=indent) + '\n'
    return atomic_write_text(path, text, mode=mode)


def read_json(path, default=None, *, strict=False):
    """The parsed file; ``default`` (a copy) when it is missing, or unreadable unless ``strict``."""
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return copy.deepcopy(default)
    except (UnicodeDecodeError, ValueError) as error:
        if strict:
            raise ValueError(f'JSON inválido en {path}: {error}') from None
        return copy.deepcopy(default)
