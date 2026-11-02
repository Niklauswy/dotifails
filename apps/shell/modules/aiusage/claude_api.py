"""Claude usage from Anthropic's OAuth usage endpoint, with Claude Code's own sign-in.

The token is read from <home>/.credentials.json just before the request and sent only to
api.anthropic.com (credentials.get_json). It is never refreshed: an expired sign-in is reported
so Claude Code can renew it, and the caller falls back to the status line snapshot.
Field names and units follow CodexBar's Claude provider (MIT): utilization 0–100, ISO resets,
extra usage in cents, cloud credits in dollars.
"""
import calendar
import importlib.util
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

HOST = 'api.anthropic.com'
URL = f'https://{HOST}/api/oauth/usage'
BETA = 'oauth-2025-04-20'
SCOPE = 'user:profile'
MODEL_WINDOWS = (('seven_day_opus', 'weekly_opus', 'Opus'), ('seven_day_sonnet', 'weekly_sonnet', 'Sonnet'))


def _credentials():
    spec = importlib.util.spec_from_file_location('wysun_ai_usage_credentials', Path(__file__).with_name('credentials.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


credentials = _credentials()


_VERSION = []


def _user_agent(version=None):
    """Anthropic serves this endpoint to Claude Code: identify as its CLI, as CodexBar does."""
    if version:
        return f'claude-cli/{version} (external, cli)'
    if not _VERSION:
        version = '2.0.0'
        binary = shutil.which('claude')
        if binary:
            try:
                out = subprocess.run([binary, '--version'], capture_output=True, text=True, timeout=3).stdout
                found = re.search(r'\d+\.\d+\.\d+', out or '')
                version = found.group(0) if found else version
            except (OSError, subprocess.SubprocessError):
                pass
        _VERSION.append(version)
    return f'claude-cli/{_VERSION[0]} (external, cli)'


def _oauth(home):
    data = credentials.read_json(Path(home) / '.credentials.json') or {}
    oauth = data.get('claudeAiOauth')
    return oauth if isinstance(oauth, dict) else None


def session(home, now):
    """{'expiresAt', 'expired'} of Claude Code's sign-in in this home, or None without one. Never the token."""
    oauth = _oauth(home)
    if not oauth or not oauth.get('accessToken'):
        return None
    expires = oauth.get('expiresAt')
    expires = float(expires) / 1000 if isinstance(expires, (int, float)) and expires > 0 else None
    # Claude Code renews a short-lived access token by itself while it has a refresh token.
    return {'expiresAt': expires, 'expired': bool(expires and expires <= now), 'renewable': bool(oauth.get('refreshToken'))}


def _epoch(text):
    if not isinstance(text, str) or not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def _window(ident, value, minutes, now, label=None):
    if not isinstance(value, dict) or not isinstance(value.get('utilization'), (int, float)):
        return None
    used = max(0.0, min(100.0, float(value['utilization'])))
    resets = _epoch(value.get('resets_at'))
    if resets and resets <= now:
        used, resets = 0.0, None
    row = {'id': ident, 'usedPercent': used, 'resetsAt': int(resets) if resets else None, 'windowMinutes': minutes}
    if label:
        row['label'] = label
    return row


def _next_month(now):
    """Midnight UTC on the 1st of next month: Anthropic's spend limits roll over then."""
    year, month = time.gmtime(now)[:2]
    year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return calendar.timegm((year, month, 1, 0, 0, 0))


def _extra(value, now):
    if not isinstance(value, dict) or value.get('is_enabled') is not True:
        return None
    used, cap = value.get('used_credits'), value.get('monthly_limit')
    if not isinstance(used, (int, float)) or not isinstance(cap, (int, float)):
        return None
    currency = (value.get('currency') or '').strip() or 'USD'
    return {'spent': round(used / 100, 2), 'cap': round(cap / 100, 2), 'currency': currency, 'resetsAt': _next_month(now)}


def _cloud(value, now):
    if not isinstance(value, dict) or not isinstance(value.get('limit_dollars'), (int, float)):
        return None
    remaining = value.get('remaining_dollars')
    if not isinstance(remaining, (int, float)):
        used = value.get('used_dollars')
        remaining = value['limit_dollars'] - used if isinstance(used, (int, float)) else None
    if remaining is None:
        return None
    expires = _epoch(value.get('resets_at'))
    return {'remaining': round(max(0.0, remaining), 2), 'expiresAt': int(expires) if expires else None,
            'expired': bool(expires and expires <= now) or bool(value.get('locked_reason'))}


def _reset_credits(value, now):
    if not isinstance(value, dict):
        return None
    credits = []
    for grant in value.get('grants') or []:
        if not isinstance(grant, dict) or grant.get('paused'):
            continue
        ends = _epoch(grant.get('ends_at'))
        if ends and ends <= now:
            continue
        try:
            left = int(grant.get('resets_left') or 0)
        except (TypeError, ValueError):
            continue
        for _ in range(max(0, left)):
            credits.append({'title': None, 'description': None, 'expiresAt': int(ends) if ends else None})
    return {'available': len(credits), 'credits': credits} if credits else None


def usage(home, now, opener=None, version=None):
    """(details, error): live Claude usage for this home, or (None, error) when it cannot be read.

    error is None, or {'kind': 'auth'|'scope'|'network'|'expired'}. Without a sign-in both are None.
    """
    oauth = _oauth(home)
    if not oauth or not oauth.get('accessToken'):
        return None, None
    state = session(home, now)
    if state and state['expired']:
        return None, (None if state['renewable'] else {'kind': 'expired', 'command': 'claude'})
    scopes = oauth.get('scopes')
    if isinstance(scopes, list) and SCOPE not in scopes:
        return None, {'kind': 'scope', 'command': 'claude /login'}
    headers = {'Authorization': 'Bearer ' + str(oauth['accessToken']), 'anthropic-beta': BETA,
               'User-Agent': _user_agent(version), 'Content-Type': 'application/json'}
    status, body = credentials.get_json(URL + '?cedar_ember=1', headers, frozenset({HOST}), opener=opener)
    if status in (400, 403) and 'user:profile' not in str(body):
        # Only the optional reset inventory was refused; ask again without it.
        status, body = credentials.get_json(URL, headers, frozenset({HOST}), opener=opener)
    del headers, oauth
    if status == 401:
        return None, {'kind': 'auth', 'command': 'claude /login'}
    if status == 403:
        return None, {'kind': 'scope', 'command': 'claude /login'}
    if status != 200 or not isinstance(body, dict):
        return None, {'kind': 'network', 'status': status}
    limits = [_window('session', body.get('five_hour'), 300, now), _window('weekly', body.get('seven_day'), 10080, now)]
    limits += [_window(ident, body.get(key), 10080, now, label) for key, ident, label in MODEL_WINDOWS]
    limits = [row for row in limits if row]
    details = {'limits': limits, 'extra': _extra(body.get('extra_usage'), now), 'cloud': _cloud(body.get('iguana_necktie'), now),
               'resetCredits': _reset_credits(body.get('cedar_ember'), now)}
    return (details if limits else None), (None if limits else {'kind': 'network', 'status': status})
