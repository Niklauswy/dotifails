"""The QGuiApplication + QML engine of a Wysun QML app, on the shell's Qt."""
from pathlib import Path
import sys

from . import bootstrap

FONTS = ('GoogleSansFlex.ttf', 'MaterialSymbolsRounded.ttf', 'CaskaydiaCoveNerdFont-Regular.ttf')
_COLLECTOR = {}


def register_fonts():
    import wysun_core
    from PySide6.QtGui import QFontDatabase
    folder = Path(wysun_core.__file__).parent / 'fonts'
    return [QFontDatabase.addApplicationFont(str(folder / name)) for name in FONTS if (folder / name).exists()]


def create_engine(app_name, extra_imports=()):
    """``(QGuiApplication, QQmlApplicationEngine)``; an existing application is reused."""
    bootstrap.require_qt()
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    imports = bootstrap.configure_qt()
    warning = bootstrap.check_versions()
    if warning:
        sys.stderr.write(warning)
    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    app.setApplicationName(app_name)
    register_fonts()
    engine = QQmlApplicationEngine()
    for path in [*imports, *map(Path, extra_imports)]:
        engine.addImportPath(str(path))
    return app, engine


def collect_on_gui_thread(interval_ms=15000):
    """Keep Python's cycle collector on the GUI thread and out of the worker threads, for apps with Python workers.

    Automatic collection runs in whichever thread allocates: it could destroy QObjects of the GUI thread from a
    worker (a QFileSystemWatcher losing its descriptor under the event loop, and a crash), so it stays disabled.
    The objects alive after startup are frozen (`gc.freeze()`), which makes every later full pass cheap because the
    frozen objects are skipped, and a timer on the GUI thread runs a full collection every ``interval_ms`` (15 s by
    default). Calling it again only changes the interval, so tests can shorten it. Idempotent; needs the
    application."""
    import gc
    from PySide6.QtCore import QCoreApplication, QTimer
    app = QCoreApplication.instance()
    if app is None:
        return
    installed = _COLLECTOR.get('timer')
    if installed is not None:
        try:
            installed.setInterval(max(1, int(interval_ms)))
            return
        except RuntimeError:                     # the previous application is gone
            _COLLECTOR.pop('timer', None)
    gc.collect()
    gc.freeze()
    gc.set_threshold(20000, 50, 50)
    gc.disable()
    timer = QTimer(app, interval=max(1, int(interval_ms)))
    timer.timeout.connect(gc.collect)
    timer.start()
    _COLLECTOR['timer'] = timer
    app.setProperty('wysunGuiCollector', True)
