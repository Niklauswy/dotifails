#!/usr/bin/env python3
"""AI provider accounts, limits and local usage for the shell's AI usage panel.

Credentials are read only where they improve the data and add no risk (AGENTS.md):
just before their request, sent only over HTTPS to the provider's own host (credentials.py),
never written, refreshed, logged, cached or put into the output. Each account is a CLI home
the user is already signed in to:
  - Claude Code (CLAUDE_CONFIG_DIR, default ~/.claude): limits come from the
    status line command, which copies `rate_limits` to
    $XDG_STATE_HOME/wysun/ai-usage/claude[-<dir name>].json; the plan and
    name come from the account profile Claude Code keeps in .claude.json.
  - Codex (CODEX_HOME, default ~/.codex): `codex app-server` answers
    `account/read` and `account/rateLimits/read` with its own session; the
    newest rollout log is the fallback.
More homes are listed in $XDG_CONFIG_HOME/wysun/ai-accounts.json:
  {"accounts": [{"provider": "codex", "home": "~/.codex-work", "label": "Work"}]}
Tokens and cost come from each home's session logs, parsed incrementally into
hourly buckets cached under $XDG_CACHE_HOME/wysun/ai-usage. Costs are API-price
estimates from pricing.json, overridable in $XDG_CONFIG_HOME/wysun/ai-pricing.json.

Prints one JSON document on stdout.
"""
import hashlib
import importlib.util
import json
import os
import selectors
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HOME = Path.home()
STATE = Path(os.environ.get('XDG_STATE_HOME') or HOME / '.local/state') / 'wysun/ai-usage'
CACHE = Path(os.environ.get('XDG_CACHE_HOME') or HOME / '.cache') / 'wysun/ai-usage'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME') or HOME / '.config') / 'wysun'
SESSIONS = STATE / 'sessions'
DEFAULT_HOMES = {
    'claude': Path(os.environ.get('CLAUDE_CONFIG_DIR') or HOME / '.claude'),
    'codex': Path(os.environ.get('CODEX_HOME') or HOME / '.codex'),
    'opencode': Path(os.environ.get('XDG_DATA_HOME') or HOME / '.local/share') / 'opencode',
}
NAMES = {'claude': 'Claude', 'codex': 'Codex', 'opencode': 'OpenCode'}
PRICING = Path(__file__).with_name('pricing.json')

HOUR = 3600
KEEP = 90 * 24 * HOUR
# Token history is kept a year, for the activity map.
YEAR = 366 * 24 * HOUR
CACHE_VERSION = 7
# Bucket fields: uncached input, cache read, cache write, output.
FIELDS = ('input', 'cacheRead', 'cacheWrite', 'output')
CLAUDE_PLANS = {'claude_pro': 'Pro', 'claude_max': 'Max', 'claude_team': 'Team', 'claude_enterprise': 'Enterprise',
                'claude_free': 'Free'}


