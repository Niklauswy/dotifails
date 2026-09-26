"""Local desktop settings, display trials and lossless component configuration."""
import configparser
import contextlib
import copy
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from settings_data import atomic_write, backup_file

ROOT = Path(__file__).resolve().parent
ROTATIONS = ('normal','left','right','inverted')
BAR_MODULES = {'orbit':'Órbita','title':'Ventana activa','bspwm':'Escritorios','resources':'CPU y memoria','network':'Red','volume':'Volumen','battery':'Batería','date':'Fecha y hora','notifications':'Notificaciones','power':'Sesión','tray':'Bandeja'}

def run(args):
    result = subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=12)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or 'No se pudo ejecutar '+str(args[0])).strip()[:500])
    return result.stdout.strip()

def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return copy.deepcopy(default if default is not None else {})

def parse_xrandr(text):
    outputs = []
    current = None
    for line in text.splitlines():
        match = re.match(r'^(\S+) (connected|disconnected)\b(.*)',line)
        if match:
            name,connection,tail = match.groups()
            geometry = re.search(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)',tail)
            # The active rotation is before the parenthesized capabilities.
            active_rotation = re.search(r'[+-]\d+[+-]\d+\s+(normal|left|right|inverted)\b',tail)
            current = dict(name=name,connected=connection=='connected',enabled=bool(geometry),primary=' primary ' in ' '+tail+' ',x=0,y=0,width=0,height=0,mode='',rate='',rotation=active_rotation[1] if active_rotation else 'normal',modes=[])
            if geometry:
                w,h,x,y = map(int,geometry.groups())
                current.update(width=w,height=h,x=x,y=y)
            outputs.append(current)
        elif current and re.match(r'^\s+\d+x\d+',line):
            parts = line.split()
            rates = []
            for token in parts[1:]:
                value = re.match(r'([\d.]+)([*+]*)',token)
                if not value:
                    continue
                rates.append(value[1])
                if '*' in value[2]:
                    current.update(mode=parts[0],rate=value[1])
            if rates:
                current['modes'].append(dict(name=parts[0],rates=rates))
    for output in outputs:
        if not output['mode'] and output['modes']:
            output['mode'] = output['modes'][0]['name']
            output['rate'] = output['modes'][0]['rates'][0]
    return outputs

def display_inventory(runner=run):
    return parse_xrandr(runner(['xrandr','--query']))

def profile_key(outputs):
    return '|'.join(sorted(o['name'] for o in outputs if o['connected']))

def display_plan(outputs):
    return [{k:o[k] for k in ('name','enabled','primary','mode','rate','rotation','x','y')} for o in outputs if o['connected']]

def display_command(plan, inventory):
    known = {o['name']:o for o in inventory if o['connected']}
    if not plan or len({p['name'] for p in plan}) != len(plan) or set(p['name'] for p in plan) != set(known):
        raise ValueError('Las pantallas conectadas cambiaron. Pulsa Detectar y vuelve a preparar la distribución.')
    enabled = [p for p in plan if p['enabled']]
    if not enabled:
        raise ValueError('Deja al menos una pantalla encendida.')
    if sum(bool(p['primary']) for p in enabled) != 1:
        raise ValueError('Elige una pantalla principal entre las encendidas.')
    args = ['xrandr']
    for p in plan:
        args += ['--output',p['name']]
        if not p['enabled']:
            args += ['--off']
            continue
        modes = {m['name']:m['rates'] for m in known[p['name']]['modes']}
        if p['mode'] not in modes or p['rate'] not in modes[p['mode']]:
            raise ValueError('Resolución o frecuencia no disponible en '+p['name'])
        if p['rotation'] not in ROTATIONS:
            raise ValueError('Rotación inválida.')
        x,y = int(p['x']),int(p['y'])
        if not 0 <= x <= 16384 or not 0 <= y <= 16384:
            raise ValueError('La posición debe estar entre 0 y 16384 píxeles.')
        args += ['--mode',p['mode'],'--rate',p['rate'],'--rotate',p['rotation'],'--pos',f'{x}x{y}']
        if p['primary']:
            args += ['--primary']
    return args

