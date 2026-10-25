"""What the installer will do, in words: phases, components and checks shared by the UI and its preview.

Pure Python (no Qt). Phase names are the exact stage names ``main.py install`` emits, so the
plan shown before installing is the timeline that lights up while it runs.
"""
import shutil

# Component copy for the window. Keys are install_model.COMPONENTS.
COMPONENTS = {
    'wayland': dict(symbol='desktop_windows', title='Sesión Wysun / Hyprland',
                    detail='Compositor, barra y paneles, lanzador, Settings, capturas con OCR, grabación, bloqueo y fondos animados.',
                    includes=('Hyprland', 'Shell', 'Lanzador', 'Settings', 'Capturas', 'Bloqueo', 'Runtime Qt')),
    'desktop': dict(symbol='apps', title='Aplicaciones Wysun',
                    detail='Music, Files, Recorder, Notas, colores y las utilidades del escritorio, con sus fuentes e iconos.',
                    includes=('Music', 'Files', 'Recorder', 'Notas', 'Temas')),
    'terminal': dict(symbol='terminal', title='Terminal',
                     detail='Ghostty con Zsh, Starship y versiones por proyecto con mise.',
                     includes=('Ghostty', 'Zsh', 'Starship', 'mise')),
    'editor': dict(symbol='code', title='Neovim',
                   detail='Editor configurado con lenguajes, autocompletado y depuración.',
                   includes=('Neovim', 'LSP', 'DAP')),
    'tools': dict(symbol='construction', title='Wysun Tools',
                  detail='Utilidades de desarrollo, red y transferencia de archivos.',
                  includes=()),
    'boot': dict(symbol='power_settings_new', title='Arranque Macrodata',
                 detail='GRUB, la carga y la pantalla de acceso como terminal de refinamiento.',
                 includes=()),
}
BOOT = {
    'grub': ('Menú GRUB', 'Selector de archivos de Macrodata.'),
    'plymouth': ('Carga, apagado y reinicio', 'El refinamiento de Cold Harbor durante el arranque.'),
    'greeter': ('Pantalla de acceso', 'La terminal del bloqueo como inicio de sesión, con greetd.'),
}
EXTRAS = {
    'brave': ('Brave', 'Navegador', 'public'),
    'discord': ('Discord', 'Comunidades y llamadas', 'group'),
    'obsidian': ('Obsidian', 'Notas enlazadas', 'description'),
}
# What the window offers: the desktop is always there; three pieces and three apps are optional.
CORE = ('wayland', 'desktop', 'terminal')
ADDONS = {
    'editor': ('code', 'Neovim', 'Editor con lenguajes, autocompletado y depuración.', 6),
    'tools': ('construction', 'Wysun Tools', 'Utilidades de desarrollo, red y transferencia.', 7),
    'boot': ('power_settings_new', 'Macrodata', 'GRUB, carga y acceso como terminal de refinamiento.', 12),
}
PRESETS = {
    'complete': ('Completo', ('wayland', 'desktop', 'terminal', 'editor', 'tools', 'boot')),
    'essential': ('Esencial', ('wayland', 'desktop', 'terminal')),
}
# Read-only checks about the machine itself; the rest depend on the selection.
HOST_CHECKS = ('system', 'user', 'sudo', 'space', 'system-space', 'paths', 'lock',
               'apt-get', 'apt-cache', 'dpkg-query', 'package-health', 'network')

SYMBOLS = {
    'Repositorios oficiales de la distribución': ('dns', 'Añade solo los backports oficiales de tu distribución si faltan.'),
    'Índices APT y compatibilidad de dependencias': ('sync', 'Actualiza los índices y simula la resolución antes de tocar paquetes.'),
    'Actualización del sistema': ('system_update_alt', 'Actualiza tus paquetes sin retirar ninguno ni cambiar de distribución.'),
    'Paquetes del sistema': ('archive', 'Instala las dependencias de tu selección con APT.'),
    'Herramientas verificadas': ('verified_user', 'Descarga herramientas fijadas y comprueba su suma.'),
    'Configuraciones y respaldos': ('backup', 'Respalda tus archivos y copia Wysun, sus dotfiles y su runtime.'),
    'Aplicación Wysun': ('apps', 'Actualiza las aplicaciones, el shell y el runtime si cambió.'),
    'Instalador y recuperación': ('history', 'Actualiza este instalador y sus accesos.'),
    'Registrar sesión Wysun / Hyprland': ('login', 'Añade la sesión a tu gestor de acceso sin cambiar la predeterminada.'),
    'Arranque y acceso': ('power_settings_new', 'Respalda y aplica el arranque Macrodata, y comprueba la configuración generada.'),
    'Lenguajes y plugins de Neovim': ('code', 'Prepara lenguajes, plugins y herramientas del editor.'),
    'Aplicaciones opcionales': ('apps', 'Instala tus aplicaciones Flatpak para tu usuario.'),
    'Caché de terminal': ('terminal', 'Reconstruye la caché de resaltado de bat.'),
    'Fuentes del escritorio': ('format_paint', 'Actualiza la caché de fuentes.'),
    'Verificación final': ('check_circle', 'Comprueba que cada componente quedó completo.'),
}


