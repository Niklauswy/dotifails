#!/usr/bin/env python3
"""Restore confirmed Hyprland preferences at login; independently guard display trials."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from environment_settings import EnvironmentSettings, display_inventory, display_command, display_plan, profile_key, restore_display, render_wallpaper, run, read_json, trial_lock
from settings_data import atomic_write

def guard(folder,runner=run):
    folder=Path(folder)
    while True:
        if (folder/'accepted').exists() or (folder/'reverted').exists():return
        with trial_lock(folder):
            trial=read_json(folder/'trial.json')
            if time.time()>=trial['deadline']:
                if (folder/'accepted').exists() or (folder/'reverted').exists():return
                try:
                    restore_display(trial['old'],runner)
                    atomic_write(folder/'reverted','ok')
                except Exception as exc:
                    atomic_write(folder/'error',str(exc))
                return
        time.sleep(.1)

def start_applications(backend):
    entries=[r for r in backend.autostart_entries() if r['managed'] and r['enabled']]
    if not entries:return
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR',str(backend.home/'.cache')))/'orbit-settings-startup'
    runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
    session=os.environ.get('XDG_SESSION_ID') or os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') or os.environ.get('WAYLAND_DISPLAY')
    if not session:return
    import hashlib
    marker=runtime/hashlib.sha256(session.encode()).hexdigest()
    with trial_lock(runtime):
        if marker.exists():return
        for entry in entries:
            try:subprocess.run(['gio','launch',entry['path']],capture_output=True,text=True,timeout=8,check=True)
            except Exception as exc:print('Inicio:',entry['name'],str(exc),file=sys.stderr)
        atomic_write(marker,'ok')

def restore_workspaces(backend):
    """Login/hotplug: regenerate hypr-workspaces.lua and pin it live.

    The saved layout wins; without one the automatic 1-5 / 6-9 / 10 layout for
    the outputs connected now is used and only the generated fragment is
    written, never environment.json. Persistent rules only place empty
    workspaces and move an existing one (with its windows) to its output.
    """
    import fcntl
    import workspace_layout as layouts
    try:
        outputs=display_inventory(backend.runner)
        if not any(o.get('enabled',True) for o in outputs):return
        backend.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        # Serialize with Ajustes and with several monitor.added events at login.
        with (backend.path.parent/'environment.lock').open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            backend.reload()
            mapping=backend.effective_workspace_layout(outputs)
            if not mapping:return
            text=layouts.lua_fragment(mapping)
            path=backend.config/'orbit/hypr-workspaces.lua'
            if not path.is_file() or path.read_text()!=text:atomic_write(path,text)
            backend.runner(['hyprctl','eval',layouts.live_script(mapping,{})])
    except Exception as exc:print('Escritorios:',str(exc),file=sys.stderr)

def revive_displays(backend,inventory):
    """Every connected screen is off: switch them all on, so a saved rule can never leave a black desktop.

    This happens when the arrangement saved for other company (say, the laptop panel turned off while
    two monitors were plugged in) is the only rule left and the monitors are no longer there.
    """
    from display_layout import fill_modes,monitors_fragment,normalize
    connected=[o for o in inventory if o['connected']]
    if not connected or any(o['enabled'] for o in connected):return False
    plan=display_plan(inventory)
    for p in plan:p['enabled']=True
    plan=normalize(fill_modes(plan,{o['name']:o['modes'] for o in connected}))
    plan[0]['primary']=True
    backend.runner(display_command(plan,inventory))
    atomic_write(backend.config/'orbit/hypr-monitors.lua',monitors_fragment(plan))
    return True

def restore_displays(backend):
    """Login/hotplug: apply the arrangement confirmed for these screens.

    The matching profile is applied live and written to hypr-monitors.lua so a
    later config reload keeps it. Without a confirmed profile nothing changes.
    """
    from display_layout import monitors_fragment,normalize
    try:
        inventory=display_inventory(backend.runner)
        backend.reload()
        plan=backend.section('displays').get('profiles',{}).get(profile_key(inventory))
        if not plan:return revive_displays(backend,inventory)
        plan=normalize(plan)
        current={p['name']:p for p in display_plan(inventory)}
        wanted={p['name']:p for p in plan}
        path=backend.config/'orbit/hypr-monitors.lua';text=monitors_fragment(plan)
        if not path.is_file() or path.read_text()!=text:atomic_write(path,text)
        keys=('enabled','mode','rate','rotation','x','y')
        if any(current.get(n,{}).get(k)!=wanted[n].get(k) for n in wanted for k in keys):
            backend.runner(display_command(plan,inventory))
        return True
    except Exception as exc:print('Pantallas:',str(exc),file=sys.stderr);return False

def restore(preserve_workspaces=False):
    backend=EnvironmentSettings()
    if (backend.home/'.config/orbit/theme.json').exists():
        try:
            from theme_runtime import restore_theme
            restore_theme(backend.home)
        except Exception as exc:print('Tema:',str(exc),file=sys.stderr)
    if not backend.data:return
    inventory=display_inventory()
    plan=backend.section('displays').get('profiles',{}).get(profile_key(inventory))
    if plan:
        try:run(display_command(plan,inventory))
        except Exception as exc:print('Pantallas:',str(exc),file=sys.stderr)
    else:
        try:revive_displays(backend,inventory)
        except Exception as exc:print('Pantallas:',str(exc),file=sys.stderr)
    # Run after the display profile: the compositor may have reordered monitors.
    restore_workspaces(backend)
    if backend.section('wallpaper').get('default'):
        try:render_wallpaper(backend.wallpaper_values(),display_inventory())
        except Exception as exc:print('Fondo:',str(exc),file=sys.stderr)
    start_applications(backend)

if __name__=='__main__':
    if len(sys.argv)>2 and sys.argv[1]=='guard':guard(sys.argv[2])
    elif len(sys.argv)>=2 and sys.argv[1]=='restore':restore('--preserve-workspaces' in sys.argv[2:])
    elif sys.argv[1:]==['workspaces']:
        # Screens first: the automatic workspace split follows their order.
        backend=EnvironmentSettings();restore_displays(backend);restore_workspaces(backend)
