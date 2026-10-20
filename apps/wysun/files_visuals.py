# Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
# Fuente: 507d66285e9d9fde9330adc64159cfdebb28c19a; véase THIRD_PARTY.md.
# Los QML de origen no incluyen avisos de copyright adicionales por archivo.
"""Restrained desktop file-browser surfaces and original vector iconography."""
from collections.abc import Mapping
from functools import lru_cache
from html import escape
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap

# Files roles map onto Wysun theme tokens (wysun_theme.json); values follow
# the active style and variant. Durations are milliseconds, geometry is px.
ROLES = {
    "window": "canvas", "canvas": "canvas", "mica": "material_mid", "sidebar": "inset", "surface": "surface",
    "toolbar": "material_top", "toolbar_end": "material_bottom",
    "text": "text", "muted": "muted", "subtle": "subtle",
    "border": "line", "divider": "divider", "hover": "hover",
    "pressed": "pressed", "selected": "selection", "selected_text": "selection_text",
    "accent": "accent", "accent_hover": "accent_hover", "focus": "focus",
    "disabled": "disabled", "disabled_surface": "disabled_surface",
    "error": "danger", "scroll": "scrollbar", "scroll_hover": "line_strong",
    "paper": "surface", "preview": "well",
}


class _Colors(Mapping):
    """Live '#rrggbb' view of the Files roles for the active theme."""
    def __getitem__(self, role):
        from theme_tokens import color
        return color(ROLES[role]).name()
    def __iter__(self):
        return iter(ROLES)
    def __len__(self):
        return len(ROLES)


COLORS = _Colors()
TOKENS = {
    "colors": COLORS,
    "radii": {"small": 6, "control": 8, "surface": 10},
    "space": {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24},
    "motion": {"duration": 180, "fast": 150, "slow": 220},
    "shadow": {"color": "shadow", "blur": 18, "offset_y": 3},
}

