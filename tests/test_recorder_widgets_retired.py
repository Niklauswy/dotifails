"""The Recorder's Widgets window, its embedded player and wysun_media's Widgets player are gone, and nothing points at them."""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
RETIRED_FILES = [
    *(f'apps/recorder/wysun_recorder/ui/{name}.py' for name in
      ('app_window', 'app_library', 'app_pages', 'app_kit', 'media_host', 'tokens', 'material', 'icons', 'motion')),
    *(f'apps/python/wysun_media/{name}.py' for name in
      ('player', 'controls', 'bar', 'menus', 'audio', 'image', 'video', 'shape', 'symbols', 'host')),
    'apps/recorder/tests/test_player_component.py',
    'tests/media_host.py', 'tests/wayland_media_case.py', 'tests/media_benchmark.py', 'tests/test_media_integration.py',
    *(f'tests/test_media_{name}.py' for name in ('player', 'controls', 'image', 'shape')),
]
EVERYWHERE = re.compile('|'.join((
    r'wysun_media[./](player|controls|bar|menus|audio|image|video|shape|symbols|host)\b',
    r'from wysun_media import [^\n]*\b(host|symbols|shape|controls|image|video|player|Host|install_host|MediaPlayer)\b',
    r'wysun_recorder[./]ui[./](app_|media_host|tokens|material|icons|motion)',
    r'\b(request_show|take_show_request)\b',
    r'wayland_media_case|media_benchmark|tests/media_host|test_media_(player|controls|image|shape|integration)',
)))
RECORDER_ONLY = re.compile(r"'--show'|\"--show\"")
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.superpowers', 'vendor', 'superpowers'}      # docs/superpowers is history
SUFFIXES = {'.py', '.md', '.qml', '.json', '.sh', '.toml'}


def sources():
    for base in ('apps', 'tests', 'docs', 'installer', 'bin', 'manifests'):
        for path in (ROOT / base).rglob('*'):
            if path.is_file() and path.suffix in SUFFIXES and not SKIP_DIRS & set(path.parts) \
                    and path != Path(__file__).resolve():
                yield path
    for name in ('ARCHITECTURE.md', 'AGENTS.md'):
        yield ROOT / name


class RetiredTests(unittest.TestCase):
    def test_retired_files_are_gone(self):
        self.assertEqual([name for name in RETIRED_FILES if (ROOT / name).exists() or (ROOT / name).is_symlink()], [])

    def test_nothing_references_the_retired_names(self):
        found = []
        for path in sources():
            text = path.read_text(errors='ignore')
            for number, line in enumerate(text.splitlines(), 1):
                relative = path.relative_to(ROOT).as_posix()
                if EVERYWHERE.search(line) or (RECORDER_ONLY.search(line) and relative.startswith(('apps/recorder', 'bin/'))):
                    found.append(f'{relative}:{number}: {line.strip()[:100]}')
        self.assertEqual(found, [])

    def test_recorder_ui_does_not_pull_in_qt_widgets(self):
        code = ('import sys; sys.path[:0] = [%r, %r]\n'
                'import wysun_recorder.ui.controller\n'
                "print('PySide6.QtWidgets' in sys.modules)" % (str(ROOT / 'apps/recorder'), str(ROOT / 'apps/python')))
        done = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=60)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, 'False'), done.stderr[-500:])

    def test_the_recorder_no_longer_lists_or_edits_videos(self):
        code = ('import sys; sys.path[:0] = [%r, %r]\n'
                'from wysun_recorder import library, videolibrary\n'
                'names = ("entries", "rename", "organize", "delete", "restore", "create_edit", "enrich", "thumbnail")\n'
                'print([n for n in names if hasattr(videolibrary.VideoLibrary, n)], hasattr(library, "Entry"))'
                % (str(ROOT / 'apps/recorder'), str(ROOT / 'apps/python')))
        done = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=60)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, '[] False'), done.stderr[-500:])


if __name__ == '__main__':
    unittest.main()
