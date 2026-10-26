"""Private, application-scoped ScreenCast restore tokens.

Only an opaque token returned by the portal is stored. No screenshot, frame,
file descriptor, window title or other desktop content is persisted here.
Tokens are scoped by source kind so a monitor consent is never replayed for a
window request (or the reverse). Monitor and region recordings share one token
per output (``monitor:DP-1``) so each screen asks for consent only once.
"""
import json
import os
import re
from pathlib import Path

from wysun_core import paths
from wysun_core.jsonio import atomic_write_text

VERSION = 1
MAX_TOKEN = 16384
KINDS = ('monitor', 'window', 'desktop')
OUTPUT_KIND = re.compile(r'monitor:[A-Za-z0-9._-]{1,64}')


def output_kind(name):
    """Token kind for one named output, or plain 'monitor' when unknown."""
    kind = 'monitor:' + str(name or '')
    return kind if OUTPUT_KIND.fullmatch(kind) else 'monitor'


def _kind(kind):
    return kind in KINDS or (isinstance(kind, str) and OUTPUT_KIND.fullmatch(kind) is not None)


def _root():
    return paths.state('wysun', 'recorder')


def _path():
    return _root() / 'screencast-consent.json'


def _valid(kind, token):
    return (
        _kind(kind)
        and isinstance(token, str)
        and 0 < len(token) <= MAX_TOKEN
        and not any(ord(character) < 32 for character in token)
    )


def load(kind):
    """Return a previously accepted token for this source kind, or an empty string."""
    if not _kind(kind):
        return ''
    try:
        data = json.loads(_path().read_text())
    except (OSError, ValueError, TypeError):
        return ''
    tokens = data.get('tokens') if isinstance(data, dict) else None
    token = tokens.get(kind, '') if isinstance(tokens, dict) else ''
    return token if _valid(kind, token) else ''


def save(kind, token):
    """Atomically persist a portal-issued token with owner-only permissions."""
    if not _valid(kind, token):
        return False
    token = token.strip()
    if not _valid(kind, token):
        return False
    root = _root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
        data = json.loads(_path().read_text())
    except (OSError, ValueError, TypeError):
        data = {}
    tokens = data.get('tokens') if isinstance(data, dict) else None
    tokens = dict(tokens) if isinstance(tokens, dict) else {}
    tokens[kind] = token
    clean = {key: value for key, value in tokens.items() if _valid(key, value)}
    payload = {'version': VERSION, 'tokens': clean}
    atomic_write_text(_path(), json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n', mode=0o600)
    return True


def clear(kind=None):
    """Forget one source kind, or every stored token when kind is omitted."""
    if kind is not None and not _kind(kind):
        raise ValueError('Tipo de fuente desconocido')
    path = _path()
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError, TypeError):
        return
    tokens = data.get('tokens') if isinstance(data, dict) else None
    if not isinstance(tokens, dict):
        return
    if kind is None:
        tokens = {}
    else:
        tokens.pop(kind, None)
    payload = {'version': VERSION, 'tokens': {key: value for key, value in tokens.items() if _valid(key, value)}}
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n', mode=0o600)
