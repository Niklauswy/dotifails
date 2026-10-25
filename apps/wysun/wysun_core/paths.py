"""Where Wysun keeps things, resolved from the environment on every call.

XDG variables count only when set to an absolute path, as the specification says.
Callers name their own namespace (``paths.data('orbit', 'colors.json')``).
"""
import os
import stat
import tempfile
from pathlib import Path


def _xdg(variable, fallback):
    value = os.environ.get(variable, '')
    return Path(value) if os.path.isabs(value) else home() / fallback


def home():
    return Path.home()


def config_home():
    return _xdg('XDG_CONFIG_HOME', '.config')


def data_home():
    return _xdg('XDG_DATA_HOME', '.local/share')


def state_home():
    return _xdg('XDG_STATE_HOME', '.local/state')


def cache_home():
    return _xdg('XDG_CACHE_HOME', '.cache')


def bin_home():
    return home() / '.local/bin'


def runtime_dir():
    value = os.environ.get('XDG_RUNTIME_DIR', '')
    return Path(value) if os.path.isabs(value) else Path(tempfile.gettempdir())


def config(*parts):
    return config_home().joinpath(*parts)


def data(*parts):
    return data_home().joinpath(*parts)


def state(*parts):
    return state_home().joinpath(*parts)


def cache(*parts):
    return cache_home().joinpath(*parts)


def runtime(*parts):
    return runtime_dir().joinpath(*parts)


def private_dir(path):
    """Create ``path`` (0o700) or check an existing one is a real directory only this user can enter."""
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError(f'{path} es un enlace simbólico')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError(f'{path} debe ser un directorio privado')
    return path
