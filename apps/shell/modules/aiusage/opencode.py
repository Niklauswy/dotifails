"""OpenCode: local usage history from its database and OpenCode Go quota with the CLI's own sign-in.

History comes from the assistant messages in opencode.db (legacy `message` and v2 `session_message`,
a migrated message counted once), opened read-only. Each message carries OpenCode's own cost, which
is 0 for subscriptions (OpenCode Go, Copilot) and free models; those are estimated at the model's API
price from the catalog OpenCode caches (models.json, models.dev), so a truly free model stays at $0
and a model missing from it is unpriced.
The quota comes from https://opencode.ai/zen/go/v1/usage with the sign-in the OpenCode CLI keeps
(active `credential` row for `opencode-go`, else `opencode`; legacy auth.json `opencode-go` key),
read just before the request and sent only to opencode.ai. Formats follow CodexBar's OpenCode Go
provider (MIT). Without a subscription or sign-in there is history and no quota.
"""
import importlib.util
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

HOST = 'opencode.ai'
URL = f'https://{HOST}/zen/go/v1/usage'
WINDOWS = (('rolling', 'session', 300), ('weekly', 'weekly', 10080), ('monthly', 'monthly', 43200))
PERCENT_KEYS = ('usagePercent', 'usedPercent', 'percentUsed', 'percent', 'usage_percent', 'used_percent', 'utilization')
RESET_KEYS = ('resetsAt', 'resets_at', 'resetAt', 'reset_at', 'resetInSec', 'resetInSeconds', 'resetSeconds', 'reset_in_sec', 'resetsInSec')

HISTORY_SQL = """
SELECT m.id, m.data, COALESCE(s.directory, ''), m.session_id FROM message m LEFT JOIN session s ON s.id = m.session_id
WHERE json_valid(m.data) AND json_extract(m.data, '$.role') = 'assistant'
"""
HISTORY_V2_SQL = """
SELECT m.id, m.data, COALESCE(s.directory, ''), m.session_id FROM session_message m LEFT JOIN session_v2 s ON s.id = m.session_id
WHERE m.type = 'assistant' AND json_valid(m.data)
"""


