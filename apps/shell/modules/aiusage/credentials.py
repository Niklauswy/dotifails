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
# Some provider hosts sit behind bot filters that refuse urllib's default signature (Cloudflare 1010).
USER_AGENT = 'Wysun/1 (ai-usage)'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib copies Authorization to a redirect's host; a redirect is answered as the error it is instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def build_opener(*handlers):
    """An opener that never follows redirects."""
    return urllib.request.build_opener(_NoRedirect, *handlers)


def read_json(path):
    """The parsed JSON file, or None when it is missing, unreadable or malformed (never its contents)."""
    try:
        with open(path, 'rb') as handle:
            value = json.loads(handle.read())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _defaults(headers):
    """Headers plus a User-Agent of our own, unless the caller already chose one."""
    merged = dict(headers)
    if not any(key.lower() == 'user-agent' for key in merged):
        merged['User-Agent'] = USER_AGENT
    return merged


def get_json(url, headers, allowed, timeout=MAX_TIMEOUT, opener=None):
    """GET url and parse its JSON body: (status, body); (0, None) when the request did not complete.

    Raises ValueError (before any request) unless url is https and its host is in `allowed`.
    """
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in allowed:
        raise ValueError('host not allowed')
    request = urllib.request.Request(url, headers=dict(_defaults(headers), Accept='application/json'))
    opener = opener or build_opener().open
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
