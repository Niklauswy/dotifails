"""Helpers for the QML suites: locating the qml-runtime venv and running code in it.

The QML suites only run with the venv Python (the system PySide6 has no QtQuick). Run them through
``tests/test_qml_runtime.py`` or directly::

    <venv>/bin/python3 -m unittest discover -s tests/qml -t tests -p 'check_*.py'
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STAMP = 'WYSUN_QML_RUNTIME.json'


def candidate_prefixes():
    override = os.environ.get('WYSUN_QML_RUNTIME')
    if override:                      # an explicit override is authoritative (also to force the skip)
        return [Path(override)]
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return [Path.home() / '.cache/wysun-fase1/qml-runtime', data / 'wysun/qml-runtime']


def venv_python():
    """The venv's python3 when it exists and its stamp is complete; else None."""
    for prefix in candidate_prefixes():
        python = prefix / 'bin/python3'
        try:
            stamp = json.loads((prefix / STAMP).read_text())
        except (OSError, ValueError):
            continue
        if python.exists() and isinstance(stamp, dict) and stamp.get('pyside6'):
            return python
    return None


def in_venv():
    """True when this process already runs in a qml-runtime venv."""
    return (Path(sys.prefix) / STAMP).exists()


def run_in_venv(args, **env):
    python = venv_python()
    if python is None:
        raise RuntimeError('no qml-runtime venv')
    full = dict(os.environ, QT_QPA_PLATFORM='offscreen', WYSUN_REDUCED_MOTION='0',
                PYTHONPATH=os.pathsep.join([str(ROOT / 'apps/python'), str(ROOT / 'apps/python/vendor'), str(ROOT / 'tests')]),
                TMPDIR=str(Path.home() / '.cache/wysun-fase1/tmp'))
    full.update({k: str(v) for k, v in env.items()})
    Path(full['TMPDIR']).mkdir(parents=True, exist_ok=True)
    return subprocess.run([str(python), *args], cwd=ROOT, env=full, capture_output=True, text=True)


# ---------------------------------------------------------------------------------------------------------
# Everything below needs the venv Python (PySide6 + QtQuick). Import it only from the check_*.py suites.
# ---------------------------------------------------------------------------------------------------------
STYLES = ('material3',)          # a new design system is one more entry (and its tokens/palettes)
SEEDS = {'green': '2e7d32', 'orange': 'e65100', 'blue': '1565c0'}
VARIANTS = {'green': 'tonalspot', 'orange': 'vibrant', 'blue': 'expressive'}
LIBRARY = ROOT / 'apps/qml/WysunM3'


