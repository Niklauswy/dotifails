"""Recorded points of every usage limit, for the burndown chart and the previous windows.

Entries are {"t", "account", "limit", "used", "resetsAt"}; backend.py stores them as JSON lines.
A window is the run of entries sharing one reset time; a different reset time starts the next one.
"""
KEEP = 90 * 86400
EVERY = 15 * 60
SAME_RESET = 120


def append(entries, accounts, now):
    """Entries plus a point per limit that changed (or every 15 min), without points older than 90 days."""
    last = {}
    for entry in entries:
        last[(entry['account'], entry['limit'])] = entry
    kept = [e for e in entries if e.get('t', 0) >= now - KEEP]
    for account in accounts:
        if account.get('source') == 'history':
            continue
        for limit in account.get('limits') or []:
            previous = last.get((account['id'], limit['id']))
            point = {'t': round(now), 'account': account['id'], 'limit': limit['id'],
                     'used': round(float(limit['usedPercent']), 1), 'resetsAt': limit.get('resetsAt')}
            if previous and previous['used'] == point['used'] and _same(previous.get('resetsAt'), point['resetsAt']) \
                    and now - previous['t'] < EVERY:
                continue
            kept.append(point)
    return kept


def _same(a, b):
    return a is None or b is None or abs(a - b) <= SAME_RESET


def _windows(points):
    groups = []
    for point in sorted(points, key=lambda p: p['t']):
        if groups and _same(groups[-1]['resetsAt'], point.get('resetsAt')):
            groups[-1]['points'].append(point)
            groups[-1]['resetsAt'] = groups[-1]['resetsAt'] or point.get('resetsAt')
        else:
            groups.append({'resetsAt': point.get('resetsAt'), 'points': [point]})
    return groups


def attach(entries, account, cost_between):
    """Fill each limit of the account with `history` (current window) and `windows` (up to 4 earlier ones).

    cost_between(start, end) is the account's cost between two epochs.
    """
    for limit in account.get('limits') or []:
        groups = _windows([e for e in entries if e['account'] == account['id'] and e['limit'] == limit['id']])
        current = groups.pop() if groups and _same(groups[-1]['resetsAt'], limit.get('resetsAt')) else None
        limit['history'] = [[p['t'], p['used']] for p in current['points']] if current else []
        span = (limit.get('windowMinutes') or 0) * 60
        windows = []
        for group in reversed(groups[-4:]):
            ended = int(group['resetsAt'] or group['points'][-1]['t'])
            exhausted = next((p['t'] for p in group['points'] if p['used'] >= 100), None)
            start = ended - span if span else group['points'][0]['t']
            windows.append({'endedAt': ended, 'usedPercent': group['points'][-1]['used'], 'exhaustedAt': exhausted,
                            'cost': round(cost_between(start, ended), 4)})
        limit['windows'] = windows
