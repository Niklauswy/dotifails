"""Material presentation adapter for Wysun Music's native widgets.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source: https://github.com/caelestia-dots/shell
Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a
Presentation translated from dashboard/Media.qml, dashboard/media/Details.qml,
widgets/CoverArt.qml, nexus/NavPane.qml, StyledRect.qml, StyledText.qml and
StateLayer.qml. Upstream files have no per-file copyright notices. See
THIRD_PARTY.md and LICENSES/GPL-3.0.txt. This is not an upstream music app.

No colour producer or preference storage lives here. Geometry derives from
Wysun's existing semantic tokens; proportions below describe Music's layout.
Buttons keep the shared interruptible MotionButton/reduced-motion behaviour.
"""
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (QFont, QFontDatabase, QIcon, QPainter, QPixmap,
                           QTextLayout)

from theme_tokens import color, extend_style, family as theme_family, tokens


# Asset families are resource identifiers, not independent theme typography.
# F8 can bundle these same offline resources alongside the native application.
FONT_FILES = ('Rubik-Variable.ttf', 'MaterialSymbolsRounded.ttf')
TEXT_FAMILY = 'Rubik'
SYMBOL_FAMILY = 'Material Symbols Rounded'
_font_ids = {}
# Material Symbols names -> (ligature, bundled Lucide fallback). Only symbols
# the integrator packages are requested; everything else stays in Lucide.
SYMBOLS = {
    'music': ('music_note', 'music'),
    'albums': ('library_music', 'music'),
    'heart': ('favorite', 'heart'),
    'favorite': ('favorite', 'heart'),
    'users': ('group', 'users'),
    'download': ('download', 'download'),
    'folder-open': ('folder_open', 'folder-open'),
    'play': ('play_arrow', 'play'),
    'pause': ('pause', 'pause'),
    'skip-back': ('skip_previous', 'skip-back'),
    'skip-forward': ('skip_next', 'skip-forward'),
    'shuffle': ('shuffle', 'shuffle'),
    'repeat': ('repeat', 'repeat'),
    'lyrics': ('lyrics', 'file-text'),
    'volume-2': ('volume_up', 'volume-2'),
    'search': ('search', 'search'),
    'arrow-right': ('arrow_forward', 'arrow-right'),
}


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


def display_family():
    """Rubik when packaged, otherwise the active theme's own fallback list."""
    families = set(QFontDatabase.families())
    return TEXT_FAMILY if TEXT_FAMILY in families else theme_family()


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
    if family not in set(QFontDatabase.families()):
        return False
    return _renders_one_glyph(text, family)


def material_icon(name, size=20, tint='glyph'):
    """Themed QIcon: Material Symbols ligature, else the bundled Lucide asset."""
    size = max(12, int(round(size)))
    entry = SYMBOLS.get(name)
    if entry and ligature_available(entry[0]):
        pixmap = _ligature_pixmap(entry[0], size, tint)
        result = QIcon(pixmap)
    else:
        from icons import icon
        return icon(entry[1] if entry else name, size, tint)
    # Register with the shared icon refresh so a live scheme change re-tints it.
    from icons import remember
    return remember(result, material_icon, (name, size, tint))


def _ligature_pixmap(text, size, tint):
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    pixmap.setDevicePixelRatio(2)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.TextAntialiasing)
    font = QFont(SYMBOL_FAMILY)
    font.setPixelSize(size)
    painter.setFont(font)
    painter.setPen(color(tint))
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, text)
    painter.end()
    return pixmap


def metric(name, scale=1):
    return round(tokens()[name] * scale)


MUSIC_STYLE = '''
QWidget {font-family:"Rubik",@font_family;font-size:@font_body;}
QWidget#musicNavigation {background:@surface;border-radius:@radius_l;}
QWidget#musicArtwork {background:@surface_raised;border-radius:@radius_l;}
QWidget#musicTracks {background:@surface;border-radius:@radius_l;}
QWidget#musicPlayer {background:@surface;border-radius:@radius_l;}
QWidget#musicLyrics {background:@surface;border-radius:@radius_l;}
QListWidget, QTreeWidget, QScrollArea {background:transparent;border:0;}
QListWidget::item {padding:@space_s;border-radius:@radius_control;}
QListWidget::item:hover {background:@hover;}
QListWidget::item:selected {background:@selection;color:@selection_text;}
QListWidget::item:focus {border:@focus_width solid @focus;}
QTreeWidget::item {padding:@space_xs;border:0;border-radius:@radius_s;}
QTreeWidget::item:hover {background:@hover;}
QTreeWidget::item:selected {background:@selection;color:@selection_text;}
QTreeWidget::item:focus {border:@focus_width solid @focus;}
QHeaderView::section {background:transparent;color:@muted;border:0;padding:@space_s;font-size:@font_small;}
QLabel#musicHeading {font-size:@font_title;font-weight:600;}
QLabel#musicCategory {font-size:@font_caption;color:@muted;font-weight:600;}
QLabel#subtitle {font-size:@font_small;color:@muted;}
QLabel#musicDetail {font-size:@font_small;color:@muted;}
QLabel#musicTrackTitle {font-size:@font_body;font-weight:600;}
QLineEdit {background:@well;border:@border solid @line;border-radius:@radius_control;padding:@space_s;font-size:@font_body;}
QLineEdit:focus {border:@focus_width solid @focus_input;}
QPushButton {padding:@space_s;border-radius:@radius_control;}
QPushButton:hover {background:@hover;}
QPushButton:pressed {background:@pressed;}
QPushButton:checked {background:@selection;color:@selection_text;border:@border solid @selection_line;}
QPushButton:focus {border:@focus_width solid @focus;}
QPushButton#primary {background:@accent;color:@on_accent;}
QPushButton#primary:hover {background:@accent_hover;}
QPushButton#primary:pressed {background:@accent_pressed;}
QPushButton:disabled {background:@disabled_surface;color:@disabled;}
'''


def apply_music_style(widget):
    load_fonts()
    extend_style(widget, MUSIC_STYLE)
