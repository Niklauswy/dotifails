"""Atomic writes and XDG lookups live in wysun_core; nobody keeps a private copy."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# path → plan that removes it. Each entry must still need it (see the last test).
PENDING = {
    'apps/capture/loomrec/ui/theme_core.py': '02b',
    'apps/capture/loomrec/ui/tokens.py': '02b', 'apps/capture/loomrec/ui/motion.py': '02b',
    'apps/capture/loomrec/ui/app_kit.py': '02b',
    'apps/shell/modules/aiusage/backend.py': '04',
}
SCOPES = ('apps/wysun', 'apps/shell', 'apps/capture/loomrec')
ATOMIC = re.compile(r'os\.replace\(|mkstemp\(|\b\w+\.replace\(\s*(self\.)?\w*(path|target|dest|final)\w*\s*\)')
XDG = re.compile(r'XDG_(CONFIG|DATA|STATE|CACHE)_HOME|XDG_RUNTIME_DIR')


def sources():
    for scope in SCOPES:
        for path in sorted((ROOT / scope).rglob('*.py')):
            relative = path.relative_to(ROOT).as_posix()
            if '/wysun_core/' in relative or '/vendor/' in relative or '/tests/' in relative:
                continue
            yield relative, path


def offenders(pattern):
    found = []
    for relative, path in sources():
        if relative in PENDING:
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.search(line):
                found.append(f'{relative}:{number}')
    return found


class CoreOwnsIOTests(unittest.TestCase):
    maxDiff = None

    def test_atomic_writes_live_in_wysun_core(self):
        self.assertEqual(offenders(ATOMIC), [])

    def test_xdg_lookups_live_in_wysun_core(self):
        self.assertEqual(offenders(XDG), [])

    def test_pending_entries_still_need_it(self):
        for relative in PENDING:
            text = (ROOT / relative).read_text()
            self.assertTrue(ATOMIC.search(text) or XDG.search(text), f'{relative} no longer needs PENDING')


if __name__ == '__main__':
    unittest.main()
