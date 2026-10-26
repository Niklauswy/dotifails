"""Wysun is the only name: no file, path or line keeps one of the identities it replaced."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Spelled in pieces so this file does not match itself.
FORMER = re.compile('|'.join(('or' + 'bit', 'loom' + 'rec', 'doti' + 'fails')), re.I)
# The GitHub repository keeps its name: it is an external identity, not one of Wysun's.
REPOSITORY = 'github.com/Niklauswy/' + 'doti' + 'fails'
SKIPPED_PREFIXES = ('docs/superpowers/',          # dated plans and designs: the history of this rename
                    'apps/shell/plugin/3rdparty/', 'apps/python/vendor/', 'LICENSES/', 'assets/icons/')
# Third-party provenance, and the emoji keywords, where the former name is an ordinary English word.
SKIPPED_FILES = {'THIRD_PARTY.md', 'apps/python/wysun_services/emojis.txt'}
BINARY = {'.png', '.jpg', '.gif', '.webp', '.ttf', '.otf', '.svg', '.gz', '.7z', '.xz', '.so', '.ico', '.mp4', '.pdf'}


class LegacyNameTests(unittest.TestCase):
    def test_no_file_path_or_line_uses_a_former_name(self):
        files = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                               stdout=subprocess.PIPE, check=True).stdout.decode().split('\0')
        offenders = []
        for relative in filter(None, files):
            if relative.startswith(SKIPPED_PREFIXES) or relative in SKIPPED_FILES:
                continue
            if FORMER.search(relative):
                offenders.append(relative)
                continue
            path = ROOT / relative
            if path.is_symlink() or not path.is_file() or path.suffix.lower() in BINARY:
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if FORMER.search(line.replace(REPOSITORY, '')):
                    offenders.append('%s:%d' % (relative, number))
        self.assertEqual(offenders, [])

    def test_former_environment_prefixes_are_gone(self):
        hits = subprocess.run(['git', '-C', str(ROOT), 'grep', '-nE', 'OR' + 'BIT_|DOTI' + 'FAILS_|LOOM' + 'REC_',
                               '--', '.', ':!docs/superpowers'], capture_output=True, text=True).stdout
        self.assertEqual(hits, '')


if __name__ == '__main__':
    unittest.main()
