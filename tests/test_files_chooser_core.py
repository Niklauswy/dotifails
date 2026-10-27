"""The chooser's rules without a window (wysun_files.core.chooser)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_files.core.chooser import ChooserSession, local_path  # noqa: E402


class ChooserCoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.base = Path(self.dir.name)
        for name in ('first.png', 'second.png', 'notes.txt', 'space ñ.pdf'):
            (self.base / name).write_bytes(b'fixture')
        (self.base / 'folder').mkdir()

    def tearDown(self):
        self.dir.cleanup()

    def session(self, mode='open', **options):
        options['current_folder'] = os.fsencode(self.base) + b'\0'
        return ChooserSession(mode, 'Selector de prueba', options)

    def test_initial_folder_title_and_modes(self):
        s = self.session(multiple=True)
        self.assertEqual(s.initial_folder, str(self.base))
        self.assertEqual(s.title, 'Selector de prueba — Wysun Selector')
        self.assertTrue(s.multiple)
        self.assertTrue(self.session('savefiles').directory)
        self.assertEqual(ChooserSession('open', '', {'current_folder': b'/no/existe\0'}).initial_folder, str(Path.home()))

    def test_filters_intersect_query_and_keep_folders(self):
        s = self.session(filters=[('Imágenes', [(0, '*.png')]), ('PDF', [(1, 'application/pdf')])])
        self.assertTrue(s.accepts(self.base / 'first.png', False))
        self.assertFalse(s.accepts(self.base / 'notes.txt', False))
        self.assertTrue(s.accepts(self.base / 'folder', True))
        self.assertFalse(s.accepts(self.base / 'first.png', False, query='second'))
        s.filter_index = 1
        self.assertTrue(s.accepts(self.base / 'space ñ.pdf', False))
        self.assertFalse(s.accepts(self.base / 'first.png', False))

    def test_multiple_and_utf8_uris(self):
        s = self.session(multiple=True)
        state, targets = s.resolve(self.base, [self.base / 'first.png', self.base / 'space ñ.pdf'])
        self.assertEqual(state, 'ok')
        code, result = s.result(targets)
        self.assertEqual(code, 0)
        self.assertEqual(set(result['uris']), {(self.base / n).as_uri() for n in ('first.png', 'space ñ.pdf')})

    def test_cancel_returns_no_files(self):
        self.assertEqual(self.session().result([]), (1, {}))

    def test_directory_accepts_current_folder(self):
        state, targets = self.session(directory=True).resolve(self.base, [])
        self.assertEqual((state, targets), ('ok', [self.base]))

    def test_single_selection_and_disappearing_file(self):
        s = self.session()
        self.assertEqual(s.resolve(self.base, [self.base / 'first.png', self.base / 'second.png'])[0], 'error')
        (self.base / 'first.png').unlink()
        self.assertEqual(s.resolve(self.base, [self.base / 'first.png']),
                         ('error', 'La selección ya no está disponible o no es del tipo solicitado.'))

    def test_save_confirms_overwrite_and_never_writes(self):
        s = self.session('save', current_name='first.png')
        self.assertEqual(s.current_name, 'first.png')
        self.assertEqual(s.resolve(self.base, [], 'first.png')[0], 'confirm')
        self.assertEqual(s.resolve(self.base, [], 'first.png', replace=True), ('ok', [self.base / 'first.png']))
        self.assertEqual((self.base / 'first.png').read_bytes(), b'fixture')
        self.assertEqual(s.resolve(self.base, [], 'folder'), ('error', 'El nombre corresponde a una carpeta.'))

    def test_save_rejects_path_escape_and_adds_the_suffix(self):
        s = self.session('save', default_suffix='md')
        self.assertEqual(s.resolve(self.base, [], '../escape')[0], 'error')
        self.assertEqual(s.resolve(self.base, [], 'nota'), ('ok', [self.base / 'nota.md']))

    def test_savefiles_unique_names_without_writing(self):
        s = self.session('savefiles', files=[b'first.png\0', b'new.txt\0'])
        state, targets = s.resolve(self.base, [])
        self.assertEqual(targets, [self.base / 'first (1).png', self.base / 'new.txt'])
        self.assertFalse((self.base / 'new.txt').exists())

    def test_choices_and_filter_in_the_result(self):
        s = self.session(choices=[('mode', 'Modo', [('a', 'A'), ('b', 'B')], 'a'), ('readonly', 'Solo lectura', [], 'false')],
                         filters=[('Imágenes', [(0, '*.png')])])
        code, result = s.result([self.base / 'first.png'], {'mode': 'b', 'readonly': 'true'})
        self.assertEqual(result['choices'], [('mode', 'b'), ('readonly', 'true')])
        self.assertEqual(result['current_filter'], ('Imágenes', [(0, '*.png')]))

    def test_local_path_refuses_remote_uris(self):
        self.assertEqual(local_path('file:///tmp/a%20b'), Path('/tmp/a b'))
        with self.assertRaises(ValueError):
            local_path('https://example.com/x')


if __name__ == '__main__':
    unittest.main()
