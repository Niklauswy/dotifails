#!/usr/bin/env python3
"""Bounded wallpaper adapter; delegates writes and colour generation to Wysun.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Origen: modules/launcher/WallpaperList.qml and items/WallpaperItem.qml,
commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
"""
import argparse
import json
import os
from pathlib import Path
import sys

LIMIT = 512
EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def app_root():
    source = Path(__file__).resolve().parents[3] / 'wysun'
    if (source / 'environment_settings.py').is_file():
        return source
    installed = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'orbit/app'
    if not (installed / 'environment_settings.py').is_file():
        raise ValueError('No se encuentra el backend de Ajustes de Wysun.')
    return installed


def list_wallpapers(settings, extra_folders=()):
    """No recursion, network, subprocesses or unbounded directory walk."""
    values = settings.wallpaper_values()
    current = values.get('default', '')
    paths = [current] + [v.get('path', '') for v in values.get('monitors', {}).values() if isinstance(v, dict)]
    folders = values.get('folders', [])
    if not isinstance(folders, list):
        folders = []
    folders = folders[:32] + list(extra_folders)
    for folder in folders:
        if not isinstance(folder, (str, Path)) or not str(folder).startswith('/'):
            continue
        try:
            with os.scandir(folder) as entries:
                for index, entry in enumerate(entries):
                    if index >= 4096 or len(paths) >= LIMIT:
                        break
                    if Path(entry.name).suffix.lower() in EXTENSIONS and entry.is_file():
                        paths.append(entry.path)
        except OSError:
            continue
        if len(paths) >= LIMIT:
            break
    result, seen = [], set()
    for value in paths:
        if not isinstance(value, str) or not value.startswith('/'):
            continue
        path = Path(value)
        if path in seen or not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        seen.add(path)
        result.append({'path': str(path), 'name': path.name, 'current': str(path) == current})
        if len(result) >= LIMIT:
            break
    return sorted(result, key=lambda row: (not row['current'], row['name'].casefold(), row['path']))


def select_wallpaper(settings, path, folders=()):
    if not any(row['path'] == path for row in list_wallpapers(settings, folders)):
        raise ValueError('El fondo ya no está disponible en las carpetas configuradas.')
    # Existing API validates images, preserves unknown settings and monitor overrides,
    # makes a backup and calls regenerate_if_dynamic. No new scheme.json writer.
    values = settings.wallpaper_values()
    values['default'] = path
    settings.apply_wallpaper(values)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Fondos locales de Wysun')
    parser.add_argument('action', choices=('list', 'wallpaper'))
    parser.add_argument('path', nargs='?')
    args = parser.parse_args(argv)
    try:
        source = app_root()
        sys.path.insert(0, str(source))
        from environment_settings import EnvironmentSettings
        settings = EnvironmentSettings()
        bundled = source.parents[1] / 'assets/backgrounds'
        folders = (Path.home() / '.local/share/backgrounds', Path.home() / 'Pictures/Wallpapers', bundled)
        if args.action == 'list':
            if args.path:
                raise ValueError('La consulta de fondos no acepta una ruta.')
            print(json.dumps(list_wallpapers(settings, folders), ensure_ascii=False))
        else:
            if not args.path:
                raise ValueError('Selecciona un fondo de la lista.')
            select_wallpaper(settings, args.path, folders)
            print('Fondo actualizado. Los ajustes por monitor se conservan.')
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
