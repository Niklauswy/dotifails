#!/usr/bin/env python3
"""Standalone local Linux PDF reader."""
import sys
import os
import importlib.util
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMessageBox
from wysun_core import paths as core_paths
from wysun_core.qt_theme import watch_theme


def main():
    if any(arg in ('--help', '-h') for arg in sys.argv[1:]):
        print('Wysun PDF · lector local con anotaciones\nUso: wysun pdf [archivo.pdf ...]')
        return 0
    if importlib.util.find_spec('fitz') is None:
        runtime = core_paths.data('wysun', 'pdf-runtime')
        interpreter = runtime / 'bin/python3'
        if interpreter.is_file() and Path(sys.prefix) != runtime:
            os.execv(str(interpreter), [str(interpreter), os.path.realpath(__file__), *sys.argv[1:]])
    app = QApplication([sys.argv[0]])
    app.setApplicationName('Wysun PDF')
    app.setOrganizationName('Wysun')
    app.setDesktopFileName('wysun-pdf')
    app.setStyle('Fusion')
    watch_theme()
    if importlib.util.find_spec('fitz') is None:
        QMessageBox.warning(None, 'Wysun PDF', 'Falta el motor PDF (python3-fitz). Instala la dependencia del lector y vuelve a abrirlo.')
        return 1
    paths = []
    for value in sys.argv[1:]:
        if value == '--':
            continue
        url = QUrl(value)
        if url.scheme() and not url.isLocalFile():
            QMessageBox.warning(None, 'Wysun PDF', 'Solo se admiten documentos locales.')
            return 1
        paths.append(url.toLocalFile() if url.isLocalFile() else value)
    from pdf_window import PdfWindow
    windows = [PdfWindow(path) for path in paths] if paths else [PdfWindow()]
    for window in windows:
        window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
