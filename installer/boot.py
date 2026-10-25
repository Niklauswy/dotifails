#!/usr/bin/env python3
"""System appearance only. Never installs GRUB, never restarts or stops the display manager.

The greeter component sets up Wysun's login screen with greetd (the refinement terminal of the lock,
apps/shell/greeter.qml) and makes greetd the display manager for the next boot; the previous manager
is recorded in the journal and re-enabled on restore. Nothing is restarted now."""
import argparse
import configparser
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
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


GREETER = 'usr/local/share/wysun/greeter'
GREETER_FILES = ('GreeterRoot.qml', 'LockScene.qml', 'LockPalette.qml', 'WysunMark.qml', 'FounderFilm.qml')
GREETER_STATE = '/var/lib/greetd/wysun-greeter.json'
GREETER_LAUNCHER = """#!/bin/sh
# Wysun greeter (greetd): a minimal Hyprland showing the refinement terminal. If the compositor or
# the screen fail, fall back to greetd's own text login so the machine is never left without one.
flag="${XDG_RUNTIME_DIR:-/tmp}/wysun-greeter-failed"
umask 077
logdir="${XDG_STATE_HOME:-$HOME/.local/state}/wysun"
mkdir -p "$logdir" || exit 1
if [ -f "$logdir/greeter.log" ]; then
    mv -f "$logdir/greeter.log" "$logdir/greeter.previous.log"
fi
rm -f "$flag"
if Hyprland --config /usr/local/share/wysun/greeter/hyprland.conf >"$logdir/greeter.log" 2>&1 && [ ! -e "$flag" ]; then
    exit 0
fi
rm -f "$flag"
exec /usr/sbin/agreety --cmd "${SHELL:-/bin/sh}"
"""
GREETD_CONFIG = """# Wysun · greetd. Restore the previous display manager with installer/boot.py --restore ID.
[terminal]
vt = 7

[default_session]
command = "/usr/local/libexec/wysun-greeter"
user = "_greetd"
"""


# GRUB prints "Loading Linux…" / "Loading initial ramdisk…" in its terminal when an entry starts, and that
# terminal has no background of its own: a black box over the card. This script (after 00_header) gives it
# the card's own pixels under the box (term_c.png, stretched to the window) and redefines load_video, which
# Debian's Linux entries call first, to print in the card's blue: the messages vanish into the card. The
# console and the entry editor keep the normal colours. Verified in QEMU/OVMF with the real theme.
GRUB_QUIET_SCRIPT = r"""#!/bin/sh
# Wysun · boot messages print on the card instead of in a black box (written by installer/boot.py).
set -e
. "$pkgdatadir/grub-mkconfig_lib"
theme_dir=/boot/grub/themes/orbit
[ -f "$theme_dir/term_c.png" ] || exit 0
card="$(make_system_path_relative_to_its_root "$theme_dir/term_c.png")"
cat <<EOF
insmod gfxterm_background
insmod png
background_image -m stretch "(\$root)$card"
function load_video {
  if [ x\$feature_all_video_module = xy ]; then
    insmod all_video
  else
    insmod efi_gop
    insmod efi_uga
    insmod ieee1275_fb
    insmod vbe
    insmod vga
    insmod video_bochs
    insmod video_cirrus
  fi
  set color_normal=blue/black
}
EOF
"""