def phase(name):
    symbol, detail = SYMBOLS.get(name, ('fiber_manual_record', ''))
    return dict(name=name, symbol=symbol, detail=detail)


def phases(plan, batcat=None):
    """Stages ``main.py install`` runs for ``plan`` (an InstallOptions.summary()), in order."""
    selected = set(plan.get('components', ()))
    config_only = plan.get('config_only', False)
    names = []
    if not config_only:
        if plan.get('prepare_repositories'):
            names.append('Repositorios oficiales de la distribución')
        if plan.get('prepare_repositories') or plan.get('upgrade_system'):
            names.append('Índices APT y compatibilidad de dependencias')
        if plan.get('upgrade_system'):
            names.append('Actualización del sistema')
        names += ['Paquetes del sistema', 'Herramientas verificadas']
    names.append('Configuraciones y respaldos')
    if not config_only:
        if 'wayland' in selected:
            names.append('Registrar sesión Wysun / Hyprland')
        if 'boot' in selected:
            names.append('Arranque y acceso')
        if 'editor' in selected and not plan.get('skip_nvim_tools'):
            names.append('Lenguajes y plugins de Neovim')
        if plan.get('extras'):
            names.append('Aplicaciones opcionales')
    if 'terminal' in selected and (shutil.which('batcat') if batcat is None else batcat):
        names.append('Caché de terminal')
    if not config_only and selected & {'desktop', 'terminal'}:
        names.append('Fuentes del escritorio')
    if not config_only:
        names.append('Verificación final')
    return [phase(name) for name in names]


UPDATE_PHASES = ('Configuraciones y respaldos', 'Aplicación Wysun', 'Instalador y recuperación')


def update_phases():
    """Stages of ``install --wysun-only``."""
    return [phase(name) for name in UPDATE_PHASES]


def system_name(fields):
    return fields.get('PRETTY_NAME') or fields.get('NAME') or 'Distribución sin identificar'


def supported(fields, machine):
    major = fields.get('VERSION_ID', '').split('.')[0]
    return machine == 'x86_64' and ((fields.get('ID') == 'debian' and major == '13') or
                                    (fields.get('ID') == 'parrot' and major == '7'))


def backports_suite(fields):
    major = fields.get('VERSION_ID', '').split('.')[0]
    return {('debian', '13'): 'trixie-backports', ('parrot', '7'): 'echo-backports'}.get((fields.get('ID'), major))


def preview_checks(fields, machine):
    """Demonstration results for the preview: plausible, labelled, and never measured."""
    name = system_name(fields) if supported(fields, machine) else 'Debian GNU/Linux 13 (trixie)'
    note = ' · simulado'
    return [
        dict(key='system', level='ok', title=name, detail='x86_64 · compatible' + note),
        dict(key='sudo', level='ok', title='Autorización del sistema', detail='Se solicitaría mediante sudo al instalar' + note),
        dict(key='space', level='ok', title='42.0 GB disponibles en el hogar', detail='Margen de trabajo suficiente' + note),
        dict(key='system-space', level='ok', title='18.5 GB disponibles en el sistema', detail='Margen para paquetes y caché' + note),
        dict(key='package-health', level='ok', title='Estado de los paquetes', detail='Sin operaciones pendientes de APT/dpkg' + note),
        dict(key='paths', level='ok', title='Destino y configuración', detail='Las configuraciones existentes se respaldarían' + note),
        dict(key='network', level='info', title='Conexión a Internet necesaria', detail='La vista previa no se conecta a ningún repositorio.'),
    ]


def host_checks(checks):
    return [check for check in checks if check['key'] in HOST_CHECKS]


def selection_checks(checks):
    return [check for check in checks if check['key'] not in HOST_CHECKS]


def blocking(checks):
    return [check for check in checks if check['level'] == 'error']


def selection_title(components, extras=()):
    """«Wysun + Neovim + Blue CRT»: the choice in a few words."""
    names = ['Wysun'] + [ADDONS[key][1] for key in ADDONS if key in components] + [EXTRAS[key][0] for key in EXTRAS if key in extras]
    return ' + '.join(names)


def summary_line(plan):
    """One line for the action bar: what the plan amounts to."""
    if not plan:
        return ''
    parts = [f"{len(plan['components'])} componentes"]
    if plan.get('config_only'):
        parts.append('solo configuraciones')
    else:
        parts.append(f"{len(plan['packages'])} paquetes")
    if plan.get('upgrade_system'):
        parts.append('sistema al día')
    return ' · '.join(parts)


SHORTCUTS = (
    (('Super', 'Espacio'), 'Lanzador'),
    (('Super', 'Enter'), 'Terminal'),
    (('Super', 'Alt', 'F'), 'Files'),
    (('Super', 'Alt', ','), 'Settings'),
    (('Super', '/'), 'Todos los atajos'),
    (('Super', 'X'), 'Sesión'),
)
