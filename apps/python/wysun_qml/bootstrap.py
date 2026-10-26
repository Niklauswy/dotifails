"""Run PySide6 on the shell runtime's Qt instead of the wheel's own copy.

The wheel's Qt is binary-identical to the runtime Qt (qml-runtime keeps only the bindings), so the runtime's
``libQt6*.so.6`` are loaded by absolute path *before* PySide6 is imported: the dynamic linker reuses an
already-loaded soname, and the process ends up with exactly one Qt, the shell's. Plugins and QML imports are
pointed at the runtime too. Nothing is exported (no LD_LIBRARY_PATH), so child processes (mpv...) inherit nothing.
"""
import ctypes
import json
import os
from pathlib import Path
import sys

from wysun_core import launch, paths

# Libraries PySide6's QtCore/QtGui/QtQml/QtQuick modules and the Wayland platform link against.
PRELOAD = ('Core', 'Gui', 'DBus', 'Network', 'OpenGL', 'Qml', 'QmlMeta', 'QmlModels', 'QmlWorkerScript', 'Quick',
           'WaylandClient')
STAMP = 'WYSUN_QML_RUNTIME.json'
REEXEC = 'WYSUN_QML_REEXEC'
RUNTIME_HINT = ('Wysun: falta el runtime del shell (Qt privado); sin él PySide6 cargaría otro Qt. Instálalo con '
                './instalar.sh --wysun-only.\n')
HINT = ('Wysun: falta el runtime QML (venv de PySide6). Créalo con: python3 installer/qml_runtime.py '
        '(o ./instalar.sh --wysun-only).\n')


def _data_home():
    return paths.data_home()


def runtime_dir():
    """The shell runtime prefix (Qt, Quickshell, plugin, M3Shapes)."""
    return Path(os.environ.get('WYSUN_RUNTIME') or _data_home() / 'wysun/runtime')


def qt_prefix():
    """``<runtime>/qt/<version>/gcc_64``; the version comes from the runtime's own stamp."""
    base = runtime_dir() / 'qt'
    try:
        version = json.loads((runtime_dir() / 'RUNTIME.json').read_text())['qt']['version']
        return base / version / 'gcc_64'
    except (OSError, ValueError, KeyError, TypeError):
        found = sorted(base.glob('*/gcc_64'))
        return found[-1] if found else base / 'missing' / 'gcc_64'


def qml_runtime_python():
    """The qml-runtime venv's interpreter when it exists with a complete stamp, else None."""
    prefix = Path(os.environ.get('WYSUN_QML_RUNTIME') or _data_home() / 'wysun/qml-runtime')
    try:
        stamp = json.loads((prefix / STAMP).read_text())
    except (OSError, ValueError):
        return None
    python = prefix / 'bin/python3'
    return python if python.exists() and isinstance(stamp, dict) and stamp.get('pyside6') else None


def ensure_runtime_python(module, argv=None):
    """Re-execute ``python -m module`` with the venv's interpreter unless this process already is it."""
    argv = list(sys.argv[1:] if argv is None else argv)
    python = qml_runtime_python()
    if python is None:
        sys.stderr.write(HINT)
        raise SystemExit(2)
    if Path(sys.prefix).resolve() == python.parent.parent.resolve():
        os.environ.pop(REEXEC, None)          # children (another Wysun app) may re-exec on their own
        return
    if os.environ.get(REEXEC):                # already re-executed once: never loop
        sys.stderr.write(f'Wysun: {python} no es el Python de este proceso ({sys.executable}); revisa WYSUN_QML_RUNTIME.\n')
        raise SystemExit(2)
    os.execve(str(python), launch.argv(module, *argv, python=str(python)), {**launch.environment(), REEXEC: '1'})


def preload_qt(prefix=None):
    """Load the runtime's Qt libraries by absolute path; returns the module names that were loaded."""
    lib = Path(prefix or qt_prefix()) / 'lib'
    loaded = []
    for name in PRELOAD:
        path = lib / f'libQt6{name}.so.6'
        if path.exists():
            ctypes.CDLL(str(path), mode=ctypes.RTLD_GLOBAL)
            loaded.append(name)
    return loaded


def library_path():
    """The WysunM3 library: the override, else the qml/ folder next to this package's tree (apps/qml in the
    repository, ~/.local/share/wysun/qml when installed next to ~/.local/share/wysun/app)."""
    override = os.environ.get('WYSUN_QML_LIB')
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / 'qml'


def require_qt():
    """preload_qt(), exiting with a hint when the runtime's QtCore is missing (PySide6 would find another Qt)."""
    loaded = preload_qt()
    if 'Core' not in loaded:
        sys.stderr.write(RUNTIME_HINT)
        raise SystemExit(2)
    return loaded


def configure_qt(prefix=None):
    """Point plugins at the runtime and return the QML import paths (call after ``preload_qt``)."""
    from PySide6.QtCore import QCoreApplication
    prefix = Path(prefix or qt_prefix())
    QCoreApplication.setLibraryPaths([str(prefix / 'plugins')])
    paths = [prefix / 'qml', runtime_dir() / 'deps/lib/qt6/qml', library_path()]
    return [path for path in paths if path.is_dir() or path == library_path()]


def pyside_version():
    from importlib import metadata
    return metadata.version('PySide6_Essentials')


def _qt_version():
    from PySide6.QtCore import qVersion
    return qVersion()


def check_versions():
    """A warning text when the loaded Qt and the bindings differ (never raises), else None."""
    qt, bindings = _qt_version(), pyside_version()
    if qt == bindings:
        return None
    return (f'Wysun: Qt {qt} no coincide con PySide6 {bindings}; los bindings usan API privada de QtQml. '
            'Actualiza el venv: python3 installer/qml_runtime.py\n')