def _credentials():
    spec = importlib.util.spec_from_file_location('wysun_ai_usage_credentials', Path(__file__).with_name('credentials.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


credentials = _credentials()


def _connect(db):
    return sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2)


def _rows(db, sql):
    try:
        with closing(_connect(db)) as connection:
            return connection.execute(sql).fetchall()
    except sqlite3.Error:
        return []


def catalog(path):
    """{provider: {model: cost}} from OpenCode's models.json cache; {} when missing or unreadable."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    prices = {}
    for provider, entry in (data.items() if isinstance(data, dict) else ()):
        models = entry.get('models') if isinstance(entry, dict) else None
        for name, model in (models.items() if isinstance(models, dict) else ()):
            cost = model.get('cost') if isinstance(model, dict) else None
            if isinstance(cost, dict):
                prices.setdefault(provider, {})[name] = cost
    return prices


def _rate(cost, key):
    value = cost.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def estimate(prices, provider, name, tokens):
    """API price in USD of one message (input, cacheRead, cacheWrite, output), or None when unknown.

    Context tiers apply when the prompt (input plus cache) passes their size, as models.dev publishes them.
    """
    cost = (prices.get(provider) or {}).get(name)
    if cost is None:
        return None
    prompt = tokens[0] + tokens[1] + tokens[2]
    tiers = [t for t in cost.get('tiers') or [] if isinstance(t, dict)
             and isinstance((t.get('tier') or {}).get('size'), (int, float)) and prompt > t['tier']['size']]
    if tiers:
        cost = dict(cost, **{k: v for k, v in max(tiers, key=lambda t: t['tier']['size']).items() if k != 'tier'})
    rates = (_rate(cost, 'input'), _rate(cost, 'cache_read'), _rate(cost, 'cache_write'), _rate(cost, 'output'))
    return sum(count * rate for count, rate in zip(tokens, rates)) / 1_000_000


def history(db, since, prices=None):
    """Assistant messages newer than `since` (epoch s): time, session, project, provider, model, tokens and cost.

    A recorded cost of 0 with tokens is re-estimated from `prices` (see `catalog`).
    """
    prices = prices or {}
    found = {}
    for sql, v2 in ((HISTORY_SQL, False), (HISTORY_V2_SQL, True)):
        for ident, raw, directory, session_id in _rows(db, sql):
            if ident in found:
                continue
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            created = (data.get('time') or {}).get('created')
            if not isinstance(created, (int, float)) or created / 1000 < since:
                continue
            model = data.get('model') if v2 else None
            provider = (model or {}).get('providerID') if v2 else data.get('providerID')
            name = (model or {}).get('id') if v2 else data.get('modelID')
            tokens = data.get('tokens') or {}
            cache = tokens.get('cache') or {}
            counts = (int(tokens.get('input') or 0), int(cache.get('read') or 0), int(cache.get('write') or 0),
                      int(tokens.get('output') or 0) + int(tokens.get('reasoning') or 0))
            cost = data.get('cost')
            cost = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
            if not any(counts):
                cost = cost or 0.0  # an aborted message without tokens must not leave its hour unpriced
            elif not cost:
                cost = estimate(prices, provider, name, counts)
            found[ident] = {
                'time': created / 1000, 'session': session_id or '', 'project': directory or (data.get('path') or {}).get('cwd') or '',
                'provider': provider or 'unknown', 'model': f"{provider or 'unknown'}/{name or 'unknown'}",
                'input': counts[0], 'cacheRead': counts[1], 'cacheWrite': counts[2], 'output': counts[3],
                'cost': cost,
            }
    return list(found.values())


def _credential(data_dir):
    """The active CLI sign-in value (opencode-go first, then opencode), or None. Never printed."""
    rows = _rows(Path(data_dir) / 'opencode.db', "SELECT integration_id, value FROM credential WHERE active = 1 AND "
                 "integration_id IN ('opencode-go', 'opencode') ORDER BY CASE integration_id WHEN 'opencode-go' THEN 0 ELSE 1 END")
    if not rows:
        return None
    chosen = [value for integration, value in rows if integration == rows[0][0]]
    if len(chosen) != 1:
        return None
    try:
        value = json.loads(chosen[0])
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _login(data_dir, now):
    """(token, expiresAt) of the CLI sign-in for OpenCode Go; (None, expiresAt) when expired or ambiguous."""
    value = _credential(data_dir)
    if value is not None:
        if value.get('type') == 'key':
            return value.get('key') or None, None
        if value.get('type') == 'oauth':
            expires = value.get('expires')
            expires = expires / 1000 if isinstance(expires, (int, float)) else None
            if not expires or expires <= now:
                return None, expires
            return value.get('access') or None, expires
        return None, None
    legacy = (credentials.read_json(Path(data_dir) / 'auth.json') or {}).get('opencode-go')
    if isinstance(legacy, dict) and legacy.get('type') == 'api':
        return legacy.get('key') or None, None
    return None, None


def profile(data_dir):
    """E-mail and workspace the CLI sign-in carries, for the account header; never the token."""
    value = _credential(data_dir) or {}
    metadata = value.get('metadata') if isinstance(value.get('metadata'), dict) else {}
    return {'email': metadata.get('email'), 'organization': metadata.get('orgName')}


def session(data_dir, now):
    """{'expiresAt', 'expired'} of an OAuth sign-in, or None (API keys do not expire). Never the token."""
    token, expires = _login(data_dir, now)
    if expires is None:
        return None
    return {'expiresAt': expires, 'expired': token is None}


def _number(source, keys):
    for key in keys:
        value = source.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _reset(source, now):
    """Absolute reset time: the API sends ISO-8601 `resetsAt`; older answers sent seconds from now."""
    for key in RESET_KEYS:
        value = source.get(key)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
            except ValueError:
                continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return now + value
    return None


def _cloudflare_block(body):
    """Cloudflare's bot filter answers 403 with its own JSON, not the provider's refusal."""
    return isinstance(body, dict) and 'cloudflare.com' in str(body.get('type') or '')


def usage(data_dir, now, opener=None):
    """(limits, error): OpenCode Go windows, or ([], error|None) without a usable sign-in or subscription."""
    token, expires = _login(data_dir, now)
    if not token:
        return [], ({'kind': 'expired', 'command': 'opencode auth login'} if expires else None)
    status, body = credentials.get_json(URL, {'Authorization': 'Bearer ' + token}, frozenset({HOST}), opener=opener)
    del token
    if status == 401:
        return [], {'kind': 'auth', 'command': 'opencode auth login'}
    if status == 403:
        # A valid sign-in without OpenCode Go behind it is not a sign-in problem.
        return [], ({'kind': 'network'} if _cloudflare_block(body) else None)
    if status != 200 or not isinstance(body, dict):
        return [], ({'kind': 'network'} if status in (0, 429) or status >= 500 else None)
    windows = body.get('usage') if isinstance(body.get('usage'), dict) else {}
    limits = []
    for key, ident, minutes in WINDOWS:
        window = windows.get(key)
        if not isinstance(window, dict):
            continue
        percent = _number(window, PERCENT_KEYS)
        if window.get('status') == 'rate-limited':
            # The published percent is floored, so a spent window can still read 99.
            percent = 100.0
        if percent is None:
            continue
        reset = _reset(window, now)
        limits.append({'id': ident, 'usedPercent': max(0.0, min(100.0, percent)),
                       'resetsAt': int(reset) if reset else None, 'windowMinutes': minutes})
    return limits, None
