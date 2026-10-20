"""Native presentation translated from Caelestia's shell widgets.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source: 507d66285e9d9fde9330adc64159cfdebb28c19a, modules/nexus/NavPane.qml,
modules/dashboard/Media.qml, dashboard/media/Details.qml, components/widgets/
CoverArt.qml and components/{StyledRect,StyledText,StateLayer}.qml.
2026-10-20: QWidget navigation, content hierarchy and static media fallback;
no QML/plugin imports, rotating cover, shader, visualiser or media backend.
Full license and source mapping travel in assets/licenses and UPSTREAM.md.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFontDatabase, QFont, QRawFont, QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel

from .tokens import tokens, color, apply_style, on_theme_changed

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


def metric(key, factor=1):
    return round(tokens()[key] * factor)


def layout_tokens(layout, inset='space_xl', gap='space_m'):
    """Keep layout geometry live, including style changes after construction."""
    def update():
        margin = metric(inset) if inset else 0
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(metric(gap))
    # Keep the closure alive with the layout; theme listeners remain weak.
    layout._wysun_update = update
    import weakref
    reference = weakref.ref(layout)
    def changed():
        current = reference()
        if current is not None:
            try: current._wysun_update()
            except RuntimeError: pass  # Qt has already deleted its owning page.
    on_theme_changed(changed)
    update()


class Navigation(QFrame):
    """NavPane hierarchy with keyboard-native buttons and compact labelled tooltips."""
    def __init__(self, title, entries, active=0):
        super().__init__()
        from .components import SoftButton, label
        self.setObjectName('captureNavigation')
        self.setAccessibleName('Navegación de ' + title)
        apply_style(self, 'QFrame#captureNavigation {background:@well; border-radius:@radius_l;}')
        column = QVBoxLayout(self)
        layout_tokens(column, 'space_m')
        self.heading = label(title, 'section')
        self.heading.setWordWrap(True)
        column.addWidget(self.heading)
        self.buttons = []
        for i, (text, symbol, callback) in enumerate(entries):
            button = SoftButton(text, symbol, quiet=True)
            button.setCheckable(i == active)
            button.setChecked(i == active)
            button.clicked.connect(callback)
            column.addWidget(button)
            self.buttons.append((button, text))
        column.addStretch()
        self.note = label('En este equipo', 'subtitle')
        self.note.setWordWrap(True)
        column.addWidget(self.note)
        on_theme_changed(self.sync)
        self.expanded = True
        self.sync()

    def sync(self):
        self.setFixedWidth(metric('space_xl', 8) if self.expanded else metric('space_xl', 3))
        self.heading.setVisible(self.expanded)
        self.note.setVisible(self.expanded)
        for button, text in self.buttons:
            button.setText(text if self.expanded else '')
            button.setAccessibleName(text)
            button.setToolTip(text)

    def compact(self, compact):
        if self.expanded != (not compact):
            self.expanded = not compact
            self.sync()


class Workspace(QWidget):
    def __init__(self, navigation, content):
        super().__init__()
        self.navigation = navigation
        row = QHBoxLayout(self)
        layout_tokens(row, 'space_m')
        row.addWidget(navigation)
        row.addWidget(content, 1)

    def resizeEvent(self, event):
        self.navigation.compact(self.width() < metric('space_xl', 36))
        if hasattr(self, 'preview'):
            self.preview.setVisible(self.width() >= metric('space_xl',44))
        super().resizeEvent(event)


class MediaPreview(QFrame):
    """CoverArt's image/fallback hierarchy, with a static 16:9 video thumbnail."""
    def __init__(self, kind='grabación'):
        super().__init__()
        self.kind = kind
        from .components import label
        self.setObjectName('capturePreview')
        self.setMinimumWidth(0)
        apply_style(self, 'QFrame#capturePreview {background:@well; border-radius:@radius_l;}')
        column = QVBoxLayout(self)
        layout_tokens(column, 'space_l')
        self.art = _Artwork()
        column.addWidget(self.art, 1)
        self.title = label('Tu próxima ' + kind, 'section')
        self.title.setWordWrap(True)
        column.addWidget(self.title)
        self.details = label('Selecciona un elemento para ver sus detalles.', 'subtitle')
        self.details.setWordWrap(True)
        column.addWidget(self.details)

    def select(self, item, *_):
        self.art.image = item.icon().pixmap(640, 360) if item else QPixmap()
        lines = item.text().split('\n') if item else []
        self.title.setText(lines[0] if lines else 'Tu próxima ' + self.kind)
        self.details.setText('\n'.join(lines[1:]) if len(lines) > 1 else 'Selecciona un elemento para ver sus detalles.')
        self.art.update()


class _Artwork(QWidget):
    def __init__(self):
        super().__init__()
        self.image = QPixmap()
        self.setMinimumHeight(metric('space_xl', 6))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = metric('radius_l')
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)
        painter.fillRect(rect, color('surface_raised'))
        if not self.image.isNull():
            scaled = self.image.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap((self.width()-scaled.width())//2, (self.height()-scaled.height())//2, scaled)
        else:
            from .icons import icon
            size = metric('space_xl', 3)
            pix = icon('library', 'accent', size).pixmap(size, size)
            painter.drawPixmap((self.width()-size)//2, (self.height()-size)//2, pix)
        painter.end()
