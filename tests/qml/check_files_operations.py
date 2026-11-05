"""Wysun Files' operations for QML (venv Python): clipboard formats and cut marks, copy/move off the GUI thread
one at a time with progress, conflicts that stop with the exact name, new folder/file and rename with validation,
the trash (in a private XDG_DATA_HOME) with undo, properties, opening and the terminal (F-40…F-49)."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402


class CleanExitTests(unittest.TestCase):
    def test_quitting_after_copying_does_not_crash(self):
        # Qt announces the clipboard while the application goes away; nothing of ours may still listen.
        script = '''
import sys, tempfile
from pathlib import Path
from wysun_qml import bootstrap
bootstrap.preload_qt()
from PySide6.QtCore import QSettings
from wysun_files.quick.window import QmlFilesWindow
folder = Path(tempfile.mkdtemp())
(folder / "a.txt").write_text("a")
window = QmlFilesWindow([str(folder)], settings=QSettings(str(folder / "s.ini"), QSettings.IniFormat), thumbnails=False)
window.present()
window.ops.copy([str(folder / "a.txt")])
window.app.processEvents()
window.close()
'''
        done = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])

    def test_quitting_the_event_loop_after_copying_does_not_crash(self):
        # As app.main does it: the window and the application end with the function.
        script = '''
import sys, tempfile
from pathlib import Path
from wysun_qml import bootstrap
bootstrap.preload_qt()
def main():
    from PySide6.QtCore import QSettings, QTimer
    from wysun_files.quick.window import QmlFilesWindow
    folder = Path(tempfile.mkdtemp())
    (folder / "a.txt").write_text("a")
    window = QmlFilesWindow([str(folder)], settings=QSettings(str(folder / "s.ini"), QSettings.IniFormat), thumbnails=False)
    window.app.aboutToQuit.connect(window.close)
    window.present()
    window.ops.copy([str(folder / "a.txt")])
    QTimer.singleShot(100, window.window.close)
    return window.app.exec()
sys.exit(main())
'''
        done = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])


class OperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()

    def setUp(self):
        from PySide6.QtCore import QSettings
        from wysun_files.quick.controller import FilesController
        from wysun_files.quick.operations import Operations
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        self.tmp = tempfile.TemporaryDirectory(prefix='files-ops-', dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src, self.dst = self.root / 'origen', self.root / 'destino'
        self.src.mkdir()
        self.dst.mkdir()
        (self.src / 'a.txt').write_text('a')
        (self.src / 'b.txt').write_text('b')
        data = self.root / 'data'
        patcher = patch.dict(os.environ, {'XDG_DATA_HOME': str(data)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.files = FilesController([str(self.src)], settings=QSettings(str(self.root / 's.ini'), QSettings.IniFormat),
                                     thumbnails=False)
        self.addCleanup(self.files.close)
        self.ops = Operations(self.files)
        self.addCleanup(self.ops.close)
        self.messages, self.failures = [], []
        self.ops.message.connect(self.messages.append)
        self.ops.failed.connect(lambda title, text: self.failures.append(text))
        self.h.wait_for(lambda: not self.model().property('loading'), 2000)

    def tearDown(self):
        # These tests stand in for another app with a QMimeData made in Python: it must not outlive the interpreter.
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().clear()

    def model(self):
        return self.files.property('current').property('model')

    def idle(self, ms=5000):
        self.assertTrue(self.h.wait_for(lambda: not self.ops.property('busy'), ms), 'operation still running')
        self.h.pump(20)

    def paths(self, *names):
        return [str(self.src / n) for n in names]

    # ---------------------------------------------------------------- clipboard
    def test_copy_puts_every_format_on_the_clipboard(self):
        from PySide6.QtGui import QGuiApplication
        self.ops.copy(self.paths('a.txt', 'b.txt'))
        mime = QGuiApplication.clipboard().mimeData()
        self.assertEqual([u.toLocalFile() for u in mime.urls()], self.paths('a.txt', 'b.txt'))
        self.assertTrue(bytes(mime.data('x-special/gnome-copied-files')).startswith(b'copy\nfile://'))
        self.assertEqual(mime.text(), '\n'.join(self.paths('a.txt', 'b.txt')))
        self.assertTrue(self.ops.property('canPaste'))
        self.assertEqual(self.messages[-1], '2 elementos copiados')

    def test_paste_copies_in_a_thread_and_reports_progress(self):
        progress = []
        self.ops.progressChanged.connect(lambda: progress.append(self.ops.property('busyText')))
        self.ops.copy(self.paths('a.txt', 'b.txt'))
        self.ops.paste(str(self.dst))
        self.assertTrue(self.ops.property('busy'))
        self.idle()
        self.assertEqual(sorted(p.name for p in self.dst.iterdir()), ['a.txt', 'b.txt'])
        self.assertTrue((self.src / 'a.txt').exists())
        self.assertIn('Copiando 2 de 2', progress)
        self.assertEqual(self.messages[-1], 'Copiado')

    def test_cut_marks_rows_then_paste_moves_and_clears_the_clipboard(self):
        from PySide6.QtGui import QGuiApplication
        self.ops.cut(self.paths('a.txt'))
        row = self.model().rowOf(str(self.src / 'a.txt'))
        cut_role = [r for r, n in self.model().roleNames().items() if bytes(n) == b'cut'][0]
        self.assertTrue(self.model().data(self.model().index(row), cut_role))
        self.ops.paste(str(self.dst))
        self.idle()
        self.assertTrue((self.dst / 'a.txt').exists())
        self.assertFalse((self.src / 'a.txt').exists())
        mime = QGuiApplication.clipboard().mimeData()
        self.assertFalse(mime is not None and mime.hasUrls())
        self.assertFalse(self.ops.property('canPaste'))

    def test_a_name_in_use_stops_everything_with_its_name(self):
        (self.dst / 'b.txt').write_text('ya')
        self.ops.copy(self.paths('a.txt', 'b.txt'))
        self.ops.paste(str(self.dst))
        self.idle()
        self.assertFalse((self.dst / 'a.txt').exists(), 'nothing is copied when one target exists')
        self.assertEqual((self.dst / 'b.txt').read_text(), 'ya')
        self.assertIn('Ya existe', self.failures[-1])
        self.assertIn('b.txt', self.failures[-1])

    def test_one_operation_at_a_time(self):
        import threading
        gate = threading.Event()
        from wysun_files import ops as module
        real = module.execute_operation

        def slow(*args, **kwargs):
            gate.wait(5)
            return real(*args, **kwargs)
        with patch.object(module, 'execute_operation', side_effect=slow):
            self.ops.copy(self.paths('a.txt'))
            self.ops.paste(str(self.dst))
            self.assertFalse(self.ops.mkdir(str(self.dst), 'otra'))
            self.assertEqual(self.messages[-1], 'Espera a que termine la operación actual')
            gate.set()
            self.idle()
        self.assertTrue((self.dst / 'a.txt').exists())

    def test_ending_keeps_what_another_app_copied(self):
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QGuiApplication
        from wysun_files.quick.operations import _release_clipboard
        mime = QMimeData()
        mime.setText('ajeno')
        QGuiApplication.clipboard().setMimeData(mime)
        _release_clipboard()
        self.assertEqual(QGuiApplication.clipboard().text(), 'ajeno')
        self.ops.copy(self.paths('a.txt'))
        _release_clipboard()
        self.assertFalse(self.ops.property('canPaste'))

    def test_paste_takes_files_copied_in_other_apps(self):
        from PySide6.QtCore import QMimeData, QUrl
        from PySide6.QtGui import QGuiApplication
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.src / 'b.txt'))])
        QGuiApplication.clipboard().setMimeData(mime)
        self.assertTrue(self.h.wait_for(lambda: self.ops.property('canPaste'), 500))
        self.ops.paste(str(self.dst))
        self.idle()
        self.assertTrue((self.dst / 'b.txt').exists())

    # ---------------------------------------------------------------- names
    def test_validate_name(self):
        self.assertEqual(self.ops.validateName('tesis.pdf'), '')
        self.assertEqual(self.ops.validateName('a/b'), 'El nombre no puede contener «/».')
        self.assertEqual(self.ops.validateName(''), 'Escribe un nombre.')
        self.assertEqual(self.ops.validateName('..'), 'El nombre no puede ser «.» ni «..».')

    def test_suggested_names_do_not_collide(self):
        (self.dst / 'Carpeta nueva').mkdir()
        self.assertEqual(self.ops.freeName(str(self.dst), 'Carpeta nueva'), 'Carpeta nueva (2)')
        self.assertEqual(self.ops.freeName(str(self.dst), 'Sin título.txt'), 'Sin título.txt')

    def test_mkdir_new_file_and_rename(self):
        self.assertTrue(self.ops.mkdir(str(self.dst), 'clases'))
        self.idle()
        self.assertTrue((self.dst / 'clases').is_dir())
        self.assertTrue(self.ops.newFile(str(self.dst), 'notas.md'))
        self.idle()
        self.assertEqual((self.dst / 'notas.md').read_text(), '')
        self.assertTrue(self.ops.rename(str(self.dst / 'notas.md'), 'apuntes.md'))
        self.idle()
        self.assertTrue((self.dst / 'apuntes.md').exists())
        self.assertTrue(self.ops.newFile(str(self.dst), 'apuntes.md'))
        self.idle()
        self.assertIn('Ya existe', self.failures[-1])
        self.assertFalse(self.ops.rename(str(self.dst / 'apuntes.md'), 'x/y'))

    def test_the_new_entry_is_selected(self):
        self.files.property('current').navigate(str(self.dst))
        self.h.wait_for(lambda: not self.model().property('loading'), 2000)
        self.ops.mkdir(str(self.dst), 'nueva')
        self.idle()
        self.assertTrue(self.h.wait_for(lambda: self.model().property('selectedPaths') == [str(self.dst / 'nueva')], 3000))

    # ---------------------------------------------------------------- trash
    def test_trash_never_deletes_and_undo_restores(self):
        trashed = []
        self.ops.trashed.connect(lambda count: trashed.append(count))
        self.ops.trash(self.paths('a.txt', 'b.txt'))
        self.idle(10000)
        self.assertEqual(trashed, [2])
        self.assertFalse((self.src / 'a.txt').exists())
        trash = Path(os.environ['XDG_DATA_HOME']) / 'Trash'
        self.assertEqual(sorted(p.name for p in (trash / 'files').iterdir()), ['a.txt', 'b.txt'])
        self.ops.undoTrash()
        self.idle()
        self.assertEqual((self.src / 'a.txt').read_text(), 'a')
        self.assertEqual((self.src / 'b.txt').read_text(), 'b')
        self.assertEqual(list((trash / 'files').iterdir()), [])
        self.assertEqual(self.messages[-1], '2 elementos restaurados')

    def test_undo_does_not_overwrite(self):
        self.ops.trash(self.paths('a.txt'))
        self.idle(10000)
        (self.src / 'a.txt').write_text('nuevo')
        self.ops.undoTrash()
        self.idle()
        self.assertEqual((self.src / 'a.txt').read_text(), 'nuevo')
        self.assertIn('Ya existe', self.failures[-1])

    # ---------------------------------------------------------------- open, properties, terminal
    def test_open_routes_by_kind(self):
        (self.src / 'foto.jpg').write_bytes(b'x')
        (self.src / 'clip.mp4').write_bytes(b'x')
        (self.src / 'doc.pdf').write_bytes(b'x')
        from wysun_files.quick import operations as module
        with patch.object(module, 'launch') as player, patch.object(module, 'open_pdf') as pdf, \
                patch.object(module.QDesktopServices, 'openUrl', return_value=True) as desktop:
            self.ops.open(self.paths('foto.jpg', 'a.txt', 'clip.mp4', 'doc.pdf'))
        player.assert_called_once_with(self.paths('foto.jpg', 'clip.mp4'))
        pdf.assert_called_once_with(str(self.src / 'doc.pdf'))
        self.assertEqual(desktop.call_args.args[0].toLocalFile(), str(self.src / 'a.txt'))

    def test_open_refuses_more_than_ten(self):
        from wysun_files.quick import operations as module
        with patch.object(module.QDesktopServices, 'openUrl') as desktop:
            self.ops.open([str(self.src / 'a.txt')] * 11)
        desktop.assert_not_called()
        self.assertEqual(self.failures[-1], 'Abre hasta 10 archivos a la vez.')

    def test_properties(self):
        os.symlink(self.src / 'a.txt', self.src / 'enlace')
        info = self.ops.properties(str(self.src / 'a.txt'))
        rows = {r['label']: r['value'] for r in info['rows']}
        self.assertEqual(info['name'], 'a.txt')
        self.assertEqual(rows['Ruta'], str(self.src))
        self.assertEqual(rows['Tamaño'], '1 B')
        self.assertRegex(rows['Permisos'], r'^[r-][w-][x-][r-][w-][x-][r-][w-][x-] · ')
        link = {r['label']: r['value'] for r in self.ops.properties(str(self.src / 'enlace'))['rows']}
        self.assertEqual(link['Destino del enlace'], str(self.src / 'a.txt'))
        folder = self.ops.properties(str(self.src))
        self.assertEqual({r['label']: r['value'] for r in folder['rows']}['Contiene'], '3 elementos')

    def test_terminal_opens_in_the_folder(self):
        from wysun_files.quick import operations as module
        with patch.object(module.shutil, 'which', side_effect=lambda name: '/usr/bin/kitty' if name == 'kitty' else None), \
                patch.object(module.subprocess, 'Popen') as popen:
            self.ops.terminal(str(self.dst))
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], ['/usr/bin/kitty'])
        self.assertEqual(popen.call_args.kwargs['cwd'], str(self.dst))

    def test_ghostty_gets_its_own_instance_in_the_folder(self):
        # With gtk-single-instance a launch goes to the running instance, which ignores the working directory.
        from wysun_files.quick import operations as module
        with patch.object(module.shutil, 'which', side_effect=lambda name: '/usr/bin/ghostty' if name == 'ghostty' else None), \
                patch.object(module.subprocess, 'Popen') as popen:
            self.ops.terminal(str(self.dst))
        self.assertEqual(popen.call_args.args[0], ['/usr/bin/ghostty', '--gtk-single-instance=false', f'--working-directory={self.dst}'])

    def test_share_on_the_network_starts_lanshare_detached(self):
        from wysun_files.quick import operations as module
        with patch.object(module.subprocess, 'Popen') as popen:
            self.assertTrue(self.ops.shareOnNetwork([str(self.src)], True, True))
        argv, kwargs = popen.call_args.args[0], popen.call_args.kwargs
        self.assertEqual(argv[0], str(Path(sys.base_prefix) / 'bin/python3'), 'the system Python, not the QML venv')
        self.assertEqual(argv[1:], ['-P', '-m', 'wysun_lanshare', '--subidas', '--clave', '--', str(self.src)])
        self.assertTrue(kwargs['start_new_session'])
        self.assertNotIn('QML_IMPORT_PATH', kwargs['env'])
        self.assertIn('PYTHONPATH', kwargs['env'])
        with patch.object(module.subprocess, 'Popen') as popen:
            self.assertTrue(self.ops.shareOnNetwork(self.paths('a.txt', 'b.txt'), True, False))
        self.assertEqual(popen.call_args.args[0][1:], ['-P', '-m', 'wysun_lanshare', '--', *self.paths('a.txt', 'b.txt')],
                         'uploads only for one folder')
        self.assertFalse(self.ops.shareOnNetwork([], False, False))

    def test_sharing_a_risky_folder_with_uploads_says_why_instead_of_failing_silently(self):
        from wysun_files.quick import operations as module
        with patch.object(module.subprocess, 'Popen') as popen, patch.dict(os.environ, {'HOME': str(self.src)}):
            self.assertFalse(self.ops.shareOnNetwork([str(self.src)], True, False))
            popen.assert_not_called()
            self.assertIn('carpeta personal', self.failures[-1])
            self.assertTrue(self.ops.shareOnNetwork([str(self.src)], False, False), 'read-only is fine')

    def test_upload_to_drive_starts_wysun_drive_detached(self):
        from wysun_files.quick import operations as module
        with patch.object(module.subprocess, 'Popen') as popen:
            self.assertTrue(self.ops.uploadToDrive(self.paths('a.txt', 'b.txt'), True))
        argv, kwargs = popen.call_args.args[0], popen.call_args.kwargs
        self.assertEqual(argv[0], str(Path(sys.base_prefix) / 'bin/python3'))
        self.assertEqual(argv[1:], ['-P', '-m', 'wysun_drive', 'up', '--notificar', '--origen', 'files', '--link', '--', *self.paths('a.txt', 'b.txt')])
        self.assertTrue(kwargs['start_new_session'])
        self.assertIn('PYTHONPATH', kwargs['env'])
        with patch.object(module.subprocess, 'Popen') as popen:
            self.assertTrue(self.ops.uploadToDrive(self.paths('a.txt'), False))
        self.assertNotIn('--link', popen.call_args.args[0])
        self.assertFalse(self.ops.uploadToDrive([], True))

    def test_uris_for_dragging(self):
        self.assertEqual(self.ops.uris(self.paths('a.txt')), ['file://' + str(self.src / 'a.txt')])


if __name__ == '__main__':
    unittest.main()
