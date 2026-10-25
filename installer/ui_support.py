"""Locate/package Music and Files' Material kit without a desktop dependency."""
from pathlib import Path
import shutil
import sys

MODULES = ('theme_core.py', 'theme_tokens.py', 'wysun_theme.json', 'music_material.py',
           'icons.py', 'ui_motion.py', 'ui_appearance.py', 'ui_theme.py', 'hypr_settings.py', 'desktop_backend.py')
MUSIC = ('__init__.py', 'ui/__init__.py', 'ui/style.py', 'ui/shapes.py', 'ui/widgets.py')


def prepare_imports():
    here = Path(__file__).resolve().parent
    for candidate in (here / 'ui_runtime', here.parent / 'apps/wysun'):
        if (candidate / 'theme_tokens.py').is_file():
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
    for relative in MUSIC:
        target = destination / 'wysun_music' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(app / 'wysun_music' / relative, target)
    for relative in ('assets/fonts', 'assets/lucide'):
        shutil.copytree(app / relative, destination / relative)
    for file in (app / 'assets').glob('*.svg'):
        shutil.copy2(file, destination / 'assets' / file.name)
    shutil.copytree(source / 'assets/backgrounds', destination / 'backgrounds')
