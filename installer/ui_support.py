"""Locate/package Music and Files' Material kit without a desktop dependency."""
from pathlib import Path
import shutil
import sys

MODULES = ('icons.py', 'ui_theme.py', 'hypr_settings.py', 'desktop_backend.py')


def prepare_imports():
    here = Path(__file__).resolve().parent
    for candidate in (here / 'ui_runtime', here.parent / 'apps/wysun'):
        if (candidate / 'wysun_core/qt_theme.py').is_file():
            sys.path.insert(0, str(candidate))
            return candidate
    raise RuntimeError('Faltan los componentes visuales. Actualiza el instalador desde una copia completa de Wysun.')


def package_runtime(source, destination):
    source, destination = Path(source), Path(destination)
    app = source / 'apps/wysun'
    for relative in MODULES:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(app / relative, target)
    shutil.copytree(app / 'wysun_core', destination / 'wysun_core', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for relative in ('assets/lucide',):
        shutil.copytree(app / relative, destination / relative)
    for file in (app / 'assets').glob('*.svg'):
        shutil.copy2(file, destination / 'assets' / file.name)
    shutil.copytree(source / 'assets/backgrounds', destination / 'backgrounds')
