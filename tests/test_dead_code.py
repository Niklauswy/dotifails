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


def shell_modules():
    return sorted(p.name for p in (ROOT / 'apps/shell/modules').iterdir() if p.is_dir())


def unimported_shell_modules(files):
    """Shell modules no file outside the module imports (``qs.modules.x``) or loads by path (``modules/x``)."""
    unused = []
    for module in shell_modules():
        own = ROOT / 'apps/shell/modules' / module
        # Provenance manifests (UPSTREAM.json) list every imported path; they load nothing.
        corpus = '\n'.join(t for p, t, _ in files if own not in p.parents and p.suffix != '.json')
        if not re.search(rf'qs\.modules\.{module}\b|modules/{module}\b', corpus):
            unused.append(module)
    return unused


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

    def test_every_shell_module_is_imported(self):
        self.assertEqual(unimported_shell_modules(corpus_files(ROOT)), [])

    def test_upstream_manifest_does_not_keep_shell_modules_alive(self):
        manifest_only = tuple(f for f in corpus_files(ROOT) if f[0].name == 'UPSTREAM.json')
        self.assertEqual(unimported_shell_modules(manifest_only), shell_modules())

    def test_real_lock_does_not_import_the_old_one(self):
        self.assertFalse((ROOT / 'apps/shell/modules/lock').exists())
        self.assertNotRegex((ROOT / 'apps/shell/lock.qml').read_text(), r'qs\.modules\.lock\s*$')

    def test_shell_has_no_unloaded_shortcuts_daemon(self):
        self.assertFalse((ROOT / 'apps/shell/daemons/Shortcuts.qml').exists())

    def test_upstream_manifest_lists_only_existing_files(self):
        data = json.loads((ROOT / 'apps/shell/UPSTREAM.json').read_text())
        missing = [f for f in data['imported_files'] if not (ROOT / 'apps/shell' / f).exists()]
        self.assertEqual(missing, [])

    DELETED = ('color_window.py', 'utility_material', 'notes_window.py', 'theme_demo', 'screen_lock',
               'wysun_fonts', 'clean_legacy', 'ui/components.py', 'ui/materials.py', 'apps/shell/modules/lock/',
               'Shortcuts.qml', '--pick-color', 'install-local.py', 'restore-materials.py',
               'portal_shortcuts', 'loomrec/integration.py', 'loomrec/analysis.py', 'loomrec/editing.py',
               'files_motion', 'files_visuals', 'desktop_common', 'link_preview', 'system_panels',
               'energy_data', 'clipboard_data')

    def test_docs_do_not_point_to_deleted_files(self):
        docs = [p for p in (ROOT / 'docs').rglob('*.md') if 'superpowers' not in p.parts]
        docs += [ROOT / n for n in ('README.md', 'ARCHITECTURE.md', 'THIRD_PARTY.md', 'AGENTS.md')]
        docs += list((ROOT / 'apps').glob('*/README.md')) + list((ROOT / 'apps').glob('*/UPSTREAM.md'))
        hits = [f'{p.relative_to(ROOT)}:{name}' for p in docs for name in self.DELETED if name in p.read_text()]
        self.assertEqual(hits, [])

    def test_subprocess_backends_count_as_alive(self):
        corpus = alive_names(ROOT)
        for backend in ('launcher_data', 'process_data', 'wysun_scheme', 'code_preview'):
            self.assertRegex(corpus, rf'\b{backend}\b')


if __name__ == '__main__':
    unittest.main()
