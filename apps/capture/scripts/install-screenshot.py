#!/usr/bin/env python3
"""Versioned screenshot-only user install; no desktop settings/Recorder mutation."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile


def digest(data):return hashlib.sha256(data).hexdigest()


def write(path,data,mode=0o644):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise ValueError('Refusing symlink destination: '+str(path))
    fd,tmp=tempfile.mkstemp(prefix='.wybieshot-install-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.chmod(tmp,mode);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

class Installer:
    def __init__(self,source,data_home,bin_home,python=sys.executable):
        self.source=Path(source).resolve();self.data=Path(data_home).absolute();self.bin=Path(bin_home).absolute()
        self.base=self.data/'wybie-screenshot';self.python=str(Path(python).resolve())
        self.manifest=self.base/'install-manifest.json'

    def payload(self):
        files={}
        # Snapshot shared UI modules read-only; no dependency on an installed Recorder.
        for package in ('wybieshot','loomrec'):
            for path in (self.source/package).rglob('*.py'):
                if '__pycache__' not in path.parts:files[str(path.relative_to(self.source))]=path.read_bytes()
        if 'wybieshot/ui/main.py' not in files:raise ValueError('Incomplete application: UI is not integrated')
        release=digest(b''.join(key.encode()+files[key] for key in sorted(files)))[:20]
        bundle=self.base/'releases'/release
        outputs={bundle/key:(value,0o644) for key,value in files.items()}
        launcher=('#!/bin/sh\nexport PYTHONPATH='+shlex.quote(str(bundle))+'\nexec '+shlex.quote(self.python)+' -m wybieshot "$@"\n').encode()
        executable=self.bin/'wybie-screenshot'
        icon=self.data/'icons/hicolor/scalable/apps/wybie-screenshot.svg'
        if any(c in str(executable) for c in ('\n','\r','%','"','`','$','\\')):raise ValueError('Unsupported desktop launcher path')
        desktop=('[Desktop Entry]\nType=Application\nName=Wysun Screenshot\nComment=Captura, anota y compone imágenes localmente\nExec="'+str(executable)+'"\nIcon=wybie-screenshot\nTerminal=false\nCategories=Graphics;Photography;\nStartupWMClass=wybie-screenshot\n').encode()
        outputs[executable]=(launcher,0o755)
        outputs[self.data/'applications/wybie-screenshot.desktop']=(desktop,0o644)
        outputs[icon]=((self.source/'assets/wybie-screenshot.svg').read_bytes(),0o644)
        return release,outputs

    def install(self,dry_run=False):
        release,outputs=self.payload()
        previous={}
        if self.manifest.is_symlink():raise ValueError('Symlinked install manifest')
        if self.manifest.exists():previous=json.loads(self.manifest.read_text()).get('files',{})
        conflicts=[]
        for path,(data,mode) in outputs.items():
            if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Symlinked install path: '+str(path))
            if path.exists() and digest(path.read_bytes()) not in (digest(data),previous.get(str(path))):conflicts.append(str(path))
        if conflicts:raise ValueError('Preserving modified files: '+', '.join(conflicts))
        result={'release':release,'files':len(outputs),'dry_run':dry_run,'launcher':str(self.bin/'wybie-screenshot')}
        if dry_run:return result
        for path,(data,mode) in outputs.items():write(path,data,mode)
        write(self.manifest,json.dumps({'version':1,'release':release,'files':{str(p):digest(d) for p,(d,m) in outputs.items()}},indent=2).encode(),0o600)
        return result

    def uninstall(self,dry_run=False):
        if self.manifest.is_symlink():raise ValueError('Symlinked install manifest')
        data=json.loads(self.manifest.read_text());removed=[];preserved=[]
        for name,expected in data['files'].items():
            path=Path(name)
            # A tampered manifest must never delete unrelated locations.
            allowed=(path==self.bin/'wybie-screenshot' or path==self.data/'applications/wybie-screenshot.desktop' or path==self.data/'icons/hicolor/scalable/apps/wybie-screenshot.svg' or path.is_relative_to(self.base/'releases'))
            if not allowed:raise ValueError('Unmanaged manifest path')
            if not path.exists() and not path.is_symlink():continue
            if any(p.is_symlink() for p in (path,*path.parents)) or not path.is_file() or digest(path.read_bytes())!=expected:preserved.append(str(path));continue
            removed.append(str(path))
        if not dry_run:
            for path in removed:Path(path).unlink()
            if not preserved:self.manifest.unlink()
        return {'removed':removed,'preserved':preserved,'sessions_preserved':str(self.base/'sessions'),'dry_run':dry_run}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true');parser.add_argument('--uninstall',action='store_true')
    parser.add_argument('--data-home',type=Path,default=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share')))
    parser.add_argument('--bin-home',type=Path,default=Path.home()/'.local/bin')
    args=parser.parse_args()
    if not args.uninstall and importlib.util.find_spec('PySide6') is None:parser.error('PySide6 >=6.8 is required; no dependencies installed implicitly')
    installer=Installer(Path(__file__).resolve().parents[1],args.data_home,args.bin_home)
    print(json.dumps(installer.uninstall(args.dry_run) if args.uninstall else installer.install(args.dry_run),indent=2))

if __name__=='__main__':main()
