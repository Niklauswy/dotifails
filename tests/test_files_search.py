"""wysun_files.core.search: the launcher's file search (same index, same scoring as FileSearch.mjs), without Qt."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_files.core import search  # noqa: E402

LINES = """dDocuments
dDocuments/Invoices
dDocuments/Invoices/2024
fDocuments/Invoices/2024/march.pdf
fDocuments/tesis final.pdf
fDownloads/Canción.mp3
d.config
f.config/secret-tesis.conf
fPictures/tesis.png
fnotas.md
"""


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.index = search.parse(LINES)

    def paths(self, query, limit=50):
        return [row[0] for row in search.search(self.index, query, limit)]

    def test_every_token_must_match_names_or_folders(self):
        self.assertEqual(self.paths('documents inv pdf'), ['Documents/Invoices/2024/march.pdf'])
        self.assertEqual(self.paths('nada-parecido'), [])
        self.assertEqual(self.paths('   '), [])

    def test_accents_and_case_are_folded(self):
        self.assertEqual(self.paths('CANCION'), ['Downloads/Canción.mp3'])

    def test_better_names_first_and_hidden_last(self):
        found = self.paths('tesis')
        self.assertEqual(found[0], 'Pictures/tesis.png')
        self.assertEqual(found[-1], '.config/secret-tesis.conf')

    def test_a_dot_asks_for_hidden_entries(self):
        self.assertEqual(self.paths('.conf')[0], '.config')

    def test_folders_are_marked_and_limit_applies(self):
        rows = search.search(self.index, 'invoices', 1)
        self.assertEqual(rows, [('Documents/Invoices', True)])

    def test_a_large_index_is_quick_enough(self):
        import time
        index = search.parse('\n'.join(f'fcarpeta{i % 50}/archivo{i}.txt' for i in range(100000)))
        started = time.perf_counter()
        search.search(index, 'archivo99', 150)
        self.assertLess(time.perf_counter() - started, 1.5)

    def test_load_missing_index_is_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(search.load(Path(folder) / 'no.idx').size, 0)


if __name__ == '__main__':
    unittest.main()
