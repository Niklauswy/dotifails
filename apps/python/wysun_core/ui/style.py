"""Theme access for painted widgets: metrics, the type scale, Material symbols and the kit QSS."""
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPainterPath

from ..qt_theme import color, extend_style, tokens
from .fonts import SYMBOL_FAMILY, display_family, ligature_available, load_fonts


def metric(name, scale=1.0):
    return round(tokens()[name] * scale)


@lru_cache(maxsize=64)
def _text_font(family, points, weight):
    result = QFont(family)
    result.setPointSizeF(max(6.0, points))
    result.setWeight(QFont.Weight(weight))
    return result


def text_font(role='body.medium', weight=None, scale=1.0):
    """The theme's family (mono for ``mono.*``) at a role of the shell's type scale (``'label.small'``…``'headline.large'``),
    in points × scale; ``weight`` overrides the role's."""
    values = tokens()
    weight = values[f'font.{role}.weight'] if weight is None else weight
    family = values['font.family.mono'] if role.startswith('mono.') else display_family()
    return QFont(_text_font(family, round(values[f'font.{role}.size'] * scale, 2), int(weight)))


@lru_cache(maxsize=64)
def _symbol_font(pixels):
    result = QFont(SYMBOL_FAMILY)
    result.setPixelSize(pixels)
    return result


@lru_cache(maxsize=256)
def _symbol_path(name, pixels, filled):
    """Glyph outline at the origin's centre. ``filled`` keeps only outer contours
    and fills them: the FILL axis is not reachable from PySide6's QFont.Tag."""
    font = _symbol_font(pixels)
    path = QPainterPath()
    path.addText(0, 0, font, name)
    if filled:
        polygons = path.toSubpathPolygons()
        bounds = [polygon.boundingRect() for polygon in polygons]
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        for index, polygon in enumerate(polygons):
            inner = any(j != index and other != bounds[index] and other.contains(bounds[index])
                        for j, other in enumerate(bounds))
            if not inner:
                path.addPolygon(polygon)
                path.closeSubpath()
        path = path.simplified()
    metrics = QFontMetricsF(font)
    # Same placement as drawText(AlignCenter): centred advance, centred line box.
    return path.translated(-metrics.horizontalAdvance(name) / 2, (metrics.ascent() - metrics.descent()) / 2)


_fallback = [None]


def set_symbol_fallback(painter_function):
    """Register ``painter_function(painter, rect, name, ink, size)`` for glyphs the font lacks; returns the previous one.

    Wysun's apps register their Lucide icons (icons.py); without one, a missing glyph draws nothing.
    """
    previous, _fallback[0] = _fallback[0], painter_function
    return previous


def paint_symbol(painter, rect, name, tint, size=None, filled=False):
    """Draw a Material symbol centred in ``rect``; ``tint`` is a token name or QColor.

    A missing glyph is drawn by the registered fallback; returns False when nothing was drawn.
    """
    load_fonts()
    size = round(size or tokens()['icon.size'] * 1.2)
    ink = color(tint) if isinstance(tint, str) else tint
    rect = QRectF(rect)
    if not ligature_available(name):
        if _fallback[0] is None:
            return False
        _fallback[0](painter, rect, name, ink, size)
        return True
    painter.save()
    if filled:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(rect.center())
        painter.fillPath(_symbol_path(name, size, True), ink)
    else:
        painter.setFont(_symbol_font(size))
        painter.setPen(ink)
        painter.drawText(rect, Qt.AlignCenter, name)
    painter.restore()
    return True


def clock(seconds):
    """m:ss, or h:mm:ss from one hour."""
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    return f'{hours}:{rest // 60:02}:{rest % 60:02}' if hours else f'{rest // 60}:{rest % 60:02}'


KIT_STYLE = '''
QWidget {color:@text;}
QScrollArea, QListView, QAbstractScrollArea {background:transparent;border:0;outline:0;}
QScrollArea > QWidget > QWidget {background:transparent;}
QScrollBar:vertical {background:transparent;width:8px;margin:2px;}
QScrollBar::handle:vertical {background:@scrollbar;border-radius:3px;min-height:32px;}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {background:transparent;}
QScrollBar:horizontal {height:0;}
QLineEdit {background:@well;border:@border.width solid @line;border-radius:@rounding.medium;padding:@spacing.small @spacing.medium;
           selection-background-color:@text_selection;}
QLineEdit:focus {border:@border.focus solid @focus_input;}
QLineEdit#kitSearch {border-radius:18px;padding:0 @spacing.medium 0 34px;min-height:36px;background:@well;}
QPushButton {padding:@spacing.small @spacing.large;border-radius:@rounding.medium;background:@fill;border:0;color:@control_text;}
QPushButton:hover {background:@hover;}
QPushButton:pressed {background:@pressed;}
QPushButton:focus {border:@border.focus solid @focus;}
QPushButton:disabled {background:@disabled_surface;color:@disabled;}
QPushButton#primary {background:@accent;color:@on_accent;font-weight:600;}
QPushButton#primary:hover {background:@accent_hover;}
QPushButton#primary:pressed {background:@accent_pressed;}
QMenu {background:@menu;color:@text;border:@border.width solid @line_strong;border-radius:@rounding.medium;padding:@spacing.extraSmall;}
QMenu::item {padding:@spacing.small @spacing.extraLarge @spacing.small @spacing.medium;border-radius:@rounding.small;}
QMenu::item:selected {background:@menu_selected;}
QMenu::item:disabled {color:@disabled;}
QMenu::separator {height:1px;background:@divider;margin:@spacing.extraSmall @spacing.small;}
QToolTip {background:@tooltip;color:@on_tooltip;border:@border.width solid @tooltip_line;padding:@spacing.extraSmall @spacing.small;}
QLabel#heading {font-size:@font.title.large.size;font-weight:700;}
QLabel#muted {color:@muted;font-size:@font.body.small.size;}
'''


def apply_kit_style(widget):
    """Themed QSS for colours/shapes plus the theme's body font, inherited by children."""
    load_fonts()
    extend_style(widget, KIT_STYLE)
    widget.setFont(text_font('body.medium'))
