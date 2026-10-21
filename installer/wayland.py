"""Wayland deployment for Wysun / Hyprland; owned paths are updated in place."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys


RELEASES = {'debian': 'trixie-backports', 'parrot': 'echo-backports'}


def package_specs(source, fields):
    """Use the distribution's own repository; never add or mix repositories."""
    suite = RELEASES[fields['ID']]
    manifest = json.loads((Path(source) / 'manifests/packages.json').read_text())
    names = list(manifest['wayland_backports'])
    # Installed development packages from the same source require exact ABI
    # versions. Select those siblings explicitly instead of upgrading all audio
    # and network packages through a global -t policy.
    for name in manifest.get('wayland_installed_abi_companions', []):
        result = subprocess.run(['dpkg-query', '-W', '-f=${db:Status-Status}', name],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
        if result.returncode == 0 and result.stdout.strip() == 'installed':
            names.append(name)
    return [name + '/' + suite for name in names]


def check_repository(source, fields):
    specs = package_specs(source, fields)
    for spec in specs:
        result = subprocess.run(['apt-cache', 'show', spec], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if result.returncode or not result.stdout.strip():
            raise RuntimeError('Falta ' + spec + '. Consulta docs/wayland.md; no se añadirán repositorios automáticamente.')
        supported = {'hyprland': '0.55', 'xdg-desktop-portal-hyprland': '1.4', 'hyprpicker': '0.4'}
        name = spec.split('/')[0]
        if name in supported:
            versions = re.findall(r'^Version: (.+)$', result.stdout, re.M)
            if not versions or not re.match(r'(?:\d+:)?' + re.escape(supported[name]) + r'\.', versions[0]):
                raise RuntimeError(name + ' requiere la serie comprobada ' + supported[name] +
                                   '.x; revisa y prueba el nuevo runtime antes de instalar otra versión.')
    return specs


def simulate_packages(source, fields, wanted):
    """Resolve the full ABI closure without changing APT state or packages."""
    check_repository(source, fields)
    command = ['apt-get', '--simulate', '--no-remove', 'install', '--no-install-recommends', *wanted]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=60)
    if result.returncode or re.search(r'^Remv ', result.stdout, re.M):
        raise RuntimeError('Plan APT Wayland incompatible; no se aplicó.\n' + result.stdout)
    return result.stdout


def configure(deployment):
    from capture_distribution import _publish
    d = deployment
    d.stage('Sesión adicional Wysun / Hyprland')
    # Shared applications retain their existing storage and command identities.
    for source, target in (('apps/wysun', '.local/share/orbit/app'),
                           ('apps/tools', '.local/share/orbit/tools'),
                           ('apps/shell', '.local/share/wysun/quickshell')):
        if not (d.source / source).is_dir():
            raise RuntimeError('Fuente incompleta: ' + source)
        _publish_asset(d, d.source / source, target)
    if any(p in d.conflicts for p in ('.local/share/orbit/app', '.local/share/wysun/quickshell')):
        return
    migrate_legacy_names(d)
    ensure_runtime(d)
    d.deploy(d.source / 'config/.local/bin/orbit', Path('.local/bin/orbit'))
    for name in ('orbit-files', 'orbit-tools', 'wysun-shell',
                 'wysun-session', 'wysun-session-services', 'wysun-lock', 'wysun-wm', 'wysun-control', 'wysun-workspaces', 'wysun-share-picker', 'wysun-recover', 'wysun-idle'):
        _publish(d, (d.source / 'bin' / name).read_text(), '.local/bin/' + name, executable=True)
    # A terminal must remain reachable even without the optional terminal component.
    _publish(d, '#!/bin/sh\nif command -v ghostty >/dev/null 2>&1; then exec ghostty "$@"; fi\n'
             'exec foot "$@"\n', '.local/bin/wysun-terminal', executable=True)
    # File-level ownership preserves unrelated Wysun preferences.
    for name in ('hyprland.lua',):
        _publish(d, (d.source / 'config/.config/wysun' / name).read_text(), '.config/wysun/' + name)
    _publish(d, xdph_config(d.home), '.config/hypr/xdph.conf')
    _publish(d, '[preferred]\ndefault=hyprland;gtk;\n'
             'org.freedesktop.impl.portal.ScreenCast=hyprland;\n'
             'org.freedesktop.impl.portal.Screenshot=hyprland;\n'
             'org.freedesktop.impl.portal.FileChooser=gtk;\n',
             '.config/xdg-desktop-portal/wysun-portals.conf')
    for relative in ('.local/share/applications/orbit-music.desktop',
                     '.local/share/icons/hicolor/scalable/apps/musika.svg',
                     '.local/share/applications/orbit-files.desktop'):
        _publish(d, (d.source / 'config' / relative).read_text(), relative)
    for path in sorted((d.source / 'assets/backgrounds').glob('*')):
        if path.is_file():_publish_asset(d, path, '.local/share/backgrounds/' + path.name)
    d.configure_wysun()


def xdph_config(home):
    """Restore tokens by default; Wysun answers its own one-shot picker requests."""
    return ('# Wysun: xdg-desktop-portal-hyprland. Other clients keep hyprland-share-picker.\n'
            'screencopy {\n    allow_token_by_default = true\n'
            # Wysun Recorder reads system-memory frames; a mid-stream switch to
            # DMA-BUF modifiers ends the stream with "unhandled format".
            '    force_shm = true\n'
            '    custom_picker_binary = ' + str(Path(home) / '.local/bin/wysun-share-picker') + '\n}\n')


def _publish_asset(deployment, source, relative):
    from main import fingerprint, copy
    from install_events import emit
    d = deployment
    target = d.destination(relative)
    if (target.exists() or target.is_symlink()) and relative not in d.receipt['files'] and fingerprint(target) != fingerprint(source):
        copy(source, d.backup / 'incoming' / relative)
        d.conflicts.append(relative)
        emit('conflict', path=relative)
        return
    d.deploy(source, Path(relative))


def migrate_legacy_names(deployment):
    """Copy (never move) state stored under the former Caelestia names; the old copies are left for `dotifails clean`."""
    import shutil
    d = deployment
    old, new = d.home / '.config/wysun/caelestia', d.home / '.config/wysun/shell'
    if old.is_dir() and not new.exists():
        shutil.copytree(old, new, symlinks=True)
        print('Wysun: configuración del shell copiada de ' + str(old) + ' a ' + str(new))


def ensure_runtime(deployment):
    """Build or refresh the private Qt/Quickshell/plugin runtime (idempotent, stamped, no system changes)."""
    d = deployment
    if os.environ.get('WYSUN_SKIP_RUNTIME') == '1':
        return
    from main import run
    prefix = d.home / '.local/share/wysun/runtime'
    env = dict(os.environ, HOME=str(d.home))
    d.stage('Runtime del shell Wysun (Qt, Quickshell, plugin)')
    run([sys.executable, d.source / 'installer/runtime_build.py', '--prefix', prefix], env=env)


def update_runtime(deployment):
    """Application-only update when the optional shell is already managed."""
    d = deployment
    if '.local/share/wysun/quickshell' not in d.receipt['files']:
        return
    from capture_distribution import _publish
    d.deploy(d.source / 'apps/shell', Path('.local/share/wysun/quickshell'))
    if not d.conflicts:
        migrate_legacy_names(d)
        ensure_runtime(d)
    for name in ('wysun-shell', 'wysun-session', 'wysun-session-services', 'wysun-lock', 'wysun-wm', 'wysun-control', 'wysun-workspaces', 'wysun-share-picker', 'wysun-recover', 'wysun-idle'):
        _publish(d, (d.source / 'bin' / name).read_text(), '.local/bin/' + name, executable=True)

