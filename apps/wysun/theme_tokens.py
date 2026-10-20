"""Complete desktop themes and shared native colour/motion tokens."""
import colorsys,json,os,re,time
from pathlib import Path
from PySide6.QtGui import QColor

THEMES={
 'tokyo':dict(name='Tokyo',wallpaper='tokyo.png',description='Violeta luminoso, negro ciruela y movimiento suave.',background='#17131f',surface='#211b2e',foreground='#e5dcfa',accent='#bb9af7',muted='#9c8fb7',hue=.755,saturation=.32,enter=300,exit=170,lift=16,radius=24,pulse=.38,lock_enter=.40,lock_exit=.32,palette=['#15121c','#f7768e','#9ece6a','#e0af68','#7aa2f7','#bb9af7','#7dcfff','#a9b1d6','#504267','#ff9eaa','#b9e58b','#f2c77d','#a4b9ff','#d1b2ff','#9ce6ff','#e5dcfa']),
 'severance':dict(name='Severance',wallpaper='azul.jpg',description='Azul petróleo, acentos de hielo y movimiento preciso.',background='#0c171c',surface='#15272e',foreground='#d2e4e8',accent='#79c9dc',muted='#7c9aa4',hue=.535,saturation=.34,enter=190,exit=120,lift=8,radius=16,pulse=.24,lock_enter=.24,lock_exit=.20,palette=['#0b151a','#df8790','#a4c3a4','#d7c49c','#7fa8d8','#a2a7cd','#79c9dc','#a8bcc3','#3e5c67','#f0a3ab','#bdd4bb','#ead8b6','#a6c5e9','#c2c5e2','#a3e2ee','#e1eff1'])
}
THEMES['space-black']=dict(name='Space Black',wallpaper='space-black.png',description='Grafito y plata · movimiento sutil.',background='#101012',surface='#202023',foreground='#e6e6e8',accent='#ceced4',muted='#919198',hue=0,saturation=0,enter=260,exit=160,lift=6,radius=20,pulse=.28,lock_enter=.28,lock_exit=.24,palette=['#101012','#de9297','#a9beaa','#cec1a5','#adb7ce','#b7acc6','#adbfc5','#c5c5ca','#55555c','#edacb0','#c3d3c2','#e0d4bc','#c8cede','#d3c9df','#c8d9de','#eeeef0'])
ALIASES={'azul':'severance','morado':'tokyo','Tokyo':'tokyo','Severance':'severance'}
_cache=(0,None,None)

def normalize(value):
    key=ALIASES.get(value,value)
    return key if key in THEMES else 'severance'

def theme_id(home=None):
    override=os.environ.get('ORBIT_THEME')
    if override:return normalize(override)
    global _cache
    from hypr_settings import config_dir
    root=config_dir(home)
    now=time.monotonic()
    if _cache[1]==root and now-_cache[0]<.25:return _cache[2]
    value='severance'
    for path in (root/'orbit/theme.json',):
        try:
            data=json.loads(path.read_text());value=normalize(data.get('id',data.get('name','severance')));break
        except (OSError,ValueError,TypeError):continue
    _cache=(now,root,value);return value

def tokens(home=None):return THEMES[theme_id(home)]
def invalidate():
    global _cache
    _cache=(0,None,None)

def theme_color(value,key=None):
    """Tint UI neutrals/cool accents; preserve semantic warning/success colours."""
    if not isinstance(value,str) or not re.fullmatch(r'#[\da-fA-F]{6}',value):return value
    red,green,blue=[int(value[n:n+2],16)/255 for n in (1,3,5)]
    hue,light,saturation=colorsys.rgb_to_hls(red,green,blue)
    theme=THEMES[key] if key else tokens()
    if .46<=hue<=.83 or saturation<.16:
        if light<.035 or (saturation<.02 and light>.95):return value
        hue=theme['hue'];saturation=theme['saturation'] if key or not theme['saturation'] else min(.48,max(theme['saturation']*.45,saturation*.82))
        if light<.18:saturation=theme['saturation']
        rgb=colorsys.hls_to_rgb(hue,light,saturation)
        return '#'+''.join(f'{round(v*255):02x}' for v in rgb)
    return value

class ThemeColor(QColor):
    def __init__(self,*values):
        if len(values)==1 and isinstance(values[0],str):values=(theme_color(values[0]),)
        elif len(values) in (3,4) and all(isinstance(v,int) for v in values):
            colour=QColor(theme_color('#'+''.join(f'{v:02x}' for v in values[:3])))
            if len(values)==4:colour.setAlpha(values[3])
            values=(colour,)
        super().__init__(*values)

def theme_css(style):
    style=re.sub(r'#[\da-fA-F]{6}(?![\da-fA-F])',lambda m:theme_color(m[0]),style)
    def rgb(match):
        values=match[2].split(',')
        try:
            raw='#'+''.join(f'{int(v.strip()):02x}' for v in values[:3]);new=theme_color(raw)
            mapped=[str(int(new[i:i+2],16)) for i in (1,3,5)]+values[3:]
            return match[1]+'('+','.join(mapped)+')'
        except (ValueError,IndexError):return match[0]
    return re.sub(r'\b(rgb|rgba)\(([^)]+)\)',rgb,style)

def apply_style(widget,style):
    widget.setProperty('orbitOriginalStyle',style)
    widget.setStyleSheet(theme_css(style))

def refresh_widgets():
    from PySide6.QtWidgets import QApplication,QWidget
    invalidate()
    from icons import glyph,badge
    glyph.cache_clear();badge.cache_clear()
    app=QApplication.instance()
    if app and app.property('orbitOriginalStyle') is not None:app.setStyleSheet(theme_css(app.property('orbitOriginalStyle')))
    for widget in QApplication.allWidgets():
        style=widget.property('orbitOriginalStyle')
        if style is not None:widget.setStyleSheet(theme_css(style))
        QWidget.update(widget)
    from icons import refresh_icons
    refresh_icons()

def watch_theme():
    """Watch files and parent directories so atomic replace and late creation work."""
    from PySide6.QtCore import QFileSystemWatcher,QTimer,QObject
    from PySide6.QtWidgets import QApplication
    from hypr_settings import config_dir
    app=QApplication.instance()
    if not app or hasattr(app,'orbitThemeWatcher'):return
    class ThemeWatcher(QObject):
        def __init__(self):
            super().__init__(app);self.watcher=QFileSystemWatcher(self);self.timer=QTimer(self)
            self.timer.setSingleShot(True);self.timer.setInterval(40)
            self.key=theme_id();self.watcher.fileChanged.connect(self.changed);self.watcher.directoryChanged.connect(self.changed)
            self.timer.timeout.connect(self.refresh);self.arm()
        def arm(self):
            targets=set()
            for path in (config_dir()/'orbit/theme.json',):
                if path.exists():targets.add(str(path))
                parent=path.parent
                while not parent.exists() and parent!=parent.parent:parent=parent.parent
                if parent.exists():targets.add(str(parent))
            current=set(self.watcher.files()+self.watcher.directories())
            if current-targets:self.watcher.removePaths(list(current-targets))
            if targets-current:self.watcher.addPaths(list(targets-current))
        def changed(self,*_):self.timer.start()
        def refresh(self):
            self.arm();invalidate();key=theme_id()
            if key!=self.key:self.key=key;refresh_widgets()
    app.orbitThemeWatcher=ThemeWatcher()
