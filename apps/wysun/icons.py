from pathlib import Path
from functools import lru_cache
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPixmap,QPainter,QPen,QColor,QFont,QIcon
from wysun_core.qt_theme import on_theme_changed
from wysun_core.ui import style as kit

ASSETS=Path(__file__).parent/'assets/lucide'
ALIASES={
 'home':'search','files':'folder-open','file':'file-text','text':'file-text','calc':'calculator',
 'windows':'panels-top-left','window':'panels-top-left','emoji':'smile','settings':'settings-2','system':'cpu',
 'network':'wifi','wifi':'wifi','vpn':'shield-check','ssh':'server','url':'globe','web':'globe',
 'audio':'volume-2','notifications':'bell','notification':'bell','back':'arrow-left','favorite':'pin','clock':'calendar',
 'shutdown':'power','reboot':'rotate-cw','suspend':'moon','logout':'log-out','color':'palette','trash':'trash-2',
 'edit-paste':'clipboard','system-search':'search','camera-photo':'camera','face-smile':'smile',
 'accessories-calculator':'calculator','network-wireless':'wifi','preferences-system-windows':'panels-top-left',
 'utilities-terminal':'terminal','preferences-system':'settings-2','text-x-generic':'file-text',
 'accessories-text-editor':'file-text','preferences-desktop-wallpaper':'image','applications-graphics':'palette',
 'audio-volume-high':'volume-2','audio-volume-muted':'volume-x','preferences-desktop-notification':'bell',
 'preferences-desktop':'sliders-horizontal','action':'arrow-right','info':'circle-help','command':'terminal',
 'notes':'file-text','wallpaper':'image','compositor':'sliders-horizontal','mute':'volume-x','screenshot':'camera',
 'network_action':'wifi','network_device':'cable','status_action':'sliders-horizontal'
}
# Category hues are theme tokens: graphite in the dark palette, darker in the light one.
ACCENTS={'clipboard':'cat_orange','files':'cat_blue','file':'cat_blue','calculator':'cat_green','calc':'cat_green','emoji':'cat_yellow','windows':'cat_indigo','network':'cat_cyan','bluetooth':'cat_periwinkle','settings':'cat_lavender','power':'cat_rose','terminal':'cat_slate'}

def tint(color):
 """Icon colour: a theme token name, or an explicit '#rrggbb' (user colours, previews)."""
 if isinstance(color,str) and color.startswith('#'):return color
 from wysun_core.qt_theme import color as token
 return token(color or 'glyph').name()

@lru_cache(maxsize=512)
def glyph(name,size=24,color='glyph'):
 color=tint(color)
 from wysun_core.qt_theme import tokens
 stroke=tokens()['icon_stroke']
 path=ASSETS/(ALIASES.get(name,name)+'.svg')
 if not path.exists():path=ASSETS/'file-text.svg'
 data=path.read_text().replace('currentColor',color).replace('width="24"',f'width="{size*2}"').replace('height="24"',f'height="{size*2}"').replace('stroke-width="2"',f'stroke-width="{stroke:g}"')
 pm=QPixmap();pm.loadFromData(data.encode(),'SVG');pm.setDevicePixelRatio(2)
 return pm

@lru_cache(maxsize=160)
def badge(name,size=30):
 color=tint(ACCENTS.get(name,'cat_slate'));pm=QPixmap(size*2,size*2);pm.fill(Qt.transparent);pm.setDevicePixelRatio(2);p=QPainter(pm);p.setRenderHint(QPainter.Antialiasing);c=QColor(color);c.setAlpha(27);p.setBrush(c);c.setAlpha(38);p.setPen(QPen(c,1));p.drawRoundedRect(QRectF(.5,.5,size-1,size-1),7,7);p.drawPixmap((size-18)//2,(size-18)//2,glyph(name,18,color));p.end();return pm

_icon_specs={}
def remember(result,factory,args):
 """Record how a themed QIcon was made so refresh_icons can rebuild it."""
 _icon_specs[result.cacheKey()]=(factory,tuple(args));return result

def icon(name,size=20,color='glyph'):
 return remember(QIcon(glyph(name,size,color)),icon,(name,size,color))

def refresh_icons():
 """Rebuild every remembered icon after a theme change (buttons, actions, items)."""
 from PySide6.QtWidgets import QApplication,QAbstractButton,QListWidget,QTreeWidget,QTreeWidgetItemIterator,QTableWidget,QComboBox
 if not _icon_specs:return
 def refreshed(current):
  spec=_icon_specs.get(current.cacheKey())
  return spec[0](*spec[1]) if spec else current
 for widget in QApplication.allWidgets():
  for action in widget.actions() or ():
   if not action.icon().isNull():action.setIcon(refreshed(action.icon()))
  if isinstance(widget,QAbstractButton):widget.setIcon(refreshed(widget.icon()))
  elif isinstance(widget,QListWidget):
   for i in range(widget.count()):item=widget.item(i);item.setIcon(refreshed(item.icon()))
  elif isinstance(widget,QComboBox):
   for i in range(widget.count()):widget.setItemIcon(i,refreshed(widget.itemIcon(i)))
  elif isinstance(widget,QTreeWidget):
   iterator=QTreeWidgetItemIterator(widget)
   while iterator.value():
    item=iterator.value()
    for col in range(item.columnCount()):item.setIcon(col,refreshed(item.icon(col)))
    iterator+=1
  elif isinstance(widget,QTableWidget):
   for row in range(widget.rowCount()):
    for col in range(widget.columnCount()):
     item=widget.item(row,col)
     if item:item.setIcon(refreshed(item.icon()))

@lru_cache(maxsize=2000)
def emoji_pixmap(emoji,size=42):
 pm=QPixmap(size,size);pm.fill(Qt.transparent);p=QPainter(pm);p.setRenderHint(QPainter.TextAntialiasing);f=QFont('Noto Color Emoji');f.setPixelSize(int(size*.82));p.setFont(f);p.drawText(QRectF(0,0,size,size),Qt.AlignCenter,emoji);p.end();return pm


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


def paint_symbol(painter, rect, name, tint, size=None, filled=False):
    """The kit's Material symbol, or the matching Lucide glyph when the ligature is unavailable."""
    if kit.paint_symbol(painter, rect, name, tint, size, filled):
        return
    from wysun_core.qt_theme import color, tokens
    size = round(size or tokens()['icon_size'] * 1.2)
    ink = color(tint) if isinstance(tint, str) else tint
    rect = QRectF(rect)
    pixmap = glyph(FALLBACK.get(name, 'music'), max(12, round(size * .8)), ink.name())
    side = pixmap.width() / pixmap.devicePixelRatio()
    painter.drawPixmap(QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2, side, side),
                       pixmap, QRectF(pixmap.rect()))


def _follow_theme():
    glyph.cache_clear()
    badge.cache_clear()
    refresh_icons()


on_theme_changed(_follow_theme)
