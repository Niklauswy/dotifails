from pathlib import Path
from functools import lru_cache
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPixmap,QPainter,QPen,QColor,QFont,QIcon

ASSETS=Path(__file__).parent/'assets/lucide'
ALIASES={
 'home':'search','files':'folder-open','file':'file-text','text':'file-text','snippet':'code','snippets':'code','calc':'calculator',
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
 'network_action':'wifi','network_device':'cable','status_action':'sliders-horizontal','snippet-edit':'pencil'
}
ACCENTS={'clipboard':'#E9AA75','files':'#84B9E9','file':'#84B9E9','snippets':'#B9A1E5','snippet':'#B9A1E5','calculator':'#9CCDA1','calc':'#9CCDA1','emoji':'#E6C47A','windows':'#A1B7DC','network':'#82BDDF','bluetooth':'#88ABEB','settings':'#B7ADDB','power':'#DD969B','terminal':'#ABB8C6'}

@lru_cache(maxsize=512)
def glyph(name,size=24,color='#CDD0DA'):
 path=ASSETS/(ALIASES.get(name,name)+'.svg')
 if not path.exists():path=ASSETS/'file-text.svg'
 data=path.read_text().replace('currentColor',color).replace('width="24"',f'width="{size*2}"').replace('height="24"',f'height="{size*2}"').replace('stroke-width="2"','stroke-width="1.8"')
 pm=QPixmap();pm.loadFromData(data.encode(),'SVG');pm.setDevicePixelRatio(2)
 return pm

@lru_cache(maxsize=160)
def badge(name,size=30):
 color=ACCENTS.get(name,'#ABB8CB');pm=QPixmap(size*2,size*2);pm.fill(Qt.transparent);pm.setDevicePixelRatio(2);p=QPainter(pm);p.setRenderHint(QPainter.Antialiasing);c=QColor(color);c.setAlpha(27);p.setBrush(c);c.setAlpha(38);p.setPen(QPen(c,1));p.drawRoundedRect(QRectF(.5,.5,size-1,size-1),7,7);p.drawPixmap((size-18)//2,(size-18)//2,glyph(name,18,color));p.end();return pm

def icon(name,size=20):return QIcon(glyph(name,size))

@lru_cache(maxsize=2000)
def emoji_pixmap(emoji,size=42):
 pm=QPixmap(size,size);pm.fill(Qt.transparent);p=QPainter(pm);p.setRenderHint(QPainter.TextAntialiasing);f=QFont('Noto Color Emoji');f.setPixelSize(int(size*.82));p.setFont(f);p.drawText(QRectF(0,0,size,size),Qt.AlignCenter,emoji);p.end();return pm
