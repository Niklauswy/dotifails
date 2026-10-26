"""Colour input parsing shared by the shell and legacy utility."""
import re
from PySide6.QtGui import QColor


def parse_color(text):
    text = text.strip()
    if re.fullmatch(r'[\da-fA-F]{6}', text): text = '#' + text
    if text.lower().startswith(('rgb(', 'hsl(')):  # theme-exception: sintaxis de color escrita por el usuario
        match = re.fullmatch(r'(rgb|hsl)\(\s*([\d.]+)\s*,\s*([\d.]+)(%?)\s*,\s*([\d.]+)(%?)\s*\)', text.lower())
        if not match: return QColor()
        kind, a, b, bp, c, cp = match.groups()
        try: a, b, c = map(float, (a, b, c))
        except ValueError: return QColor()
        if kind == 'rgb':
            if bp or cp or any(v < 0 or v > 255 for v in (a,b,c)): return QColor()
            return QColor(round(a), round(b), round(c))
        if bp != '%' or cp != '%' or not (0 <= a <= 360 and 0 <= b <= 100 and 0 <= c <= 100): return QColor()
        return QColor.fromHslF((a % 360)/360, b/100, c/100)
    color = QColor(text)
    if color.isValid() and color.alpha() != 255: return QColor()
    return color