# Native Qt widgets have no CSS transition support. These motion tokens are also
# used by the window's optional QVariantAnimation feedback, not unsupported QSS.
_STYLE_TEMPLATE = """
QWidget { background: @canvas; color: @text; font-family: @font_family; font-size: @font_body; }
QLabel { background: transparent; }
QWidget#glassCanvas { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 @material_top,stop:0.55 @material_mid,stop:1 @material_bottom); }
QWidget#workspace { background: transparent; }
QWidget#selectionPreview { background: @surface/155; border: 1px solid @material_edge; border-radius: @radius_m; }
QWidget#selectionPreview QLabel { background: transparent; border: none; }

QMainWindow, QDialog, QMessageBox, QInputDialog { background: @canvas; color: @text; }
QWidget#toolbar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 @material_top,stop:1 @material_bottom); border: none; border-bottom: 1px solid @line; }
QWidget#sidebar { background: @inset/160; border: none; }
QWidget#sidebar QLabel { background: transparent; color: @muted; font-size: @font_small; font-weight: 600; }
QFrame#contentSurface { background: @surface; border: 1px solid @line; border-radius: @radius_l; }
QListWidget#places { background: transparent; border: none; outline: none; padding: 0 8px; }
QListWidget#places::item { height: 30px; padding: 0 8px; border: 1px solid transparent; border-left: 3px solid transparent; border-radius: @radius_s; margin: 2px 0; color: @text; }
QListWidget#places::item:selected { background: @selection; color: @selection_text; border-left-color: @accent; }
QListWidget#places::item:hover:!selected { background: @hover; }
QListWidget#places::item:focus { border-color: @focus; }
QLabel#folderTitle { background: transparent; font-size: @font_heading; font-weight: 600; color: @text; }
QWidget#pathbar { background: @surface; border-top: 1px solid @divider; }
QWidget#pathbar QLabel { background: transparent; font-size: @font_small; color: @muted; }
QWidget#inspector { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 @surface/220,stop:1 @inset/205); border-left: 1px solid @divider; }
QWidget#inspector QLabel { background: transparent; }
QLabel#inspectorName { font-size: @font_heading; font-weight: 600; }
QLabel#muted, QLabel#inspectorLocation { color: @muted; font-size: @font_body; }
QWidget#glassCanvas { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 @material_top,stop:0.55 @material_mid,stop:1 @material_bottom); }
QWidget#workspace { background: transparent; }
QWidget#selectionPreview { background: @surface/155; border: 1px solid @material_edge; border-radius: @radius_m; }
QWidget#selectionPreview QLabel { background: transparent; border: none; }

QWidget#viewGroup { background: @disabled_surface; border: 1px solid @line; border-radius: @radius_control; }
QLabel#status, QStatusBar { background: transparent; color: @muted; font-size: @font_small; border: none; }
QStatusBar::item { border: none; }
QLineEdit { border: 1px solid @line; border-bottom: 1px solid @line_strong; border-radius: @radius_control; background: @surface; color: @text; padding: 6px 10px; selection-background-color: @selection; selection-color: @selection_text; }
QLineEdit:hover { border-color: @line_strong; }
QLineEdit:focus { border: 1px solid @focus; border-bottom: 2px solid @focus; padding-bottom: 5px; }
QLineEdit:disabled { color: @disabled; background: @disabled_surface; border-color: @divider; }
QLineEdit#search { min-height: 18px; }
QToolButton, QPushButton { background: transparent; border: 1px solid transparent; border-radius: @radius_control; padding: 5px; color: @text; }
QPushButton { background: @surface; border: 1px solid @line; padding: 6px 12px; }
QToolButton:hover, QPushButton:hover { background: @hover; border-color: @line; }
QToolButton:pressed, QPushButton:pressed { background: @pressed; border-color: @line_strong; }
QToolButton:checked, QPushButton:checked { background: @selection; color: @selection_text; border-color: @selection_line; }
QToolButton:focus, QPushButton:focus { border-color: @focus; }
SoftButton:!checked { background: transparent; }
QPushButton#breadcrumb { background: transparent; border-color: transparent; }
QPushButton#breadcrumb:focus { border-color: @focus; }
QWidget#folderPage, QStackedWidget { background: @surface; }
QToolButton:disabled, QPushButton:disabled { color: @disabled; background: transparent; border-color: transparent; }
QPushButton#actionButton, QPushButton:default { background: @accent; border-color: @accent; color: @on_accent; padding: 6px 14px; }
QPushButton#actionButton:hover, QPushButton:default:hover { background: @accent_hover; border-color: @accent_hover; }
QPushButton#actionButton:pressed, QPushButton:default:pressed { background: @accent_pressed; }
QPushButton#actionButton:disabled, QPushButton:default:disabled { background: @disabled_surface; color: @disabled; border-color: @line; }
QTreeView, QListView { background: @surface; alternate-background-color: @well; color: @text; border: none; outline: none; selection-background-color: @selection; selection-color: @selection_text; }
QTreeView::item { min-height: 29px; border: 1px solid transparent; }
QTreeView::item:selected, QListView::item:selected { background: @selection; color: @selection_text; border: 1px solid @selection_line; }
QTreeView::item:hover:!selected, QListView::item:hover:!selected { background: @hover; }
QTreeView::item:focus, QListView::item:focus { border: 1px solid @focus; }
QListView::item { border: 1px solid transparent; border-radius: @radius_control; padding: 4px; }
QHeaderView { background: @surface; }
QHeaderView::section { background: @surface; color: @muted; border: none; border-bottom: 1px solid @divider; padding: 7px 10px; font-size: @font_small; font-weight: 600; }
QHeaderView::section:hover { background: @hover; }
QTabWidget::pane { border: none; background: @surface; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: @muted; min-width: 100px; padding: 8px 18px; margin: 3px 2px 0; border: 1px solid transparent; border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { background: @surface; color: @text; border-color: @line; border-bottom-color: @surface; }
QTabBar::tab:hover:!selected { background: @hover; }
QTabBar::tab:disabled { color: @disabled; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 3px 2px; }
QScrollBar::handle:vertical { background: @scrollbar; min-height: 32px; border-radius: 3px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 3px; }
QScrollBar::handle:horizontal { background: @scrollbar; min-width: 32px; border-radius: 3px; }
QScrollBar::handle:hover { background: @line_strong; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QSplitter::handle { background: transparent; width: 1px; }
QMenu { background: @menu; color: @text; border: 1px solid @line_strong; border-radius: @radius_control; padding: 5px; }
QMenu::item { padding: 7px 28px 7px 12px; border: 1px solid transparent; border-radius: @radius_s; }
QMenu::item:selected { background: @selection; color: @selection_text; }
QMenu::item:disabled { color: @disabled; }
QMenu::separator { height: 1px; background: @line; margin: 5px 8px; }
QToolTip { background: @surface; color: @text; border: 1px solid @line; border-radius: @radius_s; padding: 6px 9px; }
QProgressBar { border: 1px solid @line; border-radius: @radius_s; background: @disabled_surface; color: @text; text-align: center; min-height: 12px; }
QProgressBar::chunk { background: @accent; border-radius: 5px; }
QSlider::groove:horizontal { height: 4px; background: @line; border-radius: 2px; }
QSlider::sub-page:horizontal { background: @accent; border-radius: 2px; }
QSlider::handle:horizontal { background: @surface; border: 3px solid @accent; width: 10px; margin: -6px 0; border-radius: @radius_control; }
QSlider::handle:horizontal:hover { border-color: @accent_hover; }
QSlider::handle:horizontal:disabled { border-color: @disabled; }
QCheckBox { background: transparent; spacing: 8px; }
QComboBox, QSpinBox { background: @surface; border: 1px solid @line; border-radius: @radius_s; padding: 5px 9px; selection-background-color: @selection; selection-color: @selection_text; }
QComboBox:focus, QSpinBox:focus { border-color: @focus; }
QComboBox QAbstractItemView { background: @surface; color: @text; border: 1px solid @line; selection-background-color: @selection; selection-color: @selection_text; }
"""
STYLE = _STYLE_TEMPLATE  # theme_tokens.apply_style template


