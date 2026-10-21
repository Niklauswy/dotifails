#!/usr/bin/env python3
"""Move leftovers of earlier Wysun/Orbit/Caelestia installs out of the way (reversible).

Nothing is deleted: every candidate is moved into a dated folder under
$XDG_DATA_HOME/wysun-backups/clean-<stamp>/ keeping its path relative to HOME, so `--restore` can put it back.
Private data (notes, history, recordings, captures) is never a candidate. Default is a dry run.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import sys

# (relative path under HOME, reason). Entries ending in * are glob patterns inside their parent.
CANDIDATES = (
    ('.config/wysun/caelestia', 'configuración del shell con el nombre anterior (copiada a .config/wysun/shell)'),
    ('.cache/caelestia', 'caché de imágenes del shell con el nombre anterior (se regenera)'),
    ('.local/state/caelestia', 'estado del shell con el nombre anterior'),
    ('.local/opt/wysun-caelestia-runtime', 'runtime anterior (sustituido por .local/share/wysun/runtime)'),
    ('.local/share/orbit-backup-*', 'copias de versiones antiguas de Orbit'),
    ('.local/share/orbit-v?-backup-*', 'copias de versiones antiguas de Orbit'),
    ('.local/share/orbit-desktop-backup', 'marcador de copia antigua de Orbit'),
    ('.cache/quickshell/qmlcache', 'caché QML compilada (se regenera con el runtime nuevo)'),
)


def candidates(home):
    for pattern, reason in CANDIDATES:
        parent, _, leaf = pattern.rpartition('/')
        for path in sorted((home / parent).glob(leaf)):
            if path.exists() or path.is_symlink():
                yield path, reason


def clean(home, apply, stamp=None):
    home = Path(home)
    stamp = stamp or datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    data = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')
    vault = data / 'wysun-backups' / ('clean-' + stamp)
    moved = []
    for path, reason in candidates(home):
        rel = path.relative_to(home)
        print(('mover  ' if apply else 'mover? ') + str(rel) + '  — ' + reason)
        if apply:
            target = vault / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            moved.append(str(rel))
    if apply and moved:
        (vault / 'MANIFEST.json').write_text(json.dumps({'home': str(home), 'moved': moved}, indent=2) + '\n')
        print('Respaldo en ' + str(vault) + ' (restaurar con --restore ' + str(vault) + ')')
    return moved


def restore(vault):
    vault = Path(vault)
    manifest = json.loads((vault / 'MANIFEST.json').read_text())
    home = Path(manifest['home'])
    for rel in manifest['moved']:
        target = home / rel
        if target.exists() or target.is_symlink():
            print('conservado (ya existe): ' + rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(vault / rel), str(target))
        print('restaurado: ' + rel)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--home', default=str(Path.home()))
    parser.add_argument('--apply', action='store_true', help='mover de verdad (sin esto solo lista)')
    parser.add_argument('--restore', metavar='VAULT', help='devolver a su sitio lo movido en una limpieza anterior')
    args = parser.parse_args(argv)
    if args.restore:
        restore(args.restore)
        return 0
    clean(args.home, args.apply)
    return 0


if __name__ == '__main__':
    sys.exit(main())
