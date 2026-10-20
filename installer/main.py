#!/usr/bin/env python3
"""Reproducible desktop deployment with a write-ahead backup journal."""
import argparse,datetime,fcntl,hashlib,json,os,platform,shutil,stat,subprocess,sys,tarfile,tempfile,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_model import ARTIFACTS, COMPONENTS, InstallOptions, normalize_components, package_names
from install_events import InstallationCancelled, checkpoint, emit

VERSION='1.1.0'
REPOSITORY='https://github.com/Niklauswy/dotifails.git'
WYSUN_DESKTOP='[Desktop Entry]\nType=Application\nName=Wysun\nComment=Aplicaciones y herramientas del escritorio\nExec=wysun\nIcon=system-search\nCategories=Utility;\nKeywords=Wysun;lanzador;launcher;aplicaciones;\nStartupWMClass=Orbit\n'
EXTRAS={'brave':'com.brave.Browser','discord':'com.discordapp.Discord','obsidian':'md.obsidian.Obsidian'}


def read(path,default=None):
    try:return json.loads(Path(path).read_text())
    except FileNotFoundError:return default


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    with tmp.open('x') as f:
        os.chmod(tmp,0o600);json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    tmp.replace(path)


def exists(path):return path.exists() or path.is_symlink()


def fingerprint(path):
    path=Path(path)
    if not exists(path):return None
    h=hashlib.sha256()
    def visit(p):
        h.update(str(p.relative_to(path)).encode());h.update(str(stat.S_IMODE(p.lstat().st_mode)).encode())
        if p.is_symlink():h.update(b'L'+os.readlink(p).encode())
        elif p.is_dir():
            h.update(b'D')
            for child in sorted(p.iterdir()):
                if child.name not in ('__pycache__','.git') and child.suffix!='.pyc':visit(child)
        elif p.is_file():
            h.update(b'F')
            with p.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        else:raise RuntimeError(f'Archivo especial no admitido: {p}')
    visit(path);return h.hexdigest()


def remove(path):
    if path.is_symlink() or path.is_file():path.unlink()
    elif path.is_dir():shutil.rmtree(path)


