import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'installer'))
import clean_legacy


class CleanLegacyTests(unittest.TestCase):
    def test_moves_only_known_leftovers_and_restores_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / '.config/wysun/caelestia').mkdir(parents=True)
            (home / '.config/wysun/caelestia/shell.json').write_text('{}')
            (home / '.local/share/orbit-v3-backup-1').mkdir(parents=True)
            (home / '.local/share/orbit/notes').mkdir(parents=True)
            (home / '.local/share/orbit/notes/a.md').write_text('private')
            (home / '.local/share/loomrec/projects').mkdir(parents=True)
            self.assertEqual(clean_legacy.clean(home, False), [])
            self.assertTrue((home / '.config/wysun/caelestia').exists(), 'a dry run changes nothing')
            moved = clean_legacy.clean(home, True, 'test')
            self.assertEqual(sorted(moved), ['.config/wysun/caelestia', '.local/share/orbit-v3-backup-1'])
            self.assertTrue((home / '.local/share/orbit/notes/a.md').exists())
            self.assertTrue((home / '.local/share/loomrec/projects').exists())
            vault = home / '.local/share/wysun-backups/clean-test'
            clean_legacy.restore(vault)
            self.assertEqual((home / '.config/wysun/caelestia/shell.json').read_text(), '{}')


if __name__ == '__main__':
    unittest.main()