def restore_display(plan, runner=run):
    inventory = display_inventory(runner)
    current = display_plan(inventory)
    if not current:raise ValueError('No hay pantallas conectadas para recuperar la distribución.')
    old = {p['name']:p for p in plan}
    restored = [copy.deepcopy(old.get(p['name'],p)) for p in current]
    for target,actual in zip(restored,current):
        modes={m['name']:m['rates'] for o in inventory if o['name']==target['name'] for m in o['modes']}
        if target['mode'] not in modes or target['rate'] not in modes[target['mode']]:
            target['mode'],target['rate']=actual['mode'],actual['rate']
    if not any(p['enabled'] for p in restored):
        restored[0]['enabled'] = True
    active = [p for p in restored if p['enabled']]
    if not any(p['primary'] for p in active):
        active[0]['primary'] = True
    primary=next(p for p in active if p['primary'])
    for p in restored:p['primary']=p is primary
    runner(display_command(restored,inventory))

@contextlib.contextmanager
def trial_lock(folder):
    with (Path(folder)/'lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        yield

class DisplayTrial:
    """A separate watchdog restores the old layout if this app closes or hangs."""
    def __init__(self, backend, plan):
        self.backend = backend
        inventory=display_inventory(backend.runner)
        self.old = display_plan(inventory)
        self.plan = copy.deepcopy(plan)
        self.key = profile_key(inventory)
        command = display_command(plan,inventory)
        folder = backend.home/'.cache/orbit/display-trials'
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.folder = Path(tempfile.mkdtemp(dir=folder))
        self.done=False
        atomic_write(self.folder/'trial.json',json.dumps({'old':self.old,'deadline':time.time()+35}))
        self.process = subprocess.Popen([sys.executable,str(ROOT/'settings_runtime.py'),'guard',str(self.folder)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:
            backend.runner(command)
            with trial_lock(self.folder):
                atomic_write(self.folder/'trial.json',json.dumps({'old':self.old,'deadline':time.time()+18}))
        except Exception:
            self.reject()
            raise

    def accept(self):
        if self.done:
            return
        if profile_key(display_inventory(self.backend.runner)) != self.key:
            self.reject()
            raise ValueError('Cambió la conexión de una pantalla; se revirtió la prueba.')
        with trial_lock(self.folder):
            if (self.folder/'reverted').exists() or (self.folder/'error').exists() or time.time() > read_json(self.folder/'trial.json')['deadline']:
                raise ValueError('La prueba venció. Vuelve a probar la distribución.')
            section = copy.deepcopy(self.backend.section('displays'))
            section.setdefault('profiles',{})[self.key] = self.plan
            self.backend.save_section('displays',section)
            atomic_write(self.folder/'accepted','ok')
            self.done = True

    def reject(self):
        if getattr(self,'done',False):
            return
        with trial_lock(self.folder):
            if not (self.folder/'reverted').exists():restore_display(self.old,self.backend.runner)
            atomic_write(self.folder/'reverted','ok')
        self.done = True

def ini_value(text, section, key, default=''):
    parser = configparser.ConfigParser(interpolation=None,strict=False)
    parser.read_string(text)
    return parser.get(section,key,fallback=default)

def set_ini(text, section, values):
    match = re.search(r'(?m)^\['+re.escape(section)+r'\][^\n]*\n(?P<body>.*?)(?=^\[|\Z)',text,re.S)
    if not match:
        text += '\n['+section+']\n'
        match = re.search(r'(?m)^\['+re.escape(section)+r'\][^\n]*\n(?P<body>.*?)(?=^\[|\Z)',text,re.S)
    body = match['body']
    for key,value in values.items():
        pattern = r'(?m)^\s*'+re.escape(key)+r'\s*=.*$'
        line = key+' = '+str(value)
        body = re.sub(pattern,lambda _:line,body) if re.search(pattern,body) else body.rstrip()+'\n'+line+'\n'
    return text[:match.start('body')]+body+'\n'+text[match.end('body'):]

def kv_values(text):
    return {m[1]:m[2].strip().rstrip(';').strip().strip('"') for m in re.finditer(r'(?m)^([\w-]+)\s*=\s*(.*?)\s*$',text)}

def set_values(text, values, semicolon=False):
    for key,value in values.items():
        line = key+' = '+str(value)+(';' if semicolon else '')
        pattern = r'(?m)^'+re.escape(key)+r'\s*=.*$'
        text = re.sub(pattern,lambda _:line,text) if re.search(pattern,text) else text.rstrip()+'\n'+line+'\n'
    return text

def color(value):
    if not re.fullmatch(r'#[\da-fA-F]{6}',str(value)):
        raise ValueError('Usa un color #RRGGBB.')
    return value

def bounded(value, low, high, integer=False):
    value = int(value) if integer else float(value)
    if not low <= value <= high:
        raise ValueError(f'Valor fuera del intervalo {low}–{high}.')
    return value

class EnvironmentSettings:
    def __init__(self, home=None, runner=run):
        self.home = Path(home or Path.home())
        self.runner = runner
        self.path = self.home/'.config/orbit/environment.json'
        self.reload()

    def reload(self):
        self.data = read_json(self.path)

    def section(self, name):
        return self.data.get(name,{})

    def save_section(self, name, values):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with (self.path.parent/'environment.lock').open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            self._save_section(name,values)

    def _save_section(self,name,values):
        latest = read_json(self.path)
        if latest.get(name,{}) != self.data.get(name,{}):
            raise ValueError('Esta sección cambió en otra ventana. Recarga antes de guardar.')
        latest[name] = values
        if self.path.exists():
            backup_file(self.path,self.home/'.local/share/orbit/settings-backups')
        atomic_write(self.path,json.dumps(latest,ensure_ascii=False,indent=2)+'\n')
        # Keep each section's observed version until it is explicitly reloaded.
        # Saving wallpaper must not silently approve stale monitor/bar controls.
        self.data[name] = copy.deepcopy(values)

    def edit_file(self,path,text,activate=None):
        path = Path(path)
        old = path.read_text()
        backup_file(path,self.home/'.local/share/orbit/settings-backups')
        atomic_write(path,text)
        try:
            if activate:
                activate()
        except Exception:
            atomic_write(path,old)
            raise

    def bar_values(self):
        text = (self.home/'.config/bspwm/polybar/config').read_text()
        get = lambda section,key,default='':ini_value(text,section,key,default)
        bg = get('colors','bg','#A6101118')
        return dict(height=int(get('bar/base','height','36')),offset=int(get('bar/base','offset-y','10')),radius=int(get('bar/base','radius','12')),opacity=round(int(bg[1:3],16)*100/255) if len(bg)==9 else 100,background='#'+bg[-6:],foreground=get('colors','fg','#EBECF3'),accent=get('colors','accent','#B8C8FA'),left=get('bar/left','modules-left').split(),center=get('bar/center','modules-center').split(),right=get('bar/right','modules-right').split(),monitors=self.section('bar').get('monitors',{}),tray_monitor=self.section('bar').get('tray_monitor',''))

    def apply_bar(self, values):
        old = self.bar_values()
        for key,lo,hi in [('height',24,64),('offset',0,60),('radius',0,30),('opacity',10,100)]:
            values[key] = bounded(values[key],lo,hi,True)
        for key in ('background','foreground','accent'):
            color(values[key])
        for side in ('left','center','right'):
            if len(values[side]) != len(set(values[side])) or any(x not in BAR_MODULES for x in values[side]):
                raise ValueError('Módulo de barra desconocido o repetido.')
        if any('tray' in values[side] for side in ('left','center')):
            raise ValueError('La bandeja debe ir en la sección derecha.')
        if not any(values[side] for side in ('left','center','right')):
            raise ValueError('Deja al menos un módulo en la barra.')
        path = self.home/'.config/bspwm/polybar/config'
        text = path.read_text()
        text = set_ini(text,'bar/base',{'height':values['height'],'offset-y':values['offset'],'radius':values['radius']})
        text = set_ini(text,'colors',{'bg':f"#{round(values['opacity']*255/100):02X}"+values['background'][1:],'fg':values['foreground'],'accent':values['accent']})
        for side in ('left','center','right'):
            text = set_ini(text,'bar/'+side,{'modules-'+('center' if side=='center' else side):' '.join(values[side])})
        text = set_ini(text,'bar/right-secondary',{'modules-right':' '.join(x for x in values['right'] if x!='tray')})
        previous = copy.deepcopy(self.section('bar'))
        self.save_section('bar',{'monitors':values['monitors'],'tray_monitor':values['tray_monitor']})
        try:
            self.edit_file(path,text,lambda:self.runner([str(ROOT/'desktop-bar')]))
        except Exception:
            self.save_section('bar',previous)
            try:self.runner([str(ROOT/'desktop-bar')])
            except Exception:pass
            raise

    def wallpaper_values(self):
        saved = copy.deepcopy(self.section('wallpaper'))
        if not saved.get('default'):
            try:
                for word in shlex.split((self.home/'.fehbg').read_text(),comments=True):
                    if Path(word).suffix.lower() in ('.png','.jpg','.jpeg','.webp','.bmp') and Path(word).is_file():
                        saved['default'] = word
            except (OSError,ValueError):
                pass
        if not saved.get('default'):
            theme=read_json(self.home/'.config/dotifails/theme.json',{})
            filename=theme.get('wallpaper','tokyo.png')
            if filename not in ('tokyo.png','azul.jpg'):filename='tokyo.png'
            bundled=self.home/'.local/share/backgrounds'/filename
            if bundled.is_file():saved['default']=str(bundled)
        saved.setdefault('mode','fill')
        saved.setdefault('monitors',{})
        saved.setdefault('folders',[])
        return saved

    def apply_wallpaper(self, values):
        old=copy.deepcopy(self.section('wallpaper'))
        self.save_section('wallpaper',values)
        try:render_wallpaper(values,display_inventory(self.runner),self.home,self.runner)
        except Exception:
            self.save_section('wallpaper',old)
            raise

    def component_values(self, component):
        paths = {'effects':'bspwm/picom.conf','terminal':'ghostty/config','notifications':'bspwm/dunstrc'}
        path = self.home/'.config'/paths[component]
        text = path.read_text()
        if component == 'notifications':
            return {key:ini_value(text,'global',key,default).strip('"') for key,default in [('origin','top-right'),('font','Inter 10'),('transparency','5'),('corner_radius','12'),('notification_limit','4'),('padding','18'),('gap_size','10')]} | {'timeout':ini_value(text,'urgency_normal','timeout','6')}
        return kv_values(text)

    def apply_component(self, component, values):
        if component == 'terminal':
            clean = {'font-size':bounded(values['font-size'],8,36),'background-opacity':bounded(values['background-opacity'],.1,1),'window-padding-x':bounded(values['window-padding-x'],0,60,True),'window-padding-y':bounded(values['window-padding-y'],0,60,True),'scrollback-limit':bounded(values['scrollback-limit'],1000,1000000,True)}
            font = values['font-family'].strip()
            if not font or '\n' in font or '"' in font:
                raise ValueError('Nombre de fuente inválido.')
            clean['font-family'] = '"'+font+'"'
            for k in ('background','foreground'):
                clean[k] = color(values[k])[1:]
            path = self.home/'.config/ghostty/config'
            self.edit_file(path,set_values(path.read_text(),clean),lambda:self.runner(['ghostty','+validate-config']))
        elif component == 'effects':
            path = self.home/'.config/bspwm/picom.conf'
            clean = {k:bounded(values[k],lo,hi,integer) for k,lo,hi,integer in [('corner-radius',0,30,True),('blur-strength',1,8,True),('shadow-radius',0,40,True),('shadow-opacity',0,1,False)]}
            for key in ('blur-background','shadow','fading','vsync'):
                clean[key] = 'true' if values[key] else 'false'
            duration = bounded(values['duration'],50,600,True)/1000
            text = set_values(path.read_text(),clean,True)
            text = re.sub(r'(duration\s*=\s*)[\d.]+',lambda m:m[1]+str(duration),text)
            def special_surface(match):
                block=match[0]
                condition=re.search(r'match\s*=\s*"([^"]+)"',block)
                if not condition or 'fullscreen' in condition[1]:return block
                # Explicit appearance rules otherwise override the global toggle.
                if 'blur-background' in block:block=re.sub(r'blur-background\s*=\s*(true|false)', 'blur-background = '+clean['blur-background'],block)
                if 'dock' not in condition[1] and 'desktop' not in condition[1] and 'Polybar' not in condition[1]:
                    block=re.sub(r'shadow\s*=\s*(true|false)','shadow = '+clean['shadow'],block)
                return block
            text=re.sub(r'\{[^{}]*\}',special_surface,text)
            def restart():
                subprocess.run(['pkill','-TERM','-u',str(os.getuid()),'-x','picom'],capture_output=True)
                for _ in range(30):
                    if subprocess.run(['pgrep','-u',str(os.getuid()),'-x','picom'],capture_output=True).returncode:break
                    time.sleep(.05)
                self.runner([str(self.home/'.local/bin/desktop-compositor')])
            try:self.edit_file(path,text,restart)
            except Exception:
                # edit_file has already restored the working configuration.
                try:restart()
                except Exception:pass
                raise
        elif component == 'notifications':
            path = self.home/'.config/bspwm/dunstrc'
            if values['origin'] not in ('top-left','top-center','top-right','bottom-left','bottom-center','bottom-right'):
                raise ValueError('Posición de notificaciones inválida.')
            clean = {'origin':values['origin']}
            for key,lo,hi in [('transparency',0,60),('corner_radius',0,30),('notification_limit',1,12),('padding',4,40),('gap_size',0,30)]:
                clean[key] = bounded(values[key],lo,hi,True)
            if '\n' in values['font'] or '"' in values['font']:
                raise ValueError('Fuente inválida.')
            clean['font'] = values['font']
            text = set_ini(path.read_text(),'global',clean)
            text = set_ini(text,'urgency_normal',{'timeout':bounded(values['timeout'],1,60,True)})
            self.edit_file(path,text,lambda:self.runner(['dunstctl','reload',str(path)]))
        else:
            raise ValueError('Componente desconocido.')

    def workspaces(self):
        tree = json.loads(self.runner(['bspc','wm','-d']))
        def count(node):
            return 0 if not node else int(bool(node.get('client'))) + count(node.get('firstChild')) + count(node.get('secondChild'))
        return [dict(id=f"0x{d['id']:08X}",name=d['name'],monitor=m['name'],windows=count(d.get('root')),active=d['id']==m['focusedDesktopId']) for m in tree['monitors'] for d in m['desktops']]

    def workspace_action(self, action, ident='', value=''):
        if read_json(self.path).get('workspaces',{})!=self.section('workspaces'):
            raise ValueError('Los escritorios cambiaron en otra ventana. Recarga antes de editar.')
        rows = self.workspaces()
        if action in ('rename','add'):
            if not value.strip() or len(value)>40 or any(c in value for c in '\n\r\0'):
                raise ValueError('El nombre del escritorio debe tener entre 1 y 40 caracteres.')
            if any(r['name']==value and r['id']!=ident for r in rows):
                raise ValueError('Ya existe un escritorio con ese nombre.')
        if action=='rename':self.runner(['bspc','desktop',ident,'-n',value])
        elif action=='add':self.runner(['bspc','monitor',ident,'-a',value])
        elif action=='move':
            current=next(r for r in rows if r['id']==ident)
            if sum(r['monitor']==current['monitor'] for r in rows)==1:raise ValueError('Deja un escritorio en cada monitor.')
            self.runner(['bspc','desktop',ident,'-m',value])
        elif action=='remove':
            current=next(r for r in rows if r['id']==ident)
            if current['windows'] or sum(r['monitor']==current['monitor'] for r in rows)==1:raise ValueError('Solo se pueden quitar escritorios vacíos y debe quedar uno en el monitor.')
            self.runner(['bspc','desktop',ident,'-r'])
        else:raise ValueError('Acción desconocida.')
        mapping={}
        for r in self.workspaces():mapping.setdefault(r['monitor'],[]).append(r['name'])
        self.save_section('workspaces',mapping)

    def autostart_entries(self):
        roots=[Path(p)/'autostart' for p in os.environ.get('XDG_CONFIG_DIRS','/etc/xdg').split(':')]+[self.home/'.config/autostart']
        files={}
        for folder in roots:
            for p in folder.glob('*.desktop'):files[p.name]=p
        result=[]
        for name,p in files.items():
            try:
                text=p.read_text();get=lambda k,d='':ini_value(text,'Desktop Entry',k,d)
                if get('Type','Application')!='Application':continue
                result.append(dict(id=name,name=get('Name',p.stem),command=get('Exec'),enabled=get('Hidden','false').lower()!='true',managed=name in self.section('autostart').get('entries',[]),path=str(p)))
            except (OSError,configparser.Error):continue
        return sorted(result,key=lambda r:r['name'].casefold())

    def set_autostart(self, entry, enabled):
        target=self.home/'.config/autostart'/entry['id']
        text=Path(entry['path']).read_text()
        if target.exists():backup_file(target,self.home/'.local/share/orbit/settings-backups')
        atomic_write(target,set_ini(text,'Desktop Entry',{'Hidden':'false' if enabled else 'true'}))
        entries=list(self.section('autostart').get('entries',[]))
        if entry['id'] not in entries:entries.append(entry['id'])
        self.save_section('autostart',{'entries':entries})

    def add_autostart(self, name, command):
        if not name.strip() or '\n' in name or '\n' in command or not command.strip():raise ValueError('Escribe un nombre y un comando en una sola línea.')
        argv=shlex.split(command)
        if not argv or not (shutil.which(argv[0]) or Path(argv[0]).is_file()):raise ValueError('No se encuentra el programa del comando.')
        ident='orbit-'+re.sub(r'[^a-z0-9]+','-',name.casefold()).strip('-')+'.desktop'
        path=self.home/'.config/autostart'/ident
        if path.exists():raise ValueError('Ya existe una entrada con ese nombre.')
        atomic_write(path,'[Desktop Entry]\nType=Application\nName='+name+'\nExec='+command+'\nTerminal=false\nHidden=false\n')
        self.save_section('autostart',{'entries':[*self.section('autostart').get('entries',[]),ident]})

def render_wallpaper(values, outputs, home=None, runner=run):
    from PySide6.QtCore import Qt,QRectF
    from PySide6.QtGui import QImage,QImageReader,QPainter,QColor
    home=Path(home or Path.home())
    active=[o for o in outputs if o['connected'] and o['enabled']]
    if not active:raise ValueError('No se encontraron pantallas activas.')
    width=max(o['x']+o['width'] for o in active);height=max(o['y']+o['height'] for o in active)
    if width*height>100_000_000:raise ValueError('La superficie combinada es demasiado grande.')
    canvas=QImage(width,height,QImage.Format_RGB32);canvas.fill(QColor('#111218'))
    painter=QPainter(canvas);painter.setRenderHint(QPainter.SmoothPixmapTransform)
    try:
        for output in active:
            selected=values.get('monitors',{}).get(output['name'],{})
            path=Path(selected.get('path') or values.get('default','')).expanduser()
            if not path.is_file():raise ValueError('Elige un fondo para '+output['name'])
            reader=QImageReader(str(path));reader.setAutoTransform(True)
            if reader.size().width()*reader.size().height()>70_000_000:raise ValueError('Imagen demasiado grande: '+path.name)
            image=reader.read()
            if image.isNull():raise ValueError('No se puede leer la imagen: '+path.name)
            rect=QRectF(output['x'],output['y'],output['width'],output['height'])
            mode=selected.get('mode') or values.get('mode','fill')
            if mode not in ('fill','fit','stretch','center'):raise ValueError('Modo de fondo inválido.')
            if mode=='stretch':target=rect
            else:
                scale=(max if mode=='fill' else min)(rect.width()/image.width(),rect.height()/image.height()) if mode!='center' else 1
                w,h=image.width()*scale,image.height()*scale
                target=QRectF(rect.center().x()-w/2,rect.center().y()-h/2,w,h)
            painter.save();painter.setClipRect(rect);painter.drawImage(target,image);painter.restore()
    finally:painter.end()
    folder=home/'.cache/orbit/wallpapers';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=folder/('desktop-'+str(time.time_ns())+'.png')
    if not canvas.save(str(path)):raise OSError('No se pudo preparar el fondo.')
    path.chmod(0o600)
    fehbg=home/'.fehbg'
    if fehbg.exists():backup_file(fehbg,home/'.local/share/orbit/settings-backups')
    runner(['feh','--no-fehbg','--no-xinerama','--bg-scale',str(path)])
    atomic_write(fehbg,'#!/bin/sh\n'+shlex.join(['feh','--no-fehbg','--no-xinerama','--bg-scale',str(path)])+'\n',0o700)
    # Bound generated wallpaper storage; never remove the user's source images.
    for old in sorted(folder.glob('desktop-*.png'),reverse=True)[20:]:
        if re.fullmatch(r'desktop-\d+\.png',old.name):old.unlink(missing_ok=True)
    return path

def configured_bar_monitors(active, candidates=None, home=None):
    """Called by the existing bar launcher; leave its visibility watcher intact."""
    prefs=read_json(Path(home or Path.home())/'.config/orbit/environment.json').get('bar',{})
    selected=[name for name in (candidates if candidates is not None else active) if prefs.get('monitors',{}).get(name,name in active)]
    tray=prefs.get('tray_monitor')
    if tray in selected:selected.remove(tray);selected.insert(0,tray)
    return selected
