"""Wysun Files' QML window acting on files (venv Python, offscreen, private trash): copy/paste by keyboard, the
trash dialog and «Deshacer», name dialogs with validation, the context menu's states, properties and a close
that waits for a running operation (F-05, F-31, F-40…F-47)."""
import os
from pathlib import Path
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


class FilesActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QSettings, Qt
        from wysun_files.quick.window import QmlFilesWindow
        cls.Qt = Qt
        cls.h = support.Harness.get()
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        cls.tmp = tempfile.TemporaryDirectory(prefix='files-act-', dir=scratch)
        base = Path(cls.tmp.name)
        cls.root, cls.other = base / 'casa', base / 'otra'
        cls.root.mkdir()
        cls.other.mkdir()
        cls.win = QmlFilesWindow([str(cls.root)], settings=QSettings(str(base / 's.ini'), QSettings.IniFormat), thumbnails=False)
        cls.warnings = []
        cls.win.engine.warnings.connect(lambda errors: cls.warnings.extend(e.toString() for e in errors))
        cls.win.bridge.setReducedMotion(True)
        cls.window = cls.win.window
        cls.win.present()
        cls.window.resize(1180, 800)
        cls.files, cls.ops = cls.win.files, cls.win.ops
        # A private trash; only now (the runtime is found through XDG_DATA_HOME while the engine starts).
        cls.env = patch.dict(os.environ, {'XDG_DATA_HOME': str(base / 'data')})
        cls.env.start()
        cls.h.pump(100)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.win.close()
        cls.h.pump(30)
        cls.env.stop()
        cls.tmp.cleanup()

    def setUp(self):
        for folder in (self.root, self.other):
            for item in folder.iterdir():
                if item.is_dir():
                    import shutil
                    shutil.rmtree(item)
                else:
                    item.unlink()
        (self.root / 'tesis.pdf').write_text('pdf')
        (self.root / 'notas.md').write_text('# n')
        self.tab().navigate(str(self.root))
        self.wait()
        self.model().clearSelection()
        self.warnings.clear()
        self.h.call(self.window, 'focusFiles')
        self.h.pump(30)

    def tab(self):
        return self.files.property('current')

    def model(self):
        return self.tab().property('model')

    def wait(self):
        self.assertTrue(self.h.wait_for(lambda: not self.model().property('loading') and not self.ops.property('busy'), 5000))
        self.h.pump(60)

    def find(self, name):
        return self.h.find_in(self.window.contentItem(), name)

    def key(self, key, modifiers=None, text=''):
        self.h.key(self.window, key, modifiers, text)

    def select(self, *names):
        self.model().selectPaths([str(self.root / n) for n in names])
        self.h.pump(20)

    def names(self, folder):
        return sorted(p.name for p in folder.iterdir())

    def opened(self, name):
        return bool(self.find(name).property('opened'))

    def test_copy_and_paste_by_keyboard(self):
        self.select('tesis.pdf')
        self.key(self.Qt.Key_C, self.Qt.ControlModifier, 'c')
        self.tab().navigate(str(self.other))
        self.wait()
        self.key(self.Qt.Key_V, self.Qt.ControlModifier, 'v')
        self.wait()
        self.assertEqual(self.names(self.other), ['tesis.pdf'])
        self.assertTrue(self.h.wait_for(lambda: self.model().property('selectedPaths') == [str(self.other / 'tesis.pdf')], 3000),
                        'what was pasted is selected')
        self.assertEqual(self.warnings, [])

    def test_delete_asks_then_trashes_and_undo_brings_it_back(self):
        self.select('notas.md', 'tesis.pdf')
        self.key(self.Qt.Key_Delete)
        self.assertTrue(self.opened('trashDialog'))
        self.assertEqual(self.find('trashDialog').property('title'), '¿Enviar 2 elementos a la papelera?')
        self.h.call(self.find('trashDialog'), 'close')
        self.find('trashDialog').accepted.emit('trash')
        self.wait()
        self.assertEqual(self.names(self.root), [])
        snackbars = self.find('snackbars')
        for _ in range(10):                   # earlier messages may still be queued
            if snackbars.property('currentText') == '2 elementos en la papelera':
                break
            self.h.call(snackbars, 'dismiss')
            self.h.pump(20)
        self.assertEqual(snackbars.property('currentText'), '2 elementos en la papelera')
        self.find('snackbars').actionTriggered.emit('Deshacer')
        self.wait()
        self.assertEqual(self.names(self.root), ['notas.md', 'tesis.pdf'])

    def test_rename_preselects_the_stem_and_refuses_bad_names(self):
        self.select('tesis.pdf')
        self.key(self.Qt.Key_F2)
        self.assertTrue(self.opened('nameDialog'))
        field = self.find('nameField')
        self.assertEqual(field.property('text'), 'tesis.pdf')
        self.assertEqual(self.h.call(self.window.property('dialogs'), 'selectedName'), 'tesis')
        field.setProperty('text', 'a/b')
        self.key(self.Qt.Key_Return, text='\r')
        self.assertTrue(self.opened('nameDialog'), 'stays open on a bad name')
        self.assertEqual(field.property('errorText'), 'El nombre no puede contener «/».')
        field.setProperty('text', 'final.pdf')
        self.key(self.Qt.Key_Return, text='\r')
        self.wait()
        self.assertFalse(self.opened('nameDialog'))
        self.assertEqual(self.names(self.root), ['final.pdf', 'notas.md'])

    def test_new_folder_by_keyboard_is_created_and_selected(self):
        (self.root / 'Carpeta nueva').mkdir()
        self.wait()
        self.key(self.Qt.Key_N, self.Qt.ControlModifier | self.Qt.ShiftModifier, 'N')
        self.assertTrue(self.opened('nameDialog'))
        self.assertEqual(self.find('nameField').property('text'), 'Carpeta nueva (2)')
        self.key(self.Qt.Key_Return, text='\r')
        self.wait()
        self.assertTrue((self.root / 'Carpeta nueva (2)').is_dir())
        self.assertTrue(self.h.wait_for(lambda: self.model().property('selectedPaths') == [str(self.root / 'Carpeta nueva (2)')], 3000))

    def test_context_menu_states(self):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().clear()
        self.select('tesis.pdf')
        self.h.call(self.find('folderView'), 'contextAtCurrent')
        menu = self.find('contextMenu')
        entries = {e['id']: e for e in menu.property('model').toVariant() if 'id' in e}
        self.assertTrue(entries['paste'].get('disabled'))
        self.assertFalse(entries['rename'].get('disabled', False))
        self.assertTrue(entries['tab'].get('disabled'), 'a file does not open in a tab')
        self.h.call(menu, 'close')
        self.h.call(self.find('folderView'), 'contextAt', -1, 50, 50)
        background = [e['id'] for e in menu.property('model').toVariant() if 'id' in e]
        self.assertNotIn('rename', background)
        self.assertIn('newFolder', background)
        self.h.call(menu, 'close')

    def test_properties_dialog(self):
        self.h.call(self.win.window.property('dialogs'), 'properties', str(self.root / 'tesis.pdf'))
        self.assertTrue(self.opened('propertiesDialog'))
        self.assertEqual(self.find('propertiesName').property('text'), 'tesis.pdf')
        self.h.call(self.find('propertiesDialog'), 'close')

    def test_closing_waits_for_a_running_operation(self):
        import threading
        from wysun_files import ops as module
        gate, real = threading.Event(), module.execute_operation

        def slow(*args, **kwargs):
            gate.wait(5)
            return real(*args, **kwargs)
        with patch.object(module, 'execute_operation', side_effect=slow):
            self.select('notas.md')
            self.key(self.Qt.Key_C, self.Qt.ControlModifier, 'c')
            self.ops.paste(str(self.other))
            self.window.close()
            self.h.pump(50)
            self.assertTrue(self.window.isVisible(), 'kept open while copying')
            self.assertIn('Copiando', self.find('operationText').property('text'))
            gate.set()
            self.assertTrue(self.h.wait_for(lambda: not self.window.isVisible(), 5000))
        self.assertEqual(self.names(self.other), ['notas.md'])
        self.window.setProperty('closeWhenIdle', False)
        self.win.present()
        self.window.resize(1180, 800)
        self.h.pump(50)


if __name__ == '__main__':
    unittest.main()