# When Plymouth quits, VT 1 shows the text login prompt (getty) until greetd switches to its VT for the
# greeter. Switching first, to the empty VT 7 (no cursor: vt.global_cursor_default=0), leaves a dark
# screen instead. Plymouth has already quit and VT 1 is in text mode, so the switch cannot hang; the
# timeout and the leading "-" make sure greetd starts whatever happens.
GREETD_VT_DROPIN = """# Wysun · go to the greeter's VT at once: no text login flashes in between (written by installer/boot.py).
[Service]
ExecStartPre=-/usr/bin/timeout 3 /usr/bin/chvt 7
"""
# Shutdown and reboot are over in a second or two, too fast to see the farewell. This unit holds the
# shutdown up to FAREWELL_SECONDS while Plymouth plays it; any key skips the wait. It only waits when
# Plymouth is actually showing, never longer than its own limit, and the system shuts down normally after.
FAREWELL_SECONDS = 12
FAREWELL = rf"""#!/bin/sh
# Wysun · let the farewell animation play before the machine powers off; any key skips it.
# (written by installer/boot.py)
command -v plymouth >/dev/null 2>&1 || exit 0
plymouth --ping 2>/dev/null || exit 0
plymouth watch-keystroke >/dev/null 2>&1 &
watcher=$!
ticks=0
while [ "$ticks" -lt {FAREWELL_SECONDS * 10} ] && kill -0 "$watcher" 2>/dev/null; do
    sleep 0.1
    ticks=$((ticks + 1))
done
kill "$watcher" 2>/dev/null
exit 0
"""
FAREWELL_UNIT = f"""# Wysun · the farewell plays before power-off (written by installer/boot.py).
[Unit]
Description=Wysun farewell animation (any key skips it)
DefaultDependencies=no
After=plymouth-poweroff.service plymouth-reboot.service plymouth-halt.service plymouth-kexec.service
Before=shutdown.target umount.target final.target

[Service]
Type=oneshot
ExecStart=/usr/local/libexec/wysun-farewell
TimeoutStartSec={FAREWELL_SECONDS + 8}
"""
FAREWELL_WANTS = """# Wysun · play the farewell on the way down (written by installer/boot.py).
[Unit]
Wants=wysun-farewell.service
"""


