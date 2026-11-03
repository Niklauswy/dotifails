#!/usr/bin/env python3
"""Wysun Processes: ``wysun processes [CONSULTA]`` opens the process monitor (one window per user; a second call
hands the query to the open window and focuses it). The UI runs on the qml-runtime venv."""
import signal
import subprocess
import sys


def main(argv=None):
    argv = sys.argv if argv is None else argv
    from wysun_qml import bootstrap
    bootstrap.ensure_runtime_python('wysun_processes', argv[1:])
    bootstrap.require_qt()
    bootstrap.configure_qt()
    query = ' '.join(a for a in argv[1:] if a != '--')
    from PySide6.QtCore import QTimer
    from wysun_qml import engine as qml_engine
    from wysun_processes.quick.instance import Instance
    instance = Instance()
    if instance.forward(query):
        try:
            done = subprocess.run(['hyprctl', 'dispatch', 'hl.dsp.focus({window="class:^wysun-processes$"})'],
                                  capture_output=True, text=True, timeout=2, check=False)
            if done.stdout.strip() != 'ok':
                subprocess.run(['hyprctl', 'dispatch', 'focuswindow', 'class:^wysun-processes$'], capture_output=True,
                               timeout=2, check=False)
        except (OSError, subprocess.SubprocessError):
            pass
        return 0
    from wysun_processes.quick.window import QmlProcessesWindow
    window = QmlProcessesWindow()
    app = window.app
    app.setApplicationName('Wysun Processes')
    app.setOrganizationName('Wysun')
    app.setDesktopFileName('wysun-processes')
    qml_engine.collect_on_gui_thread()

    def receive(text):
        window.procs.openContext(text)
        window.present()
    instance.listen(receive)
    if query:
        QTimer.singleShot(1300, lambda: window.procs.openContext(query))
    window.present()
    app.aboutToQuit.connect(window.close)
    app.aboutToQuit.connect(instance.close)
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: QTimer.singleShot(0, window.window.close))
    wake = QTimer(app, interval=500)          # Python runs signal handlers between bytecodes
    wake.timeout.connect(lambda: None)
    wake.start()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
