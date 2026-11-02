"""Credentials for the AI usage panel: read at the moment of use, sent only to an allowed HTTPS host.

Rules (AGENTS.md): a secret is read just before its request, travels only over HTTPS to the provider's
own host, and is never written, refreshed, logged, cached or put into output, notifications or errors.
Errors here therefore never carry request headers or file contents.
"""
import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

MAX_TIMEOUT = 5.0


def read_json(path):
    """The parsed JSON file, or None when it is missing, unreadable or malformed (never its contents)."""
    try:
        with open(path, 'rb') as handle:
            value = json.loads(handle.read())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def get_json(url, headers, allowed, timeout=MAX_TIMEOUT, opener=None):
    """GET url and parse its JSON body: (status, body); (0, None) when the request did not complete.

    Raises ValueError (before any request) unless url is https and its host is in `allowed`.
    """
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in allowed:
        raise ValueError('host not allowed')
    request = urllib.request.Request(url, headers=dict(headers, Accept='application/json'))
    opener = opener or urllib.request.urlopen
    try:
        with opener(request, timeout=min(float(timeout), MAX_TIMEOUT)) as response:
            status, raw = getattr(response, 'status', 200), response.read()
    except urllib.error.HTTPError as error:
        try:
            raw = error.read()
        except Exception:
            raw = b''
        return error.code, _parse(raw)
    except Exception:
        return 0, None
    return status, _parse(raw)


def _parse(raw):
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, (dict, list)) else None
