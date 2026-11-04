#!/usr/bin/env python3
"""Reproducible desktop deployment with a write-ahead backup journal."""
import argparse,datetime,fcntl,hashlib,json,os,platform,shutil,stat,subprocess,sys,tarfile,tempfile,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_model import ARTIFACTS, COMPONENTS, installed_components, normalize_components, package_names
from install_events import InstallationCancelled, checkpoint, emit

VERSION='2.0.0'
REPOSITORY='https://github.com/Niklauswy/dotifails.git'
WYSUN_DESKTOP='[Desktop Entry]\nType=Application\nName=Wysun\nComment=Aplicaciones y herramientas del escritorio\nExec=wysun\nIcon=system-search\nCategories=Utility;\nKeywords=Wysun;lanzador;launcher;aplicaciones;\nStartupWMClass=wysun\n'
PLAYER_DESKTOP='wysun-player.desktop'
# The desktop's two families (tokens.json: font.family.sans/mono), installed for GTK and the terminal from the
# copies the apps already bundle, with their licences: {installed name: source}.
FONT_BUNDLE={'GoogleSansFlex.ttf':'apps/python/wysun_core/fonts/GoogleSansFlex.ttf',
             'CaskaydiaCoveNerdFont-Regular.ttf':'apps/python/wysun_core/fonts/CaskaydiaCoveNerdFont-Regular.ttf',
             'licenses/OFL-GoogleSansFlex.txt':'LICENSES/OFL-GoogleSansFlex.txt',
             'licenses/OFL-CascadiaCode.txt':'LICENSES/OFL-CascadiaCode.txt',
             'licenses/MIT-NerdFonts.txt':'LICENSES/MIT-NerdFonts.txt'}
# Launchers earlier versions published; `wysun` replaces them all. An update removes the ones this installer
# wrote and the user has not changed. One the user changed becomes theirs (kept, out of the receipt); one the
# active Hyprland configuration still calls is kept until that configuration stops calling it.
DESKTOP_RETIRED=tuple('.local/bin/'+name for name in (
    'wysun-player','wysun-workspaces','wysun-files','wysun-music','wysun-pdf','wysun-screenshot','wybie-screenshot'))+(
    '.local/share/applications/wybie-screenshot.desktop','.local/share/applications/wysun-pdf.desktop','.local/share/icons/hicolor/scalable/apps/wybie-screenshot.svg')
# `wysun tools` and the scripts before it were withdrawn; their engine goes with them (each utility is now a
# package of its own in apps/python, such as wysun_lanshare).
TOOLS_RETIRED=tuple('.local/bin/'+name for name in (
    'wysun-tools','web-dev','sec-audit','file-share','gvm','gvm.sh','tailscale-killswitch','tailscale-killswitch.sh',
    'scrip.sh','rezets','zzzz.py'))+('scripts/wysun-tools','scripts/README.md','.local/share/wysun/tools')
# The graphical installer was withdrawn: `./instalar.sh` and `wysun update` replace it.
INSTALLER_RETIRED=('.local/bin/wysun-installer','.local/share/applications/wysun-installer.desktop',
                   '.local/share/applications/wysun-installer-preview.desktop')
RETIRED_COMMANDS=DESKTOP_RETIRED+TOOLS_RETIRED+INSTALLER_RETIRED
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
    if argv and argv[0]=='sudo' and os.environ.get('WYSUN_EVENTS')=='1':
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



def default_wallpaper(source):
    """File name of the wallpaper the distribution ships (wysun_core/tokens.json)."""
    return read(Path(source)/'apps/python/wysun_core/tokens.json')['wallpaper']

