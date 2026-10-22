"""Anti-regression: UI modules take colours from theme tokens, never from literals.

A literal colour (#rgb/#rrggbb/#aarrggbb, rgb()/rgba(), QColor with numbers or a
hex string, Qt.white/Qt.black...) is allowed only when justified on the same
line (``# theme-exception: reason`` / ``// theme-exception: reason``) or inside a
``theme-exception-begin: reason`` ... ``theme-exception-end`` block. ``Qt.transparent``
is not a colour. The imported shell tree (apps/shell, except its wysun/ bridge) takes every colour from
Colours.palette, which the single Wysun scheme producer fills; its own literals are upstream design.
Whole files that are not themed UI are listed in FILE_EXCEPTIONS.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ['apps/wysun', 'apps/capture/loomrec/ui', 'apps/shell/wysun', 'installer', 'bin']
SUFFIXES = {'.py', '.qml', '.js'}
# path -> justification. These files never render themed UI.
FILE_EXCEPTIONS = {
    'installer/session_registration.py': 'system session files, not a themed surface',
}
HEX = re.compile(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|(?<![\w&])#[0-9a-fA-F]{3}\b(?![\w])")
FUNCTIONS = re.compile(r"\brgba?\(|\bQColor\(\s*\d|\bQColor\(\s*['\"]#|\bQt\.(white|black|red|green|blue|gray|darkGray|lightGray|yellow|cyan|magenta|darkRed|darkGreen|darkBlue)\b")
MARK = re.compile(r"(?:#|//)\s*theme-exception(?!-)")


def sources():
    for base in SCANNED:
        for path in sorted((ROOT / base).rglob('*')):
            relative = path.relative_to(ROOT).as_posix()
            if not path.is_file() or '__pycache__' in path.parts or 'tests' in path.parts or path.name.startswith('test_'):
                continue
            if relative in FILE_EXCEPTIONS:
                continue
            if path.suffix in SUFFIXES or (base == 'bin' and not path.suffix):
                try:
                    yield relative, path.read_text().splitlines()
                except (OSError, UnicodeDecodeError):
                    continue


def violations(lines):
    inside = False
    found = []
    for number, line in enumerate(lines, 1):
        if 'theme-exception-begin' in line:
            inside = True
        elif 'theme-exception-end' in line:
            inside = False
        elif not inside and (HEX.search(line) or FUNCTIONS.search(line)) and not MARK.search(line):
            found.append(number)
    return found


class ThemeLiteralTests(unittest.TestCase):
    def test_ui_modules_use_tokens_instead_of_literal_colours(self):
        report = []
        for relative, lines in sources():
            for number in violations(lines):
                report.append(f'{relative}:{number}: {lines[number - 1].strip()[:110]}')
        self.assertEqual(report, [], 'Use a theme token, or justify the literal with "theme-exception: reason":\n' + '\n'.join(report))

    def test_every_exception_block_is_closed_and_has_a_reason(self):
        for relative, lines in sources():
            begins = sum('theme-exception-begin' in line for line in lines)
            ends = sum('theme-exception-end' in line for line in lines)
            self.assertEqual(begins, ends, relative)
            for line in lines:
                if 'theme-exception-begin' in line:
                    self.assertRegex(line, r'theme-exception-begin:\s*\S', relative + ' needs a reason')

    def test_scanner_flags_what_it_should(self):
        self.assertEqual(violations(["x = '#ff0000'", "ok = 1  # theme-exception: sample", "c = QColor(1, 2, 3)", "t = Qt.transparent", "w = Qt.white", "css = 'rgba(0,0,0,1)'"]), [1, 3, 5, 6])
        self.assertEqual(violations(["# theme-exception-begin: svg", "a = '#fff'", "# theme-exception-end", "b = '#fff'"]), [4])

    def test_exception_files_exist(self):
        for relative in FILE_EXCEPTIONS:
            self.assertTrue((ROOT / relative).is_file(), relative)


if __name__ == '__main__':
    unittest.main()
