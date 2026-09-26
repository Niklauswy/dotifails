"""Reconcile BSPWM desktops by identity; never reset or destroy their trees."""
import json
import subprocess


def run(args):
    return subprocess.check_output(args, text=True, timeout=10).strip()


def ident(value):
    return f'0x{value:08X}'


def workspace_layout(outputs, saved=None):
    active = [o for o in outputs if o['connected'] and o['enabled']]
    active.sort(key=lambda o: (not o.get('primary', False), o.get('x', 0), o['name']))
    if not active:
        raise RuntimeError('No hay una pantalla activa; se conservan todos los escritorios.')
    names = [o['name'] for o in active]
    if saved and any(name in saved for name in names):
        return {name: list(saved.get(name, [])) for name in names}
    internal = [name for name in names if name.startswith(('eDP', 'LVDS'))]
    numbered = [name for name in names if name not in internal] if len(names) >= 3 and internal else names
    layout = {name: [] for name in names}
    next_number = 1
    for i, name in enumerate(numbered):
        count = max(1, 10 // len(numbered) + (i < 10 % len(numbered)))
        layout[name] = [str(n) for n in range(next_number, next_number + count)]
        next_number += count
    for name in names:
        if name not in numbered:
            layout[name] = ['AUX']
    return layout


def reconcile(outputs, saved=None, runner=run):
    layout = workspace_layout(outputs, saved)
    snapshot = lambda: json.loads(runner(['bspc', 'wm', '-d']))
    state = snapshot()
    active = {m['name']: m for m in state['monitors'] if m['name'] in layout}
    if set(active) != set(layout):
        raise RuntimeError('BSPWM aún no reconoce las pantallas activas; vuelve a recargar.')
    target = ident(active[next(iter(layout))]['id'])
    original_focus = next((m['focusedDesktopId'] for m in state['monitors'] if m['id'] == state['focusedMonitorId']), None)
    # Rescue whole desktops, including custom names, before removing a stale monitor.
    for monitor in state['monitors']:
        if monitor['name'] in active:
            continue
        # The IPC command refuses to transfer the last desktop of a monitor.
        runner(['bspc', 'monitor', ident(monitor['id']), '-a', 'Desktop'])
        for desktop in monitor['desktops']:
            runner(['bspc', 'desktop', ident(desktop['id']), '-m', target])
        remaining = next((m for m in snapshot()['monitors'] if m['id'] == monitor['id']), None)
        if remaining:
            # BSPWM can insert an empty fallback desktop after the last transfer.
            if any(d.get('root') is not None or d['name'] != 'Desktop' for d in remaining['desktops']):
                raise RuntimeError('El monitor aún contiene ventanas; se conserva por seguridad.')
            runner(['bspc', 'monitor', ident(monitor['id']), '-r'])
    # Find the actual desktop IDs globally, including desktops rescued by BSPWM itself.
    for monitor_name, names in layout.items():
        monitor_id = active[monitor_name]['id']
        for name in names:
            matches = [(m, d) for m in snapshot()['monitors'] for d in m['desktops'] if d['name'] == name]
            if not matches:
                runner(['bspc', 'monitor', ident(monitor_id), '-a', name])
            for m, d in matches:
                if m['id'] != monitor_id:
                    if len(m['desktops']) == 1:
                        runner(['bspc', 'monitor', ident(m['id']), '-a', 'Desktop'])
                    runner(['bspc', 'desktop', ident(d['id']), '-m', ident(monitor_id)])
    # Old reset-desktops configurations can leave two occupied desktops named "1".
    # Keep both trees; only discard empty duplicates, and label occupied extras.
    for monitor in snapshot()['monitors']:
        if monitor['name'] not in layout:
            continue
        used = {d['name'] for d in monitor['desktops']}
        for name in sorted(used):
            duplicates = [d for d in monitor['desktops'] if d['name'] == name]
            if not name.isdigit() or len(duplicates) < 2:
                continue
            keeper = next((d for d in duplicates if d['id'] == original_focus and d.get('root') is not None), None)
            keeper = keeper or next((d for d in duplicates if d.get('root') is not None), duplicates[0])
            for d in duplicates:
                if d is keeper:
                    continue
                if d.get('root') is None:
                    runner(['bspc', 'desktop', ident(d['id']), '-r'])
                else:
                    suffix = 1
                    label = f'{name} · recuperado'
                    while label in used:
                        suffix += 1
                        label = f'{name} · recuperado {suffix}'
                    runner(['bspc', 'desktop', ident(d['id']), '-n', label])
                    used.add(label)
    for monitor in snapshot()['monitors']:
        if monitor['name'] not in layout:
            continue
        desktops = monitor['desktops']
        for d in list(desktops):
            if d['name'] == 'Desktop' and d.get('root') is None and len(desktops) > 1:
                runner(['bspc', 'desktop', ident(d['id']), '-r'])
                desktops.remove(d)
        ordered = sorted(desktops, key=lambda d: (0, int(d['name'])) if d['name'].isdigit() else (1, d['name']))
        if len({d['name'] for d in ordered}) == len(ordered):
            runner(['bspc', 'monitor', ident(monitor['id']), '-o', *[d['name'] for d in ordered]])
    if original_focus is not None:
        latest = snapshot()
        current = next((m['focusedDesktopId'] for m in latest['monitors'] if m['id'] == latest['focusedMonitorId']), None)
        if current != original_focus and any(d['id'] == original_focus for m in latest['monitors'] for d in m['desktops']):
            runner(['bspc', 'desktop', ident(original_focus), '-f'])


if __name__ == '__main__':
    from environment_settings import EnvironmentSettings, display_inventory
    inventory = display_inventory()
    workspace_layout(inventory)  # Refuse changes if no usable destination exists.
    for setting in ('remove_disabled_monitors', 'remove_unplugged_monitors'):
        run(['bspc', 'config', setting, 'true'])
    for output in inventory:
        if not output['connected'] and output['enabled']:
            run(['xrandr', '--output', output['name'], '--off'])
    reconcile(display_inventory(), EnvironmentSettings().section('workspaces'))