class Deployment:
    def __init__(self,home,source):
        self.home=Path(home).absolute();self.source=Path(source).resolve();self.state=self.home/'.local/state/wysun/install';self.data=self.home/'.local/share/wysun';self.receipt=read(self.state/'installed.json',{'files':{}});self.journal=None;self.conflicts=[]
        # An update keeps files the installer never managed (the user's own); a fresh install adopts them, with backup.
        self.adopt=True;self.kept=[]
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
        if previous is None and current is not None and not self.adopt:
            self.kept.append(key);return
        before=self.backup/'before'/relative
        if exists(dest):copy(dest,before)
        op={'path':key,'before':current,'after':wanted};self.journal['operations'].append(op);self.flush()
        temporary=dest.with_name('.'+dest.name+'.wysun-'+uuid.uuid4().hex)
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
    def configure_fonts(self):
        relative=Path('.local/share/fonts/wysun');staged=self.backup/'generated'/relative
        for name,source in FONT_BUNDLE.items():
            target=staged/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(self.source/source,target);target.chmod(0o644)
        self.deploy(staged,relative)
    def player_mime_types(self):
        """The types Wysun Player declares: the single source for its default associations."""
        entry=self.source/'config/.local/share/applications'/PLAYER_DESKTOP
        for line in entry.read_text().splitlines() if entry.is_file() else ():
            if line.startswith('MimeType='):return [name for name in line[9:].split(';') if name]
        return []
    def configure_files(self,player=False):
        # The desktop profile owns folder opening, portal selection and reveal actions.
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
        mime.set('Default Applications','inode/directory','wysun-files.desktop;')
        previous=mime.get('Added Associations','inode/directory',fallback='')
        alternatives=[name for name in previous.split(';') if name and name!='wysun-files.desktop']
        mime.set('Added Associations','inode/directory',';'.join(['wysun-files.desktop']+alternatives)+';')
        if mime.has_option('Removed Associations','inode/directory'):
            removed=[name for name in mime.get('Removed Associations','inode/directory').split(';') if name and name!='wysun-files.desktop']
            mime.set('Removed Associations','inode/directory',';'.join(removed)+(';' if removed else ''))
        if player:self.associate_player(mime)
        import io
        output=io.StringIO();mime.write(output,space_around_delimiters=False);self.generated(output.getvalue(),relative)
        self.files_services()
        relative=Path('.config/xdg-desktop-portal/portals.conf')
        parser=configparser.ConfigParser(interpolation=None);parser.optionxform=str
        existing=self.destination(relative)
        if existing.is_file():parser.read(existing)
        if not parser.has_section('preferred'):parser.add_section('preferred')
        if not parser.has_option('preferred','default'):parser.set('preferred','default','gtk;')
        parser.set('preferred','org.freedesktop.impl.portal.FileChooser','wysun;gtk;')
        import io
        output=io.StringIO();parser.write(output);self.generated(output.getvalue(),relative)
        self.generated('GTK_USE_PORTAL=1\n',Path('.config/environment.d/60-wysun-files.conf'))
    def files_services(self):
        """The file manager's launcher, menu entry, D-Bus/systemd activation and portal backend; no associations."""
        from capture_distribution import _publish
        self.deploy(self.source/'config/.local/share/applications/wysun-files.desktop',Path('.local/share/applications/wysun-files.desktop'))
        self.deploy(self.source/'config/.local/share/applications/wysun-processes.desktop',Path('.local/share/applications/wysun-processes.desktop'))
        service='wysun-files-integration.service'
        command='/usr/bin/env "PYTHONPATH='+str(self.home/'.local/share/wysun/app')+'" /usr/bin/python3 -P -m wysun_files.service'
        self.generated('[Unit]\nDescription=Wysun file chooser and file manager integration\nAfter=graphical-session-pre.target\n\n[Service]\nType=dbus\nBusName=org.freedesktop.impl.portal.desktop.wysun\nExecStart='+command+'\nRestart=on-failure\nTimeoutStopSec=5\n',Path('.config/systemd/user')/service)
        for name in ('org.freedesktop.impl.portal.desktop.wysun','org.freedesktop.FileManager1'):
            self.generated('[D-BUS Service]\nName='+name+'\nExec='+command+'\nSystemdService='+service+'\n',Path('.local/share/dbus-1/services')/(name+'.service'))
        self.generated('[portal]\nDBusName=org.freedesktop.impl.portal.desktop.wysun\nInterfaces=org.freedesktop.impl.portal.FileChooser;\nUseIn=Wysun;Hyprland;\n',Path('.local/share/xdg-desktop-portal/portals/wysun.portal'))

    def associate_player(self,mime):
        """Make Wysun Player the default for its image, video and audio types.

        Whatever was the default stays on as an alternative ("Open with"). This runs only in the
        full installation: updating Wysun alone never changes what the user opens files with.
        """
        for mimetype in self.player_mime_types():
            previous=mime.get('Default Applications',mimetype,fallback='')
            alternatives=[name for name in previous.split(';') if name and name!=PLAYER_DESKTOP]
            mime.set('Default Applications',mimetype,PLAYER_DESKTOP+';')
            added=[name for name in mime.get('Added Associations',mimetype,fallback='').split(';') if name and name!=PLAYER_DESKTOP and name not in alternatives]
            mime.set('Added Associations',mimetype,';'.join([PLAYER_DESKTOP]+alternatives+added)+';')
            if mime.has_option('Removed Associations',mimetype):
                removed=[name for name in mime.get('Removed Associations',mimetype).split(';') if name and name!=PLAYER_DESKTOP]
                mime.set('Removed Associations',mimetype,';'.join(removed)+(';' if removed else ''))
    def publish_dispatcher(self):
        """~/.local/bin/wysun, the single entry point; False when an unowned file is in the way."""
        from capture_distribution import _publish
        return _publish(self,(self.source/'bin/wysun').read_text(),'.local/bin/wysun',executable=True)
    def retire_commands(self,names=RETIRED_COMMANDS):
        import re
        folder=self.destination('.config/wysun')
        configs=[path.read_text(errors='replace') for path in sorted(folder.glob('*.lua')) if path.is_file()] if folder.is_dir() else []
        # Only commands the configuration runs count, not window classes such as ^wysun-files$.
        active='\n'.join(m.group(2) for text in configs for m in re.finditer(r'exec_cmd\(\s*(["\'])(.*?)\1',text))
        for relative in names:
            if relative not in self.receipt['files']:continue      # never ours: left alone
            name=Path(relative).name
            if relative.startswith('.local/bin/') and re.search(r'(?<![\w.-])'+re.escape(name)+r'(?![\w.-])',active):
                print('Wysun: se conserva '+relative+' porque ~/.config/wysun lo sigue ejecutando; cámbialo por su orden de `wysun`.');continue
            current=fingerprint(self.destination(relative))
            if current is not None and current!=self.receipt['files'][relative]:
                self.receipt['files'].pop(relative)
                print('Wysun: '+relative+' tiene cambios tuyos; ya no lo administra el instalador y se conserva.');continue
            self.retire(Path(relative))
    def configure_wysun(self):
        if not (self.source/'bin/wysun').is_file():return
        from capture_distribution import configure
        if not self.publish_dispatcher():return
        self.retire_commands()
        self.generated(WYSUN_DESKTOP,Path('.local/share/applications/wysun.desktop'))
        for name in ('wysun-settings.desktop',PLAYER_DESKTOP):
            source=self.source/'config/.local/share/applications'/name
            if source.is_file():self.deploy(source,Path('.local/share/applications')/name)
        configure(self)
    def configure_manager(self):
        manager=self.backup/'generated/manager'
        shutil.copytree(self.source/'installer',manager,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        self.deploy(manager,Path('.local/share/wysun/installer'))
        self.deploy(self.source/'manifests',Path('.local/share/wysun/manifests'))
        self.generated('#!/bin/sh\nexec python3 "$HOME/.local/share/wysun/installer/main.py" "$@"\n',Path('.local/bin/wysun-install'),True)
        self.retire_commands(INSTALLER_RETIRED)
    def configure(self,profile=None,components=None):
        # Exactly the components asked for: an update must not add terminal/editor configuration to a machine without them.
        selected=set(normalize_components(None) if components is None else components)
        if 'wayland' in selected:
            from wayland import configure
            configure(self)
            if selected == {'wayland'}:
                self.configure_manager()
                return
        self.stage('Configuraciones y aplicaciones')
        home_source=self.backup/'generated/theme-home'
        shutil.copytree(self.source/'config',home_source)
        app=self.source/'apps/python'
        if (app/'wysun_settings/theme_runtime.py').exists():
            subprocess.run([sys.executable,'-P','-m','wysun_settings.theme_runtime','render',str(home_source)],
                           env=dict(os.environ,PYTHONPATH=str(app)),check=True)
        owners={'nvim':'editor','ghostty':'terminal','fzf':'terminal','bat':'terminal','starship.toml':'terminal'}
        for base in ('.config','.local/bin'):
            for item in sorted((home_source/base).iterdir()):
                if base=='.config' and item.name=='wysun':
                    # Wysun's preferences are private runtime data, managed by file: hyprland.lua by the
                    # wayland component, theme/environment below; only the terminal's mise.zsh ships here.
                    mise=item/'mise.zsh'
                    if 'terminal' in selected and mise.is_file():self.deploy(mise,Path(base)/item.name/mise.name)
                    continue
                if owners.get(item.name,'desktop') in selected:self.deploy(item,Path(base)/item.name)
        if 'terminal' in selected:self.deploy(self.source/'config/.zshrc',Path('.zshrc'))
        if 'desktop' in selected:
            self.deploy(self.source/'apps/python',Path('.local/share/wysun/app'))
            if '.local/share/wysun/app' not in self.conflicts:
                self.configure_files(player=True)
                self.configure_wysun()
            for item in sorted((self.source/'assets/icons').iterdir()):self.deploy(item,Path('.local/share/icons')/item.name)
            for item in sorted((self.source/'assets/backgrounds').iterdir()):self.deploy(item,Path('.local/share/backgrounds')/item.name)
            for rel in ('.local/share/applications/wysun-music.desktop','.local/share/icons/hicolor/scalable/apps/musika.svg'):
                if (self.source/'config'/rel).is_file():self.deploy(self.source/'config'/rel,Path(rel))
        if selected & {'desktop','terminal'}:self.configure_fonts()
        if 'desktop' in selected:
            # The mode is the only choice: keep the user's (and any other key); a broken file starts automatic.
            try:stored=json.loads((self.home/'.config/wysun/theme.json').read_text())
            except (OSError,ValueError):stored={}
            stored=stored if isinstance(stored,dict) else {}
            stored['mode']=stored.get('mode') if stored.get('mode') in ('auto','light','dark') else 'auto'
            self.generated(json.dumps(stored,ensure_ascii=False,indent=2)+'\n',Path('.config/wysun/theme.json'))
            preferences=read(self.home/'.config/wysun/environment.json',{})
            if not preferences.get('wallpaper',{}).get('default'):
                preferences['wallpaper']=dict(default=str(self.home/'.local/share/backgrounds'/default_wallpaper(self.source)),mode='fill',monitors={},folders=preferences.get('wallpaper',{}).get('folders',[]))
                self.generated(json.dumps(preferences,indent=2)+'\n',Path('.config/wysun/environment.json'))
        self.configure_manager()
        if profile:self.deploy(self.source/'machines'/f'{profile}.sh',Path('.config/wysun/machine.sh'))
        if 'desktop' in selected:
            self.generated(WYSUN_DESKTOP,Path('.local/share/applications/wysun.desktop'))
            (self.home/'Screenshots').mkdir(exist_ok=True)
        if 'terminal' in selected:self.generated('[Desktop Entry]\nType=Application\nName=Ghostty\nExec=ghostty\nIcon=utilities-terminal\nCategories=System;TerminalEmulator;\n',Path('.local/share/applications/ghostty.desktop'))
        if 'editor' in selected:self.generated('[Desktop Entry]\nType=Application\nName=Neovim\nExec=wysun-terminal -e nvim -- %F\nIcon=nvim\nCategories=Development;TextEditor;\nMimeType=text/plain;text/x-python;application/javascript;text/x-c;text/x-c++;\n',Path('.local/share/applications/nvim.desktop'))
    def finish(self):
        self.receipt.update(version=VERSION,source=str(self.source),last_backup=self.journal['id'])
        write(self.state/'installed.json',self.receipt);self.journal['status']='conflicts' if self.conflicts else 'complete';self.journal['conflicts']=self.conflicts;self.flush()
        print(f'\nRespaldo: {self.backup}')
        if self.kept:print('Se conservan tal cual (no los administra Wysun en este equipo): '+', '.join(self.kept))
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
    d=deployment;d.stage('Herramientas con versión y SHA-256 fijadas');lock=read(d.source/'manifests/artifacts.json');root=d.data/'artifacts';root.mkdir(parents=True,exist_ok=True);cache=d.home/'.cache/wysun/install/downloads'
    wanted=set(lock) if components is None else set().union(*(ARTIFACTS[key] for key in components))
    lock={name:spec for name,spec in lock.items() if name in wanted}
    for name,spec in lock.items():
        version=root/(name+'-'+spec['version']);marker=version/'.wysun-sha256'
        if not marker.is_file() or marker.read_text()!=spec['sha256']:
            archive=fetch(spec,cache);temp=root/(name+'-staging-'+uuid.uuid4().hex)
            try:
                extract(archive,temp,spec['kind'],spec.get('executable'));(temp/'.wysun-sha256').write_text(spec['sha256'])
                if version.exists():raise RuntimeError(f'Versión existente incompleta: {version}; se conservó para inspección.')
                temp.rename(version)
            finally:
                if exists(temp):remove(temp)
        # Switch only stable pointers; old versions remain available for restoration.
        link=d.backup/'links'/name;link.parent.mkdir(exist_ok=True);link.symlink_to(version.name)
        d.deploy(link,Path('.local/share/wysun/artifacts')/name)
    for name,target in [('node','node/bin/node'),('npm','node/bin/npm'),('npx','node/bin/npx'),('nvim','nvim/bin/nvim'),('starship','starship/starship'),('yt-dlp','yt-dlp/yt-dlp')]:
        if target.split('/')[0] not in lock:continue
        d.generated('#!/bin/sh\nexport PATH="$HOME/.local/bin:$PATH"\nexec "$HOME/.local/share/wysun/artifacts/'+target+'" "$@"\n',Path('.local/bin')/name,True)
    # Mise shims dispatch by argv[0]; a shell wrapper would lose that name.
    if 'mise' in lock:
        mise_link=d.backup/'links/mise-bin';mise_link.symlink_to('../share/wysun/artifacts/mise/bin/mise');d.deploy(mise_link,Path('.local/bin/mise'))
    if 'ghostty' in lock:d.generated('#!/bin/sh\nexport PATH="$HOME/.local/bin:$PATH"\nexec "$HOME/.local/share/wysun/artifacts/ghostty/AppRun" "$@"\n',Path('.local/bin/ghostty'),True)
    if components is None or 'terminal' in components:
        for command,system in [('fd','fdfind'),('bat','batcat')]:d.generated(f'#!/bin/sh\nexec /usr/bin/{system} "$@"\n',Path('.local/bin')/command,True)
    for name in ('zsh-autosuggestions','zsh-syntax-highlighting'):
        if name not in lock:continue
        link=d.backup/'links'/('plugin-'+name);link.symlink_to('../../artifacts/'+name);d.deploy(link,Path('.local/share/wysun/zsh-custom/plugins')/name)


def packages(source,extras,components=None,boot_components=None,refresh=True):
    fields=host_supported();wanted=package_names(source,normalize_components(components),extras,boot_components)
    prefix=[] if os.geteuid()==0 else ['sudo']
    if refresh:run(prefix+['env','DEBIAN_FRONTEND=noninteractive','apt-get','-o','APT::Update::Error-Mode=any','update'])
    if components and 'wayland' in components:
        from wayland import simulate_packages
        print(simulate_packages(source,fields,wanted))
    run(prefix+['env','DEBIAN_FRONTEND=noninteractive','apt-get','-o','Dpkg::Options::=--force-confold','install','--yes','--no-remove','--no-install-recommends']+wanted)


def refresh_package_plan(source,extras,components,boot_components):
    fields=host_supported();wanted=package_names(source,components,extras,boot_components)
    prefix=[] if os.geteuid()==0 else ['sudo']
    run(prefix+['env','DEBIAN_FRONTEND=noninteractive','apt-get','-o','APT::Update::Error-Mode=any','update'])
    if 'wayland' in components:
        from wayland import simulate_packages
        print(simulate_packages(source,fields,wanted))
    else:
        run(['apt-get','--simulate','--no-remove','install','--no-install-recommends',*wanted])


def prepare_repositories(source):
    prefix=[] if os.geteuid()==0 else ['sudo']
    run(prefix+[sys.executable,str(source/'installer/repositories.py')])


def wayland_session(source):
    prefix=[] if os.geteuid()==0 else ['sudo']
    run(prefix+[sys.executable,source/'installer/session_registration.py','install','--source',source/'installer'])


def boot_appearance(source,dry_run=False,components=None):
    command=['/usr/bin/python3',str(source/'installer/boot.py'),'--source',str(source)]
    if components:command+=['--components',','.join(components)]
    if os.environ.get('WYSUN_EVENTS')=='1':command+=['--events']
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
    env=dict(env,WYSUN_NVIM_SCRIPT=str(d.home/'.config/nvim/scripts/install.lua'))
    run([d.home/'.local/bin/nvim','--headless','-n','-i','NONE','-c',
         "lua local ok,err=pcall(dofile,vim.env.WYSUN_NVIM_SCRIPT); if not ok then print(err); vim.cmd('cquit 1') end",'-c','qa'],env)
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


def required_files(home,selected):
    """Installed files doctor checks for the selected components (relative to home)."""
    required=[]
    if 'desktop' in selected:required += ['.config/wysun/hyprland.lua','.local/share/wysun/app/wysun_services/daemon.py','.local/share/wysun/quickshell/shell.qml','.local/share/backgrounds/'+read(home/'.local/share/wysun/app/wysun_core/tokens.json',{}).get('wallpaper','')]
    return required


def doctor(home,components=None):
    home=Path(home);env=dict(os.environ,HOME=str(home),PATH=str(home/'.local/bin')+':'+os.environ.get('PATH',''));failed=[]
    selected=set(normalize_components(components or installed_components(read(home/'.local/state/wysun/install/installed.json',{}))))
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
    if selected & {'desktop','wayland'}:
        try:opengl=subprocess.run(['/usr/bin/python3','-c','from PySide6 import QtOpenGL,QtOpenGLWidgets'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=25).returncode==0
        except (OSError,subprocess.TimeoutExpired):opengl=False
        # Not a failure: Wysun Player falls back to software rendering, which works but uses more CPU.
        print('OK  Wysun Player (OpenGL)' if opengl else 'AVISO Wysun Player usa renderizado por software: instala python3-pyside6.qtopengl y python3-pyside6.qtopenglwidgets')
    for rel in required_files(home,selected):
        ok=(home/rel).is_file();print(('OK  ' if ok else 'FAIL ')+rel)
        if not ok:failed.append(rel)
    if 'terminal' in selected:
        for command in ('zsh','batcat','fzf'):
            ok=shutil.which(command,path=env['PATH']) is not None
            print(('OK  ' if ok else 'FAIL ')+command)
            if not ok:failed.append(command)
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
        print('Restaurar: wysun-install restore ID');return 0
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


BRANCH='main'
SOURCE_DIR='.local/share/wysun/source'
EVERYTHING=tuple(COMPONENTS)
BOOT_SCREENS=('grub','plymouth','greeter')
EXTRA_APPS=tuple(EXTRAS)
UPDATE_STATE='.local/state/wysun/update.json'


def digest(source,*relatives):
    """One hash over files/directories of the source (missing ones count as absent)."""
    h=hashlib.sha256()
    for relative in relatives:
        h.update(relative.encode()+b'\0'+(fingerprint(Path(source)/relative) or 'absent').encode()+b'\0')
    return h.hexdigest()


def system_inputs(source,components):
    """What each privileged/slow step depends on; `wysun update` reruns a step only when its value changes."""
    source=Path(source);wanted=package_names(source,components,EXTRA_APPS,BOOT_SCREENS,inspect_installed=False)
    inputs={'packages':hashlib.sha256('\n'.join(sorted(wanted)).encode()).hexdigest()}
    if 'wayland' in components:inputs['session']=digest(source,'installer/session_registration.py','installer/wysun-session-system','installer/wysun-hyprland.desktop')
    if 'boot' in components:inputs['boot']=digest(source,'system/boot','installer/boot.py','apps/shell/greeter.qml')
    if 'editor' in components:inputs['editor']=digest(source,'manifests/plugins.json','manifests/mason.json','installer/bootstrap-nvim.lua','config/.config/nvim/scripts')
    inputs['extras']=hashlib.sha256(','.join(EXTRAS[name] for name in EXTRA_APPS).encode()).hexdigest()
    return inputs


def git(source,*args,check=True):
    return subprocess.run(['git','-C',str(source),*args],check=check,text=True,capture_output=True)


def is_checkout(source):
    return (Path(source)/'.git').exists() and git(source,'rev-parse','--is-inside-work-tree',check=False).returncode==0


def receipt_of(home):return read(Path(home)/'.local/state/wysun/install/installed.json',{})


def check_updates(home,fetch=True):
    """Compare the source checkout with its upstream; write and return the bar's update state."""
    home=Path(home);source=receipt_of(home).get('source')
    state={'checked':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'source':source,'branch':None,
           'local':None,'remote':None,'behind':0,'available':False,'error':None}
    try:
        if not source or not is_checkout(source):raise RuntimeError('la fuente instalada no es un repositorio git')
        state['branch']=git(source,'rev-parse','--abbrev-ref','HEAD').stdout.strip()
        if fetch:
            fetched=git(source,'fetch','--quiet','origin',check=False)
            if fetched.returncode:raise RuntimeError('no se pudo consultar origin')
        state['local']=git(source,'rev-parse','HEAD').stdout.strip()
        upstream=git(source,'rev-parse','@{u}',check=False)
        if upstream.returncode:raise RuntimeError('la rama '+state['branch']+' no sigue a una rama remota')
        state['remote']=upstream.stdout.strip()
        state['behind']=int(git(source,'rev-list','--count','HEAD..@{u}').stdout.strip() or 0)
        state['available']=state['behind']>0
    except (RuntimeError,OSError,ValueError,subprocess.CalledProcessError) as error:
        state['error']=str(error)
    write(home/UPDATE_STATE,state);return state


def pull(source):
    """Fast-forward the checkout to its upstream. Offline, it keeps the local copy; a diverged branch stops the update."""
    if git(source,'fetch','--quiet','origin',check=False).returncode:
        print('Wysun: sin conexión con origin; se aplica la copia local.');return
    if git(source,'rev-parse','@{u}',check=False).returncode:
        print('Wysun: la rama local no sigue a una rama remota; se aplica la copia local.');return
    merged=git(source,'merge','--ff-only','@{u}',check=False)
    if merged.returncode:
        raise RuntimeError('No se pudo avanzar '+str(source)+' hasta origin (rama divergente o cambios locales en conflicto). '
                           'Resuélvelo con git en esa carpeta y repite wysun update.\n'+(merged.stderr or merged.stdout).strip())
    print('Wysun: '+(merged.stdout.strip().splitlines() or ['al día'])[0])


def restart_shell(home,before):
    """Reload the resident and, when the installed shell changed, restart only the shell (never Hyprland)."""
    if not (os.environ.get('WAYLAND_DISPLAY') and os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')):return
    env=dict(os.environ,PATH=str(Path(home)/'.local/bin')+':'+os.environ.get('PATH',''))
    subprocess.run(['wysun','reload'],env=env,check=False)
    if fingerprint(Path(home)/'.local/share/wysun/quickshell')!=before:
        subprocess.run(['pkill','-x','quickshell'],check=False)
        subprocess.Popen(['setsid','wysun-shell'],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        print('Wysun: shell reiniciado con el código nuevo.')


def update(home):
    home=Path(home);receipt=receipt_of(home);source=receipt.get('source')
    if not receipt:raise RuntimeError('Wysun no está instalado en este equipo; ejecuta ./instalar.sh desde el repositorio.')
    if not source or not is_checkout(source):
        # Earlier versions updated from throwaway clones: keep one checkout from now on.
        source=home/SOURCE_DIR
        if not is_checkout(source):
            if exists(source):raise RuntimeError(f'{source} existe pero no es un repositorio git.')
            run(['git','clone','--branch',BRANCH,REPOSITORY,source])
    else:pull(source)
    before=fingerprint(home/'.local/share/wysun/quickshell')
    # The pulled installer applies its own code, so an update also receives installer fixes.
    result=subprocess.run([sys.executable,str(Path(source)/'installer/main.py'),'apply','--source',str(source),'--target-home',str(home)])
    if result.returncode not in (0,2):return result.returncode
    check_updates(home,fetch=False);restart_shell(home,before);return result.returncode


def plan(source,components,config_only,inputs=None,recorded=None):
    steps=[]
    if not config_only:
        due=lambda key:inputs is None or recorded is None or (key in inputs and recorded.get(key)!=inputs[key])
        if due('packages'):steps+=['Repositorios oficiales (backports) si faltan','Paquetes del sistema']
        steps.append('Herramientas verificadas (SHA-256)')
    steps.append('Configuraciones, apps y atajos (con respaldo)')
    if not config_only:
        if 'wayland' in components and due('session'):steps.append('Registrar la sesión Wysun / Hyprland')
        if 'boot' in components and due('boot'):steps.append('Arranque: GRUB, Plymouth y pantalla de acceso')
        if 'editor' in components and due('editor'):steps.append('Plugins y herramientas de Neovim')
        if due('extras'):steps.append('Brave, Discord y Obsidian (Flatpak)')
        steps.append('Verificación final')
    return steps


def deploy(source,home,components,config_only,fresh):
    """Install (fresh) or apply an update: configuration always; system steps when new or when their inputs changed."""
    source=Path(source).resolve();home=Path(home).expanduser().absolute()
    # A fresh install takes everything; an update keeps exactly the components this machine has.
    components=normalize_components(components) if fresh else tuple(key for key in COMPONENTS if key in components)
    if not (source/'config/.config/wysun/hyprland.lua').is_file():raise RuntimeError('Fuente incompleta: '+str(source))
    if not config_only:
        host_supported()
        if os.geteuid()==0:raise RuntimeError('Ejecuta como usuario normal con sudo disponible; no uses sudo.')
        if home!=Path.home():raise RuntimeError('Solo se instala en tu propio hogar.')
    recorded=receipt_of(home).get('inputs')
    inputs=system_inputs(source,components)
    # A receipt from before input tracking: the system was prepared by that installer; record it as the baseline.
    if not fresh and recorded is None:recorded=dict(inputs)
    due=lambda key:fresh or (key in inputs and recorded.get(key)!=inputs[key])
    home.mkdir(parents=True,exist_ok=True);d=Deployment(home,source);d.adopt=fresh;d.begin()
    env=dict(os.environ,HOME=str(home),PATH=str(home/'.local/bin')+':'+os.environ.get('PATH',''),XDG_CONFIG_HOME=str(home/'.config'),XDG_DATA_HOME=str(home/'.local/share'),XDG_STATE_HOME=str(home/'.local/state'),XDG_CACHE_HOME=str(home/'.cache'))
    try:
        steps=[]
        if not config_only:
            if due('packages'):
                steps+=[('Repositorios oficiales de la distribución',lambda:prepare_repositories(source)),
                        ('Índices APT y compatibilidad de dependencias',lambda:refresh_package_plan(source,EXTRA_APPS,components,BOOT_SCREENS)),
                        ('Paquetes del sistema',lambda:packages(source,EXTRA_APPS,components,BOOT_SCREENS,refresh=False))]
            steps.append(('Herramientas verificadas',lambda:install_tools(d,components)))
        steps.append(('Configuraciones y respaldos',lambda:d.configure(None,components)))
        if not config_only:
            if 'wayland' in components and due('session'):steps.append(('Registrar sesión Wysun / Hyprland',lambda:wayland_session(source) if not d.conflicts else None))
            if 'boot' in components and due('boot'):steps.append(('Arranque y acceso',lambda:boot_appearance(source,components=BOOT_SCREENS)))
            if 'editor' in components and due('editor'):steps.append(('Lenguajes y plugins de Neovim',lambda:nvim_setup(d,env)))
            if due('extras'):steps.append(('Aplicaciones Flatpak',lambda:install_extras(EXTRA_APPS,d,env)))
        if 'terminal' in components and shutil.which('batcat'):
            steps.append(('Caché de terminal',lambda:run(['batcat','cache','--build'],env) if '.config/bat' not in d.conflicts else None))
        if not config_only and set(components)&{'desktop','terminal'}:steps.append(('Fuentes del escritorio',lambda:run(['fc-cache','-f'],env)))
        def verify():
            if not doctor(home,components):return
            if fresh:raise RuntimeError('Doctor detectó dependencias incompletas; consulta el registro y repite la instalación.')
            print('AVISO: doctor detectó dependencias incompletas (arriba). La actualización se aplicó; ./instalar.sh las instala.')
        if not config_only:steps.append(('Verificación final',verify))
        for index,(name,action) in enumerate(steps):
            checkpoint();emit('phase',name=name,index=index,total=len(steps));d.stage(name);action()
            emit('phase_done',name=name,index=index+1,total=len(steps))
        d.receipt['components']=list(dict.fromkeys([*installed_components(d.receipt),*components]))
        d.receipt.pop('last_selection',None)
        if not config_only:d.receipt['inputs']=inputs
        if is_checkout(source):d.receipt['commit']=git(source,'rev-parse','HEAD').stdout.strip()
        d.finish()
        emit('result',status='conflicts' if d.conflicts else 'complete',backup=d.journal['id'],conflicts=d.conflicts,components=list(components),config_only=config_only)
        if fresh and not config_only:print('Wysun instalado. Elige la sesión «Wysun / Hyprland» al iniciar sesión. Para recibir cambios: wysun update')
        return 2 if d.conflicts else 0
    except BaseException as error:
        d.journal['status']='cancelled' if isinstance(error,InstallationCancelled) else 'failed';d.journal['error']=type(error).__name__+': '+str(error);d.flush()
        emit('result',status=d.journal['status'],backup=d.journal['id'],message=str(error),conflicts=d.conflicts)
        print(f'Instalación interrumpida. Respaldo recuperable: {d.journal["id"]}',file=sys.stderr);raise
    finally:
        d.lock.close()


def main(argv=None):
    parser=argparse.ArgumentParser(prog='wysun-install',description='Wysun · instalar todo el escritorio, actualizarlo desde git y recuperarlo')
    sub=parser.add_subparsers(dest='command',required=True,metavar='{install,update,doctor,restore}')
    hidden=argparse.SUPPRESS
    for command,text in (('install','Instalar el escritorio completo (paquetes, sesión, apps, terminal, Neovim, arranque y Flatpaks)'),
                         ('apply',hidden)):
        p=sub.add_parser(command,help=text) if text!=hidden else sub.add_parser(command)
        p.add_argument('--dry-run',action='store_true',help='Mostrar el plan sin cambiar nada')
        # For tests and the update hand-off; not part of the everyday interface.
        p.add_argument('--source',type=Path,help=hidden);p.add_argument('--target-home',type=Path,default=Path.home(),help=hidden)
        p.add_argument('--config-only',action='store_true',help=hidden)
    p=sub.add_parser('update',help='git pull del repositorio de este equipo y aplicar lo que cambió')
    p.add_argument('--check',action='store_true',help='Solo comprobar si hay cambios nuevos (escribe ~/.local/state/wysun/update.json)')
    p.add_argument('--target-home',type=Path,default=Path.home(),help=hidden)
    p=sub.add_parser('doctor',help='Comprobar la instalación');p.add_argument('--target-home',type=Path,default=Path.home(),help=hidden)
    p=sub.add_parser('restore',help='Restaurar archivos desde un respaldo');p.add_argument('id',nargs='?');p.add_argument('--target-home',type=Path,default=Path.home(),help=hidden)
    args=parser.parse_args(argv)
    if args.command=='doctor':return doctor(args.target_home)
    if args.command=='restore':return restore(args.target_home,args.id)
    if args.command=='update':
        if args.check:
            state=check_updates(args.target_home);print(json.dumps(state,ensure_ascii=False));return 0
        return update(args.target_home)
    home=args.target_home.expanduser().absolute()
    recorded_source=receipt_of(home).get('source')
    source=(args.source or (Path(recorded_source) if recorded_source and (Path(recorded_source)/'installer/main.py').is_file() else Path(__file__).resolve().parent.parent)).resolve()
    fresh=args.command=='install'
    components=EVERYTHING if fresh else (installed_components(receipt_of(home)) or EVERYTHING)
    if args.config_only:components=tuple(key for key in components if key!='boot')
    if args.dry_run:
        selected=normalize_components(components) if fresh else tuple(key for key in COMPONENTS if key in components)
        inputs=None if fresh else system_inputs(source,selected)
        recorded=None if fresh else receipt_of(home).get('inputs',inputs)
        print('Componentes: '+', '.join(COMPONENTS[key][0] for key in selected))
        print('Plan:\n'+'\n'.join('  · '+step for step in plan(source,selected,args.config_only,inputs,recorded)))
        print('Conflictos: se conservan los archivos que editaste y la versión nueva queda en incoming/ del respaldo.\nNo se ejecutarán cambios.');return 0
    return deploy(source,home,components,args.config_only,fresh)


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,RuntimeError,ValueError,subprocess.CalledProcessError) as error:
        emit('error',message=str(error));print('Error: '+str(error),file=sys.stderr);sys.exit(130 if isinstance(error,InstallationCancelled) else 1)
