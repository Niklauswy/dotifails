"""Material presentation translated to Qt Widgets for Files and utilities.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source: 507d66285e9d9fde9330adc64159cfdebb28c19a,
``modules/nexus/NavPane.qml`` (navigation rail and grouped destinations),
``components/StyledRect.qml`` (surface hierarchy and radii),
``components/StyledText.qml`` (type roles) and
``components/StateLayer.qml`` (hover/press state layer). Upstream files carry
no additional per-file copyright notices. See THIRD_PARTY.md and
LICENSES/GPL-3.0.txt.

The QML is not embedded in widgets: this module translates its presentation to
native Qt controls. Colour, radius, spacing, typography and motion always come
from Wysun's agreed ``theme_tokens`` adapter; the only fixed values are the
declared Material Symbols codepoints and the bundled OFL/Apache-2.0 resources
listed below. Native models, filesystem access, history and portal calls stay in
their original modules.
"""
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPixmap, QRawFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from desktop_common import Surface, button as native_button, text_label
from theme_tokens import color, extend_style, tokens, watch_theme

ASSETS = Path(__file__).resolve().parent / 'assets/utils-material'
SHELL_FONTS = Path(__file__).resolve().parents[1] / 'shell/assets/fonts'

# Bundled resource families. The shell subset remains authoritative when the
# integrator extends it; the complete local fallback below guarantees that the
# Wysun utilities keep their complete glyph set offline in this branch.
FONT_FILES = ('Rubik-Variable.ttf', 'MaterialSymbolsRounded.ttf')
_fonts = {}
_coverage = None


def _font_roots():
    """Offline candidates: this adapter's packaged resources, then the shell."""
    return (ASSETS, SHELL_FONTS)


def _add_font(path):
    identifier = QFontDatabase.addApplicationFont(str(path))
    families = QFontDatabase.applicationFontFamilies(identifier)
    return families[0] if families else ''


def _missing_symbols(family):
    """Names whose Material Symbols codepoint is absent from ``family``."""
    probe = QFont(family)
    probe.setPixelSize(24)
    raw = QRawFont.fromFont(probe)
    if not raw.isValid():
        return tuple(SYMBOLS)
    return tuple(name for name, codepoint in SYMBOLS.items()
                 if not raw.glyphIndexesForString(chr(codepoint))[0])


def _covers_symbols(family):
    """A font is usable when every mapped Material Symbols codepoint exists."""
    return not _missing_symbols(family)


def load_fonts():
    """Load the packaged Rubik family and a complete Material Symbols face.

    No network, host-font requirement or generated source is involved. When the
    shared shell subset has been extended with Wysun's glyph list it wins;
    otherwise the complete OFL/Apache resource shipped next to this adapter is
    used. ``glyph_coverage()`` exposes the result for tests and diagnostics.
    """
    global _coverage
    if _fonts:
        return _fonts
    for root in _font_roots():
        body = root / FONT_FILES[0]
        if body.is_file():
            family = _add_font(body)
            if family:
                _fonts['body'] = family
                break
    if 'body' not in _fonts:
        raise RuntimeError('No se pudo cargar el recurso de fuente Rubik')

    for root in _font_roots():
        path = root / FONT_FILES[1]
        if not path.is_file():
            continue
        family = _add_font(path)
        if family:
            _fonts['symbols'] = family
            _coverage = (path, family, _missing_symbols(family))
            return _fonts
    raise RuntimeError('No se pudo cargar el recurso Material Symbols Rounded')


def glyph_coverage():
    """(font path, family, missing names) for the selected symbol face."""
    load_fonts()
    return _coverage


