#!/usr/bin/env python3
"""Reproducible desktop deployment with a write-ahead backup journal."""
import argparse,datetime,fcntl,hashlib,json,os,platform,shutil,stat,subprocess,sys,tarfile,tempfile,uuid
from pathlib import Path

VERSION='1.0.0'
REPOSITORY='https://github.com/Niklauswy/dotifails.git'
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
    print('+ '+' '.join(map(str,argv)),flush=True)
    subprocess.run(list(map(str,argv)),check=True,env=env)


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
        for relative in ('.config/probe','.local/share/probe','.local/state/probe','.cache/probe'):
            self.destination(Path(relative))
        self.state.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.lock=(self.state/'install.lock').open('a');fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ident=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
        self.backup=self.state/'backups'/ident;self.backup.mkdir(parents=True,mode=0o700)
        write(self.backup/'installed-before.json',self.receipt)
        self.journal={'id':ident,'status':'running','version':VERSION,'operations':[],'stages':[]};self.flush()
        return ident
    def flush(self):write(self.backup/'journal.json',self.journal)
    def stage(self,name):self.journal['stages'].append(name);self.flush();print('\n→ '+name,flush=True)
    def destination(self,relative):
        rel=Path(relative)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('Destino fuera del hogar')
        dest=self.home/rel
        for parent in dest.parents:
            if parent==self.home:break
            if parent.is_symlink():raise RuntimeError(f'El directorio {parent} es un enlace; no se escribirá fuera del hogar.')
        return dest
    def deploy(self,source,relative):
        dest=self.destination(relative);key=str(relative);current=fingerprint(dest);wanted=fingerprint(source);previous=self.receipt['files'].get(key)
        if current==wanted:
            self.receipt['files'][key]=wanted;return
        if previous is not None and current!=previous:
            incoming=self.backup/'incoming'/relative;copy(source,incoming);self.conflicts.append(key);return
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
    def generated(self,text,relative,executable=False):
        temp=self.backup/'generated'/relative;temp.parent.mkdir(parents=True,exist_ok=True);temp.write_text(text);temp.chmod(0o755 if executable else 0o644);self.deploy(temp,relative)
    def configure_orbit(self):
        self.stage('Actualizar solo Órbita (código y lanzador)')
        self.deploy(self.source/'apps/orbit',Path('.local/share/orbit/app'))
        if self.conflicts:return
        self.deploy(self.source/'home/.local/bin/orbit',Path('.local/bin/orbit'))
        self.deploy(self.source/'installer',Path('.local/share/dotifails/installer'))
        self.generated('#!/bin/sh\nexec python3 "$HOME/.local/share/dotifails/installer/main.py" "$@"\n',Path('.local/bin/dotifails'),True)
    def configure(self,profile=None):
        self.stage('Configuraciones y aplicaciones')
        for base in ('.config','.local/bin'):
            for item in sorted((self.source/'home'/base).iterdir()):self.deploy(item,Path(base)/item.name)
        self.deploy(self.source/'home/.zshrc',Path('.zshrc'))
        self.deploy(self.source/'apps/orbit',Path('.local/share/orbit/app'))
        for item in sorted((self.source/'assets/icons').iterdir()):self.deploy(item,Path('.local/share/icons')/item.name)
        self.deploy(self.source/'assets/fonts',Path('.local/share/fonts/dotifails'))
        self.deploy(self.source/'backgrounds/tokyo.png',Path('.local/share/backgrounds/tokyo.png'))
        self.deploy(self.source/'installer',Path('.local/share/dotifails/installer'))
        self.deploy(self.source/'manifests',Path('.local/share/dotifails/manifests'))
        if profile:self.deploy(self.source/'profiles'/f'{profile}.sh',Path('.config/dotifails/machine.sh'))
        self.generated('#!/bin/sh\nexec python3 "$HOME/.local/share/dotifails/installer/main.py" "$@"\n',Path('.local/bin/dotifails'),True)
        self.generated('[Desktop Entry]\nType=Application\nName=Órbita\nComment=Aplicaciones y herramientas del escritorio\nExec=orbit\nIcon=system-search\nCategories=Utility;\n',Path('.local/share/applications/orbit.desktop'))
        self.generated('[Desktop Entry]\nType=Application\nName=Ghostty\nExec=ghostty\nIcon=utilities-terminal\nCategories=System;TerminalEmulator;\n',Path('.local/share/applications/ghostty.desktop'))
        self.generated('[Desktop Entry]\nType=Application\nName=Neovim\nExec=desktop-terminal -e nvim -- %F\nIcon=nvim\nCategories=Development;TextEditor;\nMimeType=text/plain;text/x-python;application/javascript;text/x-c;text/x-c++;\n',Path('.local/share/applications/nvim.desktop'))
        (self.home/'Screenshots').mkdir(exist_ok=True)
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


