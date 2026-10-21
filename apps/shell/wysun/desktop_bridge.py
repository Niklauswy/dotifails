#!/usr/bin/env python3
"""JSON bridge between the Nexus pages and the Wysun desktop backends (no Qt).

Usage: desktop_bridge.py ACTION [JSON-ARGS]. Prints one JSON line,
{"ok": true, "data": ...} or {"ok": false, "error": "..."}. The `processes`
action streams one JSON snapshot per line until its stdout closes.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def app_dir():
    """Directory with the Wysun Python backends: checkout first, then the installed copy."""
    candidates = [os.environ.get('WYSUN_APP_DIR'),
                  str(Path(__file__).resolve().parents[2]/'wysun'),
                  str(Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'orbit/app')]
    for candidate in candidates:
        if candidate and (Path(candidate)/'settings_data.py').is_file():
            return candidate
    raise RuntimeError('No se encontraron los módulos de Wysun.')


sys.path.insert(0, app_dir())

from environment_settings import EnvironmentSettings, DisplayTrial, display_inventory, display_plan  # noqa: E402
from settings_data import DesktopSettings, ShortcutFile, SCHEMA, PreferenceBackup, atomic_write, backup_file  # noqa: E402
from settings_shortcuts import expanded_rows, change_binding, application_shortcuts  # noqa: E402
from terminal_args import terminal_args, vim_args  # noqa: E402

HOME = Path(os.environ.get('HOME') or Path.home())
BACKUPS = HOME/'.local/share/orbit/settings-backups'
POSITIONS = [('top-left', 'Arriba · izquierda'), ('top-center', 'Arriba · centro'), ('top-right', 'Arriba · derecha'),
             ('bottom-left', 'Abajo · izquierda'), ('bottom-center', 'Abajo · centro'), ('bottom-right', 'Abajo · derecha')]
# key, label, type, low, high, default, suffix
COMPONENTS = {
    'effects': ('Efectos y animaciones', 'Ajusta el movimiento, las sombras y el cristal del compositor.', [
        ('duration', 'Duración de animaciones', 'int', 50, 600, 120, ' ms'),
        ('corner-radius', 'Esquinas', 'int', 0, 20, 12, ' px'),
        ('shadow', 'Sombras', 'bool', 0, 0, True, ''),
        ('shadow-radius', 'Tamaño de sombra', 'int', 0, 40, 18, ' px'),
        ('shadow-opacity', 'Opacidad de sombra', 'float', 0, 1, .25, ''),
        ('blur-background', 'Desenfoque de fondo', 'bool', 0, 0, True, ''),
        ('blur-strength', 'Intensidad de desenfoque', 'int', 1, 8, 3, ''),
        ('fading', 'Fundido al aparecer', 'bool', 0, 0, True, ''),
        ('vsync', 'Sincronización vertical (la gestiona el compositor)', 'fixed', 0, 0, True, '')]),
    'terminal': ('Terminal', 'Fuente, colores y espacio de Ghostty. Se ven en las terminales nuevas.', [
        ('font-family', 'Fuente', 'text', 0, 0, 'FiraCode Nerd Font', ''),
        ('font-size', 'Tamaño', 'float', 8, 36, 20, ' pt'),
        ('background-opacity', 'Opacidad del fondo', 'float', .1, 1, .6, ''),
        ('window-padding-x', 'Margen horizontal', 'int', 0, 60, 10, ' px'),
        ('window-padding-y', 'Margen vertical', 'int', 0, 60, 10, ' px'),
        ('scrollback-limit', 'Memoria del historial', 'int', 1000, 1000000, 10000, ' bytes'),
        ('background', 'Color de fondo', 'color', 0, 0, '#1a1b26', ''),  # theme-exception: valor por defecto de la terminal del usuario
        ('foreground', 'Color del texto', 'color', 0, 0, '#c0caf5', '')]),  # theme-exception: valor por defecto de la terminal del usuario
    'notifications': ('Notificaciones', 'Posición, tamaño y tiempo de los avisos de Dunst.', [
        ('origin', 'Posición', 'position', 0, 0, 'top-right', ''),
        ('font', 'Fuente y tamaño', 'text', 0, 0, 'Inter 10', ''),
        ('transparency', 'Transparencia', 'int', 0, 60, 5, ' %'),
        ('corner_radius', 'Esquinas', 'int', 0, 30, 12, ' px'),
        ('notification_limit', 'Avisos simultáneos', 'int', 1, 12, 4, ''),
        ('padding', 'Margen interior', 'int', 4, 40, 18, ' px'),
        ('gap_size', 'Separación', 'int', 0, 30, 10, ' px'),
        ('timeout', 'Duración normal', 'int', 1, 60, 6, ' s')]),
}
FILES = [('Hyprland', 'wysun/hyprland.lua'), ('Atajos Wysun', 'orbit/hypr-shortcuts.lua'),
         ('Reglas Wysun', 'orbit/hypr-settings.lua'), ('Efectos', 'orbit/hypr-effects.lua'),
         ('Notificaciones', 'wysun/dunstrc'), ('Ghostty', 'ghostty/config'),
         ('Neovim', 'nvim/lua/mappings.lua'), ('Preferencias del entorno', 'orbit/environment.json')]


def env():
    return EnvironmentSettings(HOME)


def as_bool(value):
    return str(value).lower() in ('true', '1')


# --- pantallas --------------------------------------------------------------

def layout_view(plan):
    from display_layout import order, logical_size
    boxes = []
    for p in plan:
        w, h = logical_size(p)
        boxes.append(dict(name=p['name'], x=p['x'], y=p['y'], w=w, h=h, enabled=p['enabled']))
    return dict(plan=plan, order=order(plan), boxes=boxes)


def displays_state(_args):
    from display_layout import normalize, SCALES
    outputs = display_inventory(env().runner)
    modes = {o['name']: o['modes'] for o in outputs if o['connected']}
    return dict(layout_view(normalize(display_plan(outputs))), modes=modes, scales=list(SCALES))


def displays_normalize(args):
    """Apply one edit (or a move) to a draft plan and return it normalised."""
    from display_layout import normalize, move
    plan = args['plan']
    if args.get('move'):
        plan = move(plan, args['move']['name'], args['move']['direction'])
    else:
        plan = normalize(plan)
    return layout_view(plan)


def displays_try(args):
    backend = env()
    trial = DisplayTrial(backend, args['plan'])
    return dict(folder=str(trial.folder))


def displays_settle(args):
    trial = DisplayTrial.resume(env(), args['folder'])
    if args['accept']:
        trial.accept()
        try:
            from environment_settings import render_wallpaper
            backend = env()
            if backend.section('wallpaper').get('default'):
                render_wallpaper(backend.wallpaper_values(), display_inventory(backend.runner), backend.home, backend.runner)
        except Exception:
            pass  # Qt-only wallpaper check; the shell keeps showing the previous wallpaper
    else:
        trial.reject()
    return {}


# --- escritorios ------------------------------------------------------------

def workspaces_state(_args):
    backend = env()
    outputs = [o['name'] for o in display_inventory(backend.runner) if o.get('enabled')]
    return dict(rows=backend.workspaces(), outputs=outputs)


def workspaces_edit(args):
    backend = env()
    action = args['action']
    if action == 'reset':
        backend.reset_workspace_layout()
    elif action == 'assign':
        backend.assign_workspace(int(args['number']), args['monitor'])
    elif action == 'remove':
        backend.unassign_workspace(int(args['number']))
    else:
        raise ValueError('Acción de escritorio desconocida.')
    return workspaces_state({})


# --- atajos -----------------------------------------------------------------

def shortcuts_state(args):
    model = ShortcutFile(HOME)
    from settings_data import canonical
    rows = expanded_rows(model)
    conflicts = model.conflicts()
    for row in rows:
        row['duplicate'] = bool(row.get('editable') and 'error' not in row and canonical(row['key']) in conflicts)
    return dict(rows=rows, conflicts=len(conflicts), path=str(model.path))


def shortcuts_apps(_args):
    return dict(rows=application_shortcuts(home=HOME))


def shortcuts_save(args):
    model = ShortcutFile(HOME)
    index, part = args.get('source_index'), args.get('part')
    title = args.get('title') or 'Atajo personalizado'
    if index is None:
        model.save(args['key'], args['command'], None, title)
    elif args.get('group'):
        model.save(args['key'], args['command'], index, title)
    else:
        change_binding(model, index, part, args['key'], args['command'], title)
    return shortcuts_state({})


def shortcuts_delete(args):
    model = ShortcutFile(HOME)
    change_binding(model, args['source_index'], args.get('part'))
    return shortcuts_state({})


# --- ventanas y reglas ------------------------------------------------------

def desktop_state(_args):
    backend = DesktopSettings(HOME)
    schema = {k: dict(label=t[0], kind=t[1], low=t[2], high=t[3]) for k, t in SCHEMA.items()}
    return dict(values=backend.values, rules=backend.saved.get('rules', []), schema=schema)


def desktop_apply(args):
    backend = DesktopSettings(HOME)
    values = args.get('values')
    backend.apply(dict(backend.values) if values is None else values, args['rules'])
    return desktop_state({})


# --- efectos, terminal, notificaciones ---------------------------------------

def component_state(args):
    kind = args['kind']
    title, note, schema = COMPONENTS[kind]
    values = env().component_values(kind)
    rows = []
    for key, label, typ, low, high, default, suffix in schema:
        value = values.get(key, default)
        if typ == 'int':
            value = int(float(value))
        elif typ == 'float':
            value = float(value)
        elif typ in ('bool', 'fixed'):
            value = as_bool(value)
        elif typ == 'color':
            value = '#'+str(value).lstrip('#')
        if typ in ('int', 'float'):
            value = min(max(value, low), high)
        rows.append(dict(key=key, label=label, type=typ, low=low, high=high, suffix=suffix, value=value))
    return dict(title=title, note=note, rows=rows, positions=[dict(value=v, label=l) for v, l in POSITIONS])


def component_apply(args):
    env().apply_component(args['kind'], args['values'])
    return component_state(args)


# --- inicio ------------------------------------------------------------------

def startup_state(_args):
    backend = env()
    services = []
    for name in ('Hyprland', 'quickshell', 'dunst', 'pipewire', 'wireplumber'):
        running = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', name], capture_output=True).returncode == 0
        services.append(dict(name=name, running=running))
    return dict(entries=backend.autostart_entries(), services=services)


def startup_toggle(args):
    backend = env()
    entry = next((e for e in backend.autostart_entries() if e['id'] == args['id']), None)
    if not entry:
        raise ValueError('La entrada ya no existe.')
    backend.set_autostart(entry, bool(args['enabled']))
    return startup_state({})


def startup_add(args):
    env().add_autostart(args['name'], args['command'])
    return startup_state({})


# --- archivos y copias ------------------------------------------------------

def backups_state(_args):
    rows = []
    if BACKUPS.is_dir():
        for path in sorted(BACKUPS.glob('*'), reverse=True)[:80]:
            if path.is_file() or (path/'receipt.json').is_file():
                kind = 'preferencias' if path.is_dir() else 'atajos' if path.name.endswith('-hypr-shortcuts.json') \
                    else 'ajustes' if path.name.endswith('-hypr-desktop.json') else 'archivo'
                rows.append(dict(name=path.name, path=str(path), kind=kind, restorable=kind != 'archivo'))
    config = HOME/'.config'
    return dict(backups=rows, files=[dict(title=t, path=str(config/p)) for t, p in FILES])


def backups_restore(args):
    path = (BACKUPS/Path(args['name']).name)
    if not path.exists():
        raise ValueError('La copia ya no existe.')
    backend = env()
    if path.is_dir():
        backup = PreferenceBackup.open(HOME, backend.preference_paths(), path)
        backend.undo_preferences(backup)
    elif path.name.endswith('-hypr-shortcuts.json'):
        model = ShortcutFile(HOME)
        model._write(json.loads(path.read_text()))
    elif path.name.endswith('-hypr-desktop.json'):
        data = json.loads(path.read_text())
        DesktopSettings(HOME).apply(data['values'], data['rules'])
    else:
        raise ValueError('Esta copia solo se puede inspeccionar.')
    return backups_state({})


def open_file(args):
    target = Path(args['path']).expanduser().absolute()
    allowed = [HOME/'.config', HOME/'.local/share/orbit', HOME/'.ssh']
    if not any(root == target or root in target.parents for root in allowed):
        raise ValueError('Ruta no permitida.')
    subprocess.Popen(vim_args(target), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {}


# --- SSH ---------------------------------------------------------------------

def ssh_state(_args):
    from ssh_profiles import SSHProfiles
    store = SSHProfiles()
    saved = store.saved()
    rows = [dict(r, index=i, imported=False) for i, r in enumerate(saved)]
    rows += [dict(r, index=-1, imported=True) for r in store.all()[len(saved):]]
    return dict(rows=rows)


def ssh_save(args):
    from ssh_profiles import SSHProfiles
    row = dict(name=args['name'].strip(), host=args['host'].strip(), user=args.get('user', '').strip(),
               port=int(args.get('port') or 22))
    SSHProfiles().save(row, args.get('index') if args.get('index', -1) >= 0 else None)
    return ssh_state({})


def ssh_delete(args):
    from ssh_profiles import SSHProfiles
    SSHProfiles().delete(int(args['index']))
    return ssh_state({})


def ssh_connect(args):
    from ssh_profiles import SSHProfiles, ssh_args
    row = next((r for r in SSHProfiles().all() if r['name'] == args['name']), None)
    if not row:
        raise ValueError('La conexión ya no existe.')
    subprocess.Popen(ssh_args(row), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {}


# --- procesos ----------------------------------------------------------------

def processes_details(args):
    import process_data
    return process_data.Processes().details(args['row'])


def processes_act(args):
    import process_data
    process_data.Processes().act(args['row'], args['action'])
    return {}


def process_view(rows, control, own_uid):
    """Filter, order (list or tree) and cap the snapshot according to the UI controls."""
    from process_data import matched
    by_pid = {r['pid']: r for r in rows}
    state = control.get('state', 'all')
    visible = []
    for r in rows:
        if control.get('owner', 'mine') == 'mine' and r['uid'] != own_uid:
            continue
        if (state == 'running' and r['state'] != 'R') or (state == 'paused' and r['state'] not in ('T', 't')) \
                or (state == 'busy' and r['cpu'] < 5 and r['memory'] < 250*1048576):
            continue
        if matched(r, control.get('query', '')):
            visible.append(r)
    key = control.get('sort', 'cpu')
    reverse = key in ('cpu', 'memory')
    order = (lambda r: r['name'].casefold()) if key == 'name' else (lambda r: r.get(key) or 0)
    if control.get('tree'):
        included = {r['pid']: r for r in visible}
        for r in visible:
            parent, seen = r['ppid'], {r['pid']}
            while parent in by_pid and parent not in seen:
                seen.add(parent)
                included[parent] = by_pid[parent]
                parent = by_pid[parent]['ppid']
        children = {}
        for r in included.values():
            children.setdefault(r['ppid'] if r['ppid'] in included and r['ppid'] != r['pid'] else 0, []).append(r)
        result, visited = [], set()

        def walk(parent, depth):
            for r in sorted(children.get(parent, []), key=order, reverse=reverse):
                if r['pid'] in visited:
                    continue
                visited.add(r['pid'])
                result.append(dict(r, depth=depth))
                walk(r['pid'], depth + 1)
        walk(0, 0)
        for r in sorted(included.values(), key=order, reverse=reverse):  # parent cycles: show them as roots
            if r['pid'] not in visited:
                visited.add(r['pid'])
                result.append(dict(r, depth=0))
                walk(r['pid'], 1)
        ordered = result
    else:
        ordered = [dict(r, depth=0) for r in sorted(visible, key=order, reverse=reverse)]
    return ordered[:400], len(visible)


def processes_stream(args):
    """Emit a snapshot per interval; filter/sort controls arrive as JSON lines on stdin."""
    import process_data
    import select
    model = process_data.Processes()
    control = dict(owner='mine', state='all', query='', sort='cpu', tree=False, interval=float(args.get('interval', 2)))
    own_uid = os.getuid()
    while True:
        rows = model.scan()
        shown, total = process_view(rows, control, own_uid)
        print(json.dumps(dict(ok=True, data=dict(rows=shown, matched=total, summary=model.summary)), default=str), flush=True)
        deadline = time.monotonic() + max(0.5, min(10.0, control['interval']))
        while True:
            wait = deadline - time.monotonic()
            if wait <= 0:
                break
            ready, _, _ = select.select([sys.stdin], [], [], wait)
            if not ready:
                break
            line = sys.stdin.readline()
            if not line:
                return {}
            try:
                control.update(json.loads(line))
            except ValueError:
                continue
            deadline = time.monotonic()  # redraw immediately after a control change


ACTIONS = {
    'displays.state': displays_state, 'displays.normalize': displays_normalize,
    'displays.try': displays_try, 'displays.settle': displays_settle,
    'workspaces.state': workspaces_state, 'workspaces.edit': workspaces_edit,
    'shortcuts.state': shortcuts_state, 'shortcuts.apps': shortcuts_apps,
    'shortcuts.save': shortcuts_save, 'shortcuts.delete': shortcuts_delete,
    'desktop.state': desktop_state, 'desktop.apply': desktop_apply,
    'component.state': component_state, 'component.apply': component_apply,
    'startup.state': startup_state, 'startup.toggle': startup_toggle, 'startup.add': startup_add,
    'backups.state': backups_state, 'backups.restore': backups_restore, 'file.open': open_file,
    'ssh.state': ssh_state, 'ssh.save': ssh_save, 'ssh.delete': ssh_delete, 'ssh.connect': ssh_connect,
    'processes.details': processes_details, 'processes.act': processes_act, 'processes.stream': processes_stream,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in ACTIONS:
        print(json.dumps(dict(ok=False, error='Acción desconocida.')))
        return 2
    try:
        args = json.loads(argv[2]) if len(argv) > 2 else {}
        data = ACTIONS[argv[1]](args)
        print(json.dumps(dict(ok=True, data=data), default=str))
        return 0
    except BrokenPipeError:
        return 0
    except Exception as error:  # noqa: BLE001 - every failure becomes a user-facing message
        print(json.dumps(dict(ok=False, error=(str(error) or type(error).__name__)[:400])))
        return 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
