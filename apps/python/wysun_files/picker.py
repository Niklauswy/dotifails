"""One-shot Wysun Files selector. JSON request on stdin, JSON response on stdout."""
import json
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from wysun_core.qt_theme import watch_theme
from wysun_files.chooser import FileChooser


def make_selector(request):
    initial = Path(request.get('initial') or str(Path.home())).expanduser()
    folder = initial if initial.is_dir() else initial.parent
    while not folder.is_dir() and folder != folder.parent:
        folder = folder.parent      # a moved PDF: start from the nearest folder that still exists
    if not folder.is_dir():
        folder = Path.home()
    suffix = request.get('suffix', 'pdf')
    if suffix not in ('pdf', 'md'):
        raise ValueError('Unsupported document format')
    save = bool(request.get('save'))
    options = {'current_folder': os.fsencode(folder), 'multiple': False,
               'filters': [(suffix.upper(), [(0, f'*.{suffix}')])],
               'accept_label': 'Guardar' if save else 'Abrir'}
    if save:
        options['default_suffix'] = suffix
        options['current_name'] = initial.name if not initial.is_dir() else f'documento.{suffix}'
    return FileChooser('save' if save else 'open', request.get('title', 'Seleccionar documento'), options)


def main():
    request = json.loads(sys.stdin.buffer.readline(65536))
    app = QApplication([sys.argv[0]])
    app.setApplicationName('Wysun Files')
    app.setOrganizationName('Wysun')
    app.setDesktopFileName('wysun-files')
    app.setStyle('Fusion')
    chooser = make_selector(request)
    def completed(code, result):
        print(json.dumps(dict(code=code, **result)), flush=True)
        app.quit()
    chooser.completed.connect(completed)
    watch_theme()
    chooser.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
