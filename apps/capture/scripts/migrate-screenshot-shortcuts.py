#!/usr/bin/env python3
"""Replace only the four existing Flameshot region bindings, with exact rollback."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time

spec=importlib.util.spec_from_file_location('shot_install',Path(__file__).with_name('install-screenshot.py'))
install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)
TARGETS={'super + shift + s','super + shift + q','super + shift + a','Print'}


def expand(text):
    match=re.search(r'(?<!\\)\{([^{}]*)\}',text)
    if not match:return [text]
    result=[]
    for item in match[1].split(','):
        values=[''] if item=='_' else [item]
        if re.fullmatch('[A-Za-z0-9]-[A-Za-z0-9]',item):values=[chr(n) for n in range(ord(item[0]),ord(item[2])+1)]
        for value in values:result.extend(expand(text[:match.start()]+value+text[match.end():]))
    return result


def normalize(chord):return tuple(sorted(p.strip().lower().replace('control','ctrl') for p in chord.split('+')))


def rewrite(text):
    lines=text.splitlines(keepends=True);changed=[]
    keys=[]
    for line in text.replace('\\\n','').splitlines():
        if line and not line[0].isspace() and not line.startswith(('#',r'\t')):
            keys.extend(expand(line.strip()))
    for target in TARGETS:
        if sum(normalize(k)==normalize(target) for k in keys)!=1:raise ValueError('Missing/duplicate/conflicting chord: '+target)
    for index,line in enumerate(lines):
        if 'flameshot' not in line or line.lstrip().startswith('#'):continue
        content=line.strip().removeprefix(r'\t')
        args=shlex.split(content)
        if not args or args[0]!='flameshot':raise ValueError('Unknown Flameshot wrapper; inspect manually')
        chord=lines[index-1].strip()
        if chord not in TARGETS:raise ValueError('Unexpected Flameshot binding: '+chord)
        command='"$HOME/.local/bin/wybie-screenshot" --region --delay 0'
        if args==['flameshot','gui']:pass
        elif len(args)==6 and args[:4]==['flameshot','gui','-s','-p'] and args[-1]=='-c':
            folder=args[4]
            if not re.fullmatch(r'~/[A-Za-z0-9/._-]+',folder):raise ValueError('Inspect capture path before shell migration')
            command+=' --accept-on-select --clipboard --path "$HOME/'+folder[2:]+'"'
        else:raise ValueError('Unsupported Flameshot action; preserve its semantics explicitly')
        subprocess.run(['/usr/bin/zsh','-n','-c',command],check=True,capture_output=True)
        lines[index]='    '+command+('\n' if line.endswith('\n') else '')
        changed.append({'chord':chord,'before':content,'after':command})
    if len(changed)!=4:raise ValueError('Expected exactly four existing Flameshot stanzas')
    return ''.join(lines),changed


def reload(active):
    pids=subprocess.check_output(['pgrep','-u',str(os.getuid()),'-x','sxhkd'],text=True).split()
    if len(pids)!=1:raise ValueError('Expected exactly one SXHKD; no reload')
    pid=int(pids[0]);args=[p.decode() for p in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if p]
    # This migration was audited only with the default config and no extra includes.
    if len(args)!=1:raise ValueError('SXHKD arguments changed; inspect configs before reload')
    default=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'sxhkd/sxhkdrc'
    if active.resolve()!=default.resolve():raise ValueError('Active config mismatch')
    os.kill(pid,signal.SIGUSR1)
    return pid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--active',type=Path,default=Path.home()/'.config/sxhkd/sxhkdrc')
    parser.add_argument('--source',type=Path,default=Path.home()/'dotifails/home/.config/sxhkd/sxhkdrc')
    parser.add_argument('--apply',action='store_true');parser.add_argument('--restore',type=Path)
    args=parser.parse_args()
    if args.restore:
        record=json.loads((args.restore/'manifest.json').read_text())
        for item in record['files']:
            path=Path(item['path'])
            if path.is_symlink() or install.digest(path.read_bytes())!=item['after_sha256']:raise ValueError('Changed config; preserve and restore manually: '+str(path))
            data=(args.restore/item['backup']).read_bytes()
            if install.digest(data)!=item['before_sha256']:raise ValueError('Backup integrity failure')
        for item in record['files']:install.write(Path(item['path']),(args.restore/item['backup']).read_bytes(),item['mode'])
        print(json.dumps({'restored':True,'reloaded_pid':reload(Path(record['active']))}));return
    prepared=[]
    for label,path in (('active',args.active),('source',args.source)):
        if path.is_symlink():raise ValueError('Refusing symlink configuration')
        before=path.read_bytes();after,changes=rewrite(before.decode())
        prepared.append((label,path,before,after.encode(),changes,path.stat().st_mode&0o777))
    result={'dry_run':not args.apply,'changes':{label:changes for label,path,before,after,changes,mode in prepared}}
    if not args.apply:print(json.dumps(result,indent=2));return
    base=Path(os.environ.get('XDG_STATE_HOME',Path.home()/'.local/state'))/'wybie-screenshot'/('shortcuts-'+str(time.time_ns()))
    base.mkdir(parents=True,mode=0o700)
    records=[]
    for label,path,before,after,changes,mode in prepared:
        install.write(base/(label+'.before'),before,0o600)
        records.append({'path':str(path.absolute()),'backup':label+'.before','before_sha256':install.digest(before),'after_sha256':install.digest(after),'mode':mode})
    install.write(base/'manifest.json',json.dumps({'active':str(args.active.absolute()),'files':records},indent=2).encode(),0o600)
    for label,path,before,after,changes,mode in prepared:
        if path.read_bytes()!=before:raise ValueError('Concurrent config change; no overwrite: '+str(path))
    for label,path,before,after,changes,mode in prepared:install.write(path,after,mode)
    result.update(backup=str(base),reloaded_pid=reload(args.active))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
