#!/usr/bin/env python3
"""System appearance only. Never installs GRUB or restarts the display manager."""
import argparse
import configparser
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_events import emit


def fingerprint(path):
    if not path.exists(): return None
    if path.is_symlink(): raise RuntimeError(f'Enlace no admitido: {path}')
    digest = hashlib.sha256()
    files = sorted(path.rglob('*')) if path.is_dir() else [path]
    for item in files:
        if item.is_symlink(): raise RuntimeError(f'Enlace no admitido: {item}')
        digest.update(str(item.relative_to(path) if path.is_dir() else item.name).encode())
        digest.update(str(item.stat().st_mode & 0o777).encode())
        if item.is_file(): digest.update(item.read_bytes())
    return digest.hexdigest()


def remove(path):
    if path.is_dir(): shutil.rmtree(path)
    elif path.exists(): path.unlink()


def copy(source, target, normalize=False):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir(): shutil.copytree(source, target)
    else: shutil.copy2(source, target)
    if normalize:
        for item in [target, *target.rglob('*')] if target.is_dir() else [target]:
            item.chmod(0o755 if item.is_dir() else 0o644)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    temporary.chmod(0o600); temporary.replace(path)


def read(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def merged_ini(path, section, changes):
    # Preserve unrelated options, including input/accessibility preferences.
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.optionxform = str
    if path.exists(): config.read(path)
    if not config.has_section(section): config.add_section(section)
    for key, value in changes.items(): config[section][key] = value
    import io
    stream = io.StringIO(); config.write(stream)
    return stream.getvalue()


class BootDeployment:
    def __init__(self, source, root=Path('/'), runner=None, components=None):
        self.source = Path(source).resolve()
        self.root = Path(root)
        self.state = self.path('var/lib/dotifails/boot')
        self.receipt = {}
        if os.geteuid()==0 or self.root!=Path('/'):
            self.receipt = read(self.state/'installed.json', {})
        self.runner = runner or self.run
        self.components=set(('grub','plymouth','greeter') if components is None else components)
        if not self.components or self.components-{'grub','plymouth','greeter'}:raise ValueError('Pantallas de arranque inválidas.')

    def path(self, relative):
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Destino inválido')
        target = self.root/rel
        for parent in [target, *target.parents]:
            if parent == self.root: break
            if parent.is_symlink(): raise RuntimeError(f'Enlace no admitido: {parent}')
        return target

    def run(self, command):
        print('+ '+' '.join(command), flush=True)
        subprocess.run(command, check=True, env=dict(os.environ, PATH='/usr/sbin:/usr/bin:/sbin:/bin'))

    def plan(self):
        plans=[]
        if 'grub' in self.components and self.path('etc/default/grub').is_file() and self.path('boot/grub').is_dir():
            plans.append(('grub','boot/grub/themes/orbit',self.source/'system/boot/grub'))
            plans.append(('grub','etc/default/grub.d/99-orbit-theme.cfg',
                'GRUB_THEME="/boot/grub/themes/orbit/theme.txt"\n'
                'GRUB_BACKGROUND=""\nGRUB_GFXMODE=auto\n'
                '# Keep kernel flags, encryption, timeout and default entries unchanged.\n'
                'case " $GRUB_CMDLINE_LINUX $GRUB_CMDLINE_LINUX_DEFAULT " in\n'
                '  *" splash "*) ;;\n'
                '  *) GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT quiet splash" ;;\n'
                'esac\n'))
            # A distro may force text output. Leave serial consoles intact.
            configs=[self.path('etc/default/grub'),*self.path('etc/default/grub.d').glob('*.cfg')]
            serial=any('serial' in line for p in configs for line in p.read_text().splitlines()
                       if line.strip().startswith(('GRUB_TERMINAL=', 'GRUB_TERMINAL_OUTPUT=')))
            if not serial: plans[-1]=(plans[-1][0],plans[-1][1],plans[-1][2]+'GRUB_TERMINAL_OUTPUT=gfxterm\n')
        if 'plymouth' in self.components and self.path('usr/share/plymouth/themes').is_dir():
            plans.append(('plymouth','usr/share/plymouth/themes/orbit',self.source/'system/boot/plymouth'))
            config=self.path('etc/plymouth/plymouthd.conf')
            plans.append(('plymouth','etc/plymouth/plymouthd.conf',merged_ini(config,'Daemon',{'Theme':'orbit'})))
        manager=self.path('etc/X11/default-display-manager')
        if 'greeter' in self.components and manager.exists() and Path(manager.read_text().strip()).name=='lightdm':
            plans.extend([
                ('greeter','usr/local/lib/dotifails/blue-crt.so',self.source/'native/blue-crt/blue-crt.c'),
                ('greeter','usr/share/dotifails/blue-crt',self.source/'system/boot/greeter/assets'),
                ('greeter','usr/share/xgreeters/blue-crt.desktop','[Desktop Entry]\nName=Blue CRT\nType=Application\nExec=/usr/bin/env GTK_MODULES=/usr/local/lib/dotifails/blue-crt.so /usr/sbin/slick-greeter\nX-Ubuntu-Gettext-Domain=slick-greeter\n'),
                ('greeter','usr/share/themes/Orbit-Greeter',self.source/'system/boot/greeter/Orbit-Greeter'),
                ('greeter','usr/share/backgrounds/orbit-login.png',self.source/'system/boot/greeter/background.png'),
                ('greeter','usr/share/pixmaps/orbit-login.png',self.source/'system/boot/greeter/logo.png'),
                ('greeter','etc/lightdm/lightdm.conf.d/99-orbit-greeter.conf','[Seat:*]\ngreeter-session=blue-crt\n'),
                ('greeter','etc/lightdm/slick-greeter.conf',merged_ini(self.path('etc/lightdm/slick-greeter.conf'),'Greeter',{
                    'background':'/usr/share/backgrounds/orbit-login.png','background-color':'#04047e',  # theme-exception: color del cargador de arranque del sistema, no del escritorio
                    'draw-user-backgrounds':'false','draw-grid':'false','show-hostname':'false',
                    'theme-name':'Orbit-Greeter','icon-theme-name':'Adwaita',
                    'font-name':'DejaVu Sans Mono 11','logo':'/usr/share/pixmaps/orbit-login.png',
                    'other-monitors-logo':'/usr/share/pixmaps/orbit-login.png','enable-hidpi':'auto'}))])
        return [plan for plan in plans if plan[0] in self.components]

    def refresh(self, groups, backup=None, journal=None):
        if 'grub' in groups:
            # Generate to a temporary file; never replace a working configuration
            # if grub-mkconfig or its syntax check fails.
            output=self.path('boot/grub/grub.cfg.orbit-new')
            target=self.path('boot/grub/grub.cfg')
            if backup is not None:
                before=fingerprint(target)
                if target.exists(): copy(target,backup/'before/boot/grub/grub.cfg')
                journal['operations'].append({'path':'boot/grub/grub.cfg','before':before,'after':None})
                save(backup/'journal.json',journal)
            try:
                self.runner(['grub-mkconfig','-o',str(output)])
                self.runner(['grub-script-check',str(output)])
                output.chmod(0o600)
                output.replace(target)
                if backup is not None:
                    journal['operations'][-1]['after']=fingerprint(target)
                    save(backup/'journal.json',journal)
            finally:
                if output.exists(): output.unlink()
        if 'plymouth' in groups: self.runner(['update-initramfs','-u','-k','all'])

    def build_module(self, source, target):
        target.parent.mkdir(parents=True,exist_ok=True)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','gtk+-3.0'],text=True))
        subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(source),'-o',str(target),*flags,'-lm'],check=True)
        target.chmod(0o644)

    def apply(self):
        plans=self.plan()
        if not plans: raise RuntimeError('No se encontró GRUB, Plymouth ni LightDM compatible.')
        conflicts=[rel for _,rel,_ in plans if rel in self.receipt and fingerprint(self.path(rel))!=self.receipt[rel]]
        if conflicts: raise RuntimeError('Se conservaron cambios locales; revisa: '+', '.join(conflicts))
        groups={group for group,_,_ in plans}
        required=[]
        if 'grub' in groups: required+=['grub-mkconfig','grub-script-check']
        if 'plymouth' in groups: required+=['update-initramfs']
        if 'greeter' in groups: required+=['slick-greeter','cc','pkg-config']
        if self.root==Path('/'):
            for command in required:
                if not shutil.which(command, path='/usr/sbin:/usr/bin:/sbin:/bin'):
                    raise RuntimeError(f'Falta {command}; ejecuta la instalación completa para preparar dependencias.')
        ident=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
        backup=self.state/'backups'/ident;backup.mkdir(parents=True,mode=0o700)
        journal={'id':ident,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'running','operations':[],'groups':[], 'receipt_before':self.receipt.copy()}
        save(backup/'journal.json',journal)
        emit('system_backup',id=ident,path=str(backup))
        try:
            for group,rel,payload in plans:
                target=self.path(rel);stage=backup/'staged'/rel
                if isinstance(payload,Path):
                    fingerprint(payload)
                    if payload.suffix=='.c': self.build_module(payload,stage)
                    else: copy(payload,stage,normalize=True)
                else:
                    stage.parent.mkdir(parents=True,exist_ok=True);stage.write_text(payload)
                    stage.chmod(target.stat().st_mode & 0o777 if target.exists() else 0o644)
                before=fingerprint(target);after=fingerprint(stage)
                if before==after: self.receipt[rel]=after;continue
                if target.exists(): copy(target,backup/'before'/rel)
                journal['operations'].append({'path':rel,'before':before,'after':after})
                if group not in journal['groups']: journal['groups'].append(group)
                save(backup/'journal.json',journal)
                remove(target);copy(stage,target);self.receipt[rel]=after
            self.refresh(set(journal['groups']),backup,journal)
            save(self.state/'installed.json',self.receipt)
            journal['status']='complete';save(backup/'journal.json',journal)
        except BaseException:
            self.rollback(backup,journal)
            raise
        print(f'Tema de inicio instalado. Respaldo: {ident}. Se verá al próximo inicio; la sesión sigue abierta.')
        return ident

    def rollback(self, backup, journal):
        for op in reversed(journal['operations']):
            target=self.path(op['path'])
            current=fingerprint(target)
            if current not in (None,op['after'],op['before']):
                copy(target,backup/'changes-before-restore'/op['path'])
            remove(target)
            before=backup/'before'/op['path']
            if op['before'] is not None: copy(before,target)
        self.receipt=journal['receipt_before'];save(self.state/'installed.json',self.receipt)
        journal['status']='restoring';save(backup/'journal.json',journal)
        # grub.cfg was saved exactly; only the initramfs needs rebuilding.
        self.refresh(set(journal['groups'])-{'grub'})
        journal['status']='restored';save(backup/'journal.json',journal)

    def restore(self, ident):
        if Path(ident).name!=ident or ident in ('.','..'):raise ValueError('Respaldo inválido')
        backup=self.state/'backups'/ident
        journal=read(backup/'journal.json',None)
        if not journal:raise RuntimeError('No existe ese respaldo de inicio.')
        if journal['status']!='restored':self.rollback(backup,journal)
        print(f'Restaurado: {ident}')

    def verify(self):
        if not self.receipt:raise RuntimeError('No hay una instalación de inicio registrada.')
        for rel,digest in self.receipt.items():
            if fingerprint(self.path(rel))!=digest:raise RuntimeError(f'Archivo modificado o incompleto: /{rel}')
        if self.root==Path('/'):
            if 'boot/grub/themes/orbit' in self.receipt:
                self.runner(['grub-script-check','/boot/grub/grub.cfg'])
                if 'themes/orbit/theme.txt' not in self.path('boot/grub/grub.cfg').read_text():
                    raise RuntimeError('GRUB no está usando el tema instalado.')
            if 'usr/share/plymouth/themes/orbit' in self.receipt:
                for kernel in sorted(self.path('boot').glob('vmlinuz-*')):
                    initrd=kernel.with_name(kernel.name.replace('vmlinuz-','initrd.img-',1))
                    listing=subprocess.check_output(['lsinitramfs',str(initrd)],text=True,
                        env=dict(os.environ,PATH='/usr/sbin:/usr/bin:/sbin:/bin'))
                    for name in ['orbit.script',*[p.name for p in self.path('usr/share/plymouth/themes/orbit').glob('*.png')]]:
                        if f'plymouth/themes/orbit/{name}' not in listing:
                            raise RuntimeError(f'Falta {name} en {initrd.name}')
                    print(f'OK Plymouth: {initrd.name}')
        print('OK: integridad de los temas instalados.')


