#!/usr/bin/env python3
"""Restore confirmed preferences at login; independently guard display trials."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from environment_settings import EnvironmentSettings, display_inventory, display_command, profile_key, restore_display, render_wallpaper, run, read_json, trial_lock
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
    session=os.environ.get('XDG_SESSION_ID')
    if not session:
        pid=run(['pgrep','-u',str(os.getuid()),'-x','bspwm']).splitlines()[0]
        session=pid+'-'+Path('/proc',pid,'stat').read_text().split()[21]
    import hashlib
    marker=runtime/hashlib.sha256(session.encode()).hexdigest()
    with trial_lock(runtime):
        if marker.exists():return
        for entry in entries:
            try:subprocess.run(['gio','launch',entry['path']],capture_output=True,text=True,timeout=8,check=True)
            except Exception as exc:print('Inicio:',entry['name'],str(exc),file=sys.stderr)
        atomic_write(marker,'ok')

def restore_workspaces(backend):
    for monitor,names in backend.section('workspaces').items():
        try:
            rows=[r for r in backend.workspaces() if r['monitor']==monitor]
            if not rows:continue
            for i,name in enumerate(names):
                backend.runner(['bspc','desktop',rows[i]['id'],'-n',name] if i<len(rows) else ['bspc','monitor',monitor,'-a',name])
            # Startup defaults can contain more desktops than the saved layout.
            # Never remove one holding windows after a WM restart.
            for row in rows[len(names):]:
                latest=next((r for r in backend.workspaces() if r['id']==row['id']),None)
                if latest and not latest['windows'] and names:backend.runner(['bspc','desktop',row['id'],'-r'])
        except Exception as exc:print('Escritorios:',str(exc),file=sys.stderr)

def restore(preserve_workspaces=False):
    backend=EnvironmentSettings()
    if not backend.data:return
    inventory=display_inventory()
    plan=backend.section('displays').get('profiles',{}).get(profile_key(inventory))
    if plan:
        try:run(display_command(plan,inventory))
        except Exception as exc:print('Pantallas:',str(exc),file=sys.stderr)
    if not preserve_workspaces:restore_workspaces(backend)
    if backend.section('wallpaper').get('default'):
        try:render_wallpaper(backend.wallpaper_values(),display_inventory())
        except Exception as exc:print('Fondo:',str(exc),file=sys.stderr)
    if plan or backend.section('bar'):
        run([str(Path(__file__).with_name('desktop-bar'))])
    start_applications(backend)

if __name__=='__main__':
    if len(sys.argv)>2 and sys.argv[1]=='guard':guard(sys.argv[2])
    elif len(sys.argv)>=2 and sys.argv[1]=='restore':restore('--preserve-workspaces' in sys.argv[2:])
