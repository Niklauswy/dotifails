"""JSON service for Nexus Displays and Workspaces; independent of Qt."""
import json
import os
import sys
from pathlib import Path


def app_dir():
    """Directory with the Wysun Python backends: checkout first, then the installed copy."""
    candidates = [os.environ.get('WYSUN_APP_DIR'),
                  str(Path(__file__).resolve().parents[2]/'wysun'),
                  str(Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'orbit/app')]
    for candidate in candidates:
        if candidate and (Path(candidate)/'settings_data.py').is_file():
            return candidate
    raise RuntimeError('Wysun display services are unavailable.')


sys.path.insert(0, app_dir())

from environment_settings import EnvironmentSettings, DisplayTrial, display_inventory, display_plan  # noqa: E402
HOME = Path(os.environ.get('HOME') or Path.home())


def env():
    return EnvironmentSettings(HOME)



def layout_view(plan):
    from display_layout import order, logical_size
    boxes = []
    for p in plan:
        w, h = logical_size(p)
        boxes.append(dict(name=p['name'], x=p['x'], y=p['y'], w=w, h=h, enabled=p['enabled']))
    return dict(plan=plan, order=order(plan), boxes=boxes)


def displays_state(_args):
    from display_layout import normalize, SCALES
    backend = env()
    outputs = display_inventory(backend.runner)
    from environment_settings import profile_key
    saved = backend.section('displays').get('profiles', {}).get(profile_key(outputs), [])
    primary = next((p['name'] for p in saved if p.get('enabled') and p.get('primary')), None)
    if primary and any(o['name'] == primary and o['enabled'] for o in outputs):
        for output in outputs:
            output['primary'] = output['name'] == primary
    modes = {o['name']: [dict(m, rates=list(dict.fromkeys(m['rates']))) for m in o['modes']]
             for o in outputs if o['connected']}
    return dict(layout_view(normalize(display_plan(outputs))), modes=modes, scales=list(SCALES))


def displays_widgets(args):
    mode = args.get('mode')
    if mode not in ('all', 'primary'):
        raise ValueError('Widget screens must be all or primary.')
    backend = env()
    section = dict(backend.section('displays'))
    section['widgetScreens'] = mode
    backend.save_section('displays', section)
    return dict(mode=mode)


def available_modes(backend):
    """What each connected monitor offers, for the plans that name a mode."""
    return {o['name']: o['modes'] for o in display_inventory(backend.runner) if o['connected']}


def displays_normalize(args):
    """Apply one edit (or a move) to a draft plan and return it normalised."""
    from display_layout import normalize, move, fill_modes
    # A display just switched on still says 0x0: give it a mode before it is laid out.
    plan = fill_modes(args['plan'], available_modes(env()))
    if args.get('move'):
        plan = move(plan, args['move']['name'], args['move']['direction'])
    else:
        plan = normalize(plan)
    return layout_view(plan)


def displays_try(args):
    from display_layout import fill_modes
    backend = env()
    trial = DisplayTrial(backend, fill_modes(args['plan'], available_modes(backend)))
    return dict(folder=str(trial.folder))


def displays_settle(args):
    trial = DisplayTrial.resume(env(), args['folder'])
    if args['accept']:
        if (trial.folder/'reverted').exists():
            raise ValueError('This display trial expired or was reverted. Test the layout again.')
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
    inventory = sorted(display_inventory(backend.runner), key=lambda o: (o['y'], o['x'], o['name']))
    outputs = [o['name'] for o in inventory if o.get('enabled')]
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
        raise ValueError('Unknown workspace action.')
    return workspaces_state({})


ACTIONS = {
    'displays.widgets': displays_widgets,
    'displays.state': displays_state, 'displays.normalize': displays_normalize,
    'displays.try': displays_try, 'displays.settle': displays_settle,
    'workspaces.state': workspaces_state, 'workspaces.edit': workspaces_edit,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in ACTIONS:
        print(json.dumps(dict(ok=False, error='Unknown display action.')))
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