def keyboard(path):
    """XKB settings from /etc/default/keyboard, so the password is typed in the system's layout."""
    values = {'XKBLAYOUT': 'us', 'XKBVARIANT': '', 'XKBOPTIONS': ''}
    if path.is_file():
        for line in path.read_text().splitlines():
            key, _, value = line.partition('=')
            if key.strip() in values:
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def greeter_compositor(layout):
    return f"""# Wysun greeter compositor (written by installer/boot.py).
monitor = , preferred, auto, 1
input {{
    kb_layout = {layout['XKBLAYOUT']}
    kb_variant = {layout['XKBVARIANT']}
    kb_options = {layout['XKBOPTIONS']}
}}
misc {{
    disable_hyprland_logo = true
    disable_splash_rendering = true
    force_default_wallpaper = 0
}}
animations {{
    enabled = false
}}
ecosystem {{
    no_update_news = true
    no_donation_nag = true
}}
env = WYSUN_GREETER_STATE,{GREETER_STATE}
env = WYSUN_GREETER_SCHEME,/{GREETER}/scheme.json
env = WYSUN_GREETER_MONO,DejaVu Sans Mono
env = WYSUN_LOCK_SHADERS,/{GREETER}/shaders
env = QT_QPA_PLATFORM,wayland
exec-once = sh -c '/usr/bin/quickshell --no-color --log-times -p /{GREETER}/greeter.qml >>"${{XDG_STATE_HOME:-$HOME/.local/state}}/wysun/greeter.log" 2>&1 || touch "$XDG_RUNTIME_DIR/wysun-greeter-failed"; hyprctl dispatch exit'
"""


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
        self.components=set(('grub','plymouth') if components is None else components)
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
                '# The kernel keeps GRUB\'s graphics mode: no mode switch flicker before the splash.\n'
                'GRUB_GFXPAYLOAD_LINUX=keep\n'
                '# Keep kernel flags, encryption, timeout and default entries unchanged; only add the\n'
                '# splash and hide the text cursor when they are missing.\n'
                'case " $GRUB_CMDLINE_LINUX $GRUB_CMDLINE_LINUX_DEFAULT " in\n'
                '  *" splash "*) ;;\n'
                '  *) GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT quiet splash" ;;\n'
                'esac\n'
                'case " $GRUB_CMDLINE_LINUX $GRUB_CMDLINE_LINUX_DEFAULT " in\n'
                '  *" vt.global_cursor_default="*) ;;\n'
                '  *) GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT vt.global_cursor_default=0" ;;\n'
                'esac\n'))
            plans.append(('grub','etc/grub.d/06_wysun',GRUB_QUIET_SCRIPT))
            # A distro may force text output. Leave serial consoles intact.
            configs=[self.path('etc/default/grub'),*self.path('etc/default/grub.d').glob('*.cfg')]
            serial=any('serial' in line for p in configs for line in p.read_text().splitlines()
                       if line.strip().startswith(('GRUB_TERMINAL=', 'GRUB_TERMINAL_OUTPUT=')))
            if not serial: plans[-1]=(plans[-1][0],plans[-1][1],plans[-1][2]+'GRUB_TERMINAL_OUTPUT=gfxterm\n')
        if 'plymouth' in self.components and self.path('usr/share/plymouth/themes').is_dir():
            plans.append(('plymouth','usr/share/plymouth/themes/orbit',self.source/'system/boot/plymouth'))
            config=self.path('etc/plymouth/plymouthd.conf')
            # Show the splash at once instead of after the distribution's delay.
            plans.append(('plymouth','etc/plymouth/plymouthd.conf',merged_ini(config,'Daemon',{'Theme':'orbit','ShowDelay':'0'})))
            plans.append(('plymouth','usr/local/libexec/wysun-farewell',FAREWELL))
            plans.append(('plymouth','etc/systemd/system/wysun-farewell.service',FAREWELL_UNIT))
            for target in ('poweroff','reboot','halt'):
                plans.append(('plymouth',f'etc/systemd/system/{target}.target.d/wysun-farewell.conf',FAREWELL_WANTS))
            # Never `plymouth quit --retain-splash` here: it leaves VT 1 in graphics mode and greetd then waits
            # forever to switch to its VT (no login screen at all on the first real test).
        self.skipped=[]
        if 'greeter' in self.components and not self.path('usr/sbin/greetd').exists():
            self.skipped.append('Pantalla de acceso omitida: falta greetd. Instálalo con '
                                '«sudo apt install greetd qt6-shader-baker» y repite ./instalar.sh --boot-only.')
        if 'greeter' in self.components and self.path('usr/sbin/greetd').exists():
            plans.extend([
                ('greeter',GREETER,('greeter',)),
                ('greeter','usr/local/libexec/wysun-greeter',GREETER_LAUNCHER),
                ('greeter','etc/greetd/config.toml',GREETD_CONFIG),
                ('greeter','etc/systemd/system/greetd.service.d/wysun-vt.conf',GREETD_VT_DROPIN),
                ('greeter','etc/X11/default-display-manager','/usr/sbin/greetd\n')])
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

    def display_manager(self):
        manager=self.path('etc/X11/default-display-manager')
        return Path(manager.read_text().strip()).name if manager.is_file() else None

    def systemctl(self, *arguments):
        command=['systemctl']
        if self.root!=Path('/'):command.append(f'--root={self.root}')
        self.runner([*command,*arguments])

    def switch_manager(self, previous, target):
        """Enable ``target`` as display-manager.service for the next boot; never starts or stops one."""
        if previous and previous!=target:self.systemctl('disable',f'{previous}.service')
        self.systemctl('enable','--force',f'{target}.service')

    def build_greeter(self, target):
        """The login screen: the lock's portable scene, a Severance palette, shaders and its compositor."""
        shell=self.source/'apps/shell'
        (target/'modules/lockscreen/shaders').mkdir(parents=True)
        shutil.copy2(shell/'greeter.qml',target/'greeter.qml')
        for name in GREETER_FILES:
            shutil.copy2(shell/'modules/lockscreen'/name,target/'modules/lockscreen'/name)
        # The founder's film (the reward at 100 %): only its pixel art, not the tool that prepares it.
        (target/'modules/lockscreen/film').mkdir()
        for art in sorted((shell/'modules/lockscreen/film').glob('*.png')):
            shutil.copy2(art,target/'modules/lockscreen/film'/art.name)
        # The sign-in screen always wears the Severance palette of the lock, whatever the desktop's colours.
        palette=json.loads((shell/'modules/lockscreen/severance-scheme.json').read_text())
        (target/'scheme.json').write_text(json.dumps({**palette,'flavour':'greeter'},indent=2)+'\n')
        (target/'hyprland.conf').write_text(greeter_compositor(keyboard(self.path('etc/default/keyboard'))))
        # Shaders for the distribution's Qt; without qsb the screen is drawn flat and still works.
        qsb=self.path('usr/lib/qt6/bin/qsb')
        shaders=target/'shaders';shaders.mkdir()
        if qsb.is_file():
            for source in sorted((shell/'modules/lockscreen/shaders').glob('*.frag')):
                self.runner([str(qsb),'--glsl','300es,330','-o',str(shaders/(source.name+'.qsb')),str(source)])

    def apply(self):
        plans=self.plan()
        for notice in self.skipped:print(notice,flush=True)
        if not plans: raise RuntimeError('No se encontró GRUB, Plymouth ni greetd.')
        conflicts=[rel for _,rel,_ in plans if rel in self.receipt and fingerprint(self.path(rel))!=self.receipt[rel]]
        if conflicts: raise RuntimeError('Se conservaron cambios locales; revisa: '+', '.join(conflicts))
        groups={group for group,_,_ in plans}
        required=[]
        if 'grub' in groups: required+=['grub-mkconfig','grub-script-check']
        if 'plymouth' in groups: required+=['update-initramfs']
        if 'greeter' in groups: required+=['greetd','agreety','Hyprland','quickshell','systemctl']
        if self.root==Path('/'):
            for command in required:
                if not shutil.which(command, path='/usr/sbin:/usr/bin:/sbin:/bin'):
                    raise RuntimeError(f'Falta {command}; ejecuta la instalación completa para preparar dependencias.')
        ident=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
        backup=self.state/'backups'/ident;backup.mkdir(parents=True,mode=0o700)
        journal={'id':ident,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'running','operations':[],'groups':[], 'receipt_before':self.receipt.copy()}
        if 'greeter' in groups:journal['display_manager']={'before':self.display_manager(),'after':'greetd'}
        save(backup/'journal.json',journal)
        emit('system_backup',id=ident,path=str(backup))
        try:
            for group,rel,payload in plans:
                target=self.path(rel);stage=backup/'staged'/rel
                if isinstance(payload,tuple):
                    self.build_greeter(stage)
                    copy(stage,stage.with_name(stage.name+'.normalized'),normalize=True)
                    remove(stage);stage.with_name(stage.name+'.normalized').rename(stage)
                elif isinstance(payload,Path):
                    fingerprint(payload)
                    copy(payload,stage,normalize=True)
                    # Templates stay in the repository; the system gets the generated files only.
                    for template in stage.rglob('*.in') if stage.is_dir() else ():template.unlink()
                else:
                    stage.parent.mkdir(parents=True,exist_ok=True);stage.write_text(payload)
                    executable=rel.startswith(('usr/local/libexec/','etc/grub.d/'))
                    stage.chmod(0o755 if executable else target.stat().st_mode & 0o777 if target.exists() else 0o644)
                before=fingerprint(target);after=fingerprint(stage)
                if before==after: self.receipt[rel]=after;continue
                if target.exists(): copy(target,backup/'before'/rel)
                journal['operations'].append({'path':rel,'before':before,'after':after})
                if group not in journal['groups']: journal['groups'].append(group)
                save(backup/'journal.json',journal)
                remove(target);copy(stage,target);self.receipt[rel]=after
            self.refresh(set(journal['groups']),backup,journal)
            if 'greeter' in journal['groups']:
                manager=journal['display_manager']
                self.switch_manager(manager['before'],'greetd')
                manager['switched']=True;save(backup/'journal.json',journal)
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
        manager=journal.get('display_manager') or {}
        if manager.get('switched') and manager.get('before') and manager['before']!='greetd':
            self.switch_manager('greetd',manager['before'])
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
    parser.add_argument('--components',default='grub,plymouth',help='Pantallas que se aplicarán, separadas por comas')
    parser.add_argument('--list',action='store_true',help='Listar respaldos del arranque')
    parser.add_argument('--events',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.events:os.environ['DOTIFAILS_EVENTS']='1'
    deployment=BootDeployment(args.source,components=args.components.split(','))
    if args.dry_run:
        for group,rel,_ in deployment.plan():print(f'{group}: /{rel}')
        for notice in deployment.skipped:print(notice)
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
