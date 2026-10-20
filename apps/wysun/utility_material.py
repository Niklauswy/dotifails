"""Material presentation translated to Qt Widgets for Files and utilities.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source: 507d66285e9d9fde9330adc64159cfdebb28c19a,
modules/nexus/NavPane.qml, components/{StyledRect,StyledText,StateLayer}.qml.
Upstream files contain no additional per-file copyright notices.
See THIRD_PARTY.md and LICENSES/GPL-3.0.txt. Native models/actions stay in Wysun.
"""
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QAbstractButton
from desktop_common import Surface, button as native_button, text_label
from theme_tokens import tokens, qss, apply_style, extend_style, color, on_theme_changed, watch_theme
from ui_motion import MotionButton

ASSETS = Path(__file__).parent / 'assets/utils-material'
_fonts = {}
# This adapter's typography role is Rubik, with the shared theme's fallbacks.
# All sizing, colour and motion roles are read from the agreed theme adapter.
SYMBOLS = {
    'dashboard': 0xe871, 'close': 0xe5cd, 'wifi': 0xe63e,
    'notes': 0xe06f, 'palette': 0xe40a, 'processes': 0xe1b1,
    'files': 0xe2c7, 'tools': 0xe869, 'power': 0xe8ac,
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
    'reboot': 0xf053, 'shutdown': 0xe8ac,
}


def load_fonts():
    if not _fonts:
        for key, name in [('body', 'Rubik-Variable.ttf'), ('symbols', 'MaterialSymbolsRounded.ttf')]:
            identifier = QFontDatabase.addApplicationFont(str(ASSETS / name))
            families = QFontDatabase.applicationFontFamilies(identifier)
            if not families:
                raise RuntimeError('No se pudo cargar el recurso de fuente: ' + name)
            _fonts[key] = families[0]
    return _fonts


def metrics():
    values = dict(tokens())
    values.update(gap=values['space_m'], rail_width=values['space_xl'] * 7,
                  control_height=values['space_xl'] + values['space_l'],
                  header_height=values['space_xl'] * 3)
    return values


def material_icon(name, size=None, tone='glyph'):
    from icons import remember
    families = load_fonts()
    size = size or tokens()['icon_size']
    image = QPixmap(size * 2, size * 2); image.fill(Qt.transparent)
    image.setDevicePixelRatio(2)
    painter = QPainter(image); painter.setRenderHint(QPainter.Antialiasing)
    font = QFont(families['symbols']); font.setPixelSize(size)
    painter.setFont(font); painter.setPen(color(tone))
    painter.drawText(image.rect().adjusted(0, 0, -size, -size), Qt.AlignCenter,
                     chr(SYMBOLS.get(name, SYMBOLS['dashboard'])))
    painter.end()
    return remember(QIcon(image), material_icon, (name, size, tone))


MATERIAL_STYLE = '''
QWidget {font-family: @font_family; font-size: @font_body; color: @text;}
QLabel {background: transparent;}
QLabel#title, QLabel#folderTitle {font-size: @font_title; font-weight: 600;}
QLabel#subtitle, QLabel#utilitySubtitle {color: @muted; font-size: @font_small;}
QWidget[utilitySurface="content"] {background: @surface; border-radius: @radius_l;}
QWidget[utilitySurface="navigation"] {background: @inset; border-radius: @radius_l;}
QPushButton {background: transparent; border: @border solid transparent; border-radius: @radius_control; padding: @space_s @space_m; min-height: @space_xl;}
QPushButton:hover {background: @hover;}
QPushButton:pressed {background: @pressed;}
QPushButton:checked {background: @selection; color: @selection_text;}
QPushButton:focus {border: @focus_width solid @focus;}
QPushButton:disabled {color: @disabled; background: @disabled_surface;}
QPushButton#primary {background: @accent; color: @on_accent;}
QPushButton#primary:hover {background: @accent_hover;}
QPushButton#primary:pressed {background: @accent_pressed;}
QPushButton#primary:disabled {background: @disabled_surface; color: @disabled;}
QLineEdit, QComboBox, QSpinBox {background: @well; color: @text; border: @border solid @line; border-radius: @radius_control; padding: @space_s; min-height: @space_xl;}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {border-color: @focus;}
QListWidget {background: transparent; border: none; outline: none;}
QListWidget::item {border-radius: @radius_control; padding: @space_s;}
QListWidget::item:hover {background: @hover;}
QListWidget::item:selected {background: @selection; color: @selection_text;}
QListWidget::item:focus {border: @focus_width solid @focus;}
QWidget#toolbar, QWidget#fileCommands, QWidget#pathbar {background: transparent; border: none;}
QWidget#glassCanvas {background: @canvas;}
QFrame#contentSurface {background: @surface; border: none; border-radius: @radius_l;}
QListWidget#places::item {height: @space_xl; border: none; border-radius: @radius_control;}
QListWidget#places::item:selected {background: @selection; color: @selection_text;}
QWidget#inspector {background: @surface; border: none; border-radius: @radius_l;}
QWidget#viewGroup {background: @well; border: none; border-radius: @radius_control;}
'''


