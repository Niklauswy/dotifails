"""Bundled Rubik and Material Symbols fonts, and Material Symbols glyph pixmaps."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QFont, QRawFont, QPixmap, QPainter

FONT_ROOT = Path(__file__).with_name('assets') / 'fonts'
_font_ids = None

# Material Symbols Unicode codepoints: never render a ligature word on failure.
SYMBOLS = {
    'screen': 0xe30a, 'window': 0xe051, 'library': 0xe02f, 'region': 0xe3be,
    'mic': 0xe31d, 'sound': 0xe050, 'muted': 0xe04f, 'camera': 0xe04b,
    'record': 0xe061, 'play': 0xe037, 'pause': 0xe034, 'stop': 0xe047,
    'close': 0xe5cd, 'rewind': 0xe059, 'forward': 0xe056, 'copy': 0xe14d,
    'refresh': 0xe5d5, 'eye': 0xe8f4, 'search': 0xe8b6, 'folder': 0xe2c7,
    'settings': 0xe8b8, 'more': 0xe5d3, 'plus': 0xe145, 'back': 0xe5c4,
    'export': 0xe2c6, 'undo': 0xe166, 'redo': 0xe15a, 'trash': 0xe872,
    'chevron': 0xe5cf, 'check': 0xe5ca, 'cut': 0xe14e, 'fullscreen': 0xe5d0,
    'select': 0xe925, 'text': 0xe264, 'arrow': 0xe5c8, 'rectangle': 0xeb36,
    'ellipse': 0xef4a, 'pen': 0xe3c9, 'highlight': 0xe22b, 'number': 0xe400,
    'mask': 0xe897, 'blur': 0xe3a5, 'crop': 0xe3be, 'save': 0xe161,
    'compare': 0xe3b9, 'compose': 0xe9d3,
}


def load_fonts():
    global _font_ids
    if _font_ids is None:
        _font_ids = tuple(QFontDatabase.addApplicationFont(str(FONT_ROOT / name))
                          for name in ('Rubik-Variable.ttf', 'MaterialSymbolsRounded.ttf'))
    return _font_ids


def symbol_pixmap(name, ink, size):
    """Return None for an unavailable glyph, letting the native outline fallback work."""
    load_fonts()
    point = SYMBOLS.get(name)
    if point is None or _font_ids[1] < 0:
        return None
    font = QFont('Material Symbols Rounded')
    font.setPixelSize(size * 2)
    raw = QRawFont.fromFont(font)
    if raw.familyName() != 'Material Symbols Rounded' or not raw.supportsCharacter(point):
        return None
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setPen(ink)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, chr(point))
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return pixmap
