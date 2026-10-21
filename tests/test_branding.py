"""The shell must not depend on the identity of the project it was derived from (credits excepted)."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMER = 'cae' + 'lestia'
# Legal provenance: licence text, per-file import hashes, third-party notices and architecture notes.
ALLOWED_FILES = {'THIRD_PARTY.md', 'ARCHITECTURE.md', 'apps/shell/UPSTREAM.json', 'apps/shell/LICENSE', 'apps/shell/README.md',
                 'apps/capture/UPSTREAM.md', 'docs/credits.md', 'tests/test_branding.py',
                 # Migration/cleanup of state stored under the former name, and the tests of that migration.
                 'installer/clean_legacy.py', 'installer/wayland.py', 'tests/test_clean_legacy.py',
                 'tests/test_wayland_install.py', 'tests/check_manifest.py'}


class BrandingTests(unittest.TestCase):
    def test_no_identifier_uses_the_former_project_name(self):
        files = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                               stdout=subprocess.PIPE, check=True).stdout.decode().split('\0')
        offenders = []
        for relative in filter(None, files):
            if relative in ALLOWED_FILES or relative.startswith(('assets/icons/', 'LICENSES/')):
                continue
            if FORMER in relative.lower():
                offenders.append(relative)
                continue
            path = ROOT / relative
            if not path.is_file() or path.suffix in {'.png', '.jpg', '.gif', '.webp', '.ttf', '.svg', '.gz', '.7z', '.xz', '.so', '.ico'}:
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                # Attribution headers ("Derivado de <upstream>/shell (GPL-3.0)") are legally required.
                if FORMER in line.lower() and not re.search(FORMER + r'-dots|' + FORMER + r'shell\.com', line, re.I):
                    offenders.append('%s:%d' % (relative, number))
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