def main():
    parser=argparse.ArgumentParser(description='Apariencia del arranque y acceso de Wysun')
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--restore',metavar='ID')
    parser.add_argument('--verify',action='store_true',help='Comprobar archivos, GRUB e imágenes de arranque')
    parser.add_argument('--components',default='grub,plymouth,greeter',help='Pantallas que se aplicarán, separadas por comas')
    parser.add_argument('--list',action='store_true',help='Listar respaldos del arranque')
    parser.add_argument('--events',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.events:os.environ['DOTIFAILS_EVENTS']='1'
    deployment=BootDeployment(args.source,components=args.components.split(','))
    if args.dry_run:
        for group,rel,_ in deployment.plan():print(f'{group}: /{rel}')
        return 0
    if os.geteuid()!=0:raise RuntimeError('Este paso escribe en /boot y /etc. Ejecuta ./instalar.sh --boot-only con sudo disponible.')
    if args.list:
        items=[]
        for path in sorted((deployment.state/'backups').glob('*/journal.json'),reverse=True):
            record=read(path,{})
            if record.get('id')==path.parent.name:
                item={key:record.get(key) for key in ('id','status','groups')}
                try:item['created_at']=datetime.datetime.fromisoformat(record['created_at']).timestamp()
                except (KeyError,ValueError,TypeError):item['created_at']=path.parent.stat().st_mtime
                items.append(item)
        items.sort(key=lambda item:item['created_at'],reverse=True)
        if args.events:emit('backups',items=items)
        else:print(json.dumps(items,ensure_ascii=False,indent=2))
        return 0
    deployment.state.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (deployment.state/'install.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.verify:deployment.verify()
        elif args.restore:deployment.restore(args.restore)
        else:deployment.apply()
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,RuntimeError,ValueError,subprocess.CalledProcessError) as error:
        print(f'Error: {error}',file=sys.stderr);sys.exit(1)