def _iso_hour(stamp):
    """Hour bucket (epoch seconds) of an ISO-8601 UTC timestamp."""
    try:
        moment = datetime.fromisoformat(stamp.replace('Z', '+00:00')).timestamp()
    except (AttributeError, ValueError):
        return None
    return int(moment // HOUR * HOUR)


def _add(buckets, hour, model, values):
    row = buckets.setdefault(str(hour), {}).setdefault(model, [0, 0, 0, 0])
    for i, value in enumerate(values):
        row[i] += max(0, int(value or 0))


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


# Accounts

def home_key(home):
    """Short id of a resolved home; statusline-hook.py computes the same one for its snapshot file."""
    return hashlib.sha1(str(home).encode()).hexdigest()[:10]


def account_id(provider, home):
    return provider + ':' + home_key(home)


_SIBLINGS = {}


def _sibling(name):
    """A module beside this file; the backend runs with `python3 -I`, so its folder is not on sys.path."""
    if name not in _SIBLINGS:
        spec = importlib.util.spec_from_file_location(f'wysun_ai_usage_{name}', Path(__file__).with_name(f'{name}.py'))
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        _SIBLINGS[name] = loaded
    return _SIBLINGS[name]


def load_accounts():
    """Default homes first, then the configured ones, then the Claude homes whose status line hook has run."""
    entries = [{'provider': p, 'home': str(h)} for p, h in DEFAULT_HOMES.items()]
    configured = (_read_json(CONFIG / 'ai-accounts.json') or {}).get('accounts', [])
    for entry in configured if isinstance(configured, list) else []:
        if isinstance(entry, dict) and entry.get('provider') in NAMES and entry.get('home'):
            entries.append(entry)
    announced = {s['home'] for s in map(_read_json, STATE.glob('claude-*.json')) if isinstance(s, dict) and isinstance(s.get('home'), str)}
    entries += [{'provider': 'claude', 'home': home} for home in sorted(announced)]
    accounts, seen = [], {}
    for entry in entries:
        home = Path(os.path.expanduser(str(entry['home']))).resolve()
        key = (entry['provider'], home)
        if key in seen:
            # A configured label may rename a default home.
            seen[key]['label'] = entry.get('label') or seen[key]['label']
            continue
        if not home.is_dir() or (entry['provider'] == 'opencode' and not (home / 'opencode.db').is_file()):
            continue
        account = {'id': account_id(entry['provider'], home), 'provider': entry['provider'], 'home': home,
                   'label': entry.get('label')}
        seen[key] = account
        accounts.append(account)
    return accounts


def configured_labels():
    """Labels the user gave to account ids, e.g. {"provider": "codex", "accountId": "…", "label": "Uni"}."""
    configured = (_read_json(CONFIG / 'ai-accounts.json') or {}).get('accounts', [])
    return {e['accountId']: e.get('label') for e in configured if isinstance(e, dict) and e.get('accountId')} \
        if isinstance(configured, list) else {}


def log_roots(account):
    home = account['home']
    if account['provider'] == 'claude':
        return [home / 'projects']
    return [home / 'sessions', home / 'archived_sessions']


# Log parsing

def parse_claude(handle, state, buckets):
    """Assistant messages carry per-request usage; streamed retries repeat ids."""
    seen = set(state.get('seen', []))
    for raw in handle:
        if b'"usage"' not in raw or b'"assistant"' not in raw:
            continue
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if entry.get('cwd'):
            state['project'] = entry['cwd']
        message = entry.get('message') or {}
        usage = message.get('usage')
        if entry.get('type') != 'assistant' or not isinstance(usage, dict):
            continue
        key = f"{message.get('id')}:{entry.get('requestId')}"
        if key in seen:
            continue
        seen.add(key)
        hour = _iso_hour(entry.get('timestamp'))
        if hour is None:
            continue
        _add(buckets, hour, message.get('model') or 'unknown', (
            usage.get('input_tokens'), usage.get('cache_read_input_tokens'),
            usage.get('cache_creation_input_tokens'), usage.get('output_tokens')))
    state['seen'] = sorted(seen)


def parse_codex(handle, state, buckets):
    """token_count events repeat the running total; only count when it grows."""
    model = state.get('model', 'unknown')
    total = state.get('total', 0)
    for raw in handle:
        if b'"session_meta"' in raw:
            try:
                meta = json.loads(raw)['payload']
                state['accountKey'] = meta.get('creator_account_id') or state.get('accountKey')
                state['project'] = meta.get('cwd') or state.get('project')
            except (ValueError, KeyError, AttributeError):
                pass
            continue
        if b'"turn_context"' in raw:
            try:
                model = json.loads(raw)['payload'].get('model') or model
            except (ValueError, KeyError, AttributeError):
                pass
            continue
        if b'"token_count"' not in raw:
            continue
        try:
            entry = json.loads(raw)
            info = entry['payload'].get('info') or {}
            limits = entry['payload'].get('rate_limits')
        except (ValueError, KeyError, AttributeError):
            continue
        state['lastSeen'] = max(state.get('lastSeen') or '', entry.get('timestamp') or '')
        if isinstance(limits, dict):
            state['limits'] = dict(limits, seenAt=entry.get('timestamp'))
        last = info.get('last_token_usage')
        running = (info.get('total_token_usage') or {}).get('total_tokens', 0)
        if not isinstance(last, dict) or running <= total:
            continue
        total = running
        hour = _iso_hour(entry.get('timestamp'))
        if hour is None:
            continue
        cached = last.get('cached_input_tokens') or 0
        _add(buckets, hour, model, (
            (last.get('input_tokens') or 0) - cached, cached,
            last.get('cache_write_input_tokens'), last.get('output_tokens')))
    state['model'] = model
    state['total'] = total


PARSERS = {'claude': parse_claude, 'codex': parse_codex}


def claim_sessions(files, accounts, now):
    """Claude logs name no account: the marker the status line hook leaves per session names the home that ran it."""
    ids = {a['id'] for a in accounts}
    for record in files.values():
        if record.get('provider') != 'claude' or not record.get('session'):
            continue
        try:
            owner = 'claude:' + (SESSIONS / record['session']).read_text(encoding='utf-8').strip()
        except OSError:
            continue
        if owner in ids:
            record['owner'] = owner
    try:
        markers = list(SESSIONS.iterdir())
    except OSError:
        return
    for marker in markers:
        try:
            if marker.stat().st_mtime < now - KEEP:
                marker.unlink()
        except OSError:
            pass


def load_cache():
    cache = _read_json(CACHE / 'index.json')
    if isinstance(cache, dict) and cache.get('version') == CACHE_VERSION:
        return cache
    return {'version': CACHE_VERSION, 'files': {}}


def save_cache(cache):
    CACHE.mkdir(parents=True, exist_ok=True)
    temp = CACHE / 'index.json.tmp'
    temp.write_text(json.dumps(cache, separators=(',', ':')), encoding='utf-8')
    os.replace(temp, CACHE / 'index.json')


def _complete_lines(handle, record):
    """Yield whole lines only, so a line being written is read on the next run."""
    offset = record['offset']
    for raw in handle:
        if not raw.endswith(b'\n'):
            break
        offset += len(raw)
        record['offset'] = offset
        yield raw


def scan(accounts, now):
    """Refresh the per-file buckets; appended logs are read from their last offset."""
    cache = load_cache()
    files = cache['files']
    cutoff = now - YEAR
    alive = set()
    for account in accounts:
        parser = PARSERS.get(account['provider'])
        if not parser:
            continue
        # Resolved, so a folder shared between homes by symlink is read once, for the first of them.
        for root in map(Path.resolve, log_roots(account)):
            if not root.is_dir():
                continue
            for path in root.rglob('*.jsonl'):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_mtime < cutoff:
                    continue
                key = str(path)
                if key in alive:
                    continue
                alive.add(key)
                # Claude logs sit in <project>/<session>.jsonl or <project>/<session>/subagents/….
                parts = path.relative_to(root).parts
                session = parts[1].removesuffix('.jsonl') if account['provider'] == 'claude' and len(parts) > 1 else None
                record = files.get(key)
                if record and record['size'] == stat.st_size:
                    record.update(account=account['id'], session=session)
                    continue
                if not record or stat.st_size < record['size']:
                    record = {'size': 0, 'offset': 0, 'state': {}, 'buckets': {}}
                try:
                    with path.open('rb') as handle:
                        handle.seek(record['offset'])
                        parser(_complete_lines(handle, record), record['state'], record['buckets'])
                except OSError:
                    continue
                record.update(size=stat.st_size, account=account['id'], provider=account['provider'], session=session)
                files[key] = record
    for key in list(files):
        if key not in alive:
            del files[key]
            continue
        buckets = files[key]['buckets']
        for hour in [h for h in buckets if int(h) < cutoff]:
            del buckets[hour]
    save_cache(cache)
    return files


# Cost

def load_pricing():
    prices = {}
    for path in (PRICING, CONFIG / 'ai-pricing.json'):
        models = (_read_json(path) or {}).get('models')
        if isinstance(models, dict):
            prices.update(models)
    return prices


def price_for(model, prices):
    """Exact id first, then the longest pricing key the model id starts with."""
    if model in prices:
        return prices[model]
    matches = [key for key in prices if model.startswith(key)]
    return prices[max(matches, key=len)] if matches else None


def cost_of(row, price):
    if not price:
        return None
    rates = (price.get('input'), price.get('cacheRead'), price.get('cacheWrite'), price.get('output'))
    return sum(tokens * (rate or 0) for tokens, rate in zip(row, rates)) / 1_000_000


def savings_of(row, price):
    """What cache reads would have cost as fresh input."""
    if not price or price.get('cacheRead') is None:
        return 0
    return row[1] * (price.get('input', 0) - price['cacheRead']) / 1_000_000


def _midnight(epoch):
    local = time.localtime(epoch)
    return int(time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1)))


