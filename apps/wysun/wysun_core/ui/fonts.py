"""Packaged Material fonts: Rubik text and Material Symbols, loaded from wysun_core/fonts.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source: https://github.com/caelestia-dots/shell
Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a
Font roles follow StyledText.qml / MaterialIcon.qml. Upstream files have no
per-file copyright notices. See THIRD_PARTY.md and LICENSES/GPL-3.0.txt.
"""
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QTextLayout

from ..qt_theme import family as theme_family

FONT_DIR = Path(__file__).resolve().parents[1] / 'fonts'
FONT_FILES = ('Rubik-Variable.ttf', 'MaterialSymbolsRounded.ttf')
TEXT_FAMILY = 'Rubik'
SYMBOL_FAMILY = 'Material Symbols Rounded'
_font_ids = {}
_display_family = []
_known_families = set()


def load_fonts():
    """Register the packaged fonts once; never download or require host fonts."""
    for name in FONT_FILES:
        path = FONT_DIR / name
        if path.is_file() and str(path) not in _font_ids:
            _font_ids[str(path)] = QFontDatabase.addApplicationFont(str(path))
    return tuple(family for value in _font_ids.values() if value >= 0
                 for family in QFontDatabase.applicationFontFamilies(value))


def display_family():
    """Rubik when packaged, otherwise the theme's own fallback list.

    Painters ask for this on every draw call and ``QFontDatabase.families()`` is slow,
    so a found Rubik is remembered (fonts load once; a missing one is retried).
    """
    if _display_family:
        return _display_family[0]
    if TEXT_FAMILY in set(QFontDatabase.families()):
        _display_family.append(TEXT_FAMILY)
        return TEXT_FAMILY
    return theme_family()


@lru_cache(maxsize=128)
def _renders_one_glyph(text, family):
    layout = QTextLayout(text, QFont(family))
    layout.beginLayout()
    line = layout.createLine()
    layout.endLayout()
    if line.isValid() and line.textLength() == len(text):
        return sum(len(run.glyphIndexes()) for run in layout.glyphRuns()) == 1
    return False


def ligature_available(text, family=SYMBOL_FAMILY):
    """A Material ligature is present only when it renders as one glyph (never as literal letters).

    A missing family is not cached, so fonts loaded later are picked up immediately.
    """
    if family not in _known_families and family not in set(QFontDatabase.families()):
        return False
    _known_families.add(family)
    return _renders_one_glyph(text, family)
