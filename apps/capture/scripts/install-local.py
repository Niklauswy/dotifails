#!/usr/bin/env python3
"""Reproducible user-local install; owned-file manifest, no package/desktop mutations."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def dependencies():
    commands = ['ffmpeg','ffprobe','mpv','pactl','xrandr','xdpyinfo','xwininfo']
    result = {name: bool(shutil.which(name)) for name in commands}
    result['PySide6'] = importlib.util.find_spec('PySide6') is not None
    result['Python>=3.11'] = sys.version_info >= (3,11)
    if result['ffmpeg']:
        encoders = subprocess.check_output(['ffmpeg','-hide_banner','-encoders'],stderr=subprocess.DEVNULL,text=True)
        result['libx264'] = 'libx264 ' in encoders
        result['aac'] = ' aac ' in encoders
    return result


def digest(data): return hashlib.sha256(data).hexdigest()


def active_bundle_paths():
    """Read only recorder Python import roots; never inspect recording media."""
    roots=set()
    for process in Path('/proc').glob('[0-9]*'):
        try:
            args=(process/'cmdline').read_bytes().split(b'\0')
            if not any(name in args for name in (b'loomrec',b'loomrec.worker')):continue
            if process.stat().st_uid!=os.getuid():continue
            env=(process/'environ').read_bytes().split(b'\0')
            paths=next((v.split(b'=',1)[1].decode().split(os.pathsep) for v in env if v.startswith(b'PYTHONPATH=')),[])
            roots.update(Path(value).resolve() for value in paths if value)
            roots.add((process/'cwd').resolve())
        except (OSError,UnicodeError):continue
    return roots


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.loom-install-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(name,mode);os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


class Installer:
    def __init__(self,source,data_home,bin_home,python=sys.executable):
        self.source=Path(source).resolve()
        self.data=Path(data_home).absolute()
        self.bin=Path(bin_home).absolute()
        self.base=self.data/'loomrec'
        self.manifest=self.base/'install-manifest.json'
        self.python=str(Path(python).resolve())

    def path(self,key):
        special={'launcher':self.bin/'loomrec','desktop':self.data/'applications'/'loomrec.desktop',
                 'icon':self.data/'icons'/'hicolor'/'scalable'/'apps'/'loomrec.svg'}
        if key in special:return special[key]
        part=Path(key)
        if not key.startswith(('app/','bundles/')) or part.is_absolute() or '..' in part.parts:
            raise ValueError('Invalid install manifest path')
        return self.base/part

    def prior(self):
        if not self.manifest.exists():return {}
        data=json.loads(self.manifest.read_text())
        if data.get('version')!=1:raise ValueError('Unsupported install manifest')
        return data['files']

    def payload(self):
        if not (self.source/'loomrec'/'__main__.py').is_file():raise ValueError('Source tree missing loomrec')
        result={}
        for path in sorted((self.source/'loomrec').rglob('*.py')):
            if path.is_symlink():raise ValueError('Refusing symlinked source file')
            result['app/'+path.relative_to(self.source).as_posix()]=(path.read_bytes(),0o644)
        for path in sorted((self.source/'scripts').glob('*.py')):
            if path.is_symlink():raise ValueError('Refusing symlinked installer source')
            result['app/scripts/'+path.name]=(path.read_bytes(),0o644)
        for name in ['README.md','AGENTS.md','pyproject.toml']:
            if (self.source/name).is_file():result['app/'+name]=((self.source/name).read_bytes(),0o644)
        bundle=digest(b''.join(key.encode()+b'\0'+value[0] for key,value in sorted(result.items())))[:20]
        prefix='bundles/'+bundle
        result={prefix+key[3:]:value for key,value in result.items()}
        app=self.base/prefix
        launcher=f'#!/bin/sh\nunset __PYVENV_LAUNCHER__\nexport PYTHONDONTWRITEBYTECODE=1\nexport PYTHONPATH={shlex.quote(str(app))}\nexec {shlex.quote(self.python)} -P -m loomrec "$@"\n'
        result['launcher']=(launcher.encode(),0o755)
        command=str(self.path('launcher')).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')
        desktop=f'[Desktop Entry]\nType=Application\nName=Wysun Recorder\nName[es]=Wysun Recorder\nComment=Record and edit locally\nExec="{command}"\nIcon=loomrec\nTerminal=false\nCategories=AudioVideo;Recorder;\nStartupNotify=true\n'
        result['desktop']=(desktop.encode(),0o644)
        icon='<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#19242d"/><circle cx="32" cy="32" r="18" fill="#dc695b"/><circle cx="32" cy="32" r="7" fill="#f5f0df"/></svg>\n'
        result['icon']=(icon.encode(),0o644)
        return result

    def safe_path(self,path):
        # Never follow an existing target/parent symlink during install or uninstall.
        for parent in [path,*path.parents]:
            if parent.is_symlink():raise ValueError(f'Refusing symlinked install path: {parent}')

    def install(self):
        previous=self.prior();payload=self.payload()
        for key in payload:
            path=self.path(key);self.safe_path(path)
            if path.exists() and (key not in previous or digest(path.read_bytes())!=previous[key]):
                raise FileExistsError(f'Preserving unrelated or modified file: {path}')
        backup={key:(self.path(key).read_bytes(),self.path(key).stat().st_mode & 0o777) if self.path(key).exists() else None for key in payload}
        try:
            for key,(data,mode) in payload.items():
                path=self.path(key)
                if not path.exists() or path.read_bytes()!=data:atomic_write(path,data,mode)
            manifest={'version':1,'files':{**previous,**{key:digest(value[0]) for key,value in payload.items()}}}
            self.safe_path(self.manifest)
            atomic_write(self.manifest,json.dumps(manifest,indent=2).encode(),0o600)
        except Exception:
            for key,value in backup.items():
                if value is None:self.path(key).unlink(missing_ok=True)
                else:atomic_write(self.path(key),*value)
            raise
        return {'installed':len(payload),'launcher':str(self.path('launcher')),'desktop':str(self.path('desktop')),'source':str(self.source)}

    def uninstall(self):
        previous=self.prior();preserved={};removed=[];active=active_bundle_paths();active_preserved=[]
        material_result=None
        helper_path=Path(__file__).with_name('restore-materials.py')
        if helper_path.exists() and self.data==Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share'))).absolute():
            spec=importlib.util.spec_from_file_location('loom_material_restore',helper_path)
            helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
            try:material_result=helper.restore()
            except (OSError,ValueError,KeyError) as exc:material_result={'restored':False,'preserved':str(exc)}
        shortcut_result=None
        shortcut_state=self.base/'shortcut.json'
        if shortcut_state.exists():
            spec=importlib.util.spec_from_file_location('loom_shortcut',Path(__file__).with_name('desktop-shortcut.py'))
            helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
            record=json.loads(shortcut_state.read_text())
            shortcut_result=helper.uninstall(shortcut_state)
            try:shortcut_result.update(helper.reload_verified(record['config']))
            except Exception as exc:shortcut_result['reload_notice']=str(exc)
        for key,sha in previous.items():
            path=self.path(key);self.safe_path(path)
            if not path.exists():continue
            if key.startswith(('app/','bundles/')) and any(path.is_relative_to(root) for root in active):
                preserved[key]=sha;active_preserved.append(str(path));continue
            if digest(path.read_bytes())!=sha:
                preserved[key]=sha;continue
            path.unlink();removed.append(str(path))
        if preserved:atomic_write(self.manifest,json.dumps({'version':1,'files':preserved},indent=2).encode(),0o600)
        else:self.manifest.unlink(missing_ok=True)
        # Only remove empty app directories, never recordings/settings or their parents.
        app=self.base/'app'
        if app.exists():
            for directory in sorted((p for p in app.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
                try:directory.rmdir()
                except OSError:pass
            try:app.rmdir()
            except OSError:pass
        return {'removed':len(removed),'preserved_modified':[str(self.path(k)) for k in preserved],
                'preserved_active_files':active_preserved,
                'recordings_preserved':str(self.base/'recordings'),'shortcut':shortcut_result,'materials':material_result}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--data-home',default=os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))
    parser.add_argument('--bin-home',default=str(Path.home()/'.local/bin'))
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--uninstall',action='store_true')
    args=parser.parse_args()
    if args.check:
        result=dependencies();print(json.dumps(result,indent=2));return 0 if all(result.values()) else 1
    installer=Installer(args.source,args.data_home,args.bin_home)
    if args.uninstall:result=installer.uninstall()
    else:
        missing=[k for k,v in dependencies().items() if not v]
        if missing:raise RuntimeError('Missing dependencies (nothing installed): '+', '.join(missing))
        result=installer.install()
    print(json.dumps(result,indent=2));return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
