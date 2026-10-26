"""Locate/package Music and Files' Material kit without a desktop dependency."""
from pathlib import Path
import shutil
import sys


def prepare_imports():
    here = Path(__file__).resolve().parent
    for candidate in (here / 'ui_runtime', here.parent / 'apps/python'):
        if (candidate / 'wysun_core/qt_theme.py').is_file():
            sys.path.insert(0, str(candidate))
            return candidate
    raise RuntimeError('Faltan los componentes visuales. Actualiza el instalador desde una copia completa de Wysun.')


def package_runtime(source, destination):
    source, destination = Path(source), Path(destination)
    # wysun_core is self-contained (kit, icons, fonts, assets): the installer needs nothing else of the apps.
    shutil.copytree(source / 'apps/python/wysun_core', destination / 'wysun_core', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(source / 'assets/backgrounds', destination / 'backgrounds')
