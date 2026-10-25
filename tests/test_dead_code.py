"""Source trees carry no code that only tests or documents still use.

A module is alive when a non-test, non-documentation file refers to it the way
code actually loads it: an import, a ``name.py`` path, ``-m name`` or a quoted
module name. A module referred to only by dead modules is dead too.
"""
import functools
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_SUFFIXES = {'.py', '.qml', '.js', '.sh', '.lua', '.json', '.desktop', '.toml', ''}
SKIPPED_PREFIXES = ('tests/', 'apps/capture/tests/', 'docs/')
# Run by hand, never invoked: optional registration of the root pointer helper for the Recorder.
MANUAL_ENTRY_POINTS = {'installer/pointer_registration.py'}


@functools.lru_cache(maxsize=None)
def corpus_files(root):
    listed = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                            stdout=subprocess.PIPE, check=True).stdout.decode().split('\0')
    files = []
    for relative in filter(None, listed):
        path = root / relative
        if relative.startswith(SKIPPED_PREFIXES) or '/vendor/' in relative or path.suffix not in CORPUS_SUFFIXES:
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        is_python = path.suffix == '.py' or (path.suffix == '' and text.startswith('#!') and 'python' in text.split('\n', 1)[0])
        files.append((path, text, is_python))
    return tuple(files)


def references(stem, text, is_python, package=None, same_package=False):
    """``package`` is the dotted parent a qualified name must carry (``loomrec.ui``); relative imports
    count only for files of the same package, so ``from .components`` elsewhere is someone else's module."""
    qualified = rf'(\w+\.)*{re.escape(package)}\.' if package else None
    path_or_module = rf'(?<![\w-]){stem}\.py\b|-m\s+[\'"]?{stem}\b'
    if qualified:
        path_or_module += rf'|-m\s+[\'"]?{qualified}{stem}\b'
    if re.search(path_or_module, text):
        return True
    if not is_python:
        return False
    absolute = [rf'^\s*from\s+{stem}(\s|\.)', rf'^\s*import\s+([\w., ]*,\s*)?{stem}\b']
    if not package or same_package:
        absolute.append(rf'[\'"]{stem}[\'"]')  # a module list such as installer/ui_support MODULES
    if qualified:
        absolute += [rf'^\s*from\s+{qualified}{stem}(\s|\.)', rf'^\s*import\s+{qualified}{stem}\b',
                     rf'^\s*from\s+{qualified[:-2]}\s+import\s+([\w, ]*,\s*)?{stem}\b', rf'[\'"]{qualified}{stem}[\'"]']
    if same_package:
        absolute += [rf'^\s*from\s+\.{stem}(\s|\.)', rf'^\s*from\s+\.\s+import\s+([\w, ]*,\s*)?{stem}\b']
    return any(re.search(pattern, text, re.M) for pattern in absolute)


def alive_names(root):
    return '\n'.join(text for _, text, _ in corpus_files(root))


def dotted_package(package_dir):
    """``apps/capture/loomrec/ui`` → ``loomrec.ui``; a flat directory without ``__init__.py`` has none."""
    parts = []
    current = package_dir
    while (current / '__init__.py').exists():
        parts.insert(0, current.name)
        current = current.parent
    return '.'.join(parts) or None


def dead_python_modules(package_dir):
    candidates = {p.stem: p for p in package_dir.glob('*.py')
                  if p.stem != '__init__' and str(p.relative_to(ROOT)) not in MANUAL_ENTRY_POINTS}
    files = corpus_files(ROOT)
    package = dotted_package(package_dir)
    dead = set()
    while True:
        live_files = [(p, t, py) for p, t, py in files if not (p.parent == package_dir and p.stem in dead)]
        newly = {stem for stem, path in candidates.items() if stem not in dead and not any(
            p != path and references(stem, t, py, package, p.parent == package_dir) for p, t, py in live_files)}
        if not newly:
            return sorted(dead)
        dead |= newly


class DeadCodeTests(unittest.TestCase):
    def test_every_wysun_module_is_used_outside_tests(self):
        self.assertEqual(dead_python_modules(ROOT / 'apps/wysun'), [])

    def test_every_installer_module_is_used_outside_tests(self):
        self.assertEqual(dead_python_modules(ROOT / 'installer'), [])

    def test_every_recorder_ui_module_is_used_outside_tests(self):
        self.assertEqual(dead_python_modules(ROOT / 'apps/capture/loomrec/ui'), [])

    def test_every_recorder_module_is_used_outside_tests(self):
        self.assertEqual(dead_python_modules(ROOT / 'apps/capture/loomrec'), [])

    def test_recorder_has_no_portal_colour_picker(self):
        source = (ROOT / 'apps/capture/loomrec/__main__.py').read_text()
        self.assertNotIn('--pick-color', source)

    def test_subprocess_backends_count_as_alive(self):
        corpus = alive_names(ROOT)
        for backend in ('launcher_data', 'process_data', 'wysun_scheme', 'code_preview'):
            self.assertRegex(corpus, rf'\b{backend}\b')


if __name__ == '__main__':
    unittest.main()