def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.is_symlink():target.symlink_to(os.readlink(source))
    elif source.is_dir():shutil.copytree(source,target,symlinks=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
    else:shutil.copy2(source,target)


def run(argv,env=None):
    checkpoint()
    argv=list(map(str,argv))
    if argv and argv[0]=='sudo' and os.environ.get('DOTIFAILS_EVENTS')=='1':
        argv.insert(1,'-A')
    print('+ '+' '.join(map(str,argv)),flush=True)
    try:subprocess.run(argv,check=True,env=env)
    except subprocess.CalledProcessError:
        checkpoint()
        raise


def host_supported():
    fields={}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            k,v=line.split('=',1);fields[k]=v.strip('"')
    ident=fields.get('ID');major=fields.get('VERSION_ID','').split('.')[0]
    if platform.machine()!='x86_64' or not ((ident=='debian' and major=='13') or (ident=='parrot' and major=='7')):
        raise RuntimeError('Esta versión admite Parrot 7 y Debian 13 en x86_64.')
    return fields


class Deployment:
    def __init__(self,home,source):
        self.home=Path(home).absolute();self.source=Path(source).resolve();self.state=self.home/'.local/state/dotifails';self.data=self.home/'.local/share/dotifails';self.receipt=read(self.state/'installed.json',{'files':{}});self.journal=None;self.conflicts=[]
    def begin(self):
        checkpoint()
        for relative in ('.config/probe','.local/share/probe','.local/state/probe','.cache/probe'):
            self.destination(Path(relative))
        self.state.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.lock=(self.state/'install.lock').open('a');fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ident=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
        self.backup=self.state/'backups'/ident;self.backup.mkdir(parents=True,mode=0o700)
        write(self.backup/'installed-before.json',self.receipt)
        self.journal={'id':ident,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'running','version':VERSION,'operations':[],'stages':[]};self.flush()
        emit('backup',id=ident,path=str(self.backup))
        return ident
    def flush(self):write(self.backup/'journal.json',self.journal)
    def stage(self,name):
        checkpoint();self.journal['stages'].append(name);self.flush();print('\n→ '+name,flush=True);emit('operation',name=name)
    def destination(self,relative):
        rel=Path(relative)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('Destino fuera del hogar')
        dest=self.home/rel
        for parent in dest.parents:
            if parent==self.home:break
            if parent.is_symlink():raise RuntimeError(f'El directorio {parent} es un enlace; no se escribirá fuera del hogar.')
        return dest
    def deploy(self,source,relative):
        checkpoint()
        dest=self.destination(relative);key=str(relative);current=fingerprint(dest);wanted=fingerprint(source);previous=self.receipt['files'].get(key)
        if current==wanted:
            self.receipt['files'][key]=wanted;return
        if previous is not None and current!=previous:
            incoming=self.backup/'incoming'/relative;copy(source,incoming);self.conflicts.append(key);emit('conflict',path=key);return
        before=self.backup/'before'/relative
        if exists(dest):copy(dest,before)
        op={'path':key,'before':current,'after':wanted};self.journal['operations'].append(op);self.flush()
        temporary=dest.with_name('.'+dest.name+'.dotifails-'+uuid.uuid4().hex)
        copy(source,temporary)
        # Existing directories need a rename first. The durable journal can recover an interruption here.
        displaced=dest.with_name('.'+dest.name+'.previous-'+self.journal['id'])
        op['displaced']=str(displaced.relative_to(self.home));self.flush()
        if exists(dest):dest.rename(displaced)
        temporary.rename(dest)
        if exists(displaced):remove(displaced)
        self.receipt['files'][key]=wanted
        write(self.state/'installed.json',self.receipt)
    def retire(self,relative,private=False):
        checkpoint()
        dest=self.destination(relative);key=str(relative);current=fingerprint(dest)
        if current is None:
            self.receipt['files'].pop(key,None);return
        previous=self.receipt['files'].get(key)
        if not private and (previous is None or current!=previous):
            self.conflicts.append(key);return
        copy(dest,self.backup/'before'/relative)
        self.journal['operations'].append({'path':key,'before':current,'after':None})
        self.flush();remove(dest);self.receipt['files'].pop(key,None)
        write(self.state/'installed.json',self.receipt)
    def generated(self,text,relative,executable=False):
        temp=self.backup/'generated'/relative;temp.parent.mkdir(parents=True,exist_ok=True);temp.write_text(text);temp.chmod(0o755 if executable else 0o644);self.deploy(temp,relative)
    def configure_files(self):
        # The desktop profile owns folder opening, portal selection and reveal actions.
        self.deploy(self.source/'bin/orbit-files',Path('.local/bin/orbit-files'))
        self.deploy(self.source/'config/.local/share/applications/orbit-files.desktop',Path('.local/share/applications/orbit-files.desktop'))
        # Per-user activation is supported by xdg-desktop-portal >= 1.20.
        import configparser
        # Generate the association for target-home rather than running xdg-mime
        # against the installing user's home. This also participates in rollback.
        relative=Path('.config/mimeapps.list')
        mime=configparser.ConfigParser(interpolation=None);mime.optionxform=str
        existing=self.destination(relative)
        if existing.is_file():mime.read(existing)
        for section in ('Default Applications','Added Associations'):
            if not mime.has_section(section):mime.add_section(section)
        mime.set('Default Applications','inode/directory','orbit-files.desktop;')
        previous=mime.get('Added Associations','inode/directory',fallback='')
        alternatives=[name for name in previous.split(';') if name and name!='orbit-files.desktop']
        mime.set('Added Associations','inode/directory',';'.join(['orbit-files.desktop']+alternatives)+';')
        if mime.has_option('Removed Associations','inode/directory'):
            removed=[name for name in mime.get('Removed Associations','inode/directory').split(';') if name and name!='orbit-files.desktop']
            mime.set('Removed Associations','inode/directory',';'.join(removed)+(';' if removed else ''))
        import io
        output=io.StringIO();mime.write(output,space_around_delimiters=False);self.generated(output.getvalue(),relative)
        service='orbit-files-integration.service'
        command='/usr/bin/python3 "'+str(self.home/'.local/share/orbit/app/files_service.py')+'"'
        self.generated('[Unit]\nDescription=Wysun file chooser and file manager integration\nAfter=graphical-session-pre.target\n\n[Service]\nType=dbus\nBusName=org.freedesktop.impl.portal.desktop.orbit\nExecStart='+command+'\nRestart=on-failure\nTimeoutStopSec=5\n',Path('.config/systemd/user')/service)
        for name in ('org.freedesktop.impl.portal.desktop.orbit','org.freedesktop.FileManager1'):
            self.generated('[D-BUS Service]\nName='+name+'\nExec='+command+'\nSystemdService='+service+'\n',Path('.local/share/dbus-1/services')/(name+'.service'))
        self.generated('[portal]\nDBusName=org.freedesktop.impl.portal.desktop.orbit\nInterfaces=org.freedesktop.impl.portal.FileChooser;\nUseIn=Wysun;Hyprland;\n',Path('.local/share/xdg-desktop-portal/portals/orbit.portal'))
        relative=Path('.config/xdg-desktop-portal/portals.conf')
        parser=configparser.ConfigParser(interpolation=None);parser.optionxform=str
        existing=self.destination(relative)
        if existing.is_file():parser.read(existing)
        if not parser.has_section('preferred'):parser.add_section('preferred')
        if not parser.has_option('preferred','default'):parser.set('preferred','default','gtk;')
        parser.set('preferred','org.freedesktop.impl.portal.FileChooser','orbit;gtk;')
        import io
        output=io.StringIO();parser.write(output);self.generated(output.getvalue(),relative)
        self.generated('GTK_USE_PORTAL=1\n',Path('.config/environment.d/60-orbit-files.conf'))

    def configure_orbit(self):
        self.stage('Actualizar solo Wysun (código y lanzador)')
        self.deploy(self.source/'apps/wysun',Path('.local/share/orbit/app'))
        if (self.source/'apps/tools').is_dir():self.deploy(self.source/'apps/tools',Path('.local/share/orbit/tools'))
        if self.conflicts:return
        for theme in read(self.source/'manifests/themes.json',{}).values():
            wallpaper=self.source/'assets/backgrounds'/theme['wallpaper']
            if wallpaper.is_file():self.deploy(wallpaper,Path('.local/share/backgrounds')/wallpaper.name)
        self.deploy(self.source/'config/.local/bin/orbit',Path('.local/bin/orbit'))
        if 'wayland' not in self.receipt.get('components',[]):self.configure_files()
        if (self.source/'bin/musica').is_file():self.deploy(self.source/'bin/musica',Path('.local/bin/musica'))
        if (self.source/'bin/musika').is_file():self.deploy(self.source/'bin/musika',Path('.local/bin/musika'))
        if (self.source/'config/.local/share/icons/hicolor/scalable/apps/musika.svg').is_file():self.deploy(self.source/'config/.local/share/icons/hicolor/scalable/apps/musika.svg',Path('.local/share/icons/hicolor/scalable/apps/musika.svg'))
        if (self.source/'config/.local/share/applications/orbit-music.desktop').is_file():self.deploy(self.source/'config/.local/share/applications/orbit-music.desktop',Path('.local/share/applications/orbit-music.desktop'))
        self.configure_wysun()
        from wayland import update_runtime
        update_runtime(self)
    def configure_wysun(self):
        # Keep established paths and desktop IDs so pinned launchers and data survive.
        launcher=self.source/'bin/wysun'
        if not launcher.is_file():return
        from capture_distribution import _publish,configure
        if not _publish(self,launcher.read_text(),'.local/bin/wysun',executable=True):return
        for name,mode in (('wysun-music','music'),('wysun-files','files'),('wysun-tools','tools')):
            _publish(self,'#!/bin/sh\nexec "$HOME/.local/bin/wysun" '+mode+' "$@"\n','.local/bin/'+name,executable=True)
        self.generated(WYSUN_DESKTOP,Path('.local/share/applications/orbit.desktop'))
        for name in ('orbit-settings.desktop','orbit-connections.desktop'):
            source=self.source/'config/.local/share/applications'/name
            if source.is_file():self.deploy(source,Path('.local/share/applications')/name)
        configure(self)
    def configure_scripts(self):
        self.stage('Herramientas de Wysun y migración de lanzadores')
        self.deploy(self.source/'apps/tools',Path('.local/share/orbit/tools'))
        self.deploy(self.source/'bin/orbit-tools',Path('.local/bin/orbit-tools'))
        self.deploy(self.source/'bin/orbit-tools',Path('scripts/orbit-tools'))
        self.deploy(self.source/'docs/tools.md',Path('scripts/README.md'))
        aliases={'web-dev':'dev','sec-audit':'audit','file-share':'share','gvm':'cloud','gvm.sh':'cloud','tailscale-killswitch':'vpn','tailscale-killswitch.sh':'vpn','scrip.sh':'vpn','rezets':'resets','zzzz.py':'share'}
        for name,group in aliases.items():
            self.retire(Path('scripts')/name)
            if name=='zzzz.py':
                text='#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\ncli=Path(__file__).resolve().parent.parent/"share/orbit/tools/cli.py"\nos.execv(sys.executable,[sys.executable,str(cli),"share",*sys.argv[1:]])\n'
            else:
                text='#!/bin/sh\nbase=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$base/orbit-tools" '+group+' "$@"\n'
            self.generated(text,Path('.local/bin')/name,True)
        candidates=[self.home/'.config/dotifails/rezets/accounts.json',self.home/'scripts/.rezets/accounts.json']
        legacy=next((p for p in candidates if p.is_file()),candidates[-1])
        target=Path('.config/orbit/resets/accounts.json')
        if legacy.is_file() and not exists(self.destination(target)):
            payload=legacy.read_text()
            if not isinstance(json.loads(payload),list):raise RuntimeError('Cuentas antiguas inválidas; se conservaron.')
            stage=self.backup/'generated/private-accounts.json';stage.parent.mkdir(parents=True,exist_ok=True);stage.write_text(payload);stage.chmod(0o600)
            self.deploy(stage,target)
        if (self.home/'.config/dotifails/rezets').is_dir():self.retire(Path('.config/dotifails/rezets'),private=True)
        if (self.home/'scripts/.rezets').is_dir():self.retire(Path('scripts/.rezets'),private=True)
        uploads=self.home/'scripts/uploads';inbox=Path('.local/share/orbit/transfers/inbox')
        if uploads.is_dir() and not exists(self.destination(inbox)):
            self.deploy(uploads,inbox);self.retire(Path('scripts/uploads'),private=True)
        for relative in ('scripts/__pycache__','scripts/.codex'):
            dest=self.destination(relative)
            if dest.is_dir() or (dest.is_file() and dest.stat().st_size==0):self.retire(Path(relative),private=True)
        if '.local/share/dotifails/toolbox' in self.receipt['files']:
            self.retire(Path('.local/share/dotifails/toolbox'))
    def configure_manager(self):
        self.deploy(self.source/'installer',Path('.local/share/dotifails/installer'))
        self.deploy(self.source/'manifests',Path('.local/share/dotifails/manifests'))
        self.generated('#!/bin/sh\nexec python3 "$HOME/.local/share/dotifails/installer/main.py" "$@"\n',Path('.local/bin/dotifails'),True)
        self.generated('[Desktop Entry]\nType=Application\nName=Instalador de Wysun\nComment=Instalar, actualizar y recuperar tu escritorio\nExec=dotifails gui\nIcon=preferences-desktop\nCategories=System;Settings;\nTerminal=false\nStartupWMClass=dotifails-installer\n',Path('.local/share/applications/dotifails-installer.desktop'))

    def configure(self,profile=None,theme=None,components=None):
        selected=set(normalize_components(components))
        if 'wayland' in selected:
            from wayland import configure
            configure(self)
            if selected == {'wayland'}:
                self.configure_manager()
                return
        if 'tools' in selected:self.configure_scripts()
        self.stage('Configuraciones y aplicaciones')
        requested_theme=theme
        from install_model import installer_theme,theme_selection
        theme=theme_selection(theme) and installer_theme({'id':theme}) or installer_theme(read(self.home/'.config/orbit/theme.json',{}),self.receipt.get('theme') or 'severance')
        selection=theme_selection(theme)
        appearance=read(self.source/'manifests/themes.json')[theme]
        home_source=self.backup/'generated/theme-home'
        shutil.copytree(self.source/'config',home_source)
        if appearance.get('overlay'):
            shutil.copytree(self.source/appearance['overlay'],home_source,dirs_exist_ok=True)
        if (self.source/'apps/wysun/theme_runtime.py').exists():
            sys.path.insert(0,str(self.source/'apps/wysun'))
            from theme_runtime import theme_files
            themed,_=theme_files(home_source,selection)
            for path,text in themed.items():
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(text)
        owners={'nvim':'editor','ghostty':'terminal','fzf':'terminal','bat':'terminal','starship.toml':'terminal','dotifails':'terminal'}
        for base in ('.config','.local/bin'):
            for item in sorted((home_source/base).iterdir()):
                if base=='.config' and item.name=='wysun':continue
                if base=='.config' and item.name=='orbit':
                    # Theme generation creates this directory in the staging tree.
                    # Preferences are private runtime data; manage theme/environment
                    # below by file, never deploy or fingerprint the whole directory.
                    if 'desktop' in selected:self.receipt['files'].pop('.config/orbit',None)
                    continue
                if base=='.config' and item.name=='dotifails':
                    # Manage shared configuration by file; replacing the directory would
                    # overwrite the desktop profile during a terminal-only update.
                    for child in sorted(item.iterdir()):
                        # The selected theme is generated below, not copied from
                        # the template and then immediately overwritten again.
                        if child.name=='theme.json':continue
                        owner='terminal' if child.name=='mise.zsh' else 'desktop'
                        if owner not in selected:continue
                        relative=Path(base)/item.name/child.name
                        if '.config/dotifails' in self.receipt['files'] and str(relative) not in self.receipt['files'] and fingerprint(self.destination(relative))!=fingerprint(child):
                            copy(child,self.backup/'incoming'/relative);self.conflicts.append(str(relative));emit('conflict',path=str(relative));continue
                        self.deploy(child,relative)
                    continue
                if owners.get(item.name,'desktop') in selected:self.deploy(item,Path(base)/item.name)
        if 'terminal' in selected:self.deploy(self.source/'config/.zshrc',Path('.zshrc'))
        if 'desktop' in selected:
            self.deploy(self.source/'apps/wysun',Path('.local/share/orbit/app'))
            if '.local/share/orbit/app' not in self.conflicts:
                self.configure_files()
                self.configure_wysun()
            for item in sorted((self.source/'assets/icons').iterdir()):self.deploy(item,Path('.local/share/icons')/item.name)
            for item in sorted((self.source/'assets/backgrounds').iterdir()):self.deploy(item,Path('.local/share/backgrounds')/item.name)
            # Ship the same music entry points as an orbit-only update.
            for name in ('musica','musika'):
                if (self.source/'bin'/name).is_file():self.deploy(self.source/'bin'/name,Path('.local/bin')/name)
            for rel in ('.local/share/applications/orbit-music.desktop','.local/share/icons/hicolor/scalable/apps/musika.svg'):
                if (self.source/'config'/rel).is_file():self.deploy(self.source/'config'/rel,Path(rel))
        if selected & {'desktop','terminal'}:self.deploy(self.source/'assets/fonts',Path('.local/share/fonts/dotifails'))
        if 'desktop' in selected and appearance.get('archive'):
            archive=self.source/appearance['archive']
            if hashlib.sha256(archive.read_bytes()).hexdigest()!=appearance['sha256']:raise RuntimeError('El paquete del tema no coincide con su SHA-256.')
            with tempfile.TemporaryDirectory(prefix='dotifails-theme-') as temporary:
                root=Path(temporary)
                with tarfile.open(archive) as bundle:bundle.extractall(root,filter='data')
                for group in ('icons','themes'):
                    for item in sorted((root/group).iterdir()):self.deploy(item,Path('.local/share')/group/item.name)
        if 'desktop' in selected:
            from install_model import theme_core
            self.generated(theme_core().serialize(*selection),Path('.config/orbit/theme.json'))
            preferences=read(self.home/'.config/orbit/environment.json',{})
            if requested_theme or not preferences.get('wallpaper',{}).get('default'):
                preferences['wallpaper']=dict(default=str(self.home/'.local/share/backgrounds'/appearance['wallpaper']),mode='fill',monitors={},folders=preferences.get('wallpaper',{}).get('folders',[]))
                self.generated(json.dumps(preferences,indent=2)+'\n',Path('.config/orbit/environment.json'))
            if not self.conflicts:self.receipt['theme']=theme
        self.configure_manager()
        if profile:self.deploy(self.source/'profiles'/f'{profile}.sh',Path('.config/dotifails/machine.sh'))
        if 'desktop' in selected:
            self.generated(WYSUN_DESKTOP,Path('.local/share/applications/orbit.desktop'))
            (self.home/'Screenshots').mkdir(exist_ok=True)
        if 'terminal' in selected:self.generated('[Desktop Entry]\nType=Application\nName=Ghostty\nExec=ghostty\nIcon=utilities-terminal\nCategories=System;TerminalEmulator;\n',Path('.local/share/applications/ghostty.desktop'))
        if 'editor' in selected:self.generated('[Desktop Entry]\nType=Application\nName=Neovim\nExec=wysun-terminal -e nvim -- %F\nIcon=nvim\nCategories=Development;TextEditor;\nMimeType=text/plain;text/x-python;application/javascript;text/x-c;text/x-c++;\n',Path('.local/share/applications/nvim.desktop'))
    def finish(self):
        self.receipt.update(version=VERSION,source=str(self.source),last_backup=self.journal['id'])
        write(self.state/'installed.json',self.receipt);self.journal['status']='conflicts' if self.conflicts else 'complete';self.journal['conflicts']=self.conflicts;self.flush()
        print(f'\nRespaldo: {self.backup}')
        if self.conflicts:
            print('Se conservaron tus cambios. Revisa las versiones nuevas en incoming/:\n'+'\n'.join(self.conflicts))
        else:print('Archivos instalados correctamente.')


def fetch(spec,cache):
    cache.mkdir(parents=True,exist_ok=True);target=cache/spec['sha256']
    def valid():return target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==spec['sha256']
    if not valid():
        temp=target.with_suffix('.partial');run(['curl','--fail','--location','--proto','=https','--tlsv1.2','--retry','3','--connect-timeout','20','--max-time','600','--output',temp,spec['url']]);temp.replace(target)
    if not valid():target.unlink(missing_ok=True);raise RuntimeError('La suma SHA-256 no coincide: '+spec['url'])
    return target


def extract(archive,target,kind,executable=None):
    target.mkdir(parents=True)
    if kind=='appimage':
        executable=target/'bundle.AppImage';shutil.copy2(archive,executable);executable.chmod(0o755)
        subprocess.run([str(executable),'--appimage-extract'],cwd=target,check=True,stdout=subprocess.DEVNULL);executable.unlink();nested=target/'squashfs-root'
    elif kind=='binary':
        if not executable or Path(executable).name!=executable:raise ValueError('Nombre de ejecutable inválido')
        binary=target/executable;shutil.copy2(archive,binary);binary.chmod(0o755);nested=None
    else:
        with tarfile.open(archive) as tar:tar.extractall(target,filter='data')
        children=list(target.iterdir());nested=children[0] if len(children)==1 and children[0].is_dir() else None
    if nested:
        nested=nested.resolve(strict=True)
        if not nested.is_relative_to(target.resolve()):raise RuntimeError('La extracción salió de su directorio')
        staging=target.with_name(target.name+'-flat');nested.rename(staging);shutil.rmtree(target);staging.rename(target)


def install_tools(deployment,components=None):
    d=deployment;d.stage('Herramientas con versión y SHA-256 fijadas');lock=read(d.source/'manifests/artifacts.json');root=d.data/'tools';root.mkdir(parents=True,exist_ok=True);cache=d.home/'.cache/dotifails/downloads'
    wanted=set(lock) if components is None else set().union(*(ARTIFACTS[key] for key in components))
    lock={name:spec for name,spec in lock.items() if name in wanted}
    for name,spec in lock.items():
        version=root/(name+'-'+spec['version']);marker=version/'.dotifails-sha256'
        if not marker.is_file() or marker.read_text()!=spec['sha256']:
            archive=fetch(spec,cache);temp=root/(name+'-staging-'+uuid.uuid4().hex)
            try:
                extract(archive,temp,spec['kind'],spec.get('executable'));(temp/'.dotifails-sha256').write_text(spec['sha256'])
                if version.exists():raise RuntimeError(f'Versión existente incompleta: {version}; se conservó para inspección.')
                temp.rename(version)
            finally:
                if exists(temp):remove(temp)
        # Switch only stable pointers; old versions remain available for restoration.
        link=d.backup/'links'/name;link.parent.mkdir(exist_ok=True);link.symlink_to(version.name)
        d.deploy(link,Path('.local/share/dotifails/tools')/name)
    for name,target in [('node','node/bin/node'),('npm','node/bin/npm'),('npx','node/bin/npx'),('nvim','nvim/bin/nvim'),('starship','starship/starship'),('yt-dlp','yt-dlp/yt-dlp')]:
        if target.split('/')[0] not in lock:continue
        d.generated('#!/bin/sh\nexport PATH="$HOME/.local/bin:$PATH"\nexec "$HOME/.local/share/dotifails/tools/'+target+'" "$@"\n',Path('.local/bin')/name,True)
    # Mise shims dispatch by argv[0]; a shell wrapper would lose that name.
    if 'mise' in lock:
        mise_link=d.backup/'links/mise-bin';mise_link.symlink_to('../share/dotifails/tools/mise/bin/mise');d.deploy(mise_link,Path('.local/bin/mise'))
    if 'ghostty' in lock:d.generated('#!/bin/sh\nexport PATH="$HOME/.local/bin:$PATH"\nexec "$HOME/.local/share/dotifails/tools/ghostty/AppRun" "$@"\n',Path('.local/bin/ghostty'),True)
    if components is None or 'terminal' in components:
        for command,system in [('fd','fdfind'),('bat','batcat')]:d.generated(f'#!/bin/sh\nexec /usr/bin/{system} "$@"\n',Path('.local/bin')/command,True)
    for name in ('zsh-autosuggestions','zsh-syntax-highlighting'):
        if name not in lock:continue
        link=d.backup/'links'/('plugin-'+name);link.symlink_to('../../tools/'+name);d.deploy(link,Path('.local/share/dotifails/zsh-custom/plugins')/name)


def packages(source,extras,components=None,boot_components=None):
    fields=host_supported();wanted=package_names(source,normalize_components(components),extras,boot_components)
    prefix=[] if os.geteuid()==0 else ['sudo']
    run(prefix+['env','DEBIAN_FRONTEND=noninteractive','apt-get','update'])
    if components and 'wayland' in components:
        from wayland import simulate_packages
        print(simulate_packages(source,fields,wanted))
    run(prefix+['env','DEBIAN_FRONTEND=noninteractive','apt-get','-o','Dpkg::Options::=--force-confold','install','--yes','--no-remove','--no-install-recommends']+wanted)


def wayland_session(source):
    prefix=[] if os.geteuid()==0 else ['sudo']
    run(prefix+[sys.executable,source/'installer/session_registration.py','install','--source',source/'installer'])


def boot_appearance(source,dry_run=False,components=None):
    command=['/usr/bin/python3',str(source/'installer/boot.py'),'--source',str(source)]
    if components:command+=['--components',','.join(components)]
    if os.environ.get('DOTIFAILS_EVENTS')=='1':command+=['--events']
    if dry_run:command+=['--dry-run']
    elif os.geteuid()!=0:command=['sudo']+command
    run(command)


def nvim_setup(d,env):
    if '.config/nvim' in d.conflicts:
        print('Neovim tiene cambios locales; se conserva sin reinstalar su configuración.')
        return
    d.stage('Plugins y herramientas de Neovim')
    plugins=read(d.source/'manifests/plugins.json')
    from concurrent.futures import ThreadPoolExecutor
    def prepare(item):
        name,spec=item;target=d.home/'.local/share/nvim/lazy'/name
        if not target.exists():run(['git','clone','--filter=blob:none','--no-checkout',spec['url'],target],env)
        probe=subprocess.run(['git','-C',str(target),'cat-file','-e',spec['commit']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if probe.returncode:run(['git','-C',target,'fetch','origin',spec['commit']],env)
        run(['git','-C',target,'-c','advice.detachedHead=false','checkout','--detach',spec['commit']],env)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(prepare,plugins.items()))
    run(['make','-C',d.home/'.local/share/nvim/lazy/telescope-fzf-native.nvim'],env)
    run([d.home/'.local/bin/nvim','--headless','-u','NONE','-n','-i','NONE','-l',d.source/'installer/bootstrap-nvim.lua'],env)
    # The config's install=false keeps startup inert; this explicit phase performs installation.
    env=dict(env,DOTIFAILS_NVIM_SCRIPT=str(d.home/'.config/nvim/scripts/install.lua'))
    run([d.home/'.local/bin/nvim','--headless','-n','-i','NONE','-c',
         "lua local ok,err=pcall(dofile,vim.env.DOTIFAILS_NVIM_SCRIPT); if not ok then print(err); vim.cmd('cquit 1') end",'-c','qa'],env)
    d.receipt['files']['.config/nvim']=fingerprint(d.home/'.config/nvim')
    write(d.state/'installed.json',d.receipt)


def install_extras(names,d,env):
    if not names:return
    d.stage('Aplicaciones opcionales')
    run(['flatpak','remote-add','--user','--if-not-exists','flathub','https://flathub.org/repo/flathub.flatpakrepo'],env)
    for name in names:
        run(['flatpak','install','--user','--noninteractive','flathub',EXTRAS[name]],env)
        command='brave-browser' if name=='brave' else name
        d.generated(f'#!/bin/sh\nexec flatpak run {EXTRAS[name]} "$@"\n',Path('.local/bin')/command,True)


def doctor(home,components=None):
    home=Path(home);env=dict(os.environ,HOME=str(home),PATH=str(home/'.local/bin')+':'+os.environ.get('PATH',''));failed=[]
    selected=set(normalize_components(components or read(home/'.local/state/dotifails/installed.json',{}).get('components')))
    checks={'Python Qt':(['/usr/bin/python3','-c','from PySide6 import QtCore,QtGui,QtWidgets,QtSvg; import dbus,gi'],None),
      'Neovim':([str(home/'.local/bin/nvim'),'--version'],'0.11.5'),
      'Node':([str(home/'.local/bin/node'),'--version'],'v24.19.0'),'Mise':([str(home/'.local/bin/mise'),'--version'],'2026.9.14'),'Ghostty':([str(home/'.local/bin/ghostty'),'--version'],'1.2.3'),
      'OCR':(['tesseract','--list-langs'],'spa'),'FFmpeg':(['ffmpeg','-version'],None),'mpv':(['mpv','--version'],None)}
    owners={'Neovim':'editor','Node':'terminal','Mise':'terminal','Ghostty':'terminal'}
    for label,(argv,expected) in checks.items():
        if owners.get(label,'desktop') not in selected and not ('wayland' in selected and label in ('Python Qt','OCR','FFmpeg','mpv')):continue
        checkpoint()
        try:
            result=subprocess.run(argv,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=25);ok=result.returncode==0 and (not expected or expected in result.stdout)
        except (OSError,subprocess.TimeoutExpired):ok=False
        print(('OK  ' if ok else 'FAIL ')+label)
        if not ok:failed.append(label)
    required=[]
    if 'desktop' in selected:required += ['.config/wysun/hyprland.lua','.local/share/orbit/app/orbit.py','.local/share/wysun/quickshell/shell.qml','.local/share/backgrounds/tokyo.png']
    for rel in required:
        ok=(home/rel).is_file();print(('OK  ' if ok else 'FAIL ')+rel)
        if not ok:failed.append(rel)
    if 'terminal' in selected:
        for command in ('zsh','batcat','fzf'):
            ok=shutil.which(command,path=env['PATH']) is not None
            print(('OK  ' if ok else 'FAIL ')+command)
            if not ok:failed.append(command)
    if 'tools' in selected:
        ok=(home/'.local/bin/orbit-tools').is_file();print(('OK  ' if ok else 'FAIL ')+'orbit-tools')
        if not ok:failed.append('orbit-tools')
    if 'wayland' in selected:
        try:
            result=subprocess.run([str(home/'.local/bin/wysun-session'),'--check'],env=env,timeout=25)
            if result.returncode:failed.append('Wysun / Hyprland')
        except (OSError,subprocess.TimeoutExpired):failed.append('Wysun / Hyprland')
    print('Comprobación de archivos y ejecutables. La sesión gráfica se verifica al iniciar Wysun / Hyprland.')
    return 1 if failed else 0


def restore(home,ident):
    d=Deployment(home,Path(__file__).parent.parent);state=d.state
    if not ident:
        for p in sorted((state/'backups').glob('*/journal.json')):
            j=read(p);print(j['id'],j['status'])
        print('Restaurar: dotifails restore ID');return 0
    if Path(ident).name!=ident or ident in ('.','..'):raise ValueError('Identificador inválido')
    backup=state/'backups'/ident;j=read(backup/'journal.json')
    if not j:raise RuntimeError('No existe ese respaldo')
    state.mkdir(parents=True,exist_ok=True)
    with (state/'install.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if j.get('status')=='restored':print('El respaldo ya fue restaurado.');return 0
        emergency=backup/'changes-before-restore'
        retained={}
        for op in reversed(j['operations']):
            # A worker may still import modules from its immutable release.
            # Roll back launchers, retain code until explicit later cleanup.
            if op['path'].startswith('.local/share/wysun/capture/releases/'):
                retained[op['path']]=fingerprint(d.destination(op['path']))
                continue
            dest=d.destination(op['path']);current=fingerprint(dest)
            # Preserve edits made since installation, including partial installs.
            if exists(dest) and current!=op['after']:
                save=emergency/op['path']
                if exists(save):raise RuntimeError(f'Ya existe un cambio rescatado: {save}')
                copy(dest,save)
            before=backup/'before'/op['path']
            if exists(dest):remove(dest)
            if op['before'] is not None:copy(before,dest)
            displaced=d.destination(op['displaced']) if op.get('displaced') else None
            if displaced and exists(displaced):remove(displaced)
        receipt=read(backup/'installed-before.json',{'files':{}})
        receipt['files'].update({key:value for key,value in retained.items() if value is not None})
        write(state/'installed.json',receipt);j['status']='restored';write(backup/'journal.json',j)
    print(f'Restaurado {ident}. Cambios posteriores conservados en {emergency}. Los paquetes del sistema permanecen instalados.');return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description='Wysun Desktop · instalar, verificar, actualizar y recuperar')
    sub=parser.add_subparsers(dest='command',required=True)
    for command in ('install','update'):
        p=sub.add_parser(command);p.add_argument('--source',type=Path);p.add_argument('--target-home',type=Path,default=Path.home());p.add_argument('--config-only',action='store_true');p.add_argument('--dry-run',action='store_true');p.add_argument('--extras',nargs='?',const='brave,discord,obsidian',default='');p.add_argument('--profile',choices=['samsung-touchscreen']);p.add_argument('--skip-nvim-tools',action='store_true');p.add_argument('--ref',default='master')
        p.add_argument('--scripts-only',action='store_true',help='Solo herramientas y migración respaldada de ~/scripts; sin cambiar el escritorio')
        p.add_argument('--orbit-only','--wysun-only',dest='orbit_only',action='store_true',help='Solo código y lanzador de Wysun; conserva el resto del escritorio y los datos privados')
        p.add_argument('--boot-only',action='store_true',help='Solo GRUB, Plymouth e inicio de sesión; conserva la sesión abierta y respalda /etc y /boot')
        p.add_argument('--installer-only',action='store_true',help='Actualizar solo el instalador visual, la CLI y sus manifiestos')
        p.add_argument('--theme',choices=['severance','tokyo','space-black','fluent-light','fluent-dark','azul','morado'],help='Perfil visual; Severance en instalaciones nuevas, conserva el elegido al actualizar')
        p.add_argument('--components',help='Componentes separados por comas: desktop,wayland,terminal,editor,tools,boot')
        p.add_argument('--boot-components',default='grub,plymouth,greeter',help='Pantallas de arranque: grub,plymouth,greeter')
        p.add_argument('--plan',action='store_true',help='Mostrar el plan exacto en JSON, sin aplicar cambios')
    p=sub.add_parser('doctor');p.add_argument('--target-home',type=Path,default=Path.home())
    p=sub.add_parser('restore');p.add_argument('id',nargs='?');p.add_argument('--target-home',type=Path,default=Path.home())
    p=sub.add_parser('gui');p.add_argument('--source',type=Path);p.add_argument('--target-home',type=Path,default=Path.home())
    args=parser.parse_args(argv)
    if args.command=='gui':
        from gui import launch
        return launch(args.source,args.target_home)
    if args.command=='doctor':return doctor(args.target_home)
    if args.command=='restore':return restore(args.target_home,args.id)
    if args.components and (args.boot_only or args.orbit_only or args.scripts_only or args.installer_only):raise ValueError('--components no se combina con los modos --only.')
    if args.plan and (args.boot_only or args.orbit_only or args.scripts_only or args.installer_only):raise ValueError('Los modos --only admiten --dry-run; usa --components para un plan detallado.')
    if sum((args.boot_only,args.orbit_only,args.scripts_only,args.installer_only))>1:raise ValueError('Elige un solo modo --only.')
    if args.installer_only:
        if args.extras or args.profile or args.theme:raise ValueError('--installer-only se usa sin extras, perfiles ni temas.')
        args.config_only=True
    if args.boot_only:
        if args.orbit_only or args.scripts_only or args.config_only or args.extras or args.profile or args.theme:
            raise ValueError('--boot-only se usa por separado.')
        if args.target_home!=Path.home():raise ValueError('--boot-only modifica el sistema, no otro hogar.')
        previous=read(args.target_home/'.local/state/dotifails/installed.json',{}).get('source')
        source=(args.source or (Path(previous) if previous else Path(__file__).resolve().parent.parent)).resolve()
        if not (source/'system/boot/grub/theme.txt').is_file():raise RuntimeError('Indica el repositorio completo con --source.')
        if not args.dry_run:host_supported()
        boot_appearance(source,args.dry_run,args.boot_components.split(','));return 0
    if args.orbit_only and args.scripts_only:raise ValueError('Elige --orbit-only o --scripts-only.')
    if args.scripts_only:
        if args.extras or args.profile or args.theme:raise ValueError('--scripts-only no admite extras, perfiles ni temas.')
        args.config_only=True
    if args.orbit_only:
        if args.extras or args.profile or args.theme:raise ValueError('--orbit-only no admite extras ni perfiles del sistema o temas.')
        args.config_only=True
    selected=normalize_components(args.components.split(',') if args.components else None)
    if args.config_only and not args.components:selected=tuple(key for key in selected if key!='boot')
    if args.scripts_only:selected=('tools',)
    if args.orbit_only:selected=('desktop',)
    if args.installer_only:selected=()
    if args.theme:args.theme={'azul':'severance','morado':'tokyo'}.get(args.theme,args.theme)
    if args.plan:
        if args.command=='update' and not args.source:raise ValueError('Para revisar un plan exacto de actualización, indica la copia local con --source.')
        previous=read(args.target_home/'.local/state/dotifails/installed.json',{}).get('source')
        source=(args.source or (Path(previous) if previous else Path(__file__).resolve().parent.parent))
        options=InstallOptions(source,args.target_home,selected,args.theme,tuple(filter(None,args.extras.split(','))),tuple(args.boot_components.split(',')),args.config_only,args.skip_nvim_tools,args.profile)
        print(json.dumps(options.summary(),ensure_ascii=False,indent=2));return 0
    if args.dry_run:
        if args.installer_only:print('Plan: respaldar y actualizar solo el instalador, sus manifiestos y el acceso en el menú de aplicaciones.');return 0
        if args.scripts_only:print('Plan: instalar orbit-tools y su motor; respaldar y retirar lanzadores duplicados; migrar recordatorios y subidas a sus carpetas de Wysun; conservar aliases en el PATH. Los datos privados no se añaden al repositorio.');return 0
        if args.orbit_only:print('Plan: respaldar y actualizar la familia Wysun, incluidos Recorder y Screenshot, y el gestor dotifails. No cambia atajos, notas, historial ni colores.');return 0
        if 'wayland' in selected and not args.config_only:
            from wayland import simulate_packages
            fields=host_supported()
            selected_source=args.source or Path(__file__).resolve().parent.parent
            wanted=package_names(selected_source,selected,tuple(filter(None,args.extras.split(','))),tuple(args.boot_components.split(',')))
            print(simulate_packages(source=selected_source,fields=fields,wanted=wanted))
        print('Componentes: '+', '.join(COMPONENTS[key][0] for key in selected))
        print('Plan: validar compatibilidad; instalar las dependencias seleccionadas; verificar SHA-256; respaldar y copiar configuraciones; comprobar el resultado.\nConflictos: se conservan los archivos editados y se guardan nuevas versiones en incoming/.\nNo se ejecutarán cambios.');return 0
    home=args.target_home.expanduser().absolute()
    if not args.config_only:
        host_supported()
        if os.geteuid()==0:raise RuntimeError('Ejecuta como usuario normal con sudo disponible; no uses sudo ./instalar.sh.')
        if home!=Path.home():raise RuntimeError('--target-home requiere --config-only para no modificar otro usuario.')
    names=[n.strip() for n in args.extras.split(',') if n.strip()]
    if any(n not in EXTRAS for n in names):raise ValueError('Extras válidos: brave,discord,obsidian')
    if args.command=='update' and not args.source:
        cache=home/'.cache/dotifails';cache.mkdir(parents=True,exist_ok=True);checkout=Path(tempfile.mkdtemp(prefix='update-',dir=cache))
        run(['git','clone','--depth','1','--branch',args.ref,REPOSITORY,checkout]);args.source=checkout
        # Execute the new installer, so update also receives installer fixes.
        if not (checkout/'installer/main.py').is_file():raise RuntimeError('La referencia remota aún no contiene el nuevo instalador; usa --source con el repositorio preparado.')
        command=[sys.executable,str(checkout/'installer/main.py'),'install','--source',str(checkout),'--target-home',str(home)]
        if args.config_only:command+=['--config-only']
        if args.orbit_only:command+=['--orbit-only']
        if args.scripts_only:command+=['--scripts-only']
        if args.installer_only:command+=['--installer-only']
        if args.extras:command+=['--extras',args.extras]
        if args.skip_nvim_tools:command+=['--skip-nvim-tools']
        if args.profile:command+=['--profile',args.profile]
        if args.theme:command+=['--theme',args.theme]
        if args.components:command+=['--components',args.components]
        if args.boot_components!='grub,plymouth,greeter':command+=['--boot-components',args.boot_components]
        run(command);return 0
    previous_source=read(home/'.local/state/dotifails/installed.json',{}).get('source')
    source=(args.source or (Path(previous_source) if previous_source else Path(__file__).resolve().parent.parent)).resolve()
    if not (source/'config/.config/wysun/hyprland.lua').is_file():raise RuntimeError('Indica un repositorio completo: dotifails install --source /ruta/dotifails')
    if not (args.orbit_only or args.scripts_only or args.installer_only):
        InstallOptions(source,home,selected,args.theme,tuple(names),tuple(args.boot_components.split(',')),args.config_only,args.skip_nvim_tools,args.profile).validate()
    if not args.config_only and 'wayland' in selected:
        from wayland import simulate_packages
        # Fail before creating a journal or touching user/system files.
        print(simulate_packages(source,host_supported(),package_names(source,selected,names,args.boot_components.split(','))))
    home.mkdir(parents=True,exist_ok=True);d=Deployment(home,source);d.begin()
    env=dict(os.environ,HOME=str(home),PATH=str(home/'.local/bin')+':'+os.environ.get('PATH',''),XDG_CONFIG_HOME=str(home/'.config'),XDG_DATA_HOME=str(home/'.local/share'),XDG_STATE_HOME=str(home/'.local/state'),XDG_CACHE_HOME=str(home/'.cache'))
    try:
        steps=[]
        if not args.config_only:
            steps += [('Paquetes del sistema',lambda:packages(source,names,selected,args.boot_components.split(','))),
                      ('Herramientas verificadas',lambda:install_tools(d,selected))]
        if args.installer_only:steps.append(('Instalador y recuperación',d.configure_manager))
        elif args.scripts_only:steps.append(('Herramientas personales',d.configure_scripts))
        elif args.orbit_only:steps.append(('Aplicación Wysun',d.configure_orbit))
        else:steps.append(('Configuraciones y respaldos',lambda:d.configure(args.profile,args.theme,selected)))
        if args.scripts_only or args.orbit_only:steps.append(('Instalador y recuperación',d.configure_manager))
        if not args.config_only:
            if 'wayland' in selected:steps.append(('Registrar sesión Wysun / Hyprland',lambda:wayland_session(source) if not d.conflicts else None))
            if 'boot' in selected:steps.append(('Arranque y acceso',lambda:boot_appearance(source,components=args.boot_components.split(','))))
            if 'editor' in selected and not args.skip_nvim_tools:steps.append(('Lenguajes y plugins de Neovim',lambda:nvim_setup(d,env)))
            if names:steps.append(('Aplicaciones opcionales',lambda:install_extras(names,d,env)))
        if 'terminal' in selected and '.config/bat' not in d.conflicts and shutil.which('batcat'):
            # Evaluate conflicts after the configuration stage has actually run.
            steps.append(('Caché de terminal',lambda:run(['batcat','cache','--build'],env) if '.config/bat' not in d.conflicts else None))
        if not args.config_only and set(selected)&{'desktop','terminal'}:steps.append(('Fuentes del escritorio',lambda:run(['fc-cache','-f'],env)))
        def verify():
            if doctor(home,selected):raise RuntimeError('Doctor detectó dependencias incompletas; consulta el registro y vuelve a ejecutar el instalador.')
        if not args.config_only:steps.append(('Verificación final',verify))
        for index,(name,action) in enumerate(steps):
            checkpoint();emit('phase',name=name,index=index,total=len(steps));d.stage(name);action()
            emit('phase_done',name=name,index=index+1,total=len(steps))
        if not args.installer_only:
            d.receipt['components']=list(dict.fromkeys([*d.receipt.get('components',[]),*selected]))
            d.receipt['last_selection']=list(selected)
        d.finish()
        emit('result',status='conflicts' if d.conflicts else 'complete',backup=d.journal['id'],conflicts=d.conflicts,components=list(selected),config_only=args.config_only)
        if not args.config_only:print('Sesión Wysun / Hyprland preparada. Puedes seleccionarla cuando cierres sesión voluntariamente.')
        else:print('Modo config-only: no instala paquetes, herramientas ni registra la sesión gráfica.')
        return 2 if d.conflicts else 0
    except BaseException as error:
        d.journal['status']='cancelled' if isinstance(error,InstallationCancelled) else 'failed';d.journal['error']=type(error).__name__+': '+str(error);d.flush()
        emit('result',status=d.journal['status'],backup=d.journal['id'],message=str(error),conflicts=d.conflicts)
        print(f'Instalación interrumpida. Respaldo recuperable: {d.journal["id"]}',file=sys.stderr);raise
    finally:
        d.lock.close()


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,RuntimeError,ValueError,subprocess.CalledProcessError) as error:
        emit('error',message=str(error));print('Error: '+str(error),file=sys.stderr);sys.exit(130 if isinstance(error,InstallationCancelled) else 1)
