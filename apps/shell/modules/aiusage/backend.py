#!/usr/bin/env python3
"""AI provider accounts, limits and local usage for the shell's AI usage panel.

Nothing here reads credentials. Each account is a CLI home the user is already
signed in to:
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
import json
import os
import selectors
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HOME = Path.home()
STATE = Path(os.environ.get('XDG_STATE_HOME') or HOME / '.local/state') / 'wysun/ai-usage'
CACHE = Path(os.environ.get('XDG_CACHE_HOME') or HOME / '.cache') / 'wysun/ai-usage'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME') or HOME / '.config') / 'wysun'
DEFAULT_HOMES = {
    'claude': Path(os.environ.get('CLAUDE_CONFIG_DIR') or HOME / '.claude'),
    'codex': Path(os.environ.get('CODEX_HOME') or HOME / '.codex'),
}
NAMES = {'claude': 'Claude', 'codex': 'Codex'}
PRICING = Path(__file__).with_name('pricing.json')

HOUR = 3600
KEEP = 90 * 24 * HOUR
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

def account_id(provider, home):
    return provider + ':' + hashlib.sha1(str(home).encode()).hexdigest()[:10]


def load_accounts():
    """Default homes first, then the configured ones; homes are deduplicated."""
    entries = [{'provider': p, 'home': str(h)} for p, h in DEFAULT_HOMES.items()]
    configured = (_read_json(CONFIG / 'ai-accounts.json') or {}).get('accounts', [])
    for entry in configured if isinstance(configured, list) else []:
        if isinstance(entry, dict) and entry.get('provider') in NAMES and entry.get('home'):
            entries.append(entry)
    accounts, seen = [], {}
    for entry in entries:
        home = Path(os.path.expanduser(str(entry['home']))).resolve()
        key = (entry['provider'], home)
        if key in seen:
            # A configured label may rename a default home.
            seen[key]['label'] = entry.get('label') or seen[key]['label']
            continue
        if not home.is_dir():
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
    cutoff = now - KEEP
    alive = set()
    for account in accounts:
        parser = PARSERS[account['provider']]
        for root in log_roots(account):
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
                record = files.get(key)
                if record and record['size'] == stat.st_size:
                    record['account'] = account['id']
                    continue
                if not record or stat.st_size < record['size']:
                    record = {'size': 0, 'offset': 0, 'state': {}, 'buckets': {}}
                try:
                    with path.open('rb') as handle:
                        handle.seek(record['offset'])
                        parser(_complete_lines(handle, record), record['state'], record['buckets'])
                except OSError:
                    continue
                record.update(size=stat.st_size, account=account['id'], provider=account['provider'])
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
    }


def summarise(records, keys, now, prices):
    """Totals, per-key series and model breakdown for every range."""
    result = {}
    for name, spec in ranges(now).items():
        start, step, points = spec['start'], spec['step'], spec['points']
        series = {k: {'tokens': [0] * points, 'cost': [0.0] * points} for k in keys}
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
                    cost = cost_of(row, price)
                    tokens = sum(row)
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


def claude_snapshot(home):
    """Matches the status line hook: claude.json without CLAUDE_CONFIG_DIR, claude-<dir name>.json with it."""
    paths = [STATE / f'claude-{home.name}.json']
    if home == (HOME / '.claude').resolve():
        paths.insert(0, STATE / 'claude.json')
    found = [s for s in map(_read_json, paths) if isinstance(s, dict)]
    return max(found, key=lambda s: s.get('captured_at') or 0, default=None)


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


def claude_account(account, now):
    info = claude_profile(account['home'])
    snapshot = claude_snapshot(account['home'])
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


def describe(account, now, live):
    details = claude_account(account, now) if account['provider'] == 'claude' else codex_account(account, now, live)
    label = account['label'] or details.get('name') or (details.get('email') or '').split('@')[0] or NAMES[account['provider']]
    return dict(details, id=account['id'], provider=account['provider'], providerName=NAMES[account['provider']],
                label=label, home=str(account['home']).replace(str(HOME), '~', 1))


def collect(now=None, live=True):
    now = time.time() if now is None else now
    accounts = load_accounts()
    records = list(scan(accounts, now).values())
    prices = load_pricing()
    with ThreadPoolExecutor(max_workers=max(1, len(accounts))) as pool:
        described = list(pool.map(lambda a: describe(a, now, live), accounts))
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
    for account in unique:
        if account.get('accountKey') in labels and labels[account['accountKey']]:
            account['label'] = labels[account['accountKey']]
    ids = [a['id'] for a in unique]
    for account in unique:
        account['usage'] = summarise(records, [account['id']], now, prices)
    snapshot = {'generatedAt': now, 'accounts': unique, 'usage': summarise(records, ids, now, prices)}
    save_snapshot(snapshot)
    return snapshot


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
    json.dump(collect(live='--offline' not in sys.argv), sys.stdout, separators=(',', ':'))