def apply_palette(app):
    """Files always uses the theme palette, independent of the host Qt theme."""
    from theme_tokens import apply_palette as themed
    app.setProperty('orbitThemePalette', True)
    themed(app)

_PATHS = {
    'back': '<path d="m14 5-7 7 7 7"/>',
    'forward': '<path d="m10 5 7 7-7 7"/>',
    'up': '<path d="m5 14 7-7 7 7"/>',
    'chevron': '<path d="m9 6 6 6-6 6"/>',
    'grid': '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
    'list': '<path d="M9 6h11M9 12h11M9 18h11M4 6h1M4 12h1M4 18h1"/>',
    'columns': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.1"/>',
    'search': '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    'more': '<circle cx="5" cy="12" r=".8"/><circle cx="12" cy="12" r=".8"/><circle cx="19" cy="12" r=".8"/>',
    'new-folder': '<path d="M20 10V7a2 2 0 0 0-2-2h-6l-2-2H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h8M2 8h18M18 13v8M14 17h8"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'sidebar': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M5 8h1M5 12h1M5 16h1"/>',
    'terminal': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m6 9 3 3-3 3M12 16h5"/>',
    'pin': '<path d="m8 3 8 0-1 7 4 4H5l4-4zM12 14v7"/>',
    'home': '<path d="m3 11 9-8 9 8M5 10v10h5v-6h4v6h5V10"/>',
    'download': '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/>',
    'documents': '<path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6"/>',
    'desktop': '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    'images': '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m3 17 6-5 4 4 3-3 5 4"/>',
    'video': '<rect x="3" y="5" width="13" height="14" rx="2"/><path d="m16 10 5-3v10l-5-3"/>',
    'music': '<path d="M9 17V5l11-2v12M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/>',
    'drive': '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M4 15h16M15 18h2M7 18h.1"/>',
}

@lru_cache(maxsize=256)
def _svg_icon(svg: str, size: int) -> QIcon:
    icon = QIcon()
    for scale in (1, 2):
        pixmap = QPixmap()
        data = svg.replace('<svg ', f'<svg width="{size * scale}" height="{size * scale}" ', 1)
        pixmap.loadFromData(data.encode(), 'SVG')
        pixmap.setDevicePixelRatio(scale)
        icon.addPixmap(pixmap)
    return icon