# Material Symbols Rounded codepoints, not textual ligatures. Keeping the list
# explicit makes offline coverage verifiable and gives the integrator the exact
# glyph set for the shared subset (see apps/shell/tools/subset_material_symbols.py).
SYMBOLS = {
    'dashboard': 0xe871, 'close': 0xe5cd, 'wifi': 0xe63e,
    'notes': 0xe06f, 'palette': 0xe40a, 'processes': 0xe1b1,
    'files': 0xe2c7, 'folder': 0xe2c7, 'tools': 0xe869, 'power': 0xe8ac,
    'back': 0xe5c4, 'forward': 0xe5c8, 'up': 0xe5d8,
    'sidebar': 0xe9b4, 'grid': 0xe9b0, 'list': 0xe8ef,
    'info': 0xe88e, 'search': 0xe8b6, 'more': 0xe5d3,
    'new-folder': 0xe2cc, 'plus': 0xe145, 'chevron': 0xe5cc,
    'home': 0xe88a, 'download': 0xf090, 'documents': 0xe873,
    'desktop': 0xe30c, 'images': 0xe3f4, 'video': 0xe04b,
    'music': 0xe405, 'drive': 0xe1db, 'terminal': 0xeb8e,
    'pin': 0xf10d, 'down': 0xe5c5, 'bluetooth': 0xe1a7,
    'vpn': 0xe9e0, 'ssh': 0xe0da, 'saved': 0xe161,
    'x': 0xe5cd, 'copy': 0xe14d, 'pencil': 0xe3c9, 'eye': 0xe8f4,
    'ellipsis': 0xe5d3, 'folder-open': 0xe2c8, 'refresh-cw': 0xe5d5,
    'settings': 0xe8b8, 'circle-pause': 0xe034, 'shield-check': 0xe9e0,
    'lock': 0xe897, 'suspend': 0xe51c, 'logout': 0xe9ba,
    'reboot': 0xf053, 'shutdown': 0xe8ac, 'trash': 0xe872,
}


def metrics():
    values = dict(tokens())
    values.update(gap=values['space_m'], rail_width=values['space_xl'] * 7,
                  control_height=values['space_xl'] + values['space_l'],
                  header_height=values['space_xl'] * 3)
    return values


def _fallback_icon(name, size, tone):
    """Lucide outline fallback for a name outside the declared glyph set."""
    from icons import glyph, remember
    return remember(QIcon(glyph(name, size, tone)), _fallback_icon, (name, size, tone))


def material_icon(name, size=None, tone='glyph'):
    """Tinted Material Symbols icon, with a verifiable outline fallback.

    The fallback is used only for a name that is not part of ``SYMBOLS``; every
    declared glyph is checked against the selected font by ``glyph_coverage``.
    """
    families = load_fonts()
    size = size or tokens()['icon_size']
    if name not in SYMBOLS or name in (_coverage[2] if _coverage else ()):
        return _fallback_icon(name, size, tone)
    from icons import remember
    image = QPixmap(size * 2, size * 2)
    image.fill(Qt.transparent)
    image.setDevicePixelRatio(2)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    font = QFont(families['symbols'])
    font.setPixelSize(size)
    painter.setFont(font)
    painter.setPen(color(tone))
    painter.drawText(image.rect().adjusted(0, 0, -size, -size), Qt.AlignCenter,
                     chr(SYMBOLS[name]))
    painter.end()
    return remember(QIcon(image), material_icon, (name, size, tone))


def material_pixmap(name, size=None, tone='glyph'):
    size = size or tokens()['icon_size']
    return material_icon(name, size, tone).pixmap(QSize(size, size))


