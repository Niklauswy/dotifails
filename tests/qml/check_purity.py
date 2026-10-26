"""The library stays pure: no shell coupling, no literal colours/durations, every file registered in qmldir."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / 'apps/qml/WysunM3'
ALLOWED_IMPORTS = {'QtQuick', 'QtQuick.Shapes', 'M3Shapes', 'WysunM3'}      # decision D3
MARK = re.compile(r'//\s*theme-exception')
HEX = re.compile(r'#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|(?<![\w&])#[0-9a-fA-F]{3}\b(?![\w])')
CALLS = re.compile(r'\brgba?\(|Qt\.rgba\(\s*[\d.]|Qt\.(?:white|black|red|green|blue|gray|darkGray|lightGray|yellow|cyan|magenta)\b')
DURATION = re.compile(r'\bduration\s*:\s*[1-9]')
EASING = re.compile(r'Easing\.(?!BezierSpline|Linear)\w+')


def sources():
    return sorted(path for path in LIBRARY.rglob('*.qml'))


def scripts():
    return sorted(path for path in LIBRARY.rglob('*.js'))


def code_lines(path):
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not MARK.search(line):
            yield number, line.split('//')[0] if '//' in line and 'http' not in line else line


class PurityTests(unittest.TestCase):
    def test_library_is_not_empty(self):
        self.assertGreater(len(sources()), 4)

    def test_library_imports_only_allowed_modules(self):
        for path in sources():
            for number, line in code_lines(path):
                match = re.match(r'\s*import\s+([\w.]+)', line)
                if match:
                    self.assertIn(match.group(1), ALLOWED_IMPORTS, f'{path.relative_to(ROOT)}:{number}')
                quoted = re.match(r'\s*import\s+"([^"]*)"', line)
                if quoted:       # only a helper script next to the file, never a path into another tree
                    target = quoted.group(1)
                    self.assertRegex(target, r'^[\w-]+\.js$', f'{path.relative_to(ROOT)}:{number}')
                    self.assertTrue((path.parent / target).is_file(), f'{path.relative_to(ROOT)}:{number}')

    def test_no_literal_colours(self):
        for path in sources() + scripts():
            for number, line in code_lines(path):
                self.assertIsNone(HEX.search(line) or CALLS.search(line), f'{path.relative_to(ROOT)}:{number}: {line.strip()}')

    def test_no_literal_durations_or_stock_easings(self):
        for path in sources():
            for number, line in code_lines(path):
                self.assertIsNone(DURATION.search(line) or EASING.search(line), f'{path.relative_to(ROOT)}:{number}: {line.strip()}')

    def test_qmldir_lists_every_component_file(self):
        qmldir = (LIBRARY / 'qmldir').read_text()
        listed = set(re.findall(r'^\s*(?:singleton\s+|internal\s+)?\w+\s+[\d.]+\s+(\S+\.qml)\s*$', qmldir, re.M))
        listed |= set(re.findall(r'^\s*(?:singleton\s+|internal\s+)?\w+\s+(\S+\.qml)\s*$', qmldir, re.M))
        for path in sources():
            self.assertIn(path.relative_to(LIBRARY).as_posix(), listed, f'{path.name} is not registered in qmldir')
        for name in listed:
            self.assertTrue((LIBRARY / name).is_file(), name + ' is listed but missing')


if __name__ == '__main__':
    unittest.main()
