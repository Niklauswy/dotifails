"""Installation choices and read-only checks shared by the CLI and native wizard."""
from dataclasses import dataclass, field
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


COMPONENTS = {
    'desktop': ('Aplicaciones Wysun', 'Music, Files, Recorder, fuentes, iconos y las utilidades del escritorio.'),
    'wayland': ('Escritorio y sesión', 'Hyprland, shell, lanzador, Settings, capturas, bloqueo y runtime privado.'),
    'terminal': ('Terminal y shell', 'Ghostty, Zsh, Starship y versiones por proyecto con mise.'),
    'editor': ('Neovim', 'Editor, lenguajes, autocompletado y depuración.'),
    'tools': ('Herramientas personales', 'Utilidades de desarrollo, red y transferencia de archivos.'),
    'boot': ('Arranque Macrodata', 'GRUB, carga y pantalla de acceso como terminal de refinamiento.'),
}
DEFAULT_COMPONENTS = tuple(COMPONENTS)
BOOT_COMPONENTS = {'grub': 'Menú GRUB', 'plymouth': 'Carga, apagado y reinicio', 'greeter': 'Pantalla de acceso (greetd)'}
ARTIFACTS = {
    'desktop': {'yt-dlp'},
    'terminal': {'ghostty', 'starship', 'ohmyzsh', 'zsh-autosuggestions', 'zsh-syntax-highlighting', 'mise', 'nvm', 'node'},
    'editor': {'nvim', 'node'},
    'tools': set(), 'boot': set(), 'wayland': set(),
}
WYSUN = Path(__file__).resolve().parents[1] / 'apps/wysun'


def theme_core():
    """The shared theme selection rules (apps/wysun/theme_core.py), loaded from the source tree."""
    import sys
    from ui_support import prepare_imports
    prepare_imports()
    import theme_core as module
    return module


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def normalize_components(values=None):
    selected = set(DEFAULT_COMPONENTS if values is None else values)
    unknown = selected - COMPONENTS.keys()
    if unknown:
        raise ValueError('Componentes desconocidos: ' + ', '.join(sorted(unknown)))
    if not selected:
        raise ValueError('Selecciona al menos un componente.')
    if selected & {'desktop', 'editor'}:
        selected.add('terminal')
    return tuple(key for key in COMPONENTS if key in selected)


def package_names(source, components, extras=(), boot_components=None, inspect_installed=True):
    manifest = load_json(Path(source) / 'manifests/packages.json', {})
    groups = manifest.get('components', {})
    names = list(groups.get('base', manifest.get('development', [])))
    for key in normalize_components(components):
        if key=='boot' and manifest.get('boot_components'):
            for screen in (('grub', 'plymouth') if boot_components is None else boot_components):
                names.extend(manifest['boot_components'][screen])
        else:
            names.extend(groups.get(key, manifest.get(key, [])))
    if extras:
        names.append('flatpak')
    if 'wayland' in components:
        from wayland import package_specs
        if inspect_installed:
            names.extend(package_specs(source, read_os_release()))
        else:
            from wayland import RELEASES
            suite = RELEASES.get(read_os_release().get('ID'), 'trixie-backports')
            names.extend(name + '/' + suite for name in manifest.get('wayland_backports', []))
        names.extend(load_json(Path(source) / 'manifests/runtime.json', {}).get('build_packages', []))
    return list(dict.fromkeys(names))


