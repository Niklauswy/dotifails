"""One-shot Wysun Files selector. JSON request on stdin, JSON response on stdout.

Requests: documents (``suffix`` pdf|md, ``save``) for the reader, or ``kind: "audio"`` with ``multiple`` files or a
``directory`` for Wysun Music's import."""
import json
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from wysun_core.qt_theme import watch_theme
from wysun_files.chooser import FileChooser

AUDIO = ('m4a', 'opus', 'mp3', 'flac', 'ogg', 'wav', 'aac')     # what Wysun Music imports


def make_selector(request):
    initial = Path(request.get('initial') or str(Path.home())).expanduser()
    folder = initial if initial.is_dir() else initial.parent
    while not folder.is_dir() and folder != folder.parent:
        folder = folder.parent      # a moved PDF: start from the nearest folder that still exists
    if not folder.is_dir():
        folder = Path.home()
    kind = request.get('kind', 'document')
    if kind == 'audio':
        directory = bool(request.get('directory'))
        options = {'current_folder': os.fsencode(folder), 'multiple': bool(request.get('multiple')) and not directory,
                   'directory': directory, 'accept_label': 'Importar',
                   'filters': [] if directory else [('Audio', [(0, f'*.{s}') for s in AUDIO])]}
        return FileChooser('open', request.get('title', 'Importar música'), options)
    if kind != 'document':
        raise ValueError('Unsupported request kind')
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
