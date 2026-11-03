"""Query filters and the three table views of Wysun Processes (by app, tree, list). Rows keep stable keys:
`g:<app>` for an app group, `p:<pid>:<start>` for a process."""
import re

UNITS = {'': 1024 ** 2, 'k': 1024, 'm': 1024 ** 2, 'g': 1024 ** 3}
STATE_ALIASES = {'running': 'R', 'ejecutando': 'R', 'sleeping': 'S', 'espera': 'S', 'en espera': 'S',
                 'stopped': 'T', 'pausado': 'T', 'paused': 'T', 'idle': 'I', 'inactivo': 'I', 'zombie': 'Z',
                 'zombi': 'Z', 'io': 'D', 'disk': 'D'}
NUMERIC = re.compile(r'^(cpu|mem|gpu)(<=|>=|<|>)(\d+(?:\.\d+)?)([kmg]?)$', re.I)
FIELD = re.compile(r'^(user|state|pid|ppid|app):(.+)$', re.I)
SORTS = ('name', 'cpu', 'mem', 'gpu', 'io', 'threads')


def key_of(row):
    return f"p:{row['pid']}:{row['start']}"


class Query:
    def __init__(self, text):
        self.text = text
        self.tokens, self.words, self.checks = [], [], []
        for term in text.split():
            numeric, field = NUMERIC.match(term), FIELD.match(term)
            if numeric:
                self.tokens.append(term)
                self.checks.append(self._numeric(*numeric.groups()))
            elif field:
                self.tokens.append(term)
                self.checks.append(self._field(field[1].lower(), field[2].lower()))
            else:
                self.words.append(term.casefold())

    @staticmethod
    def _numeric(name, op, value, unit):
        name = name.lower()
        limit = float(value) * (UNITS[unit.lower()] if name == 'mem' else 1)
        compare = {'<': float.__lt__, '>': float.__gt__, '<=': float.__le__, '>=': float.__ge__}[op]

        def check(row):
            actual = row.get(name)
            return actual is not None and compare(float(actual), limit)
        return check

    @staticmethod
    def _field(name, value):
        if name == 'state':
            letter = STATE_ALIASES.get(value, value.upper() if len(value) == 1 else None)
            return lambda row: row.get('state') == letter or row.get('state_label', '').casefold().startswith(value)
        if name in ('pid', 'ppid'):
            return lambda row: str(row.get(name)) == value
        return lambda row: value in str(row.get(name, '')).casefold()

    @property
    def active(self):
        return bool(self.tokens or self.words)

    def match(self, row):
        if not all(check(row) for check in self.checks):
            return False
        haystack = f"{row.get('name', '')} {row.get('pid', '')} {row.get('app', '')} {row.get('user', '')}".casefold()
        return all(word in haystack for word in self.words)


def parse_query(text):
    return Query(text or '')


def _value(row, sort):
    if sort == 'name':
        return str(row.get('name', '')).casefold()
    ema = row.get('ema') or {}
    if sort in ema:
        return ema[sort]
    return row.get(sort) or 0


def _group(app, children, expanded):
    total = lambda f: sum(c.get(f) or 0 for c in children)
    gpus = [c['gpu'] for c in children if c.get('gpu') is not None]
    key = 'g:' + app
    return dict(key=key, group=True, name=app, app=app, depth=0, kids=len(children), expanded=key in expanded,
                pid=0, cpu=total('cpu'), mem=total('mem'), io=total('io'), threads=total('threads'),
                gpu=sum(gpus) if gpus else None, user=children[0].get('user', ''), uid=children[0].get('uid'),
                state='', ema={k: sum((c.get('ema') or {}).get(k, c.get(k) or 0) for c in children)
                               for k in ('cpu', 'gpu', 'io') if any(k in (c.get('ema') or {}) for c in children)})


def _leaf(row, depth, **extra):
    out = dict(row, key=key_of(row), group=False, depth=depth)
    out.setdefault('kids', 0)
    out.setdefault('expanded', False)
    out.update(extra)
    return out


def build(rows, mode, query, sort, descending, expanded, mine, uid):
    """`(view rows, number of processes matching)` for `mode` in apps/tree/list."""
    sort = sort if sort in SORTS else 'cpu'
    order = lambda r: _value(r, sort)
    pool = [r for r in rows if not mine or r.get('uid') == uid]
    hits = [r for r in pool if query.match(r)]
    out = []
    if mode == 'apps':
        groups, sizes = {}, {}
        for r in pool:
            sizes[r['app']] = sizes.get(r['app'], 0) + 1
        for r in hits:
            groups.setdefault(r['app'], []).append(r)
        entries = []
        for app, children in groups.items():
            if sizes[app] == 1:
                entries.append((_leaf(children[0], 0, appRow=True), None))
            else:
                entries.append((_group(app, children, expanded), children))
        for head, children in sorted(entries, key=lambda e: order(e[0]), reverse=descending):
            out.append(head)
            if children and (head['expanded'] or query.active):
                head['expanded'] = True
                out.extend(_leaf(c, 1) for c in sorted(children, key=order, reverse=descending))
    elif mode == 'tree':
        by_pid = {r['pid']: r for r in pool}
        included = {r['pid']: r for r in hits}
        for r in hits:
            parent, seen = r['ppid'], {r['pid']}
            while parent in by_pid and parent not in seen:
                seen.add(parent)
                included[parent] = by_pid[parent]
                parent = by_pid[parent]['ppid']
        children = {}
        for r in included.values():
            parent = r['ppid'] if r['ppid'] in included and r['ppid'] != r['pid'] else 0
            children.setdefault(parent, []).append(r)
        seen = set()
        stack = [(r, 0) for r in reversed(sorted(children.get(0, []), key=order, reverse=descending))]
        while stack:
            r, depth = stack.pop()
            if r['pid'] in seen:
                continue
            seen.add(r['pid'])
            kids = children.get(r['pid'], [])
            open_ = bool(kids) and (key_of(r) in expanded or query.active)
            out.append(_leaf(r, depth, kids=len(kids), expanded=open_))
            if open_:
                stack.extend((k, depth + 1) for k in reversed(sorted(kids, key=order, reverse=descending)))
    else:
        out = [_leaf(r, 0) for r in sorted(hits, key=order, reverse=descending)]
    return out, len(hits)