MATERIAL_STYLE = '''
QWidget {font-family:"Rubik", @font_family; font-size:@font_body; color:@text;}
QLabel {background:transparent;}
QLabel#title, QLabel#folderTitle, QLabel#appTitle, QLabel#previewTitle {font-size:@font_title; font-weight:600;}
QLabel#subtitle, QLabel#utilitySubtitle {color:@muted; font-size:@font_small;}
QLabel#sectionLabel {color:@muted; font-size:@font_caption; font-weight:600; letter-spacing:1px;}
QLabel#sidebarNote {color:@muted; font-size:@font_caption;}
QLabel#inspectorHeading {font-size:@font_heading; font-weight:600;}
QLabel#inspectorName {font-size:@font_heading; font-weight:600;}
QLabel#noteTitle {font-size:@font_heading; font-weight:600;}
QWidget[utilitySurface="content"] {background:@surface; border-radius:@radius_l;}
QWidget[utilitySurface="navigation"] {background:@inset; border-radius:@radius_l;}
QWidget[utilitySurface="raised"] {background:@surface_raised; border-radius:@radius_l;}
QFrame#contentSurface {background:@surface; border:0; border-radius:@radius_l;}
QFrame#batteryCard {background:@card; border:@border solid @card_line; border-radius:@radius_l;}
QPushButton {background:transparent; border:@border solid transparent; border-radius:@radius_control; padding:@space_s @space_m; min-height:@space_xl; color:@text;}
QPushButton:hover {background:@hover;}
QPushButton:pressed {background:@pressed;}
QPushButton:checked {background:@selection; color:@selection_text; border-color:@selection_line;}
QPushButton:focus {border:@focus_width solid @focus;}
QPushButton:disabled {color:@disabled; background:@disabled_surface;}
QPushButton#primary {background:@accent; color:@on_accent; font-weight:600;}
QPushButton#primary:hover {background:@accent_hover;}
QPushButton#primary:pressed {background:@accent_pressed;}
QPushButton#primary:disabled {background:@disabled_surface; color:@disabled;}
QPushButton#danger {color:@danger; background:@danger_soft;}
QPushButton#danger:hover {background:@danger_hover;}
QPushButton[utilityNav="true"] {text-align:left; padding-left:@space_l; padding-right:@space_m; min-height:@control_height;}
QPushButton[utilityNav="true"]:checked {background:@nav_selected; color:@text_strong;}
QLineEdit, QComboBox, QSpinBox {background:@well; color:@text; border:@border solid @line; border-radius:@radius_control; padding:@space_s @space_m; min-height:@space_xl;}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {border-color:@focus_input;}
QListWidget, QTreeWidget, QTableWidget {background:transparent; border:0; outline:0;}
QListWidget::item {border-radius:@radius_control; padding:@space_s;}
QListWidget::item:hover {background:@hover;}
QListWidget::item:selected {background:@selection; color:@selection_text;}
QListWidget::item:focus {border:@focus_width solid @focus;}
QListWidget#places::item {height:@control_height; border:0; border-radius:@radius_control; margin:1px 0;}
QListWidget#places::item:selected {background:@selection; color:@selection_text;}
QListWidget#places::item:hover:!selected {background:@hover;}
QWidget#toolbar {background:@surface; border:0; border-bottom:@border solid @divider;}
QWidget#fileCommands, QWidget#pathbar {background:transparent; border:0;}
QWidget#pathbar {border-top:0; border-bottom:@border solid @divider;}
QWidget#viewGroup {background:@well; border:0; border-radius:@radius_control;}
QWidget#glassCanvas {background:@canvas;}
QWidget#sidebar {background:@inset; border:0;}
QLabel#sidebarHeading {color:@muted; font-size:@font_caption; font-weight:600; letter-spacing:1px; padding:@space_s @space_s @space_xs;}
QWidget#inspector {background:@surface; border:0; border-left:@border solid @divider; border-radius:@radius_l;}
QTabWidget::pane {border:0; background:transparent;}
QTabBar {background:transparent;}
QTabBar::tab {background:transparent; color:@muted; min-width:100px; padding:@space_s @space_l; margin:@space_xs @space_xs 0; border:@border solid transparent; border-top-left-radius:@radius_control; border-top-right-radius:@radius_control;}
QTabBar::tab:selected {background:@surface; color:@text; border-color:@line;}
QTabBar::tab:hover:!selected {background:@hover;}
QSplitter::handle {background:@divider; width:@border; height:@border;}
QStatusBar {background:transparent; color:@muted; border:0;}
QStatusBar::item {border:0;}
QToolTip {background:@tooltip; color:@on_tooltip; border:@border solid @tooltip_line; border-radius:@radius_s; padding:@space_s;}
QProgressBar {border:0; border-radius:@radius_s; background:@track; color:@text; text-align:center;}
QProgressBar::chunk {background:@accent; border-radius:@radius_s;}
'''