@dataclass
class InstallOptions:
    source: Path
    home: Path = field(default_factory=Path.home)
    components: tuple = field(default_factory=lambda: DEFAULT_COMPONENTS)
    extras: tuple = ()
    # The greetd login screen is experimental: only with an explicit request (never by default).
    boot_components: tuple = field(default_factory=lambda: ('grub', 'plymouth'))
    config_only: bool = False
    skip_nvim_tools: bool = False
    profile: str | None = None
    upgrade_system: bool = False
    prepare_repositories: bool = False

    def validate(self):
        self.source = Path(self.source).expanduser().resolve()
        self.home = Path(self.home).expanduser().absolute()
        self.components = normalize_components(self.components)
        if set(self.extras) - {'brave', 'discord', 'obsidian'}:
            raise ValueError('Aplicación opcional desconocida.')
        if set(self.boot_components) - BOOT_COMPONENTS.keys():
            raise ValueError('Componente de arranque desconocido.')
        if 'boot' in self.components and not self.boot_components:
            raise ValueError('Selecciona al menos una pantalla de arranque.')
        if self.config_only and 'boot' in self.components:
            raise ValueError('El modo de configuración no modifica el arranque.')
        if self.config_only and self.extras:
            raise ValueError('El modo de configuración no instala aplicaciones.')
        if self.config_only and (self.upgrade_system or self.prepare_repositories):
            raise ValueError('El modo de configuración no actualiza el sistema ni los repositorios.')
        if not self.config_only and self.home != Path.home():
            raise ValueError('La instalación del sistema utiliza tu hogar actual.')
        if self.profile and (self.profile != 'samsung-touchscreen' or 'desktop' not in self.components):
            raise ValueError('El perfil Samsung requiere el escritorio y selección explícita.')
        return self

    def argv(self):
        self.validate()
        args = ['install', '--source', str(self.source), '--target-home', str(self.home),
                '--components', ','.join(self.components)]
        if self.extras:
            args += ['--extras', ','.join(self.extras)]
        if 'boot' in self.components:
            args += ['--boot-components', ','.join(self.boot_components)]
        if self.config_only:
            args += ['--config-only']
        if self.skip_nvim_tools:
            args += ['--skip-nvim-tools']
        if self.profile:
            args += ['--profile', self.profile]
        if self.upgrade_system:
            args += ['--upgrade-system']
        if self.prepare_repositories:
            args += ['--prepare-repositories']
        return args

    def summary(self, preview=False):
        self.validate()
        artifacts = load_json(self.source / 'manifests/artifacts.json', {})
        included = set().union(*(ARTIFACTS[key] for key in self.components))
        return {
            'source': str(self.source), 'home': str(self.home),
            'components': list(self.components),
            'extras': list(self.extras), 'boot_components': list(self.boot_components) if 'boot' in self.components else [],
            'config_only': self.config_only, 'skip_nvim_tools': self.skip_nvim_tools, 'profile': self.profile,
            'upgrade_system': self.upgrade_system, 'prepare_repositories': self.prepare_repositories,
            'packages': [] if self.config_only else package_names(self.source, self.components, self.extras, self.boot_components, inspect_installed=not preview),
            'artifacts': {} if self.config_only else {k: v['version'] for k, v in artifacts.items() if k in included},
            'command': self.argv(),
            'apt_backports_suite': (__import__('wayland').RELEASES.get(read_os_release().get('ID'))
                                   if 'wayland' in self.components and not self.config_only else None),
        }


def read_os_release(path=Path('/etc/os-release')):
    try:
        return {k: v.strip('"') for k, v in (line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)}
    except OSError:
        return {}


