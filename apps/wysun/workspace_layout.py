"""Fixed numeric workspaces per output.

Workspaces 1..10 belong to an explicit output. Rules are emitted as
``hl.workspace_rule`` handles with ``persistent=true`` so an empty workspace
still opens on the configured output; moving or removing one only changes that
rule and never touches windows. Workspace 10 is shown as ``0`` in the bar so it
matches the SUPER+0 shortcut.
"""
NUMBERS = tuple(range(1, 11))
INTERNAL_PREFIXES = ('eDP', 'LVDS', 'DSI', 'edp')


def workspace_label(value):
    """Bar label for a workspace number/name: 10 is shown as 0."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return str(value).strip()
    return '0' if number == 10 else str(number)


def workspace_number(value):
    """Numeric workspace 1..10 from an id/name, or ValueError."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError('Número de escritorio inválido: '+str(value))
    if not 1 <= number <= 10:
        raise ValueError('Los escritorios van del 1 al 10.')
    return number


_number = workspace_number


def _internal(name):
    return any(str(name).startswith(prefix) for prefix in INTERNAL_PREFIXES)


def ordered_outputs(outputs):
    """Enabled output names, externals left to right and the internal last."""
    enabled = [o for o in outputs if o.get('enabled', True)]
    externals = [o for o in enabled if not _internal(o['name'])]
    internals = [o for o in enabled if _internal(o['name'])]
    externals.sort(key=lambda o: (o.get('x', 0), o['name']))
    return [o['name'] for o in externals+internals]


def default_layout(outputs):
    """Automatic layout: 1-5 / 6-9 / 10 for three outputs, 5/5 for two."""
    names = ordered_outputs(outputs)
    if not names:
        return {}
    if len(names) == 1:
        return {names[0]: list(NUMBERS)}
    if len(names) == 2:
        return {names[0]: list(range(1, 6)), names[1]: list(range(6, 11))}
    head, tail = names[:-1], names[-1]
    base = list(range(1, 10))
    share, remainder = divmod(len(base), len(head))
    mapping = {}
    index = 0
    for position, name in enumerate(head):
        count = share+(1 if position < remainder else 0)
        mapping[name] = base[index:index+count]
        index += count
    mapping[tail] = [10]
    return mapping


def normalize_layout(stored, outputs):
    """Clean saved values for the current outputs; unknown data is ignored.

    Returning ``{}`` is normal when the section predates this feature or holds
    unrelated legacy keys: callers fall back to :func:`default_layout`.
    """
    names = [o['name'] for o in outputs if o.get('enabled', True)]
    if not isinstance(stored, dict):
        return {}
    result = {}
    used = set()
    for name in names:
        raw = stored.get(name)
        if not isinstance(raw, (list, tuple)):
            continue
        values = []
        for item in raw:
            try:
                number = _number(item)
            except ValueError:
                continue
            if number not in used:
                values.append(number)
                used.add(number)
        if values:
            result[name] = values
    return result


def validate_layout(mapping, outputs):
    """Strict validation of an edited mapping against the current outputs."""
    names = [o['name'] for o in outputs if o.get('enabled', True)]
    if not names:
        raise ValueError('No hay pantallas activas para asignar escritorios.')
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError('Asigna al menos un escritorio a una pantalla.')
    clean = {}
    used = set()
    for name, raw in mapping.items():
        if name not in names:
            raise ValueError('Pantalla desconocida: '+str(name))
        if not isinstance(raw, (list, tuple)) or not raw:
            raise ValueError('Cada pantalla asignada necesita al menos un escritorio.')
        values = []
        for item in raw:
            number = _number(item)
            if number in used:
                raise ValueError('El escritorio '+str(number)+' ya está en otra pantalla.')
            used.add(number)
            values.append(number)
        clean[name] = sorted(values)
    return clean


def lua_fragment(mapping):
    """Durable fragment sourced at login; only persistent workspace rules."""
    from hypr_settings import lua
    lines = ['-- Wysun managed fixed workspaces; generated from Ajustes.'
             ' Do not edit by hand.','wysun_workspace_layout = {']
    for output, numbers in mapping.items():
        for number in numbers:
            lines.append('  '+lua(dict(workspace=str(number), monitor=output, persistent=True))+',')
    lines += ['}','for _, rule in ipairs(wysun_workspace_layout) do',
              '  if hl.get_monitor(rule.monitor) then hl.workspace_rule(rule) end',
              'end']
    return '\n'.join(lines)+'\n'


def live_script(apply, release):
    """Runtime diff: pin new placements and unpin removed ones.

    Applying a persistent rule again moves the workspace (with its windows) to
    the latest output. Releasing an empty persistent workspace removes it.
    """
    from hypr_settings import lua
    pinned = {(output, number) for output, numbers in apply.items() for number in numbers}
    rules = [(output, number, True) for output, number in sorted(pinned)]
    for output, numbers in release.items():
        for number in numbers:
            if (output, number) not in pinned:
                rules.append((output, number, False))
    lines = ['local rules = {']
    for output, number, persistent in rules:
        lines.append('  '+lua(dict(workspace=str(number), monitor=output, persistent=persistent))+',')
    lines += ['}','for _, rule in ipairs(rules) do',
              '  if hl.get_monitor(rule.monitor) then hl.workspace_rule(rule) end',
              'end']
    return '\n'.join(lines)+'\n'


def sort_key(value):
    """Numeric workspaces first and in numeric order; names after them."""
    text = str(value)
    try:
        return (0, int(text), '')
    except ValueError:
        return (1, 0, text)