def materialize(window):
    """Use the existing watcher; never create another scheme authority."""
    load_fonts()
    if getattr(window, '_utility_material', False):
        return
    window._utility_material = True
    extend_style(window, MATERIAL_STYLE)
    # qss knows font_family as a font-list token. Keep the override local to these
    # widgets; do not change the shared producer or capture's adapter.
    def update_style():
        values = dict(tokens()); values['font_family'] = [load_fonts()['body'], *values['font_family']]
        window.setStyleSheet(qss(window.property('orbitOriginalStyle'), values))
    # Bind weakly through the window so closing it releases the listener.
    window.refresh_material_style = update_style
    class Refresh:
        def apply(self):
            update_style()
    window._material_refresh = Refresh()
    on_theme_changed(window._material_refresh.apply)
    update_style()
    watch_theme()


def surface(widget, kind='content'):
    widget.setProperty('utilitySurface', kind)
    widget.setAttribute(Qt.WA_StyledBackground)
    return widget


def card_layout(kind='content'):
    widget = surface(QWidget(), kind)
    layout = QVBoxLayout(widget)
    gap = metrics()['gap']; layout.setContentsMargins(gap, gap, gap, gap)
    layout.setSpacing(gap)
    return widget, layout


def button(text, fn, name='', symbol=None):
    control = native_button(text, fn, name)
    if symbol:
        control.setIcon(material_icon(symbol, tone='on_accent' if name == 'primary' else 'glyph'))
    control.setMinimumHeight(metrics()['control_height'])
    control.setAccessibleName(text or {'x':'Cerrar', 'pin':'Fijar', 'ellipsis':'Más acciones'}.get(symbol, symbol or 'Acción'))
    return control


class MaterialSurface(Surface):
    """Compact title followed by a domain-specific workspace; same lifecycle."""
    def __init__(self, title, subtitle='', width=760, height=530, parent=None):
        titles = {'Wysun Notes':'Wysun Notas', 'Wysun Colors':'Wysun Colores',
                  'Wysun Processes':'Wysun Procesos', 'Wysun Power':'Wysun Energía',
                  'Wysun Tools':'Wysun Herramientas'}
        title = titles.get(title, title)
        super().__init__(title, subtitle, width, height, parent)
        old = self.outer.takeAt(0)
        def remove(layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
                elif item.layout(): remove(item.layout())
        remove(old.layout())
        header = QHBoxLayout(); brand = QLabel()
        brand.setPixmap(material_icon('dashboard').pixmap(metrics()['control_height'], metrics()['control_height']))
        header.addWidget(brand)
        stack = QVBoxLayout(); stack.addWidget(text_label(title, 'title'))
        if subtitle: stack.addWidget(text_label(subtitle, 'utilitySubtitle'))
        header.addLayout(stack, 1)
        close = button('', self.close); close.setIcon(material_icon('close'))
        close.setAccessibleName('Cerrar panel'); close.setToolTip('Cerrar · Esc')
        header.addWidget(close); self.outer.insertLayout(0, header)
        gap = metrics()['space_l']; self.outer.setContentsMargins(gap, gap, gap, gap)
        self.outer.setSpacing(gap)
        materialize(self)

    def showEvent(self, event):
        self.refresh_material_style()
        super().showEvent(event)

    def paintEvent(self, event):
        # This opaque Material surface avoids inherited glass/blur assumptions.
        from PySide6.QtCore import QRectF
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen); p.setBrush(color('canvas'))
        r = tokens()['radius_l']; p.drawRoundedRect(QRectF(self.rect()), r, r)
