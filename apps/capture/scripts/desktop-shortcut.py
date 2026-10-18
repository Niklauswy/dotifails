#!/usr/bin/env python3
"""One conflict-checked launch binding; preserves all existing sxhkd content."""
import argparse,json,os,re,shlex,signal,subprocess,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from loomrec.integration import shortcut_conflicts

BEGIN='# BEGIN LOOMREC MANAGED LAUNCH SHORTCUT'
END='# END LOOMREC MANAGED LAUNCH SHORTCUT'


def write(path,text,mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.loom-shortcut-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.chmod(name,mode);os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def install(config,state,launcher,chord='super + shift + l'):
    config,state,launcher=Path(config),Path(state),Path(launcher).resolve()
    if config.is_symlink():raise ValueError('Refusing to replace symlinked sxhkd configuration')
    if not launcher.is_file() or not os.access(launcher,os.X_OK):raise ValueError('Install the Wysun Recorder launcher first')
    if not re.fullmatch(r'(?:super|ctrl|shift|alt)(?:\s*\+\s*(?:super|ctrl|shift|alt))*\s*\+\s*[a-z]',chord):
        raise ValueError('Use modifier keys plus one letter; reserved VT keys are not supported')
    old=config.read_text() if config.exists() else ''
    prior=None
    clean=old
    if state.exists():
        prior=json.loads(state.read_text())
        if prior['config']!=str(config.resolve()) or old.count(prior['block'])!=1:
            raise ValueError('Managed shortcut was modified; preserving configuration')
        if prior['chord']==chord and shlex.quote(str(launcher))+' --quick-record' in prior['block']:
            return {'installed':False,'already_present':True}
        clean=old.replace(prior['block'],'',1)
    if BEGIN in clean or shortcut_conflicts(clean,chord):raise ValueError('Shortcut conflicts with existing configuration')
    block=f'\n{BEGIN}\n{chord}\n    {shlex.quote(str(launcher))} --quick-record\n{END}\n'
    backup=config.with_name(config.name+f'.loomrec-{time.time_ns()}.bak')
    mode=config.stat().st_mode & 0o777 if config.exists() else 0o600
    if config.exists():
        with backup.open('x') as f:f.write(old)
        os.chmod(backup,mode)
    if config.exists() and config.read_text()!=old:raise RuntimeError('Configuration changed concurrently; no change made')
    record={'version':1,'config':str(config.resolve()),'block':block,'backup':str(backup),'chord':chord}
    write(state,json.dumps(record,indent=2))
    try:write(config,clean+block,mode)
    except Exception:
        if prior:write(state,json.dumps(prior,indent=2))
        else:state.unlink(missing_ok=True)
        raise
    return {'installed':True,'chord':chord,'backup':str(backup)}


def uninstall(state):
    state=Path(state)
    if not state.exists():return {'removed':False}
    record=json.loads(state.read_text());config=Path(record['config']);block=record['block']
    if config.is_symlink():raise ValueError('Configuration became a symlink; preserving it')
    old=config.read_text()
    if old.count(block)!=1:raise ValueError('Managed block was modified; preserving configuration for manual review')
    write(config,old.replace(block,'',1),config.stat().st_mode & 0o777)
    state.unlink()
    return {'removed':True,'config':str(config),'backup_preserved':record['backup']}


def reload_verified(config):
    result=subprocess.run(['pgrep','-u',str(os.getuid()),'-x','sxhkd'],capture_output=True,text=True)
    pids=result.stdout.split()
    if len(pids)!=1:raise RuntimeError('Expected exactly one current-user sxhkd process; configuration saved but not reloaded')
    pid=int(pids[0]);args=Path(f'/proc/{pid}/cmdline').read_bytes().decode().split('\0')
    default=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'sxhkd/sxhkdrc'
    active=Path(args[args.index('-c')+1]) if '-c' in args else default
    if active.resolve()!=Path(config).resolve():raise RuntimeError('Running sxhkd uses another config; not reloaded')
    # Parse validation is deliberately restricted to our generated four-line stanza;
    # no rewriting/reformatting of the pre-existing user configuration occurs.
    os.kill(pid,signal.SIGUSR1)
    return {'reloaded_pid':pid}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'sxhkd/sxhkdrc'))
    parser.add_argument('--state',default=str(Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'loomrec/shortcut.json'))
    parser.add_argument('--launcher',default=str(Path.home()/'.local/bin/loomrec'))
    parser.add_argument('--chord',default='super + shift + l')
    parser.add_argument('--uninstall',action='store_true');parser.add_argument('--reload',action='store_true')
    args=parser.parse_args()
    result=uninstall(args.state) if args.uninstall else install(args.config,args.state,args.launcher,args.chord)
    if args.reload:result.update(reload_verified(args.config))
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    try:main()
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