def extract(archive,target,kind):
    target.mkdir(parents=True)
    if kind=='appimage':
        executable=target/'bundle.AppImage';shutil.copy2(archive,executable);executable.chmod(0o755)
        subprocess.run([str(executable),'--appimage-extract'],cwd=target,check=True,stdout=subprocess.DEVNULL);executable.unlink();nested=target/'squashfs-root'
    else:
        with tarfile.open(archive) as tar:tar.extractall(target,filter='data')
        children=list(target.iterdir());nested=children[0] if len(children)==1 and children[0].is_dir() else None
    if nested:
        nested=nested.resolve(strict=True)
        if not nested.is_relative_to(target.resolve()):raise RuntimeError('La extracción salió de su directorio')
        staging=target.with_name(target.name+'-flat');nested.rename(staging);shutil.rmtree(target);staging.rename(target)


def install_tools(deployment):
    d=deployment;d.stage('Herramientas con versión y SHA-256 fijadas');lock=read(d.source/'manifests/artifacts.json');root=d.data/'tools';root.mkdir(parents=True,exist_ok=True);cache=d.home/'.cache/dotifails/downloads'
    for name,spec in lock.items():
        version=root/(name+'-'+spec['version']);marker=version/'.dotifails-sha256'
        if not marker.is_file() or marker.read_text()!=spec['sha256']:
            archive=fetch(spec,cache);temp=root/(name+'-staging-'+uuid.uuid4().hex)
            try:
                extract(archive,temp,spec['kind']);(temp/'.dotifails-sha256').write_text(spec['sha256'])
                if version.exists():raise RuntimeError(f'Versión existente incompleta: {version}; se conservó para inspección.')
                temp.rename(version)
            finally:
                if exists(temp):remove(temp)
        # Switch only stable pointers; old versions remain available for restoration.
        link=d.backup/'links'/name;link.parent.mkdir(exist_ok=True);link.symlink_to(version.name)
        d.deploy(link,Path('.local/share/dotifails/tools')/name)
    for name,target in [('node','node/bin/node'),('npm','node/bin/npm'),('npx','node/bin/npx'),('nvim','nvim/bin/nvim'),('starship','starship/starship')]:
        d.generated('#!/bin/sh\nexport PATH="$HOME/.local/bin:$PATH"\nexec "$HOME/.local/share/dotifails/tools/'+target+'" "$@"\n',Path('.local/bin')/name,True)
    d.generated('#!/bin/sh\nexport PATH="$HOME/.local/bin:$PATH"\nexec "$HOME/.local/share/dotifails/tools/ghostty/AppRun" "$@"\n',Path('.local/bin/ghostty'),True)
    for command,system in [('fd','fdfind'),('bat','batcat')]:d.generated(f'#!/bin/sh\nexec /usr/bin/{system} "$@"\n',Path('.local/bin')/command,True)
    for name in ('zsh-autosuggestions','zsh-syntax-highlighting'):
        link=d.backup/'links'/('plugin-'+name);link.symlink_to('../../tools/'+name);d.deploy(link,Path('.local/share/dotifails/zsh-custom/plugins')/name)


def packages(source,extras):
    host_supported();manifest=read(source/'manifests/packages.json');wanted=manifest['desktop']+manifest['development']
    if not Path('/etc/X11/default-display-manager').exists():wanted.append('lightdm')
    if extras:wanted.append('flatpak')
    prefix=[] if os.geteuid()==0 else ['sudo']
    run(prefix+['apt-get','update']);run(prefix+['apt-get','install','--yes','--no-install-recommends']+wanted)


def session(source):
    prefix=[] if os.geteuid()==0 else ['sudo']
    run(prefix+['install','-m','755',source/'installer/orbit-session-system','/usr/local/bin/orbit-session'])
    run(prefix+['install','-m','644',source/'installer/orbit-bspwm.desktop','/usr/share/xsessions/orbit-bspwm.desktop'])
    # These are desktop dependencies, not a request to replace the current login session.
    if Path('/run/systemd/system').exists():
        run(prefix+['systemctl','enable','--now','NetworkManager.service','bluetooth.service'])


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


