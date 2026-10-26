#!/usr/bin/env python3
import os, subprocess, sys
from pathlib import Path
from wysun_core.instance import SingleInstance, send
from wysun_core import launch
endpoint=SingleInstance(f'orbit-{os.getuid()}').endpoint
mode=sys.argv[1] if len(sys.argv)>1 else 'toggle'
if mode in ('files', 'file-manager'):
    state=Path.home()/'.local/state';state.mkdir(parents=True,exist_ok=True)
    with (state/'orbit-files.log').open('a') as log:
        subprocess.Popen(launch.argv('wysun_files', *sys.argv[2:], python='/usr/bin/python3'), env=launch.environment(), stdout=log, stderr=log, start_new_session=True)
    sys.exit(0)
if mode in ('music','music-mini'):
    # music-mini: the shell's media widget with Wysun Music chosen; the app starts hidden if needed.
    route='background' if mode=='music-mini' else 'present'
    if not send(SingleInstance(f'orbit-music-app-{os.getuid()}').endpoint,route.encode(),timeout=.3):
        state=Path.home()/'.local/state';state.mkdir(parents=True,exist_ok=True)
        with (state/'orbit-music.log').open('a') as log:
            subprocess.Popen(launch.argv('wysun_music',*(['--background'] if mode=='music-mini' else []),python='/usr/bin/python3'),env=launch.environment(),stdout=log,stderr=log,start_new_session=True)
    if mode=='music-mini':
        shell=Path.home()/'.local/bin/wysun-shell'
        os.execv(str(shell),[str(shell),'media','Wysun Music'])
    sys.exit(0)
if mode in ('settings','network','processes','color','colors') or mode.startswith('settings-'):
    # These pages are shell widgets (Nexus); `wysun` asks the running shell to open them.
    wysun=Path.home()/'.local/bin/wysun'
    os.execv(str(wysun),[str(wysun),mode]+sys.argv[2:])
if not send(endpoint,mode.encode(),timeout=.3):
    state=Path.home()/'.local/state';state.mkdir(parents=True,exist_ok=True)
    with (state/'orbit.log').open('a') as log:
        start_mode='daemon' if mode=='reload' else mode
        subprocess.Popen(launch.argv('wysun_services.daemon',start_mode,*(['--daemon'] if start_mode=='daemon' else []),python='/usr/bin/python3'),env=launch.environment(),stdout=log,stderr=log,start_new_session=True)