def _paths():
    for path in (ROOT / 'apps/python', ROOT / 'apps/python/vendor'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _palettes():
    _paths()
    from types import SimpleNamespace
    from wysun_core import theme
    from wysun_services.scheme import gen_scheme, hex_to_hct
    result = {}
    for mode in ('light', 'dark'):
        result[f'default-{mode}'] = {'mode': mode, 'colours': dict(theme.data()['palettes'][mode]['scheme'])}
        for name, seed in SEEDS.items():
            spec = SimpleNamespace(name='dynamic', flavour='default', mode=mode, variant=VARIANTS[name])
            result[f'{name}-{mode}'] = {'mode': mode, 'colours': gen_scheme(spec, hex_to_hct(seed))}
    return result


class _Lazy(dict):
    def __missing__(self, key):
        raise KeyError(key)

    def load(self):
        if not self:
            self.update(_palettes())
        return self


PALETTES = _Lazy()


def palettes():
    """name -> {'mode', 'colours'}: the default wallpaper's base palette and three synthetic seeds, light and dark."""
    return PALETTES.load()


def scheme_file(palette):
    """A palette as the ``scheme.json`` document ``wysun scheme`` writes."""
    return {'name': 'dynamic', 'flavour': 'default', 'mode': palette['mode'], 'variant': 'tonalspot',
            'colours': palette['colours'], 'wallpaper_hash': '0' * 64}


def write_atomic(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(document))
    os.replace(tmp, path)


def hex_of(colour):
    """``#rrggbb`` of a QColor (alpha dropped)."""
    return '#%02x%02x%02x' % (colour.red(), colour.green(), colour.blue())


def close_to(testcase, colour, expected_hex, tolerance=2, msg=None):
    expected = expected_hex if expected_hex.startswith('#') else '#' + expected_hex
    e = [int(expected[i:i + 2], 16) for i in (1, 3, 5)]
    got = [colour.red(), colour.green(), colour.blue()]
    testcase.assertTrue(all(abs(a - b) <= tolerance for a, b in zip(got, e)),
                        (msg or 'colour') + f': got {hex_of(colour)}, expected {expected}')


def blend(over_hex, base_hex, alpha):
    """Source-over of ``over`` at ``alpha`` on ``base`` as an ``#rrggbb`` (for state-layer expectations)."""
    o = [int(over_hex.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(base_hex.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    return '#%02x%02x%02x' % tuple(round(a * alpha + c * (1 - alpha)) for a, c in zip(o, b))


class Harness:
    """One QGuiApplication + engine per process; renders QML snippets offscreen under a real ThemeBridge."""

    _instance = None

    def __init__(self):
        _paths()
        os.environ.pop('WYSUN_THEME', None)
        from wysun_qml import engine, theme_bridge
        import tempfile
        self.app, self.engine = engine.create_engine('wysun-qml-tests')
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.dir = tempfile.TemporaryDirectory(prefix='harness-', dir=scratch)
        self.home = Path(self.dir.name) / 'home'
        self.home.mkdir()
        self.bridge = theme_bridge.ThemeBridge(home=self.home)
        self.engine.rootContext().setContextProperty('bridge', self.bridge)
        self.views = []
        self.counter = 0
        import atexit
        atexit.register(self.close_views)     # views must go before the bridge their bindings read

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -- theme ---------------------------------------------------------------------------------------------
    def use(self, palette_name):
        """Show a named palette (preview override) and let the bindings settle."""
        self.bridge.setPreview(palettes()[palette_name])
        self.pump()

    def pump(self, ms=0):
        from PySide6.QtCore import QCoreApplication, QElapsedTimer
        timer = QElapsedTimer()
        timer.start()
        QCoreApplication.processEvents()
        while timer.elapsed() < ms:
            QCoreApplication.processEvents()

    def wait_for(self, condition, ms=2000):
        from PySide6.QtCore import QCoreApplication, QElapsedTimer
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < ms:
            QCoreApplication.processEvents()
            if condition():
                return True
        return bool(condition())

    # -- rendering -----------------------------------------------------------------------------------------
    def view(self, body, width=200, height=100, imports=''):
        """A shown QQuickView with ``body`` as the contents of a root Item (ThemeFeed already in place)."""
        from PySide6.QtCore import QUrl
        from PySide6.QtQuick import QQuickView
        self.counter += 1
        source = Path(self.dir.name) / f'case{self.counter}.qml'
        source.write_text(
            'import QtQuick\nimport WysunM3\n' + imports + '\n'
            f'Item {{ id: root; width: {width}; height: {height}\n'
            '  ThemeFeed { scheme: bridge.scheme; tokens: bridge.tokens; reducedMotion: bridge.reducedMotion }\n'
            + body + '\n}\n')
        view = QQuickView(self.engine, None)
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.setSource(QUrl.fromLocalFile(str(source)))
        if view.status() != QQuickView.Ready:
            raise AssertionError('QML did not load:\n' + '\n'.join(str(e) for e in view.errors()))
        view.resize(width, height)
        view.show()
        self.views.append(view)
        self.pump(30)
        return view

    def grab(self, view):
        self.pump(30)
        return view.grabWindow()

    def render(self, body, width=200, height=100, imports=''):
        view = self.view(body, width, height, imports)
        return view, self.grab(view)

    def close_views(self):
        for view in self.views:
            view.destroy()
        self.views.clear()

    def root(self, view):
        return view.rootObject()

    def call(self, obj, method, *args):
        from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, Qt
        arguments = [Q_ARG('QVariant', a) for a in args]
        from PySide6.QtQml import QJSValue
        result = QMetaObject.invokeMethod(obj, method, Qt.DirectConnection, Q_RETURN_ARG('QVariant'), *arguments)
        return result.toVariant() if isinstance(result, QJSValue) else result

    def theme(self, name):
        """A property or function result of the Theme singleton, read through a probe item."""
        view = self.view('function read(n) { return Theme[n] }', 10, 10)
        value = self.call(view.rootObject(), 'read', name)
        view.destroy()
        self.views.remove(view)
        return value

    def pixel(self, image, x, y):
        from PySide6.QtGui import QColor
        return QColor(image.pixel(int(x), int(y)))

    def roles(self, names):
        """``{role: '#rrggbb'}`` as Theme.m3<role> currently resolves them."""
        view = self.view('function all(names) { var o = {}; for (var i = 0; i < names.length; ++i) '
                         'o[names[i]] = Theme["m3" + names[i]].toString(); return o }', 10, 10)
        value = self.call(view.rootObject(), 'all', list(names))
        view.destroy()
        self.views.remove(view)
        return dict(value)
