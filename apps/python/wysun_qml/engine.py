"""The QGuiApplication + QML engine of a Wysun QML app, on the shell's Qt."""
from pathlib import Path
import sys

from . import bootstrap

FONTS = ('GoogleSansFlex.ttf', 'MaterialSymbolsRounded.ttf', 'CaskaydiaCoveNerdFont-Regular.ttf')


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


def collect_on_gui_thread(interval_ms=4000):
    """Run Python's cycle collector only on the GUI thread, for apps with Python worker threads.

    Automatic collection runs in whichever thread allocates: it could destroy QObjects of the GUI thread from a worker
    (a QFileSystemWatcher losing its descriptor under the event loop, and a crash). Idempotent; needs the application."""
    import gc
    from PySide6.QtCore import QCoreApplication, QTimer
    app = QCoreApplication.instance()
    if app is None or app.property('wysunGuiCollector'):
        return
    gc.disable()
    timer = QTimer(app, interval=interval_ms)
    timer.timeout.connect(lambda: gc.collect())
    timer.start()
    app.setProperty('wysunGuiCollector', True)
