"""File operations for the QML window (F-40…F-49): the clipboard (text/uri-list, x-special/gnome-copied-files and
text, so other file managers understand it), copy/move/trash/new/rename through ``wysun_files.ops`` in a worker
thread and one at a time, with progress for the status line, undo for the trash, properties, opening by kind
(Wysun Player for media, the browser for PDF, the system for the rest) and a terminal in a folder. ``ops`` keeps its
guarantees: it never overwrites and never deletes for good."""
import atexit
import os
from pathlib import Path
import shutil
import stat as stat_module
import subprocess
import sys
import threading

from PySide6.QtCore import Property, QMimeData, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from wysun_core import paths as core_paths
from wysun_core.launch import TERMINALS, argv as module_argv
from wysun_files import ops
from wysun_files.browser import open_pdf
from wysun_files.core import listing
from wysun_lanshare.options import risky_upload_folder
from wysun_media.source import kind_of as media_kind
from wysun_player.client import child_environment, launch

GNOME = 'x-special/gnome-copied-files'
OURS = 'application/x-wysun-files'         # marks what this process put on the clipboard
OPEN_LIMIT = 10
VERBS = {'copy': 'Copiando', 'move': 'Moviendo', 'trash': 'Enviando a la papelera', 'mkdir': 'Creando carpeta',
         'rename': 'Cambiando nombre', 'touch': 'Creando archivo', 'restore': 'Restaurando'}
DONE = {'copy': 'Copiado', 'move': 'Movido', 'mkdir': 'Carpeta creada', 'rename': 'Nombre cambiado',
        'touch': 'Archivo creado'}


def _release_clipboard():
    """Give up what we put on the clipboard as the process ends (it would not outlive us anyway): PySide must not be
    left destroying that data while the interpreter shuts down, which crashes. Someone else's content stays."""
    if QGuiApplication.instance() is None:
        return
    clipboard = QGuiApplication.clipboard()
    mime = clipboard.mimeData()
    if mime is not None and mime.hasFormat(OURS):
        clipboard.clear()
        QGuiApplication.processEvents()


atexit.register(_release_clipboard)


def _items(count):
    return '1 elemento' if count == 1 else f'{count} elementos'


def _trash_dirs(original):
    """The trash a file went to: the home one, or the ``.Trash-<uid>`` of its own disk."""
    found = [core_paths.data_home() / 'Trash']
    path = Path(original).parent
    try:
        device = path.stat().st_dev
        while path.parent != path and path.parent.stat().st_dev == device:
            path = path.parent
        found.append(path / f'.Trash-{os.getuid()}')
    except OSError:
        pass
    return found


def _touch(target):
    """Create an empty file, failing if the name is taken (O_EXCL)."""
    ops.validate_name(Path(target).name)
    if os.path.lexists(target):
        raise FileExistsError(f'Ya existe: {target}. Elige otro nombre.')
    os.close(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644))
    return [str(target)]


def _restore(originals):
    restored = []
    for original in originals:
        last = None
        for trash in _trash_dirs(original):
            if ops.trashed_name(original, trash) is not None:
                restored.append(ops.restore_from_trash(original, trash))
                last = None
                break
            last = FileNotFoundError(f'No está en la papelera: {original}')
        if last is not None:
            raise last
    return restored


class _Relay(QObject):
    progressed = Signal(int, int)
    finished = Signal(str, object, str)          # kind, result, error


