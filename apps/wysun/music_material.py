"""Packaged Material fonts for Wysun Music: Rubik text and Material Symbols.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source: https://github.com/caelestia-dots/shell
Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a
Font roles follow StyledText.qml / MaterialIcon.qml. Upstream files have no
per-file copyright notices. See THIRD_PARTY.md and LICENSES/GPL-3.0.txt.
"""
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QTextLayout

from theme_tokens import family as theme_family


# Asset families are resource identifiers, not independent theme typography.
# F8 can bundle these same offline resources alongside the native application.
FONT_FILES = ('Rubik-Variable.ttf', 'MaterialSymbolsRounded.ttf')
TEXT_FAMILY = 'Rubik'
SYMBOL_FAMILY = 'Material Symbols Rounded'
_font_ids = {}


def load_fonts():
    """Load packaged resources only; never download or require host fonts."""
    source = Path(__file__).resolve().parent
    roots = (source / 'assets/fonts', source.parent / 'shell/assets/fonts',
             Path.home() / '.local/share/wysun/quickshell/assets/fonts')
    for name in FONT_FILES:
        for root in roots:
            path = root / name
            if path.is_file():
                key = str(path)
                if key not in _font_ids:
                    _font_ids[key] = QFontDatabase.addApplicationFont(key)
                break
    return tuple(family for value in _font_ids.values() if value >= 0
                 for family in QFontDatabase.applicationFontFamilies(value))


_display_family = []
_known_families = set()


def display_family():
    """Rubik when packaged, otherwise the active theme's own fallback list.

    Painters ask for this on every draw call and ``QFontDatabase.families()`` is slow,
    so a found Rubik is remembered (fonts load once; a missing one is retried).
    """
    if _display_family:
        return _display_family[0]
    if TEXT_FAMILY in set(QFontDatabase.families()):
        _display_family.append(TEXT_FAMILY)
        return TEXT_FAMILY
    return theme_family()


def symbol_family():
    return SYMBOL_FAMILY if SYMBOL_FAMILY in set(QFontDatabase.families()) else None


@lru_cache(maxsize=128)
def _renders_one_glyph(text, family):
    font = QFont(family)
    layout = QTextLayout(text, font)
    layout.beginLayout()
    line = layout.createLine()
    layout.endLayout()
    if line.isValid() and line.textLength() == len(text):
        return sum(len(run.glyphIndexes()) for run in layout.glyphRuns()) == 1
    return False


def ligature_available(text, family=SYMBOL_FAMILY):
    """A Material ligature is present only when it renders as one glyph.

    The packaged font may be a subset (or temporarily absent while the
    integrator assembles the final set), so callers must fall back to the
    bundled Lucide SVG rather than draw literal letters. A missing family is
    not cached, so fonts loaded later are picked up immediately.
    """
    if family not in _known_families and family not in set(QFontDatabase.families()):
        return False
    _known_families.add(family)           # a loaded family stays loaded; avoids a slow lookup per glyph
    return _renders_one_glyph(text, family)
