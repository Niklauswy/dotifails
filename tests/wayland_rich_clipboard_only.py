#!/usr/bin/env python3
"""Repeat only rich clipboard after an unchanged Notes/Files flow already passed."""
import os
from pathlib import Path
import signal
import subprocess
import sys
from wayland_test_pointer import SyntheticPointer
ROOT=Path(os.environ['WYSUN_TEST_SOURCE'])
sys.path.insert(0,str(ROOT/'apps/quickshell/tests'))
from installed_apps_probe import private_environment,peer_pid,wait_for
from rich_clipboard_probe import run_rich_clipboard


def main():
    env,runtime,folder=private_environment();home=Path(env['HOME']);pid=None;pointer=SyntheticPointer(env)
    try:
        pointer.keyboard()
        subprocess.run(['/usr/bin/python3',str(ROOT/'installer/main.py'),'install','--source',str(ROOT),'--target-home',str(home),'--components','wayland','--config-only'],env=env,cwd='/',check=True,stdout=subprocess.DEVNULL,timeout=60)
        env['PATH']=str(home/'.local/bin')+':'+env['PATH']
        subprocess.run([str(home/'.local/bin/wysun'),'daemon'],env=env,cwd='/',check=True,timeout=15)
        endpoint=runtime/f'orbit-{os.getuid()}.sock';wait_for(endpoint.is_socket,'installed daemon for rich clipboard')
        pid=peer_pid(endpoint)
        if str(home/'.local/share/orbit/app/orbit.py').encode() not in Path(f'/proc/{pid}/cmdline').read_bytes():raise RuntimeError('Unexpected installed launcher peer')
        run_rich_clipboard(env,pid)
    finally:
        pointer.close()
        if pid:
            try:os.killpg(pid,signal.SIGTERM)
            except ProcessLookupError:pass

if __name__=='__main__':main()