def preflight(options):
    """No downloads, authentication, writes or privileged reads during review."""
    results = []
    def add(key, level, title, detail):
        results.append(dict(key=key, level=level, title=title, detail=detail))
    try:
        options.validate()
    except ValueError as error:
        add('options', 'error', 'Revisa la selección', str(error))
        return results
    fields = read_os_release()
    ident, major = fields.get('ID'), fields.get('VERSION_ID', '').split('.')[0]
    supported = platform.machine() == 'x86_64' and ((ident == 'debian' and major == '13') or (ident == 'parrot' and major == '7'))
    add('system', 'ok' if supported else ('warning' if options.config_only else 'error'),
        fields.get('PRETTY_NAME', 'Sistema no identificado'),
        platform.machine() + (' · compatible' if supported else ' · requiere Debian 13 o Parrot 7, x86_64'))
    required = ['installer/main.py', 'manifests/packages.json', 'manifests/artifacts.json', 'manifests/themes.json']
    if 'boot' in options.components:
        required += ['installer/boot.py', 'system/boot/grub/theme.txt', 'system/boot/plymouth/orbit.script', 'apps/shell/greeter.qml']
    if 'desktop' in options.components:
        required += ['apps/wysun/orbit.py']
    if 'tools' in options.components:
        required += ['apps/tools/cli.py', 'bin/orbit-tools']
    if 'wayland' in options.components:
        required += ['apps/shell/shell.qml', 'config/.config/wysun/hyprland.lua', 'bin/wysun-session', 'installer/session_registration.py']
    missing = [name for name in required if not (options.source / name).is_file()]
    add('source', 'error' if missing else 'ok', 'Archivos del instalador',
        'Faltan: ' + ', '.join(missing) if missing else 'Copia local completa para la selección.')
    if 'wayland' in options.components and not options.config_only and supported and options.prepare_repositories:
        from repositories import repository_spec, enabled
        suite = repository_spec(fields)[0]
        add('wayland-repository', 'info', 'Repositorio nativo: ' + suite,
            ('Ya habilitado. ' if enabled(Path('/'), suite) else 'Se habilitará con su clave oficial. ') +
            'APT actualizará los índices y verificará versiones y dependencias antes de instalar paquetes.')
    elif 'wayland' in options.components and not options.config_only and supported:
        from wayland import check_repository, simulate_packages
        try:
            specs = check_repository(options.source, fields)
            simulate_packages(options.source, fields, package_names(options.source, options.components, options.extras, options.boot_components))
            add('wayland-repository', 'ok', 'Paquetes Wayland', ', '.join(specs))
        except RuntimeError as error:
            add('wayland-repository', 'error', 'Revisa los repositorios nativos', str(error))
    if os.geteuid() == 0 and not options.config_only:
        add('user', 'error', 'Abre el instalador con tu usuario', 'La autorización de administrador se solicita solo cuando hace falta.')
    elif not options.config_only:
        add('sudo', 'ok' if shutil.which('sudo') else 'error', 'Autorización del sistema',
            'Se solicitará mediante sudo al instalar.' if shutil.which('sudo') else 'Instala sudo y configura el acceso de tu usuario.')
    ancestor = options.home
    while not ancestor.exists() and ancestor.parent != ancestor:
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free
    minimum = 512 * 1024**2 if options.config_only else 4 * 1024**3
    add('space', 'ok' if free >= minimum else 'error', f'{free / 1024**3:.1f} GB disponibles en el hogar',
        'Margen mínimo de trabajo; el tamaño final depende de paquetes, caché y respaldos.')
    if not options.config_only:
        system_free = shutil.disk_usage('/').free
        add('system-space', 'ok' if system_free >= 2 * 1024**3 else 'error', f'{system_free / 1024**3:.1f} GB disponibles en el sistema', 'Se reserva un margen mínimo de 2 GB para los paquetes.')
    paths = [options.home / relative for relative in ('.config', '.local', '.local/share', '.local/state', '.cache')]
    unsafe = [str(path) for path in paths if path.is_symlink() or (path.exists() and (not path.is_dir() or not os.access(path, os.W_OK)))]
    if not os.access(ancestor, os.W_OK):
        unsafe.append(str(ancestor))
    add('paths', 'error' if unsafe else 'ok', 'Destino y configuración',
        'Revisa permisos o enlaces: ' + ', '.join(unsafe) if unsafe else 'Las configuraciones existentes se respaldan antes de reemplazarlas.')
    lock = options.home / '.local/state/dotifails/install.lock'
    if lock.is_file():
        try:
            with lock.open('r') as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            add('lock', 'ok', 'Instalador disponible', 'No hay otra operación activa.')
        except (OSError, BlockingIOError):
            add('lock', 'error', 'Otra operación está activa', 'Espera a que termine antes de continuar.')
    if not options.config_only:
        add('network', 'info', 'Conexión a Internet necesaria', 'Los repositorios se comprobarán al descargar; esta revisión no hace solicitudes de red.')
        for command in ('apt-get', 'apt-cache', 'dpkg-query'):
            add(command, 'ok' if shutil.which(command) else 'error', command,
                'Disponible para comprobar paquetes.' if shutil.which(command) else 'Falta el gestor de paquetes de Debian.')
        if supported and shutil.which('dpkg'):
            try:
                audit = subprocess.run(['dpkg', '--audit'], text=True, capture_output=True, timeout=15)
                pending = audit.stdout.strip() or audit.stderr.strip()
                add('package-health', 'error' if audit.returncode or pending else 'ok', 'Estado de los paquetes',
                    'Hay una operación de paquetes pendiente. Completa la configuración de APT/dpkg antes de instalar.\n' + pending
                    if audit.returncode or pending else 'No hay paquetes pendientes de configuración.')
            except (OSError, subprocess.TimeoutExpired) as error:
                add('package-health', 'error', 'No se pudo comprobar APT/dpkg', str(error))
        if 'boot' in options.components:
            if 'grub' in options.boot_components:
                active = Path('/etc/default/grub').is_file() and Path('/boot/grub').is_dir()
                add('grub', 'ok' if active else 'error', 'Arranque GRUB',
                    'Se aplicará el tema Macrodata y se comprobará la configuración generada.' if active else
                    'No se detecta una instalación de GRUB. Desmarca GRUB o prepara tu gestor de arranque antes de continuar.')
    return results


def backups(home):
    root = Path(home) / '.local/state/dotifails/backups'
    entries = []
    for path in root.glob('*/journal.json'):
        record = load_json(path, {})
        if record and record.get('id') == path.parent.name:
            try:
                created=datetime.fromisoformat(record['created_at']).timestamp()
            except (KeyError, ValueError, TypeError):
                created=path.parent.stat().st_mtime
            entries.append(dict(id=record['id'], status=record.get('status', 'unknown'),
                                operations=len(record.get('operations', [])), path=str(path.parent),
                                conflicts=record.get('conflicts', []), created_at=created))
    return sorted(entries, key=lambda item:item['created_at'], reverse=True)