def materialize(window):
    """Append the translated Material rules to the window's themed template.

    ``theme_tokens.refresh_widgets`` re-renders the stored template on a live
    scheme change, so no second theme authority or listener is introduced.
    """
    load_fonts()
    if getattr(window, '_utility_material', False):
        return
    window._utility_material = True
    extend_style(window, MATERIAL_STYLE)
    watch_theme()


def surface(widget, kind='content'):
    widget.setProperty('utilitySurface', kind)
    widget.setAttribute(Qt.WA_StyledBackground)
    return widget


def card_layout(kind='content'):
    widget = surface(QWidget(), kind)
    layout = QVBoxLayout(widget)
    gap = metrics()['gap']
    layout.setContentsMargins(gap, gap, gap, gap)
    layout.setSpacing(gap)
    return widget, layout


def button(text, fn, name='', symbol=None, nav=False):
    control = native_button(text, fn, name)
    if symbol:
        control.setIcon(material_icon(symbol, tone='on_accent' if name == 'primary' else 'glyph'))
    control.setMinimumHeight(metrics()['control_height'])
    if nav:
        control.setProperty('utilityNav', True)
        control.setAccessibleName(text or symbol or 'Sección')
    else:
        control.setAccessibleName(text or {'x': 'Cerrar', 'pin': 'Fijar', 'ellipsis': 'Más acciones'}.get(symbol, symbol or 'Acción'))
    return control


def section_label(text):
    return text_label(text, 'sectionLabel')


class MaterialSurface(Surface):
    """Compact app bar plus a domain workspace, keeping the native lifecycle."""

    ICONS = {'Wysun Colors': 'palette', 'Wysun Processes': 'processes', 'Wysun Power': 'power'}
    TITLES = {'Wysun Colors': 'Wysun Colores', 'Wysun Processes': 'Wysun Procesos', 'Wysun Power': 'Wysun Energía'}

    def __init__(self, title, subtitle='', width=760, height=530, parent=None):
        title = self.TITLES.get(title, title)
        super().__init__(title, subtitle, width, height, parent)
        old = self.outer.takeAt(0)
        self._clear(old.layout())
        header = QHBoxLayout()
        header.setSpacing(metrics()['gap'])
        brand = QLabel()
        brand.setPixmap(material_pixmap(self.ICONS.get(title, 'dashboard'), metrics()['control_height'], 'accent'))
        brand.setFixedSize(metrics()['control_height'], metrics()['control_height'])
        header.addWidget(brand)
        stack = QVBoxLayout()
        stack.setSpacing(metrics()['space_xs'])
        stack.addWidget(text_label('W Y S U N', 'eyebrow'))
        stack.addWidget(text_label(title, 'title'))
        if subtitle:
            stack.addWidget(text_label(subtitle, 'utilitySubtitle'))
        header.addLayout(stack, 1)
        close = button('', self.close, symbol='close')
        close.setToolTip('Cerrar · Esc')
        close.setAccessibleName('Cerrar panel')
        header.addWidget(close, 0, Qt.AlignTop)
        self.outer.insertLayout(0, header)
        gap = metrics()['space_l']
        self.outer.setContentsMargins(gap, gap, gap, gap)
        self.outer.setSpacing(gap)
        materialize(self)

    @staticmethod
    def _clear(layout):
        while layout and layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                MaterialSurface._clear(item.layout())

    def showEvent(self, event):
        load_fonts()
        super().showEvent(event)
