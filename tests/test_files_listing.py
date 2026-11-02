"""wysun_files.core.listing: what a folder shows, without Qt (system Python)."""
from datetime import datetime
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))
from wysun_files.core import listing  # noqa: E402


def touch(path, data=b'', mtime=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_scan_lists_entries_with_stat_and_hidden_flag(self):
        touch(self.root / 'b.txt', b'hola')
        touch(self.root / '.oculto')
        (self.root / 'carpeta').mkdir()
        entries = {e.name: e for e in listing.scan(self.root)}
        self.assertEqual(set(entries), {'b.txt', '.oculto', 'carpeta'})
        self.assertTrue(entries['carpeta'].is_dir)
        self.assertEqual(entries['b.txt'].size, 4)
        self.assertTrue(entries['.oculto'].hidden)
        self.assertEqual(entries['b.txt'].path, str(self.root / 'b.txt'))

    def test_broken_symlink_is_listed_not_fatal(self):
        os.symlink(self.root / 'nada', self.root / 'roto')
        entries = {e.name: e for e in listing.scan(self.root)}
        self.assertIn('roto', entries)
        self.assertTrue(entries['roto'].symlink)
        self.assertFalse(entries['roto'].is_dir)

    def test_symlink_to_folder_counts_as_folder(self):
        (self.root / 'real').mkdir()
        os.symlink(self.root / 'real', self.root / 'enlace')
        entries = {e.name: e for e in listing.scan(self.root)}
        self.assertTrue(entries['enlace'].is_dir)
        self.assertTrue(entries['enlace'].symlink)

    def test_missing_folder_raises(self):
        with self.assertRaises(OSError):
            listing.scan(self.root / 'no-existe')


class ClassifyTests(unittest.TestCase):
    def kind(self, name, is_dir=False):
        return listing.classify(name, is_dir)

    def test_kinds_follow_the_mockup_categories(self):
        cases = {'a.jpg': 'image', 'a.MP4': 'video', 'a.ogg': 'audio', 'a.pdf': 'pdf', 'a.md': 'md', 'a.py': 'code',
                 'a.zip': 'archive', 'a.docx': 'doc', 'a.txt': 'doc', 'a.bin': 'other', 'Makefile': 'other'}
        for name, kind in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.kind(name).kind, kind)
        self.assertEqual(self.kind('x', True).kind, 'folder')

    def test_badge_and_role(self):
        pdf = self.kind('tesis.pdf')
        self.assertEqual((pdf.badge, pdf.role), ('PDF', 'error'))
        py = self.kind('main.py')
        self.assertEqual((py.badge, py.role), ('PY', 'tertiary'))
        self.assertEqual(self.kind('respaldo.tar.gz').badge, 'GZ')
        self.assertEqual(self.kind('sin-extension').badge, '')
        self.assertLessEqual(len(self.kind('a.verylongextension').badge), 4)

    def test_filter_groups_for_the_chips(self):
        groups = {'a.jpg': 'images', 'a.mkv': 'videos', 'a.flac': 'audio', 'a.pdf': 'documents', 'a.md': 'documents',
                  'a.odt': 'documents', 'a.rs': 'code', 'a.sh': 'code', 'a.zip': ''}
        for name, group in groups.items():
            with self.subTest(name=name):
                self.assertEqual(self.kind(name).group, group)

    def test_type_labels_are_spanish(self):
        self.assertEqual(self.kind('x', True).label, 'Carpeta')
        self.assertEqual(self.kind('a.pdf').label, 'Documento PDF')
        self.assertEqual(self.kind('a.png').label, 'Imagen')

    def test_special_folder_glyphs(self):
        self.assertEqual(listing.folder_glyph('/home/u/Descargas', 'Descargas'), 'download')
        self.assertEqual(listing.folder_glyph('/x/Music', 'Music'), 'music_note')
        self.assertEqual(listing.folder_glyph('/x/repos', 'repos'), 'code')
        self.assertEqual(listing.folder_glyph('/x/cualquiera', 'cualquiera'), '')
        self.assertEqual(listing.folder_glyph('/x/cosas', 'cosas', special={'/x/cosas': 'star'}), 'star')


class TextTests(unittest.TestCase):
    def test_modified_text(self):
        now = datetime(2026, 10, 26, 12, 0).timestamp()
        day = 86400
        self.assertEqual(listing.modified_text(now - 60, now), 'hoy')
        self.assertEqual(listing.modified_text(now - day, now), 'ayer')
        self.assertEqual(listing.modified_text(now - 3 * day, now), 'hace 3 días')
        self.assertEqual(listing.modified_text(datetime(2026, 10, 2, 9).timestamp(), now), '2 oct')
        self.assertEqual(listing.modified_text(datetime(2025, 5, 2, 9).timestamp(), now), 'may 2025')
        self.assertEqual(listing.modified_text(now + 3 * day, now), '29 oct')     # future dates are just dates

    def test_full_date(self):
        self.assertEqual(listing.full_date(datetime(2026, 10, 26, 12, 10).timestamp()), '26 oct 2026, 12:10')

    def test_size_text(self):
        self.assertEqual(listing.size_text(0), '0 B')
        self.assertEqual(listing.size_text(2_516_582), '2,4 MB')
        self.assertEqual(listing.size_text(1536), '1,5 KB')

    def test_count_text(self):
        self.assertEqual(listing.count_text(0), 'Vacía')
        self.assertEqual(listing.count_text(1), '1 elemento')
        self.assertEqual(listing.count_text(12), '12 elementos')
        self.assertEqual(listing.count_text(5000, capped=True), 'Más de 5000 elementos')

    def test_summary(self):
        entries = [listing.Entry('a', '/a', True, False, False, 0, 0), listing.Entry('b', '/b', False, False, False, 1_000_000, 0),
                   listing.Entry('c', '/c', False, False, False, 400_000, 0)]
        self.assertEqual(listing.summary(entries), '1 carpeta · 2 archivos · 1,3 MB')
        self.assertEqual(listing.summary([]), 'Vacía')
        self.assertEqual(listing.summary(entries[:1]), '1 carpeta')


