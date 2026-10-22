"""Theme access for Music widgets: metrics, type scale, Material symbols, QSS."""
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPainterPath

from icons import glyph
from music_material import SYMBOL_FAMILY, display_family, ligature_available, load_fonts
from theme_tokens import color, extend_style, tokens

# Material Symbols ligature -> bundled Lucide asset when the font is missing.
FALLBACK = {
    'home': 'layout-grid', 'search': 'search', 'library_music': 'music', 'add': 'plus',
    'favorite': 'heart', 'play_arrow': 'play', 'pause': 'pause', 'skip_previous': 'skip-back',
    'skip_next': 'skip-forward', 'shuffle': 'shuffle', 'repeat': 'repeat', 'repeat_one': 'repeat',
    'lyrics': 'file-text', 'queue_music': 'rows-3', 'volume_up': 'volume-2', 'volume_down': 'volume-2',
    'volume_off': 'volume-x', 'more_horiz': 'ellipsis', 'arrow_back': 'arrow-left',
    'arrow_forward': 'arrow-right', 'chevron_left': 'arrow-left', 'chevron_right': 'arrow-right',
    'close': 'x', 'download': 'download', 'folder_open': 'folder-open', 'person': 'users',
    'album': 'music', 'schedule': 'calendar', 'delete': 'trash-2', 'edit': 'pencil',
    'music_note': 'music', 'graphic_eq': 'music', 'check': 'check', 'open_in_new': 'external-link',
    'picture_in_picture_alt': 'arrow-up-right', 'queue_play_next': 'rows-3', 'playlist_add': 'plus',
    'refresh': 'refresh-cw', 'sort': 'rows-3', 'grid_view': 'layout-grid', 'speaker': 'volume-2', 'keyboard': 'keyboard',
    'explore': 'search', 'artist': 'users', 'history': 'calendar', 'expand_more': 'chevron-down', 'remove': 'arrow-left',
}


def metric(name, scale=1.0):
    return round(tokens()[name] * scale)


@lru_cache(maxsize=64)
def _text_font(family, pixels, weight):
    result = QFont(family)
    result.setPixelSize(max(8, pixels))
    result.setWeight(QFont.Weight(weight))
    return result


def text_font(role='body', weight=400, scale=1.0):
    """Rubik at a theme size role (caption/small/body/heading/title) × scale."""
    return QFont(_text_font(display_family(), round(tokens()['font_' + role] * scale), weight))


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


def paint_symbol(painter, rect, name, tint, size=None, filled=False):
    """Draw a Material symbol centred in ``rect``; ``tint`` is a token name or QColor."""
    size = round(size or tokens()['icon_size'] * 1.2)
    ink = color(tint) if isinstance(tint, str) else tint
    rect = QRectF(rect)
    if ligature_available(name):
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
        return
    pixmap = glyph(FALLBACK.get(name, 'music'), max(12, round(size * .8)), ink.name())
    side = pixmap.width() / pixmap.devicePixelRatio()
    painter.drawPixmap(QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2, side, side),
                       pixmap, QRectF(pixmap.rect()))


def stamp(seconds):
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    return f'{hours}:{rest // 60:02}:{rest % 60:02}' if hours else f'{rest // 60}:{rest % 60:02}'


def long_duration(seconds):
    minutes = int(seconds or 0) // 60
    hours, minutes = divmod(minutes, 60)
    return f'{hours} h {minutes} min' if hours else f'{minutes} min'


def songs(count):
    return f'{count} canción' if count == 1 else f'{count} canciones'


STYLE = '''
QWidget {color:@text;}
QScrollArea, QListView, QAbstractScrollArea {background:transparent;border:0;outline:0;}
QScrollArea > QWidget > QWidget {background:transparent;}
QScrollBar:vertical {background:transparent;width:8px;margin:2px;}
QScrollBar::handle:vertical {background:@scrollbar;border-radius:3px;min-height:32px;}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {background:transparent;}
QScrollBar:horizontal {height:0;}
QLineEdit {background:@well;border:@border solid @line;border-radius:@radius_control;padding:@space_s @space_m;
           selection-background-color:@text_selection;}
QLineEdit:focus {border:@focus_width solid @focus_input;}
QLineEdit#musicSearch {border-radius:18px;padding:0 @space_m 0 34px;min-height:36px;background:@well;}
QPushButton {padding:@space_s @space_l;border-radius:@radius_control;background:@fill;border:0;color:@control_text;}
QPushButton:hover {background:@hover;}
QPushButton:pressed {background:@pressed;}
QPushButton:focus {border:@focus_width solid @focus;}
QPushButton:disabled {background:@disabled_surface;color:@disabled;}
QPushButton#primary {background:@accent;color:@on_accent;font-weight:600;}
QPushButton#primary:hover {background:@accent_hover;}
QPushButton#primary:pressed {background:@accent_pressed;}
QMenu {background:@menu;color:@text;border:@border solid @line_strong;border-radius:@radius_m;padding:@space_xs;}
QMenu::item {padding:@space_s @space_xl @space_s @space_m;border-radius:@radius_s;}
QMenu::item:selected {background:@menu_selected;}
QMenu::item:disabled {color:@disabled;}
QMenu::separator {height:1px;background:@divider;margin:@space_xs @space_s;}
QToolTip {background:@tooltip;color:@on_tooltip;border:@border solid @tooltip_line;padding:@space_xs @space_s;}
QLabel#heading {font-size:@font_title;font-weight:700;}
QLabel#muted {color:@muted;font-size:@font_small;}
'''


def apply_style(widget):
    """Themed QSS for colours/shapes plus the Rubik body font, inherited by children."""
    load_fonts()
    extend_style(widget, STYLE)
    widget.setFont(text_font('body'))
