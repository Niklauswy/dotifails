"""Journaled Wysun capture deployment, adopting only verified legacy launchers.

Immutable releases keep a running Recorder worker's imports available. User media,
preferences, old releases and the original standalone manifests are never changed.
"""
import hashlib
import json
from pathlib import Path
import shlex


def _legacy_owned(deployment, relative, manifest, key):
    destination = deployment.destination(relative)
    if not destination.exists() and not destination.is_symlink():
        return True
    if str(relative) in deployment.receipt['files']:
        return True  # Deployment checks its recorded fingerprint before updating.
    if destination.is_symlink() or not destination.is_file():
        return False
    try:
        files = json.loads((deployment.home / manifest).read_text())['files']
        expected = files.get(key) if key else files.get(str(destination))
        return expected == hashlib.sha256(destination.read_bytes()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _publish(deployment, text, relative, *, executable=False, legacy=None):
    relative = Path(relative)
    manifest, key = legacy or ('.local/share/wysun/no-legacy-manifest.json', None)
    if not _legacy_owned(deployment, relative, manifest, key):
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
    source = deployment.source / 'apps/capture'
    if not source.is_dir():
        return
    deployment.stage('Actualizar Wysun Recorder y Wysun Screenshot')
    runtime = deployment.backup / 'generated/capture-release'
    runtime.mkdir(parents=True)
    # Copy only distributable source, never a user's libraries or recording files.
    import shutil
    for package in ('loomrec', 'wybieshot', 'assets'):
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
    for command, module, old, manifest in (
        ('wysun-recorder', 'loomrec', 'loomrec', '.local/share/loomrec/install-manifest.json'),
        ('wysun-screenshot', 'wybieshot', 'wybie-screenshot', '.local/share/wybie-screenshot/install-manifest.json'),
    ):
        launcher = ('#!/bin/sh\nunset __PYVENV_LAUNCHER__\n'
                    'export PYTHONDONTWRITEBYTECODE=1\n'
                    'export PYTHONPATH=' + shlex.quote(str(root)) + '\n'
                    'exec /usr/bin/python3 -P -m ' + module + ' "$@"\n')
        if not _publish(deployment, launcher, '.local/bin/' + command, executable=True):
            continue
        # Preserve old keyboard bindings, scripts and desktop IDs without
        # overwriting custom launchers that no previous installer owns.
        _publish(deployment, launcher, '.local/bin/' + old, executable=True,
                 legacy=(manifest, 'launcher' if module == 'loomrec' else None))
        title = 'Wysun Recorder' if module == 'loomrec' else 'Wysun Screenshot'
        category = 'AudioVideo;Recorder;' if module == 'loomrec' else 'Graphics;Photography;'
        comment = 'Graba y edita videos localmente' if module == 'loomrec' else 'Captura y edita imágenes localmente'
        desktop = ('[Desktop Entry]\nType=Application\nName=' + title + '\nName[es]=' + title +
                   '\nComment=' + comment + '\nExec=wysun ' + ('recorder' if module == 'loomrec' else 'screenshot') +
                   '\nIcon=' + old + '\nTerminal=false\nCategories=' + category +
                   '\nKeywords=Wysun;' + old + ';\n')
        if module == 'wybieshot':
            desktop += 'StartupWMClass=wybie-screenshot\n'
        _publish(deployment, desktop, '.local/share/applications/' + old + '.desktop',
                 legacy=(manifest, 'desktop' if module == 'loomrec' else None))
        icon = ((source / 'assets/wybie-screenshot.svg').read_text() if module == 'wybieshot' else
                '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
                '<rect width="64" height="64" rx="16" fill="#19242d"/>'
                '<circle cx="32" cy="32" r="18" fill="#dc695b"/>'
                '<circle cx="32" cy="32" r="7" fill="#f5f0df"/></svg>\n')
        _publish(deployment, icon, '.local/share/icons/hicolor/scalable/apps/' + old + '.svg',
                 legacy=(manifest, 'icon' if module == 'loomrec' else None))