class SortFilterTests(unittest.TestCase):
    def entries(self):
        E = listing.Entry
        return [E('b10.txt', '/b10.txt', False, False, False, 5, 30), E('B2.txt', '/B2.txt', False, False, False, 50, 10),
                E('zeta', '/zeta', True, False, False, 0, 5), E('Alfa', '/Alfa', True, False, False, 0, 40),
                E('foto.jpg', '/foto.jpg', False, False, False, 7, 20), E('.h', '/.h', False, True, False, 1, 1)]

    def names(self, rows):
        return [e.name for e in rows]

    def test_name_sort_is_natural_case_insensitive_folders_first(self):
        rows = listing.arrange(self.entries(), hidden=True)
        self.assertEqual(self.names(rows), ['Alfa', 'zeta', '.h', 'B2.txt', 'b10.txt', 'foto.jpg'])

    def test_descending_keeps_folders_first(self):
        rows = listing.arrange(self.entries(), key='name', descending=True)
        self.assertEqual(self.names(rows), ['zeta', 'Alfa', 'foto.jpg', 'b10.txt', 'B2.txt'])

    def test_sort_by_size_date_and_type(self):
        self.assertEqual(self.names(listing.arrange(self.entries(), key='size'))[2:], ['b10.txt', 'foto.jpg', 'B2.txt'])
        self.assertEqual(self.names(listing.arrange(self.entries(), key='modified'))[:2], ['zeta', 'Alfa'])
        self.assertEqual(self.names(listing.arrange(self.entries(), key='modified'))[2:], ['B2.txt', 'foto.jpg', 'b10.txt'])
        self.assertEqual(self.names(listing.arrange(self.entries(), key='kind'))[2:], ['B2.txt', 'b10.txt', 'foto.jpg'])

    def test_hidden_are_dropped_unless_asked(self):
        self.assertNotIn('.h', self.names(listing.arrange(self.entries())))

    def test_text_filter_ignores_case_and_accents_keeps_matching_folders_only(self):
        rows = listing.arrange(self.entries() + [listing.Entry('Canción.ogg', '/c', False, False, False, 1, 1)], text='CANCION')
        self.assertEqual(self.names(rows), ['Canción.ogg'])
        self.assertEqual(self.names(listing.arrange(self.entries(), text='al')), ['Alfa'])

    def test_kind_filter_keeps_folders(self):
        self.assertEqual(self.names(listing.arrange(self.entries(), group='images')), ['Alfa', 'zeta', 'foto.jpg'])
        self.assertEqual(self.names(listing.arrange(self.entries(), group='folders')), ['Alfa', 'zeta'])

    def test_accept_predicate_never_hides_folders(self):
        rows = listing.arrange(self.entries(), accept=lambda e: e.name.endswith('.jpg'))
        self.assertEqual(self.names(rows), ['Alfa', 'zeta', 'foto.jpg'])


class PeekTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_snippet_reads_first_lines_of_text(self):
        path = touch(self.root / 'n.md', '# Notas\n\nuno\ndos\ntres\ncuatro\ncinco\nseis\nsiete'.encode())
        self.assertEqual(listing.snippet(str(path)), ['# Notas', '', 'uno', 'dos', 'tres', 'cuatro'])

    def test_snippet_of_binary_or_unreadable_is_empty(self):
        self.assertEqual(listing.snippet(str(touch(self.root / 'b.txt', b'\0\1\2abc'))), [])
        self.assertEqual(listing.snippet(str(self.root / 'falta.txt')), [])

    def test_snippet_truncates_long_lines(self):
        path = touch(self.root / 'l.py', ('x' * 500).encode())
        self.assertEqual(len(listing.snippet(str(path))[0]), 48)

    def test_child_count_caps(self):
        (self.root / 'd').mkdir()
        for i in range(7):
            touch(self.root / 'd' / f'{i}')
        self.assertEqual(listing.child_count(str(self.root / 'd'), limit=5), (5, True))
        self.assertEqual(listing.child_count(str(self.root / 'd')), (7, False))
        self.assertEqual(listing.child_count(str(self.root / 'falta')), (0, False))


if __name__ == '__main__':
    unittest.main()
