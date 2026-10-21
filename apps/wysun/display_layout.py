"""Display arrangement that Hyprland can always use.

Plans are lists of ``{name, enabled, primary, mode, rate, rotation, x, y,
scale}``. Free dragging easily leaves monitors overlapping or separated by a
gap, which Hyprland accepts but then behaves erratically (cursor trapped,
surfaces on the wrong output). :func:`normalize` turns any draft into rows of
edge-to-edge monitors starting at 0x0, keeping the order the user chose.
"""
import copy

ROTATED = ('left', 'right')
SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)


def logical_size(p):
    """Size in layout pixels after rotation and scale."""
    try:
        w, h = (int(v) for v in str(p['mode']).split('x'))
    except (KeyError, ValueError):
        w, h = 1920, 1080
    if p.get('rotation') in ROTATED:
        w, h = h, w
    scale = float(p.get('scale', 1) or 1)
    return round(w / scale), round(h / scale)


def _rows(active):
    """Group monitors whose vertical extents overlap into rows, top to bottom."""
    rows = []
    for p in sorted(active, key=lambda p: (p['y'] + logical_size(p)[1] / 2)):
        top, bottom = p['y'], p['y'] + logical_size(p)[1]
        for row in rows:
            if top < row['bottom'] and bottom > row['top']:
                row['items'].append(p)
                row['top'], row['bottom'] = min(row['top'], top), max(row['bottom'], bottom)
                break
        else:
            rows.append({'top': top, 'bottom': bottom, 'items': [p]})
    rows.sort(key=lambda row: row['top'])
    return rows


def normalize(plan):
    """Edge-to-edge rows from 0x0, left-to-right by each monitor's centre."""
    plan = copy.deepcopy(plan)
    active = [p for p in plan if p.get('enabled', True)]
    y = 0
    for row in _rows(active):
        items = sorted(row['items'], key=lambda p: (p['x'] + logical_size(p)[0] / 2, p['name']))
        x = 0
        height = 0
        for p in items:
            w, h = logical_size(p)
            p['x'], p['y'] = x, y
            x += w
            height = max(height, h)
        y += height
    return plan


def order(plan):
    """Enabled monitor names in reading order (rows, then left to right)."""
    return [p['name'] for p in sorted((p for p in plan if p.get('enabled', True)), key=lambda p: (p['y'], p['x']))]


def move(plan, name, direction):
    """Swap ``name`` with its neighbour in the same row ('left'/'right'), or
    place it on its own row above/below every other monitor."""
    plan = normalize(plan)
    target = next((p for p in plan if p['name'] == name and p.get('enabled', True)), None)
    if target is None:
        return plan
    if direction in ('left', 'right'):
        row = sorted((p for p in plan if p.get('enabled', True) and p['y'] == target['y']), key=lambda p: p['x'])
        index = row.index(target)
        other = index - 1 if direction == 'left' else index + 1
        if 0 <= other < len(row):
            row[index], row[other] = row[other], row[index]
            x = 0
            for p in row:
                p['x'] = x
                x += logical_size(p)[0]
        elif len(row) == 1:
            # A display moved above/below must also be able to rejoin a row.
            others = [p for p in plan if p.get('enabled', True) and p is not target]
            if others:
                neighbour = min(others, key=lambda p: abs(p['y'] - target['y']))
                adjacent = [p for p in others if p['y'] == neighbour['y']]
                target['y'] = neighbour['y']
                target['x'] = (min(p['x'] for p in adjacent) - logical_size(target)[0]
                               if direction == 'left' else max(p['x'] + logical_size(p)[0] for p in adjacent))
    elif direction in ('above', 'below'):
        others = [p for p in plan if p.get('enabled', True) and p is not target]
        if others:
            top = min(p['y'] for p in others)
            bottom = max(p['y'] + logical_size(p)[1] for p in others)
            target['y'] = top - logical_size(target)[1] - 1 if direction == 'above' else bottom + 1
            target['x'] = min(p['x'] for p in others)
    return normalize(plan)


def overlaps(plan):
    """Pairs of enabled monitors that overlap (should be empty after normalize)."""
    active = [p for p in plan if p.get('enabled', True)]
    found = []
    for i, a in enumerate(active):
        aw, ah = logical_size(a)
        for b in active[i + 1:]:
            bw, bh = logical_size(b)
            if a['x'] < b['x'] + bw and b['x'] < a['x'] + aw and a['y'] < b['y'] + bh and b['y'] < a['y'] + ah:
                found.append((a['name'], b['name']))
    return found


def monitors_fragment(plan):
    """Durable Lua rules for this arrangement, loaded after local.lua."""
    from hypr_settings import lua
    lines = ['-- Wysun managed display arrangement; generated from Ajustes > Pantallas.',
             '-- Do not edit by hand: delete this file to return to automatic placement.']
    for p in sorted(plan, key=lambda p: not p.get('enabled', True)):
        values = dict(output=p['name'])
        if not p.get('enabled', True):
            values['disabled'] = True
        else:
            values.update(mode=p['mode'] + '@' + p['rate'], position=f"{int(p['x'])}x{int(p['y'])}",
                          scale=float(p.get('scale', 1) or 1),
                          transform={'normal': 0, 'left': 1, 'inverted': 2, 'right': 3}[p.get('rotation', 'normal')])
        lines.append('hl.monitor(' + lua(values) + ')')
    return '\n'.join(lines) + '\n'
