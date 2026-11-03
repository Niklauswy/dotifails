#!/usr/bin/env python3
"""Wysun Files (F-01, F-06): ``wysun files [CARPETA|ARCHIVO|file://…]…`` opens one window per process with a tab per
location (a file opens its folder with it selected). Other schemes and missing locations are refused with a
message; the window then opens in the home folder. The UI runs on the qml-runtime venv."""
import os
import signal
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def local_paths(arguments):
    """``(paths, problems)``: local folders/files to open, and what was refused (Qt-free)."""
    paths, problems = [], []
    for value in arguments:
        if value == '--' or value.startswith('-'):
            continue
        url = urlparse(value)
        if url.scheme and url.scheme != 'file':
            problems.append('Solo se admiten carpetas locales: ' + value)
            continue
        path = Path(unquote(url.path) if url.scheme == 'file' else value).expanduser().absolute()
        if not os.path.lexists(path):
            problems.append('La ubicación no existe: ' + str(path))
            continue
        paths.append(str(path))
    return paths, problems


def main(argv=None):
    argv = sys.argv if argv is None else argv
    from wysun_qml import bootstrap
    bootstrap.ensure_runtime_python('wysun_files', argv[1:])
    from wysun_qml import naming
    naming.set_process_name('wysun-files')            # ps/top read the app, not `python3`
    bootstrap.require_qt()
    bootstrap.configure_qt()
    paths, problems = local_paths(argv[1:])
    from PySide6.QtCore import QTimer
    from wysun_files.quick.window import QmlFilesWindow
    window = QmlFilesWindow(paths or [str(Path.home())])
    app = window.app
    app.setApplicationName('Wysun Files')
    app.setOrganizationName('Wysun')
    app.setDesktopFileName('wysun-files')
    for problem in problems:
        sys.stderr.write(problem + '\n')
        window.files.message.emit(problem)
    window.present()
    app.aboutToQuit.connect(window.close)
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: QTimer.singleShot(0, window.window.close))
    wake = QTimer(app, interval=500)          # Python runs signal handlers between bytecodes
    wake.timeout.connect(lambda: None)
    wake.start()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
