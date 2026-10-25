"""Every file whose header points to THIRD_PARTY.md is actually named there."""
import itertools
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POINTER = re.compile(r'(Véanse|see|See) THIRD_PARTY\.md')


def expand(text):
    """``dir/{a,b}.qml`` → ``dir/a.qml dir/b.qml`` so brace-grouped notices count."""
    def one(token):
        parts = re.split(r'\{([^{}]*)\}', token)
        choices = [[p] if i % 2 == 0 else p.split(',') for i, p in enumerate(parts)]
        return [''.join(c) for c in itertools.product(*choices)]
    return ' '.join(name for token in re.findall(r'`([^`]+)`', text) for name in one(token))


class ThirdPartyTests(unittest.TestCase):
    def test_files_pointing_to_notices_are_named_in_them(self):
        notices = (ROOT / 'THIRD_PARTY.md').read_text()
        named = notices + '\n' + expand(notices)
        listed = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'], stdout=subprocess.PIPE,
                                check=True).stdout.decode().split('\0')
        missing = []
        for relative in filter(None, listed):
            path = ROOT / relative
            if relative == 'THIRD_PARTY.md' or not path.is_file():
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            if POINTER.search(text) and relative not in named and f'/{path.name}' not in named and path.name not in expand(notices).split():
                missing.append(relative)
        self.assertEqual(missing, [])


if __name__ == '__main__':
    unittest.main()
