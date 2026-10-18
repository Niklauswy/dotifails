#!/usr/bin/env python3
"""Standalone Wysun file manager. Accepts local paths and file:// URLs."""
import sys
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMessageBox


def local_paths(arguments):
    paths = []
    for value in arguments:
        if value == '--':
            continue
        url = QUrl(value)
        if url.scheme() and not url.isLocalFile():
            raise ValueError('Solo se admiten carpetas locales: ' + value)
        path = Path(url.toLocalFile() if url.isLocalFile() else value).expanduser().absolute()
        if not path.exists():
            raise ValueError('La ubicación no existe: ' + str(path))
        paths.append(str(path if path.is_dir() else path.parent))
    return paths or [str(Path.home())]


def main():
    app = QApplication([sys.argv[0]])
    app.setApplicationName('Wysun Files')
    app.setOrganizationName('Orbita')
    app.setDesktopFileName('orbit-files')
    app.setStyle('Fusion')
    try:
        paths = local_paths(sys.argv[1:])
    except ValueError as exc:
        QMessageBox.warning(None, 'No se pudo abrir la ubicación', str(exc))
        return 1
    from files_window import FilesWindow
    from theme_tokens import watch_theme
    window = FilesWindow(paths=paths)
    watch_theme()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