def doctor(home):
    home=Path(home);env=dict(os.environ,HOME=str(home),PATH=str(home/'.local/bin')+':'+os.environ.get('PATH',''));failed=[]
    checks={'Python Qt':(['/usr/bin/python3','-c','from PySide6 import QtCore,QtGui,QtWidgets,QtSvg; import Xlib,dbus,gi'],None),
      'BSPWM':(['bspwm','-v'],None),'Picom':(['picom','--version'],'v12'), 'Neovim':([str(home/'.local/bin/nvim'),'--version'],'0.11.5'),
      'Node':([str(home/'.local/bin/node'),'--version'],'v24.19.0'),'Ghostty':([str(home/'.local/bin/ghostty'),'--version'],'1.2.3'),
      'OCR':(['tesseract','--list-langs'],'spa'),'FFmpeg':(['ffmpeg','-version'],None),'mpv':(['mpv','--version'],None)}
    for label,(argv,expected) in checks.items():
        try:
            result=subprocess.run(argv,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=25);ok=result.returncode==0 and (not expected or expected in result.stdout)
        except (OSError,subprocess.TimeoutExpired):ok=False
        print(('OK  ' if ok else 'FAIL ')+label)
        if not ok:failed.append(label)
    for rel in ('.config/bspwm/bspwmrc','.config/sxhkd/sxhkdrc','.local/share/orbit/app/orbit.py','.local/share/backgrounds/tokyo.png'):
        ok=(home/rel).is_file();print(('OK  ' if ok else 'FAIL ')+rel)
        if not ok:failed.append(rel)
    print('Comprobación de archivos y ejecutables. La sesión gráfica se verifica al iniciar Órbita/BSPWM.')
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
        for op in reversed(j['operations']):
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
        write(state/'installed.json',read(backup/'installed-before.json',{'files':{}}));j['status']='restored';write(backup/'journal.json',j)
    print(f'Restaurado {ident}. Cambios posteriores conservados en {emergency}. Los paquetes del sistema permanecen instalados.');return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description='Órbita Desktop · instalar, verificar, actualizar y recuperar')
    sub=parser.add_subparsers(dest='command',required=True)
    for command in ('install','update'):
        p=sub.add_parser(command);p.add_argument('--source',type=Path);p.add_argument('--target-home',type=Path,default=Path.home());p.add_argument('--config-only',action='store_true');p.add_argument('--dry-run',action='store_true');p.add_argument('--extras',nargs='?',const='brave,discord,obsidian',default='');p.add_argument('--profile',choices=['samsung-touchscreen']);p.add_argument('--skip-nvim-tools',action='store_true');p.add_argument('--ref',default='master')
        p.add_argument('--orbit-only',action='store_true',help='Solo código y lanzador de Órbita; conserva el resto del escritorio y los datos privados')
    p=sub.add_parser('doctor');p.add_argument('--target-home',type=Path,default=Path.home())
    p=sub.add_parser('restore');p.add_argument('id',nargs='?');p.add_argument('--target-home',type=Path,default=Path.home())
    args=parser.parse_args(argv)
    if args.command=='doctor':return doctor(args.target_home)
    if args.command=='restore':return restore(args.target_home,args.id)
    if args.orbit_only:
        if args.extras or args.profile:raise ValueError('--orbit-only no admite extras ni perfiles del sistema.')
        args.config_only=True
    if args.dry_run:
        if args.orbit_only:print('Plan: respaldar y actualizar únicamente Órbita, su lanzador y el gestor dotifails. No cambia atajos, notas, historial ni colores.');return 0
        print('Plan: validar Parrot 7/Debian 13 x86_64; instalar dependencias; verificar SHA-256; respaldar y copiar configs; registrar sesión; preparar Neovim; doctor.\nConflictos: se conservan los archivos editados y se guardan nuevas versiones en incoming/.\nNo se ejecutarán cambios.');return 0
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
        if args.extras:command+=['--extras',args.extras]
        if args.skip_nvim_tools:command+=['--skip-nvim-tools']
        if args.profile:command+=['--profile',args.profile]
        run(command);return 0
    previous_source=read(home/'.local/state/dotifails/installed.json',{}).get('source')
    source=(args.source or (Path(previous_source) if previous_source else Path(__file__).resolve().parent.parent)).resolve()
    if not (source/'home/.config/bspwm/bspwmrc').is_file():raise RuntimeError('Indica un repositorio completo: dotifails install --source /ruta/dotifails')
    home.mkdir(parents=True,exist_ok=True);d=Deployment(home,source);d.begin()
    env=dict(os.environ,HOME=str(home),PATH=str(home/'.local/bin')+':'+os.environ.get('PATH',''),XDG_CONFIG_HOME=str(home/'.config'),XDG_DATA_HOME=str(home/'.local/share'),XDG_STATE_HOME=str(home/'.local/state'))
    try:
        if not args.config_only:d.stage('Paquetes del sistema');packages(source,names);install_tools(d)
        if args.orbit_only:d.configure_orbit()
        else:d.configure(args.profile)
        if not args.config_only:
            d.stage('Registro de sesión');session(source)
            if not args.skip_nvim_tools:nvim_setup(d,env)
            install_extras(names,d,env)
            run(['fc-cache','-f'],env)
            result=doctor(home)
            if result:raise RuntimeError('Doctor detectó dependencias incompletas; consulta la salida y vuelve a ejecutar el instalador.')
        d.finish()
        if not args.config_only:print('Cierra sesión cuando quieras y elige Órbita / BSPWM. Tu sesión actual sigue abierta.')
        else:print('Modo config-only: no instala paquetes, herramientas ni registra la sesión gráfica.')
        return 2 if d.conflicts else 0
    except BaseException as error:
        d.journal['status']='failed';d.journal['error']=type(error).__name__+': '+str(error);d.flush()
        print(f'Instalación interrumpida. Respaldo recuperable: {d.journal["id"]}',file=sys.stderr);raise


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,RuntimeError,ValueError,subprocess.CalledProcessError) as error:print('Error: '+str(error),file=sys.stderr);sys.exit(1)
