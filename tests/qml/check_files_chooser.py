"""Wysun Files' file chooser in QML (venv Python, offscreen): the same window in selector mode (F-62…F-67): portal
filters (glob and MIME) that keep folders, folder mode, single and multiple selection, save with the default
suffix and a replace confirmation, save-files with unique names, choices, cancel, Enter that enters a folder or
accepts, no destructive keys, and the one-shot picker's requests (F-60)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402


class ChooserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import Qt
        cls.Qt = Qt
        cls.h = support.Harness.get()

    def setUp(self):
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        self.tmp = tempfile.TemporaryDirectory(prefix='files-choose-', dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'clases').mkdir()
        for name in ('playa.jpg', 'montaña.png', 'tesis.pdf', 'notas.md'):
            (self.root / name).write_bytes(b'x')
        self.results = []
        self.windows = []

    def open(self, mode='open', title='Adjuntar', **options):
        from PySide6.QtCore import QSettings
        from wysun_files.quick.chooser import QmlChooserWindow
        options.setdefault('current_folder', os.fsencode(str(self.root)) + b'\0')
        window = QmlChooserWindow(mode, title, options, settings=QSettings(str(self.root / 's.ini'), QSettings.IniFormat),
                                  thumbnails=False)
        self.warnings = []
        window.engine.warnings.connect(lambda errors: self.warnings.extend(e.toString() for e in errors))
        window.chooser.completed.connect(lambda code, result: self.results.append((code, result)))
        window.bridge.setReducedMotion(True)
        window.present()
        window.window.resize(1000, 700)
        self.windows.append(window)
        self.addCleanup(self._close, window)
        self.win = window
        self.model = window.files.property('current').property('model')
        self.assertTrue(self.h.wait_for(lambda: not self.model.property('loading'), 3000))
        self.h.pump(50)
        return window

    def _close(self, window):
        window.close()
        self.h.pump(20)

    def names(self):
        return [Path(self.model.pathAt(r)).name for r in range(self.model.rowCount())]

    def find(self, name):
        return self.h.find_in(self.win.window.contentItem(), name)

    def key(self, key, modifiers=None, text=''):
        self.h.key(self.win.window, key, modifiers, text)

    def select(self, *names):
        self.model.selectPaths([str(self.root / n) for n in names])
        self.h.pump(20)

    # ---------------------------------------------------------------- open
    def test_loads_with_its_title_and_no_warnings(self):
        self.open()
        self.assertEqual(self.win.window.property('title'), 'Adjuntar — Wysun Selector')
        self.assertEqual(self.warnings, [])
        self.assertIsNone(self.find('selectionBar'), 'no destructive actions in the chooser')

    def test_glob_filters_keep_folders_and_switch(self):
        self.open(filters=[('Imágenes', [(0, '*.jpg'), (0, '*.png')]), ('PDF', [(0, '*.pdf')])])
        self.assertEqual(self.names(), ['clases', 'montaña.png', 'playa.jpg'])
        self.win.chooser.setFilter(1)
        self.assertEqual(self.names(), ['clases', 'tesis.pdf'])

    def test_mime_filter_and_current_filter_option(self):
        filters = [('Todo', [(0, '*')]), ('Imágenes', [(1, 'image/*')])]
        self.open(filters=filters, current_filter=filters[1])
        self.assertEqual(self.names(), ['clases', 'montaña.png', 'playa.jpg'])

    def test_accepting_one_file(self):
        self.open(filters=[('Todo', [(0, '*')])], choices=[('enc', 'Codificación', [('utf8', 'UTF-8'), ('latin1', 'Latin-1')], 'utf8'),
                                                         ('sub', 'Incluir subcarpetas', [], 'false')])
        self.win.chooser.setChoice('enc', 'latin1')
        self.win.chooser.setChoice('sub', 'true')
        self.select('tesis.pdf')
        self.key(self.Qt.Key_Return, text='\r')
        self.assertEqual(len(self.results), 1)
        code, result = self.results[0]
        self.assertEqual(code, 0)
        self.assertEqual(result['uris'], [(self.root / 'tesis.pdf').as_uri()])
        self.assertEqual(result['current_filter'], ('Todo', [(0, '*')]))
        self.assertEqual(result['choices'], [('enc', 'latin1'), ('sub', 'true')])
        self.assertFalse(self.win.window.isVisible())

    def test_enter_on_a_folder_enters_it(self):
        self.open()
        self.select('clases')
        self.key(self.Qt.Key_Return, text='\r')
        self.assertTrue(self.h.wait_for(lambda: self.win.files.property('current').property('path') == str(self.root / 'clases'), 2000))
        self.assertEqual(self.results, [])

    def test_single_selection_unless_multiple(self):
        self.open()
        self.model.select(1, 'single')
        self.h.call(self.find('folderView'), 'press', 2, self.Qt.LeftButton, self.Qt.ControlModifier)
        self.assertEqual(len(self.model.property('selectedPaths')), 1)
        self.key(self.Qt.Key_A, self.Qt.ControlModifier, 'a')
        self.assertEqual(len(self.model.property('selectedPaths')), 1)

    def test_multiple(self):
        self.open(multiple=True)
        self.select('playa.jpg', 'tesis.pdf')
        self.h.call(self.win.window, 'accept')
        self.assertEqual(self.results[0][1]['uris'], [(self.root / 'playa.jpg').as_uri(), (self.root / 'tesis.pdf').as_uri()])

    def test_a_vanished_selection_is_an_error(self):
        self.open()
        self.select('notas.md')
        (self.root / 'notas.md').unlink()
        self.h.call(self.win.window, 'accept')
        self.assertEqual(self.results, [])
        self.assertIn('ya no está disponible', self.win.chooser.property('error'))

    def test_folder_mode_hides_files_and_returns_the_folder(self):
        self.open(directory=True, accept_label='Seleccionar')
        self.assertEqual(self.names(), ['clases'])
        self.h.call(self.win.window, 'accept')
        self.assertEqual(self.results[0][1]['uris'], [self.root.as_uri()])

    def test_cancel_and_escape_reply_cancelled(self):
        self.open()
        self.key(self.Qt.Key_Escape)
        self.assertEqual(self.results, [(1, {})])
        self.assertFalse(self.win.window.isVisible())

    def test_closing_the_window_cancels_once(self):
        self.open()
        self.win.window.close()
        self.h.pump(20)
        self.assertEqual(self.results, [(1, {})])

    def test_no_destructive_keys(self):
        self.open()
        self.select('tesis.pdf')
        self.key(self.Qt.Key_Delete)
        self.key(self.Qt.Key_F2)
        self.h.pump(50)
        self.assertTrue((self.root / 'tesis.pdf').exists())
        self.assertIsNone(self.find('trashDialog'))

    # ---------------------------------------------------------------- save
    def test_save_adds_the_suffix_and_confirms_replacing(self):
        self.open('save', 'Guardar documento', current_name='tesis', default_suffix='pdf')
        field = self.find('saveName')
        self.assertEqual(field.property('text'), 'tesis')
        self.h.call(self.win.window, 'accept')
        self.assertEqual(self.results, [])
        dialog = self.find('replaceDialog')
        self.assertTrue(dialog.property('opened'))
        self.assertEqual(dialog.property('title'), '¿Reemplazar «tesis.pdf»?')
        dialog.accepted.emit('replace')
        self.h.pump(20)
        self.assertEqual(self.results[0][1]['uris'], [(self.root / 'tesis.pdf').as_uri()])
        self.assertEqual((self.root / 'tesis.pdf').read_bytes(), b'x', 'the chooser never writes')

    def test_save_new_name_and_errors(self):
        self.open('save', 'Guardar')
        self.find('saveName').setProperty('text', 'clases')
        self.h.call(self.win.window, 'accept')
        self.assertEqual(self.win.chooser.property('error'), 'El nombre corresponde a una carpeta.')
        self.find('saveName').setProperty('text', 'a/b')
        self.h.call(self.win.window, 'accept')
        self.assertEqual(self.win.chooser.property('error'), 'Escribe un nombre de archivo válido.')
        self.find('saveName').setProperty('text', 'nuevo.txt')
        self.key(self.Qt.Key_Return, text='\r')
        self.assertEqual(self.results[0][1]['uris'], [(self.root / 'nuevo.txt').as_uri()])
        self.assertFalse((self.root / 'nuevo.txt').exists())

    def test_clicking_a_file_while_saving_takes_its_name(self):
        self.open('save', 'Guardar')
        self.model.select(self.model.rowOf(str(self.root / 'notas.md')), 'single')
        self.h.pump(20)
        self.assertEqual(self.find('saveName').property('text'), 'notas.md')

    def test_save_files_get_unique_names(self):
        self.open('savefiles', 'Guardar varios', files=[os.fsencode('tesis.pdf') + b'\0', os.fsencode('otro.txt') + b'\0'])
        self.h.call(self.win.window, 'accept')
        self.assertEqual(self.results[0][1]['uris'], [(self.root / 'tesis (1).pdf').as_uri(), (self.root / 'otro.txt').as_uri()])


class PickerRequestTests(unittest.TestCase):
    """What the one-shot picker asks for (stdin JSON) as chooser options."""

    def test_documents_and_audio(self):
        from wysun_files.picker import request_options
        home = str(Path.home())
        mode, title, options = request_options({'suffix': 'md', 'save': True, 'initial': home + '/no/existe/notas.md'})
        self.assertEqual(mode, 'save')
        self.assertEqual(options['default_suffix'], 'md')
        self.assertEqual(options['current_folder'], os.fsencode(home))
        self.assertEqual(options['current_name'], 'notas.md')
        mode, _title, options = request_options({'kind': 'audio', 'multiple': True})
        self.assertEqual((mode, options['multiple'], options['accept_label']), ('open', True, 'Importar'))
        self.assertIn((0, '*.flac'), options['filters'][0][1])
        _mode, _title, options = request_options({'kind': 'audio', 'directory': True})
        self.assertEqual((options['directory'], options['filters']), (True, []))
        with self.assertRaises(ValueError):
            request_options({'kind': 'video'})


if __name__ == '__main__':
    unittest.main()