def ranges(now):
    hour_now = int(now // HOUR * HOUR)
    midnight = _midnight(now)
    return {
        '24h': {'start': hour_now - 23 * HOUR, 'step': HOUR, 'points': 24},
        '7d': {'start': midnight - 6 * 86400, 'step': 86400, 'points': 7},
        '30d': {'start': midnight - 29 * 86400, 'step': 86400, 'points': 30},
        '90d': {'start': midnight - 89 * 86400, 'step': 86400, 'points': 90},
        '365d': {'start': midnight - 364 * 86400, 'step': 86400, 'points': 365},
        'hours90': {'start': hour_now - (90 * 24 - 1) * HOUR, 'step': HOUR, 'points': 90 * 24},
    }


def summarise(records, keys, now, prices):
    """Totals, per-key series and model breakdown for every range."""
    result = {}
    for name, spec in ranges(now).items():
        start, step, points = spec['start'], spec['step'], spec['points']
        series = {k: {'tokens': [0] * points, 'cost': [0.0] * points, 'unpriced': [False] * points} for k in keys}
        sessions = {k: 0 for k in keys}
        models = {}
        projects = {}
        totals = dict.fromkeys(FIELDS, 0)
        totals.update(cost=0.0, savings=0.0, unpriced=0)
        for record in records:
            key = record.get('owner') or record['account']
            if key not in series:
                continue
            active = False
            project = record['state'].get('project') or ''
            spent = {'tokens': 0, 'cost': 0.0}
            for hour, by_model in record['buckets'].items():
                hour = int(hour)
                if hour < start:
                    continue
                active = True
                # Daily points follow local midnights, so DST days stay aligned.
                index = (hour - start) // step if step == HOUR else round((_midnight(hour) - start) / 86400)
                index = max(0, min(points - 1, index))
                for model, row in by_model.items():
                    price = price_for(model, prices)
                    # OpenCode rows carry the cost OpenCode itself recorded as a fifth field.
                    cost = row[4] if len(row) > 4 and row[4] is not None else cost_of(row[:4], price)
                    tokens = sum(row[:4])
                    series[key]['tokens'][index] += tokens
                    spent['tokens'] += tokens
                    spent['cost'] += cost or 0
                    item = models.setdefault(model, {'model': model, 'provider': record.get('provider'), 'tokens': 0,
                                                     'cost': None if cost is None else 0.0})
                    item['tokens'] += tokens
                    for i, field in enumerate(FIELDS):
                        totals[field] += row[i]
                    if cost is None:
                        totals['unpriced'] += tokens
                        series[key]['unpriced'][index] = True
                    else:
                        series[key]['cost'][index] += cost
                        item['cost'] = (item['cost'] or 0) + cost
                        totals['cost'] += cost
                    totals['savings'] += savings_of(row, price)
            if active:
                sessions[key] += 1
                entry = projects.setdefault(project, {'path': project, 'tokens': 0, 'cost': 0.0, 'sessions': 0,
                                                      'providers': []})
                entry['tokens'] += spent['tokens']
                entry['cost'] += spent['cost']
                entry['sessions'] += 1
                if record.get('provider') not in entry['providers']:
                    entry['providers'].append(record.get('provider'))
        processed = sum(totals[field] for field in FIELDS)
        ordered = sorted(models.values(), key=lambda m: (m['cost'] or 0, m['tokens']), reverse=True)
        for item in ordered:
            item['tokenShare'] = item['tokens'] / processed if processed else 0
            item['costShare'] = (item['cost'] or 0) / totals['cost'] if totals['cost'] else 0
        result[name] = {
            'start': start, 'step': step, 'points': points,
            'series': series, 'sessions': sessions, 'sessionCount': sum(sessions.values()),
            'totals': dict(totals, processed=processed),
            'byKey': {k: {'tokens': sum(series[k]['tokens']), 'cost': sum(series[k]['cost'])} for k in keys},
            'models': ordered,
            'projects': describe_projects(projects.values(), totals['cost'], processed),
        }
    return result


def describe_projects(projects, cost, processed):
    """Projects by cost, named after their folder; agent worktrees fold into their repo."""
    grouped = {}
    for item in projects:
        path = Path(item['path']) if item['path'] else None
        parts = path.parts if path else ()
        name = ('~' if path == HOME else path.name) if path else ''
        worktree = 'worktrees' in parts
        if worktree:
            # ~/.codex/worktrees/<id>/<repo> and ~/.ao/data/worktrees/<repo>/<branch>
            at = parts.index('worktrees')
            after = parts[at + 1:]
            if after:
                name = after[-1] if parts[at - 1] == '.codex' else after[0]
        entry = grouped.setdefault(name, {'name': name, 'path': '', 'tokens': 0, 'cost': 0.0, 'sessions': 0,
                                          'providers': [], 'worktrees': 0})
        if path and (not worktree or not entry['path']):
            entry['path'] = str(path).replace(str(HOME), '~', 1)
        entry['worktrees'] += worktree
        entry['tokens'] += item['tokens']
        entry['cost'] += item['cost']
        entry['sessions'] += item['sessions']
        entry['providers'] += [p for p in item['providers'] if p not in entry['providers']]
    ordered = sorted(grouped.values(), key=lambda p: (p['cost'], p['tokens']), reverse=True)
    for entry in ordered:
        entry['costShare'] = entry['cost'] / cost if cost else 0
        entry['tokenShare'] = entry['tokens'] / processed if processed else 0
    return ordered


# Limits

def _limit(ident, used, resets_at, window, now):
    if used is None:
        return None
    resets_at = int(resets_at) if resets_at else None
    # A window that has rolled over since the snapshot starts empty again.
    if resets_at and resets_at <= now:
        used, resets_at = 0, None
    return {'id': ident, 'usedPercent': max(0.0, min(100.0, float(used))), 'resetsAt': resets_at,
            'windowMinutes': window}


def claude_snapshot(home, named_by_folder=True):
    """The newest snapshot with limits that the status line hook left for this home.

    statusline-hook.py names it after the home's key. Earlier hooks used claude.json without
    CLAUDE_CONFIG_DIR and claude-<folder name>.json with it; the folder name only identifies
    a home while no other Claude home has the same one.
    """
    paths = [STATE / f'claude-{home_key(home)}.json']
    if named_by_folder:
        paths.append(STATE / f'claude-{home.name}.json')
    if home == (HOME / '.claude').resolve():
        paths.append(STATE / 'claude.json')
    found = [s for s in map(_read_json, paths) if isinstance(s, dict)]
    # A session reports no limits until its first reply, so a snapshot without them never hides one with.
    return max([s for s in found if s.get('rate_limits')] or found, key=lambda s: s.get('captured_at') or 0, default=None)


def claude_profile(home):
    """Display name and plan from the profile Claude Code caches; no tokens live there."""
    config = HOME / '.claude.json' if home == (HOME / '.claude').resolve() else home / '.claude.json'
    profile = (_read_json(config) or {}).get('oauthAccount') or {}
    tier = profile.get('userRateLimitTier') or profile.get('organizationRateLimitTier') or ''
    plan = CLAUDE_PLANS.get(profile.get('organizationType'))
    for multiple in ('20x', '5x'):
        if plan == 'Max' and multiple in tier:
            plan = f'Max {multiple}'
    return {'email': profile.get('emailAddress'), 'name': profile.get('displayName') or profile.get('fullName'),
            'organization': profile.get('organizationName'), 'plan': plan,
            'extraUsage': profile.get('hasExtraUsageEnabled')}


def claude_account(account, now, named_by_folder=True, live=True, opener=None):
    """Live usage from Anthropic's API when Claude Code's sign-in allows it, else the status line snapshot."""
    api = _sibling('claude_api')
    details, error = api.usage(account['home'], now, opener) if live else (None, None)
    base = claude_statusline_account(account, now, named_by_folder)
    base.update(session=api.session(account['home'], now), error=error, extra=None, cloud=None)
    if details:
        base.update(details, available=True, reason=None, source='api', updatedAt=now)
    return base


def claude_statusline_account(account, now, named_by_folder=True):
    info = claude_profile(account['home'])
    snapshot = claude_snapshot(account['home'], named_by_folder)
    if not snapshot:
        return dict(info, available=False, reason='statusline', limits=[])
    limits = snapshot.get('rate_limits') or {}
    rows = [
        _limit('session', (limits.get('five_hour') or {}).get('used_percentage'),
               (limits.get('five_hour') or {}).get('resets_at'), 300, now),
        _limit('weekly', (limits.get('seven_day') or {}).get('used_percentage'),
               (limits.get('seven_day') or {}).get('resets_at'), 10080, now),
    ]
    for key, value in limits.items():
        if key.startswith('seven_day_') and isinstance(value, dict):
            rows.append(_limit('weekly_' + key[len('seven_day_'):], value.get('used_percentage'),
                               value.get('resets_at'), 10080, now))
    rows = [row for row in rows if row]
    return dict(info, available=bool(rows), reason=None if rows else 'statusline', limits=rows,
                model=snapshot.get('model'), source='statusline', updatedAt=snapshot.get('captured_at'))


def find_codex():
    found = shutil.which('codex')
    if found:
        return found
    for folder in ('.local/bin', '.local/share/mise/shims', '.npm-global/bin', '.bun/bin', '.cargo/bin'):
        candidate = HOME / folder / 'codex'
        if os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def codex_rpc(binary, home, timeout=8):
    """Ask the signed-in Codex CLI for its account and limits over app-server JSON-RPC."""
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'wysun', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'account/read', 'params': {'refreshToken': False}},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'account/rateLimits/read'},
    ]
    env = dict(os.environ, CODEX_HOME=str(home))
    process = subprocess.Popen([binary, 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True, env=env)
    answers = {}
    try:
        process.stdin.write(''.join(json.dumps(r) + '\n' for r in requests).encode())
        process.stdin.flush()
        deadline = time.monotonic() + timeout
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        buffer = b''
        while len(answers) < 2 and time.monotonic() < deadline:
            if not selector.select(max(0.0, deadline - time.monotonic())):
                break
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                break
            buffer += chunk
            *lines, buffer = buffer.split(b'\n')
            for line in lines:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if message.get('id') in (2, 3):
                    answers[message['id']] = message.get('result')
        return answers.get(2), answers.get(3)
    finally:
        process.kill()
        process.wait()


def reset_credits(summary):
    """Available Codex reset credits as reported with the limits (read only)."""
    if not isinstance(summary, dict):
        return None
    credits = [{'title': c.get('title'), 'description': c.get('description'), 'expiresAt': c.get('expiresAt')}
               for c in summary.get('credits') or [] if isinstance(c, dict) and c.get('status') in (None, 'available')]
    return {'available': int(summary.get('availableCount') or 0), 'credits': credits}


def codex_from_logs(home):
    newest = None
    root = home / 'sessions'
    if root.is_dir():
        for path in root.rglob('*.jsonl'):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if not newest or mtime > newest[0]:
                newest = (mtime, path)
    if not newest:
        return None
    found = None
    with newest[1].open('rb') as handle:
        for raw in handle:
            if b'"rate_limits"' in raw:
                found = raw
    try:
        limits = json.loads(found)['payload']['rate_limits']
    except (TypeError, ValueError, KeyError):
        return None
    convert = lambda w: w and {'usedPercent': w.get('used_percent'), 'resetsAt': w.get('resets_at'),
                               'windowDurationMins': w.get('window_minutes')}
    return {'rateLimits': {'primary': convert(limits.get('primary')), 'secondary': convert(limits.get('secondary')),
                           'planType': limits.get('plan_type')}, 'updatedAt': newest[0]}


def codex_account(account, now, live=True):
    binary = find_codex()
    profile, result, source, updated = None, None, 'app-server', now
    if live and binary:
        try:
            profile, result = codex_rpc(binary, account['home'])
        except OSError:
            pass
    if not result:
        result, source = codex_from_logs(account['home']), 'logs'
        updated = (result or {}).get('updatedAt')
    limits = (result or {}).get('rateLimits') or {}
    rows = []
    for ident, window in (('session', limits.get('primary')), ('weekly', limits.get('secondary'))):
        if window:
            rows.append(_limit(ident, window.get('usedPercent'), window.get('resetsAt'),
                               window.get('windowDurationMins'), now))
    rows = [row for row in rows if row]
    signed_in = (profile or {}).get('account') or {}
    plan = signed_in.get('planType') or limits.get('planType')
    credits = limits.get('credits') or {}
    return {'email': signed_in.get('email'), 'name': None, 'organization': None,
            'plan': plan.replace('_', ' ').title() if isinstance(plan, str) else None,
            'credits': credits.get('balance') if credits.get('hasCredits') else None,
            'accountKey': (result or {}).get('accountId'),
            'resetCredits': reset_credits((result or {}).get('rateLimitResetCredits')),
            'available': bool(rows), 'reason': None if rows else ('cli' if not binary else 'empty'),
            'limits': rows, 'source': source, 'updatedAt': updated}


def opencode_records(accounts, now):
    """One usage record per OpenCode session, built from its database on every run (it is small)."""
    records = []
    for account in accounts:
        if account['provider'] != 'opencode':
            continue
        sessions = {}
        for row in _sibling('opencode').history(account['home'] / 'opencode.db', now - YEAR):
            record = sessions.setdefault(row['session'], {
                'account': account['id'], 'provider': 'opencode', 'session': row['session'],
                'state': {'project': row['project']}, 'buckets': {}})
            hour = str(int(row['time'] // HOUR * HOUR))
            bucket = record['buckets'].setdefault(hour, {}).setdefault(row['model'], [0, 0, 0, 0, 0.0])
            for i, field in enumerate(FIELDS):
                bucket[i] += row[field]
            bucket[4] = None if bucket[4] is None or row['cost'] is None else bucket[4] + row['cost']
        records += sessions.values()
    return records


def opencode_account(account, now, live=True, opener=None):
    module = _sibling('opencode')
    limits, error = module.usage(account['home'], now, opener) if live else ([], None)
    return {'email': None, 'name': None, 'organization': None, 'plan': 'Go' if limits else None, 'credits': None,
            'available': bool(limits), 'reason': None if limits else 'subscription', 'limits': limits,
            'source': 'opencode-api' if limits else 'local', 'updatedAt': now, 'error': error,
            'session': module.session(account['home'], now)}


def history_account(key, records, label, now):
    """A Codex account seen in the logs but not signed in to any home: usage and its last known limits."""
    snapshot = max((r['state'].get('limits') for r in records if r['state'].get('limits')),
                   key=lambda l: l.get('seenAt') or '', default=None) or {}
    seen = _iso_hour(snapshot.get('seenAt')) if snapshot.get('seenAt') else None
    rows = []
    for ident, window in (('session', snapshot.get('primary')), ('weekly', snapshot.get('secondary'))):
        if isinstance(window, dict):
            rows.append(_limit(ident, window.get('used_percent'), window.get('resets_at'), window.get('window_minutes'), now))
    rows = [row for row in rows if row]
    plan = snapshot.get('plan_type')
    return {'id': 'codex:' + key[:12], 'provider': 'codex', 'providerName': NAMES['codex'],
            'label': label or 'Account ' + key[:4], 'email': None, 'name': None, 'organization': None,
            'plan': plan.replace('_', ' ').title() if isinstance(plan, str) else None, 'credits': None,
            'accountKey': key, 'available': bool(rows), 'reason': None if rows else 'history', 'limits': rows,
            'source': 'history', 'updatedAt': seen, 'home': None}


def describe(account, now, live, shared_names=frozenset(), opener=None):
    if account['provider'] == 'claude':
        details = claude_account(account, now, account['home'].name not in shared_names, live, opener)
    elif account['provider'] == 'opencode':
        details = opencode_account(account, now, live, opener)
    else:
        details = codex_account(account, now, live)
    label = account['label'] or details.get('name') or (details.get('email') or '').split('@')[0] or NAMES[account['provider']]
    return dict(details, id=account['id'], provider=account['provider'], providerName=NAMES[account['provider']],
                label=label, home=str(account['home']).replace(str(HOME), '~', 1))


def tell_apart(accounts, named):
    """Accounts of one provider that came out with the same label are told apart by e-mail, then by folder.

    Labels the user chose (ids in `named`) are never changed.
    """
    groups = {}
    for account in accounts:
        groups.setdefault((account['provider'], account['label']), []).append(account)
    for group in groups.values():
        if len(group) < 2:
            continue
        for account in group:
            if account['id'] not in named:
                account['label'] = (account.get('email') or '').split('@')[0] or account['label']
        labels = Counter(a['label'] for a in group)
        for account in group:
            if account['id'] not in named and labels[account['label']] > 1 and account.get('home'):
                account['label'] += f" ({Path(account['home']).name})"


def collect(now=None, live=True, opener=None):
    now = time.time() if now is None else now
    accounts = load_accounts()
    files = scan(accounts, now)
    claim_sessions(files, accounts, now)
    records = list(files.values()) + opencode_records(accounts, now)
    prices = load_pricing()
    folders = Counter(a['home'].name for a in accounts if a['provider'] == 'claude')
    shared_names = {name for name, count in folders.items() if count > 1}
    with ThreadPoolExecutor(max_workers=max(1, len(accounts))) as pool:
        described = list(pool.map(lambda a: describe(a, now, live, shared_names, opener), accounts))
    # Two homes signed in to the same Codex account report the same id; keep the first.
    unique, keys = [], set()
    for account in described:
        key = account.get('accountKey')
        if key and key in keys:
            continue
        keys.add(key)
        unique.append(account)
    # Codex sessions name the account that ran them; route each to that account,
    # and give accounts that only appear in the logs a history tab of their own.
    # Without a live answer, a home is signed in to the account of its newest session.
    for account in unique:
        if account['provider'] == 'codex' and not account.get('accountKey'):
            own = [r for r in records if r['account'] == account['id'] and r['state'].get('accountKey')]
            if own:
                account['accountKey'] = max(own, key=lambda r: r['state'].get('lastSeen') or '')['state']['accountKey']
    by_key = {a['accountKey']: a for a in unique if a.get('accountKey')}
    labels = configured_labels()
    orphans = {}
    for record in records:
        key = record['state'].get('accountKey') if record.get('provider') == 'codex' else None
        if not key:
            continue
        if key in by_key:
            record['owner'] = by_key[key]['id']
        else:
            orphans.setdefault(key, []).append(record)
    for key, owned in sorted(orphans.items(), key=lambda item: -len(item[1])):
        account = history_account(key, owned, labels.get(key), now)
        for record in owned:
            record['owner'] = account['id']
        unique.append(account)
    named = {a['id'] for a in accounts if a['label']}
    for account in unique:
        if account.get('accountKey') in labels and labels[account['accountKey']]:
            account['label'] = labels[account['accountKey']]
            named.add(account['id'])
    tell_apart(unique, named)
    ids = [a['id'] for a in unique]
    for account in unique:
        account['usage'] = summarise(records, [account['id']], now, prices)
    record_limits(unique, records, now)
    providers = sorted({a['provider'] for a in unique})
    status = service_status(providers, now, live and '--no-status' not in sys.argv, opener)
    agents = running_agents(accounts, files, now)
    disk_usage(unique, now)
    snapshot = {'generatedAt': now, 'version': 2, 'status': status, 'agents': agents, 'accounts': unique, 'usage': summarise(records, ids, now, prices)}
    save_snapshot(snapshot)
    return snapshot


def record_limits(accounts, records, now):
    """Store a point per changed limit and give every limit its burndown and previous windows."""
    history = _sibling('limit_history')
    path = STATE / 'limits.jsonl'
    entries = []
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    entries = history.append(entries, accounts, now)
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.tmp')
        temp.write_text(''.join(json.dumps(e, separators=(',', ':')) + '\n' for e in entries), encoding='utf-8')
        os.replace(temp, path)
    except OSError:
        pass
    prices = load_pricing()
    for account in accounts:
        owned = [r for r in records if (r.get('owner') or r['account']) == account['id']]
        history.attach(entries, account, lambda start, end, owned=owned: cost_between(owned, start, end, prices))


def cost_between(records, start, end, prices):
    total = 0.0
    for record in records:
        for hour, by_model in record['buckets'].items():
            if start <= int(hour) < end:
                for model, row in by_model.items():
                    cost = row[4] if len(row) > 4 and row[4] is not None else cost_of(row[:4], price_for(model, prices))
                    total += cost or 0
    return total


DISK_TTL = 86400


def disk_usage(accounts, now):
    """Each account's folder size, measured at most once a day (cached by account id)."""
    path = CACHE / 'disk.json'
    cached = _read_json(path) or {}
    result, changed = {}, False
    for account in accounts:
        if account.get('source') == 'history' or not account.get('home'):
            continue
        entry = cached.get(account['id'])
        if not isinstance(entry, dict) or now - entry.get('measuredAt', 0) >= DISK_TTL:
            home = Path(str(HOME) + account['home'][1:] if account['home'].startswith('~') else account['home'])
            entry = _sibling('disk').measure(home, account['provider'], now)
            entry['root'] = str(home).replace(str(HOME), '~', 1)
            changed = True
        result[account['id']] = entry
        account['disk'] = entry
    if changed:
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + '.tmp')
            temp.write_text(json.dumps(result), encoding='utf-8')
            os.replace(temp, path)
        except OSError:
            pass


BUSY_SECONDS = 15


def session_details(files, provider, account, cwd, started, now):
    """Model, tokens, cost and busy state of the newest log of `provider` in `cwd` since `started`."""
    prices = load_pricing()
    best = None
    for path, record in files.items():
        if record.get('provider') != provider or record['state'].get('project') != cwd:
            continue
        if account and (record.get('owner') or record.get('account')) != account:
            continue
        try:
            mtime = os.stat(path).st_mtime
        except OSError:
            continue
        if started and mtime < started - 60:
            continue
        if not best or mtime > best[0]:
            best = (mtime, record)
    if not best:
        return None
    mtime, record = best
    since = int((started or 0) // HOUR * HOUR)
    tokens, cost, model, newest = 0, 0.0, None, -1
    for hour, by_model in record['buckets'].items():
        if int(hour) < since:
            continue
        for name, row in by_model.items():
            tokens += sum(row[:4])
            cost += cost_of(row[:4], price_for(name, prices)) or 0
            if int(hour) >= newest:
                newest, model = int(hour), name
    return {'model': model, 'tokens': tokens, 'cost': round(cost, 4), 'busy': now - mtime < BUSY_SECONDS}


def running_agents(accounts, files, now):
    if '--no-agents' in sys.argv:
        return []
    homes = {(a['provider'], str(Path(a['home']).resolve())): a['id'] for a in accounts}
    try:
        return _sibling('agents').scan(Path('/proc'), homes, now,
                                       lambda provider, account, cwd, started: session_details(files, provider, account, cwd, started, now))
    except OSError:
        return []


STATUS_TTL = 120


def service_status(providers, now, live, opener=None):
    """Status per provider, refetched at most every STATUS_TTL seconds; the cached one when offline."""
    path = CACHE / 'status.json'
    cached = _read_json(path) or {}
    result = {}
    for provider in providers:
        entry = cached.get(provider)
        if live and (not isinstance(entry, dict) or now - entry.get('checkedAt', 0) >= STATUS_TTL):
            entry = dict(_sibling('service_status').fetch(provider, opener=opener), checkedAt=now)
        if isinstance(entry, dict):
            result[provider] = entry
    if live and result != cached:
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + '.tmp')
            temp.write_text(json.dumps(result), encoding='utf-8')
            os.replace(temp, path)
        except OSError:
            pass
    return result


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def prepare_account(provider):
    """A new, empty home for another account, set up so the panel finds it; its folder, or None.

    Claude: ~/.claude-<n> whose settings.json runs the status line hook. Codex: ~/.codex-<n>, listed in
    ai-accounts.json. The sign-in itself is the provider's own (`claude` /login, `codex login`).
    """
    if provider not in ('claude', 'codex'):
        return None
    n = 2
    while (HOME / f'.{provider}-{n}').exists():
        n += 1
    folder = HOME / f'.{provider}-{n}'
    folder.mkdir(mode=0o700)
    if provider == 'claude':
        hook = Path(__file__).with_name('statusline-hook.py')
        _write_json(folder / 'settings.json', {'statusLine': {'type': 'command', 'command': f'python3 -I {hook}'}})
    else:
        config = _read_json(CONFIG / 'ai-accounts.json') or {}
        accounts = config.get('accounts') if isinstance(config.get('accounts'), list) else []
        config['accounts'] = accounts + [{'provider': 'codex', 'home': str(folder)}]
        _write_json(CONFIG / 'ai-accounts.json', config)
    return str(folder)


def save_snapshot(snapshot):
    """Last result, read by the shell at start so the panel paints before the first refresh."""
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        temp = CACHE / 'snapshot.json.tmp'
        temp.write_text(json.dumps(snapshot, separators=(',', ':')), encoding='utf-8')
        os.replace(temp, CACHE / 'snapshot.json')
    except OSError:
        pass


if __name__ == '__main__':
    if '--prepare-account' in sys.argv:
        index = sys.argv.index('--prepare-account')
        print(prepare_account(sys.argv[index + 1] if index + 1 < len(sys.argv) else '') or '')
        sys.exit(0)
    json.dump(collect(live='--offline' not in sys.argv), sys.stdout, separators=(',', ':'))
