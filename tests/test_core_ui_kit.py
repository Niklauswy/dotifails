"""The Material widget kit is defined once, in wysun_core.ui, and nobody borrows it from Music."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ('StateLayer', 'PillButton', 'Chip', 'Slider', 'ElidedLabel', 'Panel', 'NavItem', 'SearchField', 'Toast')
CORE_UI = ROOT / 'apps/wysun/wysun_core/ui'
# Different widgets that only share a name with a kit class (compared when the kit was extracted).
DISTINCT = {
    'apps/capture/loomrec/ui/app_window.py:NavItem': "Recorder's own rail item (65 % like the kit row)",
    'installer/material_widgets.py:Panel': "the installer's hero panel, unrelated to the kit surface",
    'apps/wysun/pdf_material.py:Panel': "the PDF reader's own ReaderTheme-driven panel (to review with the reader)",
    'apps/wysun/wysun_media/controls.py:Toast': 'the player HUD pill, part of the wysun_media Host contract',
}


def sources():
    for base in ('apps', 'installer'):
        for path in (ROOT / base).rglob('*.py'):
            if '/vendor/' not in path.as_posix() and not any(part.is_symlink() for part in path.parents):
                yield path


def definitions(names):
    found = []
    for path in sources():
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names and CORE_UI not in path.parents:
                found.append(f'{path.relative_to(ROOT)}:{node.name}')
    return sorted(found)


class KitTests(unittest.TestCase):
    maxDiff = None

    def test_kit_classes_are_defined_once(self):
        self.assertEqual([d for d in definitions(KIT) if d not in DISTINCT], [])

    def test_nobody_imports_the_kit_from_music(self):
        borrowed = [str(p.relative_to(ROOT)) for p in sources()
                    if ROOT / 'apps/wysun/wysun_music' not in p.parents
                    and re.search(r'wysun_music\.ui\.(shapes|widgets|sidebar)', p.read_text())]
        self.assertEqual(borrowed, [])
        self.assertFalse((ROOT / 'apps/wysun/wysun_files/kit.py').exists())


    def test_no_window_reimplements_frameless_resize(self):
        offenders = [str(p.relative_to(ROOT)) for p in sources() if CORE_UI not in p.parents
                     and re.search(r'^\s*(RESIZE_MARGIN\s*=|def _edges\()', p.read_text(), re.M)]
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
