"""Journaled Wysun Recorder deployment in immutable, hash-named releases.

Immutable releases keep a running Recorder worker's imports available. User media,
preferences and old releases are never changed.
"""
import hashlib
from pathlib import Path
import shlex


def _owned(deployment, relative):
    """A file may be (re)written when it does not exist or this installer wrote it (Deployment checks its fingerprint)."""
    destination = deployment.destination(relative)
    return (not destination.exists() and not destination.is_symlink()) or str(relative) in deployment.receipt['files']


def _publish(deployment, text, relative, *, executable=False):
    relative = Path(relative)
    if not _owned(deployment, relative):
        # Keep the new version reviewable using the same incoming/ convention.
        incoming = deployment.backup / 'incoming' / relative
        incoming.parent.mkdir(parents=True, exist_ok=True)
        incoming.write_text(text)
        incoming.chmod(0o755 if executable else 0o644)
        deployment.conflicts.append(str(relative))
        from install_events import emit
        emit('conflict', path=str(relative))
        return False
    deployment.generated(text, relative, executable)
    return str(relative) not in deployment.conflicts


def configure(deployment):
    source = deployment.source / 'apps/recorder'
    if not source.is_dir():
        return
    deployment.stage('Actualizar Wysun Recorder')
    runtime = deployment.backup / 'generated/capture-release'
    import shutil
    if runtime.exists():
        shutil.rmtree(runtime)   # a full installation publishes the family twice (wayland, then desktop)
    runtime.mkdir(parents=True)
    # Copy only distributable source, never a user's libraries or recording files.
    # wysun_core (paths, atomic files, single instance, tokens), wysun_qml (the QML runtime helpers) and qml/WysunM3
    # (the component library) are shared with Wysun: apps/recorder links to their source, and each release carries its
    # own copy so a running Recorder never imports another version. The settings window's own QML is part of
    # wysun_recorder (ui/qml).
    import shutil
    for package in ('wysun_recorder', 'assets', 'wysun_core', 'wysun_qml', 'qml'):
        shutil.copytree(source / package, runtime / package,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('README.md', 'UPSTREAM.md'):
        shutil.copy2(source / name, runtime / name)
    digest = hashlib.sha256()
    for path in sorted(runtime.rglob('*')):
        if path.is_file():
            digest.update(path.relative_to(runtime).as_posix().encode() + b'\0' + path.read_bytes())
    release = digest.hexdigest()[:20]
    relative = Path('.local/share/wysun/capture/releases') / release
    deployment.deploy(runtime, relative)
    if str(relative) in deployment.conflicts:
        return
    root = deployment.home / relative
    launcher = ('#!/bin/sh\nunset __PYVENV_LAUNCHER__\n'
                'export PYTHONDONTWRITEBYTECODE=1\n'
                'export PYTHONPATH=' + shlex.quote(str(root)) + '\n'
                'export WYSUN_QML_LIB=' + shlex.quote(str(root / 'qml')) + '\n'
                'exec /usr/bin/python3 -P -m wysun_recorder "$@"\n')
    if _publish(deployment, launcher, '.local/bin/wysun-recorder', executable=True):
        title = 'Wysun Recorder'
        desktop = ('[Desktop Entry]\nType=Application\nName=' + title + '\nName[es]=' + title +
                   '\nComment=Ajustes de grabación de Wysun\nExec=wysun recorder' +
                   '\nIcon=wysun-recorder\nTerminal=false\nCategories=AudioVideo;Recorder;' +
                   '\nKeywords=Wysun;Recorder;\nStartupWMClass=wysun-recorder\n')
        _publish(deployment, desktop, '.local/share/applications/wysun-recorder.desktop')
        icon = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
                '<rect width="64" height="64" rx="16" fill="#19242d"/>'  # theme-exception: icono de aplicacion
                '<circle cx="32" cy="32" r="18" fill="#dc695b"/>'  # theme-exception: icono de aplicacion
                '<circle cx="32" cy="32" r="7" fill="#f5f0df"/></svg>\n')  # theme-exception: icono de aplicacion
        _publish(deployment, icon, '.local/share/icons/hicolor/scalable/apps/wysun-recorder.svg')
