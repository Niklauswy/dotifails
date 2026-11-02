"""One-shot Wysun Files selector. JSON request on stdin, JSON response on stdout (F-60).

Requests: documents (``suffix`` pdf|md, ``save``), or ``kind: "audio"`` with ``multiple`` files or a ``directory``
for Wysun Music's import. The answer is ``{"code": 0|1, "uris": [...], ...}`` as the portal would reply."""
import json
import os
import sys
from pathlib import Path

AUDIO = ('m4a', 'opus', 'mp3', 'flac', 'ogg', 'wav', 'aac')     # what Wysun Music imports


def request_options(request):
    """``(mode, title, options)`` of a picker request, as the portal would pass them."""
    initial = Path(request.get('initial') or str(Path.home())).expanduser()
    folder = initial if initial.is_dir() else initial.parent
    while not folder.is_dir() and folder != folder.parent:
        folder = folder.parent      # a moved file: start from the nearest folder that still exists
    if not folder.is_dir():
        folder = Path.home()
    kind = request.get('kind', 'document')
    if kind == 'audio':
        directory = bool(request.get('directory'))
        options = {'current_folder': os.fsencode(folder), 'multiple': bool(request.get('multiple')) and not directory,
                   'directory': directory, 'accept_label': 'Importar',
                   'filters': [] if directory else [('Audio', [(0, f'*.{s}') for s in AUDIO])]}
        return 'open', request.get('title', 'Importar música'), options
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
    return ('save' if save else 'open'), request.get('title', 'Seleccionar documento'), options


def main(argv=None):
    argv = sys.argv if argv is None else argv
    from wysun_qml import bootstrap
    bootstrap.ensure_runtime_python('wysun_files.picker', argv[1:])     # before reading stdin: exec keeps it unread
    request = json.loads(sys.stdin.buffer.readline(65536))
    mode, title, options = request_options(request)
    bootstrap.require_qt()
    bootstrap.configure_qt()
    from wysun_files.quick.chooser import QmlChooserWindow
    window = QmlChooserWindow(mode, title, options)
    window.app.setApplicationName('Wysun Files')
    window.app.setDesktopFileName('wysun-files')

    def completed(code, result):
        result = dict(result)
        if 'current_filter' in result:
            name, rules = result['current_filter']
            result['current_filter'] = [name, [list(rule) for rule in rules]]
        if 'choices' in result:
            result['choices'] = [list(pair) for pair in result['choices']]
        print(json.dumps(dict(code=code, **result)), flush=True)
        window.app.quit()

    window.chooser.completed.connect(completed)
    window.present()
    return window.app.exec()


if __name__ == '__main__':
    sys.exit(main())