class Operations(QObject):
    busyChanged = Signal()
    progressChanged = Signal()
    clipboardChanged = Signal()
    message = Signal(str)
    failed = Signal(str, str)                    # title, text
    trashed = Signal(int)                        # count (the window offers «Deshacer»)
    finished = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent or controller)
        self.controller = controller
        self._busy, self._kind, self._done, self._total = False, '', 0, 0
        self._undo = []
        self._snapshot = b''
        self._select = []
        self._relay = _Relay(self)
        self._relay.progressed.connect(self._progressed, Qt.QueuedConnection)
        self._relay.finished.connect(self._finished, Qt.QueuedConnection)
        clipboard = QGuiApplication.clipboard()
        clipboard.dataChanged.connect(self._clipboard_changed)
        QGuiApplication.instance().aboutToQuit.connect(_release_clipboard)
        self._clipboard_changed()

    # ---------------------------------------------------------------- state
    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    @Property(str, notify=progressChanged)
    def busyText(self):
        if not self._busy:
            return ''
        verb = VERBS.get(self._kind, 'Trabajando')
        return f'{verb} {self._done + 1 if self._done < self._total else self._done} de {self._total}' if self._total > 1 else f'{verb}…'

    @Property(float, notify=progressChanged)
    def progress(self):
        return self._done / self._total if self._busy and self._total > 1 else -1.0

    @Property(bool, notify=clipboardChanged)
    def canPaste(self):
        mime = QGuiApplication.clipboard().mimeData()
        return bool(mime and any(url.isLocalFile() for url in mime.urls()))

    @Property(bool, notify=busyChanged)
    def canUndo(self):
        return bool(self._undo) and not self._busy

    # ---------------------------------------------------------------- clipboard
    def _set_clipboard(self, paths, cut):
        mime = QMimeData()
        urls = [QUrl.fromLocalFile(p) for p in paths]
        mime.setUrls(urls)
        mime.setData(GNOME, (('cut' if cut else 'copy') + '\n' + '\n'.join(u.toString() for u in urls)).encode())
        mime.setText('\n'.join(paths))
        mime.setData(OURS, b'1')
        QGuiApplication.clipboard().setMimeData(mime)

    @Slot('QVariantList')
    def copy(self, paths):
        if paths:
            self._set_clipboard(list(paths), False)
            self.message.emit(f'{_items(len(paths))} copiados' if len(paths) > 1 else '1 elemento copiado')

    @Slot('QVariantList')
    def cut(self, paths):
        if paths:
            self._set_clipboard(list(paths), True)
            self.message.emit(f'{_items(len(paths))} listos para mover' if len(paths) > 1 else '1 elemento listo para mover')

    @Slot()
    def _clipboard_changed(self):
        mime = QGuiApplication.clipboard().mimeData()
        cut = []
        if mime is not None and bytes(mime.data(GNOME)).startswith(b'cut\n'):
            cut = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
        self.controller.setCut(cut)
        self.clipboardChanged.emit()

    @Slot(str)
    def paste(self, folder):
        mime = QGuiApplication.clipboard().mimeData()
        paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()] if mime else []
        if not paths:
            return
        self._snapshot = bytes(mime.data(GNOME))
        kind = 'move' if self._snapshot.startswith(b'cut\n') else 'copy'
        self._start(kind, lambda progress: ops.execute_operation(kind, paths, folder, progress=progress), len(paths),
                    select=[os.path.join(folder, os.path.basename(p)) for p in paths])

    @Slot('QVariantList', result='QVariantList')
    def uris(self, paths):
        """``file://`` URLs of ``paths`` (what a drag towards another app carries)."""
        return [QUrl.fromLocalFile(p).toString() for p in paths]

    # ---------------------------------------------------------------- running
    def _start(self, kind, work, total, select=()):
        if self._busy:
            self.message.emit('Espera a que termine la operación actual')
            return False
        self._busy, self._kind, self._done, self._total = True, kind, 0, max(1, total)
        self._select = list(select)
        self.busyChanged.emit()
        self.progressChanged.emit()
        relay = self._relay

        def run():
            try:
                result, error = work(lambda done, all_: relay.progressed.emit(done, all_)), ''
            except Exception as problem:            # reported to the user, never raised in Qt
                result, error = [], str(problem)
            relay.finished.emit(kind, result, error)

        threading.Thread(target=run, name='wysun-files-op', daemon=False).start()
        return True

    @Slot(int, int)
    def _progressed(self, done, total):
        self._done, self._total = done, max(1, total)
        self.progressChanged.emit()

    @Slot(str, object, str)
    def _finished(self, kind, result, error):
        self._busy = False
        if error:
            self.failed.emit('La operación no se completó', error)
        elif kind == 'trash':
            self._undo = list(result)
            self.trashed.emit(len(result))
        elif kind == 'restore':
            self._undo = []
            self.message.emit(f'{_items(len(result))} restaurados' if len(result) > 1 else '1 elemento restaurado')
            self._select = list(result)
        else:
            self.message.emit(DONE.get(kind, 'Listo'))
            if kind == 'move':
                mime = QGuiApplication.clipboard().mimeData()
                if self._snapshot.startswith(b'cut\n') and mime is not None and bytes(mime.data(GNOME)) == self._snapshot:
                    QGuiApplication.clipboard().clear()
        if not error and self._select:
            tab = self.controller.current
            for path in result or []:
                if self.controller.thumbs is not None:
                    self.controller.thumbs.forget(path)
            if os.path.dirname(self._select[0]) == tab.property('path'):
                tab.model.refresh()
                tab.select_when_loaded(self._select)
        self._select = []
        self.busyChanged.emit()
        self.progressChanged.emit()
        self.finished.emit()

    # ---------------------------------------------------------------- names
    @Slot(str, result=str)
    def validateName(self, name):
        if not name:
            return 'Escribe un nombre.'
        if '/' in name:
            return 'El nombre no puede contener «/».'
        if name in ('.', '..'):
            return 'El nombre no puede ser «.» ni «..».'
        if '\0' in name:
            return 'El nombre no puede contener caracteres nulos.'
        return ''

    @Slot(str, str, result=str)
    def freeName(self, folder, name):
        """``name``, or ``name (2)``… when it is taken (a proposal; the operation still refuses collisions)."""
        stem, suffix = (name, '') if os.path.isdir(os.path.join(folder, name)) else os.path.splitext(name)
        candidate, index = name, 2
        while os.path.lexists(os.path.join(folder, candidate)):
            candidate = f'{stem} ({index}){suffix}'
            index += 1
        return candidate

    @Slot(str, str, result=bool)
    def mkdir(self, folder, name):
        if self.validateName(name):
            return False
        target = os.path.join(folder, name)
        return self._start('mkdir', lambda progress: ops.execute_operation('mkdir', [], target), 1, select=[target])

    @Slot(str, str, result=bool)
    def newFile(self, folder, name):
        if self.validateName(name):
            return False
        target = os.path.join(folder, name)
        return self._start('touch', lambda progress: _touch(target), 1, select=[target])

    @Slot(str, str, result=bool)
    def rename(self, path, name):
        if self.validateName(name) or name == os.path.basename(path):
            return False
        target = os.path.join(os.path.dirname(path), name)
        return self._start('rename', lambda progress: ops.execute_operation('rename', [path], target), 1, select=[target])

    # ---------------------------------------------------------------- trash
    @Slot('QVariantList', result=bool)
    def trash(self, paths):
        paths = list(paths)
        if not paths:
            return False
        return self._start('trash', lambda progress: ops.execute_operation('trash', paths, '', progress=progress), len(paths))

    @Slot(result=bool)
    def undoTrash(self):
        originals = list(self._undo)
        if not originals:
            return False
        return self._start('restore', lambda progress: _restore(originals), len(originals), select=originals)

    # ---------------------------------------------------------------- opening
    @Slot('QVariantList')
    def open(self, paths):
        paths = [p for p in paths if p]
        if len(paths) > OPEN_LIMIT:
            self.failed.emit('Selecciona menos archivos', 'Abre hasta 10 archivos a la vez.')
            return
        media = [p for p in paths if os.path.isfile(p) and media_kind(p)]
        if media:
            launch(media)                        # one Wysun Player window for all of them, in order
        for path in paths:
            if path in media or os.path.isdir(path):
                continue
            if path.lower().endswith('.pdf'):
                try:
                    open_pdf(path)
                except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                    self.failed.emit('No se pudo abrir el PDF', str(error))
            elif not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                self.failed.emit('No se pudo abrir', 'No hay una aplicación disponible para abrir este archivo.')

    @Slot(str)
    def terminal(self, folder):
        for command in TERMINALS:
            binary = shutil.which(command)
            if binary:
                # Ghostty's single instance would open the window wherever it runs, ignoring where we ask.
                argv = [binary, '--gtk-single-instance=false', f'--working-directory={folder}'] if command == 'ghostty' else [binary]
                subprocess.Popen(argv, cwd=folder, start_new_session=True, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return
        self.failed.emit('Terminal no disponible', 'No se encontró una terminal compatible.')

    @Slot('QVariantList', bool, bool, result=bool)
    def shareOnNetwork(self, paths, uploads, password):
        """`wysun lanshare PATH… [--subidas] [--clave]` on its own: the bar shows it and stops it from then on."""
        paths = [p for p in paths if p]
        if not paths:
            return False
        args = []
        if uploads and len(paths) == 1 and os.path.isdir(paths[0]):
            # LANShare refuses these and, detached, its message would reach nobody.
            if risky_upload_folder(paths[0]):
                self.failed.emit('No se pudo compartir', 'Con subidas no se puede compartir tu carpeta personal, / ni '
                                 'carpetas de programas. Comparte una subcarpeta, por ejemplo Descargas.')
                return False
            args.append('--subidas')
        if password:
            args.append('--clave')
        # LANShare is stdlib + wysun_core: the system Python, outside the QML venv's Qt setup.
        argv = module_argv('wysun_lanshare', *args, '--', *paths, python=str(Path(sys.base_prefix) / 'bin/python3'))
        try:
            subprocess.Popen(argv, env=child_environment(), cwd=os.path.dirname(paths[0]) or None, start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as error:
            self.failed.emit('No se pudo compartir', error.strerror or str(error))
            return False
        return True

    # ---------------------------------------------------------------- properties
    @Slot(str, result='QVariantMap')
    def properties(self, path):
        target = Path(path)
        try:
            info = target.lstat()
        except OSError as error:
            return {'name': target.name, 'error': str(error), 'rows': []}
        is_dir = target.is_dir()
        kind = listing.classify(target.name, is_dir)
        rows = [{'label': 'Ruta', 'value': str(target.parent) if target.name else '/'}]
        if target.is_symlink():
            rows.append({'label': 'Tipo', 'value': 'Enlace simbólico'})
            rows.append({'label': 'Destino del enlace', 'value': os.readlink(target)})
        else:
            rows.append({'label': 'Tipo', 'value': kind.label})
        if is_dir:
            count, capped = listing.child_count(path)
            rows.append({'label': 'Contiene', 'value': listing.count_text(count, capped)})
        else:
            rows.append({'label': 'Tamaño', 'value': listing.size_text(info.st_size)})
        try:
            owner = __import__('pwd').getpwuid(info.st_uid).pw_name
        except (KeyError, ImportError):
            owner = str(info.st_uid)
        rows.append({'label': 'Permisos', 'value': f'{stat_module.filemode(info.st_mode)[1:]} · {owner}'})
        rows.append({'label': 'Modificado', 'value': listing.full_date(info.st_mtime)})
        created = getattr(info, 'st_birthtime', None)
        if created:
            rows.append({'label': 'Creado', 'value': listing.full_date(created)})
        subtitle = kind.label if is_dir else f'{kind.label} · {listing.size_text(info.st_size)}'
        return {'name': target.name or '/', 'subtitle': subtitle, 'kind': kind.kind, 'icon': kind.icon,
                'badge': kind.badge, 'role': kind.role, 'rows': rows, 'path': str(target)}

    def close(self):
        """Stop listening: Qt announces the clipboard while the application goes away."""
        try:
            QGuiApplication.clipboard().dataChanged.disconnect(self._clipboard_changed)
        except (RuntimeError, TypeError):
            pass
