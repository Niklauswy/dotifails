"""The runnable gallery of the shared M3 base (``python3 -m wysun_qml``).

Shows every WysunM3 component on an adaptive navigation, with the live theme or a preview palette, and doubles as
the capture and scroll-benchmark tool::

    python3 -m wysun_qml [--page lists] [--palette green --mode dark] [--width 700 --height 800]
    python3 -m wysun_qml --shot out.png [...]      # render, save and quit (offscreen too)
    python3 -m wysun_qml --bench                    # scroll 10 000 list items, print fps and memory, quit
"""
import argparse
import json
from pathlib import Path
import sys

from . import bootstrap

APP_ID = 'wysun-qml-gallery'
TITLE = 'Wysun · M3 gallery'
PAGES = ('theme', 'buttons', 'chips', 'fields', 'lists', 'navigation', 'overlays', 'motion', 'empty')
SEEDS = {'green': ('2e7d32', 'tonalspot'), 'orange': ('e65100', 'vibrant'), 'blue': ('1565c0', 'expressive')}
PALETTES = ('live', 'default', *SEEDS)


def gallery_dir():
    """apps/qml/gallery next to the library (source tree or the installed copy)."""
    return bootstrap.library_path() / 'gallery'


def palette(name, mode):
    """A preview scheme {'mode', 'colours'}: the default wallpaper's base palette or a synthetic seed."""
    from wysun_core import theme
    if name == 'default':
        return {'mode': mode, 'colours': dict(theme.data()['palettes'][mode]['scheme'])}
    from types import SimpleNamespace
    from wysun_services.scheme import gen_scheme, hex_to_hct
    seed, variant = SEEDS[name]
    spec = SimpleNamespace(name='dynamic', flavour='default', mode=mode, variant=variant)
    return {'mode': mode, 'colours': gen_scheme(spec, hex_to_hct(seed))}


def parse(argv):
    parser = argparse.ArgumentParser(prog='python3 -m wysun_qml', description=TITLE)
    parser.add_argument('--page', choices=PAGES, default='theme')
    parser.add_argument('--palette', choices=PALETTES, default='live')
    parser.add_argument('--mode', choices=('light', 'dark'))
    parser.add_argument('--width', type=int, default=1000)
    parser.add_argument('--height', type=int, default=760)
    parser.add_argument('--shot', metavar='PNG')
    parser.add_argument('--bench', action='store_true')
    parser.add_argument('--reduced-motion', action='store_true')
    return parser.parse_args(argv)


def _controller_class():
    from PySide6.QtCore import Property, QObject, Signal, Slot

    class Controller(QObject):
        """What the gallery's QML asks of Python: preview palettes and modes on the ThemeBridge."""
        changed = Signal()

        def __init__(self, bridge, name, mode):
            super().__init__()
            self._bridge = bridge
            self._name = name
            self._mode = mode
            self._apply()

        def _apply(self):
            if self._name == 'live' and self._mode is None:
                self._bridge.setPreview(None)
            else:
                live = self._bridge.scheme
                mode = self._mode or live.get('mode', 'dark')
                self._bridge.setPreview(dict(live, mode=mode) if self._name == 'live' and live.get('mode') == mode
                                        else palette('default' if self._name == 'live' else self._name, mode))
            self.changed.emit()

        @Slot(str)
        def setPalette(self, name):
            self._name = name
            self._apply()

        @Slot(str)
        def setMode(self, mode):
            self._mode = mode or None
            self._apply()

        def _get_palette(self):
            return self._name

        def _get_mode(self):
            return self._mode or self._bridge.scheme.get('mode', 'dark')

        def _get_palettes(self):
            return list(PALETTES)

        palette = Property(str, _get_palette, notify=changed)
        mode = Property(str, _get_mode, notify=changed)
        palettes = Property('QVariantList', _get_palettes, constant=True)

    return Controller


def build(options, app_and_engine=None):
    """Create (or reuse) the app and engine, load the gallery and return (app, engine, window, controller)."""
    from PySide6.QtCore import QUrl
    from . import engine as engine_module, theme_bridge
    app, engine = app_and_engine or engine_module.create_engine(APP_ID)
    app.setDesktopFileName(APP_ID)                 # the Wayland app_id, so hyprctl shows class wysun-qml-gallery
    bridge = theme_bridge.ThemeBridge(parent=engine)
    if options.reduced_motion:
        bridge.setReducedMotion(True)
    controller = _controller_class()(bridge, options.palette, options.mode)
    controller.setParent(engine)
    context = engine.rootContext()
    context.setContextProperty('bridge', bridge)
    context.setContextProperty('gallery', controller)
    context.setContextProperty('galleryOptions', {'page': options.page, 'width': options.width,
                                                  'height': options.height, 'title': TITLE, 'bench': options.bench})
    engine.load(QUrl.fromLocalFile(str(gallery_dir() / 'Gallery.qml')))
    windows = engine.rootObjects()
    if not windows:
        raise SystemExit('wysun_qml: the gallery did not load')
    return app, engine, windows[-1], controller


def memory():
    """{'rss_mb', 'pss_mb'} of this process from /proc (Linux)."""
    values = {}
    try:
        for line in Path('/proc/self/smaps_rollup').read_text().splitlines():
            key, _, rest = line.partition(':')
            if key in ('Rss', 'Pss'):
                values[key.lower() + '_mb'] = round(int(rest.split()[0]) / 1024, 1)
    except OSError:
        pass
    return values


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    options = parse(argv)
    bootstrap.ensure_runtime_python('wysun_qml', argv)
    bootstrap.preload_qt()
    from PySide6.QtCore import QTimer
    from PySide6.QtQuick import QQuickWindow  # noqa: F401  (window objects come back as QQuickWindow)
    app, engine, window, controller = build(options)

    if options.shot:
        def shoot():
            ok = False
            try:
                image = window.grabWindow()
                Path(options.shot).parent.mkdir(parents=True, exist_ok=True)
                ok = not image.isNull() and image.save(options.shot)
            finally:
                app.exit(0 if ok else 1)
        # Let the page settle (fonts, the first transition) before grabbing.
        QTimer.singleShot(400, shoot)
    elif options.bench:
        def report(result):
            result = result.toVariant() if hasattr(result, 'toVariant') else result
            print('BENCH ' + json.dumps({**dict(result), **memory()}), flush=True)
            app.exit(0)
        window.benchFinished.connect(report)
    return app.exec()