def ui_icon(name: str, size: int = 18, color: str = 'muted') -> QIcon:
    """Outline icon; ``color`` is a theme token (or an explicit '#rrggbb')."""
    from utility_material import material_icon
    return material_icon(name, size, color)

# theme-exception-begin: ilustración de carpeta
_FOLDER = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<defs><linearGradient id="back" x2="0" y2="1"><stop stop-color="#a5d6fa"/><stop offset="1" stop-color="#5997d3"/></linearGradient><linearGradient id="front" x2="0" y2="1"><stop stop-color="#8dc8f6"/><stop offset=".48" stop-color="#6db4ec"/><stop offset="1" stop-color="#4c96d4"/></linearGradient></defs>
<path d="M11 24q0-5 5-5h23q3 0 5 3l5 5h35q5 0 5 5v44q0 6-6 6H17q-6 0-6-6z" fill="#111" opacity=".15" transform="translate(0 3)"/>
<path d="M11 24q0-5 5-5h23q3 0 5 3l5 5h35q5 0 5 5v44q0 6-6 6H17q-6 0-6-6z" fill="url(#back)"/>
<path d="M16 32h68v42H16z" fill="#bcecff"/>
<path d="M10 40q0-5 5-5h71q5 0 5 5l-3 37q-.4 6-6 6H18q-6 0-6-6z" fill="url(#front)"/>
<path d="M15 35.7h71q3.5 0 4.2 3" stroke="#b4e9ff" stroke-width="1.2" fill="none" opacity=".75"/>
<path d="M18 82h64" stroke="#137fc6" stroke-width="1" opacity=".6"/>
</svg>'''
# theme-exception-end


def file_icon(path, size: int = 80) -> QIcon:
    path = Path(path)
    if path.is_dir():
        return _svg_icon(_FOLDER, size)
    suffix = path.suffix.lower().lstrip('.')
    # theme-exception-begin: ilustraciones de tipo de archivo (legibles en claro y oscuro)
    groups = [({'png','jpg','jpeg','gif','webp','svg','heic','bmp'}, '#7650a7'), ({'mp4','mkv','mov','webm','avi'}, '#8050a3'), ({'mp3','wav','flac','ogg','m4a'}, '#b23e60'), ({'pdf'}, '#b73e3c'), ({'zip','tar','gz','bz2','xz','7z'}, '#876438'), ({'py','js','ts','tsx','jsx','json','html','css','sh'}, '#376caa'), ({'doc','docx','md','txt','odt'}, '#326e9d'), ({'csv','xls','xlsx','ods'}, '#327652')]  # theme-exception: tintes de ilustraciones por tipo de archivo
    color = next((c for extensions, c in groups if suffix in extensions), '#58697c')  # theme-exception: tintes de ilustraciones por tipo de archivo
    badge = escape((suffix or 'FILE').upper()[:5])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><linearGradient id="paper" x2="0" y2="1"><stop stop-color="#fafbfc"/><stop offset="1" stop-color="#d4d8df"/></linearGradient></defs><path d="M25 10h33l19 19v56q0 5-5 5H25q-5 0-5-5V15q0-5 5-5z" fill="#000" opacity=".18" transform="translate(0 2)"/><path d="M25 10h33l19 19v56q0 5-5 5H25q-5 0-5-5V15q0-5 5-5z" fill="url(#paper)"/><path d="M58 10v15q0 5 5 5h14" fill="#b8c0cb"/><path d="M59 10v14q0 5 5 5h13" fill="#edf0f4"/><path d="M31 41h34M31 48h34M31 55h24" stroke="#aab3c0" stroke-width="2" opacity=".55"/><rect x="27" y="65" width="56" height="18" rx="4" fill="{color}"/><text x="55" y="77.5" text-anchor="middle" font-family="DejaVu Sans" font-size="10" font-weight="bold" fill="#fff">{badge}</text></svg>'''
    # theme-exception-end
    return _svg_icon(svg, size)
