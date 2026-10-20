"""Hyprland 0.55 Lua configuration, scoped to Wysun-owned fragments."""
import copy
import json
import math
import os
from pathlib import Path
import re
from desktop_backend import Desktop


def config_dir(home=None):
    home=Path(home or Path.home())
    return Path(os.environ.get('XDG_CONFIG_HOME',str(home/'.config'))) if home==Path.home() else home/'.config'


def lua(value):
    if value is None:return 'nil'
    if type(value) is bool:return 'true' if value else 'false'
    if type(value) in (float,int):
        if not math.isfinite(value):raise ValueError('Número inválido')
        return str(value)
    if isinstance(value,str):
        if any(ord(c)<32 for c in value):raise ValueError('Texto Lua inválido')
        return json.dumps(value,ensure_ascii=False)
    if isinstance(value,dict):return '{ '+', '.join('['+lua(k)+'] = '+lua(v) for k,v in value.items())+' }'
    if isinstance(value,(list,tuple)):return '{ '+', '.join(map(lua,value))+' }'
    raise ValueError('Tipo Lua inválido')


def option(runner,name):
    item=json.loads(runner(['hyprctl','-j','getoption',name]))
    for key in ('bool','int','float','str','custom','css','gradient'):
        if key in item:return item[key]
    raise RuntimeError('No se pudo leer el ajuste actual: '+name)


def snapshot_config(runner,shape,prefix=''):
    result={}
    for key,value in shape.items():
        name=prefix+key
        result[key]=snapshot_config(runner,value,name+(':' if not prefix else '.')) if isinstance(value,dict) else option(runner,name)
    return result


def evaluate(runner,text):
    result=runner(['hyprctl','eval',text])
    if result.strip()!='ok':raise RuntimeError('Hyprland rechazó el cambio: '+result[:500])


def apply_fragment(runner,files,text,rollback):
    """Publish durable files before changing runtime; restore both on any failure."""
    from settings_data import atomic_write,backup_file
    originals={path:path.read_text() if path.exists() else None for path in files}
    for path in files:backup_file(path,path.parent/'backups')
    attempted=False
    try:
        for path,content in files.items():atomic_write(path,content)
        attempted=True;evaluate(runner,text)
    except Exception as error:
        failures=[]
        for path,content in originals.items():
            try:
                if content is None:path.unlink(missing_ok=True)
                else:atomic_write(path,content)
            except Exception as exc:failures.append(str(exc))
        if attempted:
            try:evaluate(runner,rollback)
            except Exception as exc:failures.append(str(exc))
        if failures:raise RuntimeError(str(error)+'; recuperación incompleta: '+'; '.join(failures)) from error
        raise


def inventory(runner):
    monitors=json.loads(runner(['hyprctl','-j','monitors','all']));rows=[]
    for index,m in enumerate(monitors):
        scale=float(m.get('scale',1));w,h=m.get('width',0),m.get('height',0);transform=m.get('transform',0)
        if transform%2:w,h=h,w
        modes={}
        for mode in m.get('availableModes',[]):
            match=re.fullmatch(r'(\d+x\d+)@([\d.]+)Hz',mode)
            if match:modes.setdefault(match[1],[]).append(match[2])
        current=f"{m.get('width',0)}x{m.get('height',0)}";rate=f"{m.get('refreshRate',60):.2f}"
        if m.get('width') and rate not in modes.setdefault(current,[]):modes[current].append(rate)
        rows.append(dict(name=m['name'],connected=True,enabled=not m.get('disabled',False),primary=bool(m.get('focused',index==0)),
            x=m.get('x',0),y=m.get('y',0),width=round(w/scale),height=round(h/scale),scale=scale,
            mode=current,rate=rate,rotation={0:'normal',1:'left',2:'inverted',3:'right'}.get(transform,'normal'),
            modes=[dict(name=k,rates=v) for k,v in modes.items()]))
    return rows


def display_command(plan,outputs):
    known={o['name']:o for o in outputs if o['connected']}
    if not plan or set(p['name'] for p in plan)!=set(known) or len(plan)!=len(known):raise ValueError('Las pantallas conectadas cambiaron. Vuelve a detectar.')
    if not any(p['enabled'] for p in plan):raise ValueError('Deja al menos una pantalla encendida.')
    parts=[]
    for p in sorted(plan,key=lambda p:not p['enabled']):
        current=known[p['name']];values=dict(output=p['name'])
        if not p['enabled']:values['disabled']=True
        else:
            modes={m['name']:m['rates'] for m in current['modes']}
            if p['mode'] not in modes or p['rate'] not in modes[p['mode']]:raise ValueError('Modo no disponible en '+p['name'])
            if p['rotation'] not in ('normal','left','right','inverted'):raise ValueError('Rotación inválida')
            x,y=int(p['x']),int(p['y']);scale=float(p.get('scale',current.get('scale',1)))
            if not (-32768<=x<=32768 and -32768<=y<=32768 and .25<=scale<=4):raise ValueError('Posición o escala inválida')
            values.update(mode=p['mode']+'@'+p['rate'],position=f'{x}x{y}',scale=scale,transform={'normal':0,'left':1,'inverted':2,'right':3}[p['rotation']])
        parts.append('hl.monitor('+lua(values)+')')
    preferred=next((p for p in plan if p.get('primary') and p['enabled']),None)
    if preferred:parts.append('hl.dispatch(hl.dsp.focus('+lua({'monitor':preferred['name']})+'))')
    return ['hyprctl','eval','; '.join(parts)]


MAPPING={'window_gap':('general','gaps_in'),'border_width':('general','border_size'),
         'focus_follows_pointer':('input','follow_mouse'),'pointer_follows_focus':('cursor','no_warps'),
         'split_ratio':('dwindle','default_split_ratio')}
COLOR_MAPPING={'focused_border_color':'active_border','normal_border_color':'inactive_border'}


def config(values):
    result={}
    for key,value in values.items():
        if key in MAPPING:
            section,name=MAPPING[key]
            if key=='focus_follows_pointer':value=1 if str(value)=='true' else 0
            elif key=='pointer_follows_focus':value=str(value)!='true'
            elif key=='split_ratio':value=float(value)*2
            else:value=int(value)
            result.setdefault(section,{})[name]=value
        elif key in COLOR_MAPPING:result.setdefault('general',{}).setdefault('col',{})[COLOR_MAPPING[key]]='rgb('+str(value).lstrip('#')+')'  # theme-exception: sintaxis de color de Hyprland
    return result


def script(values,rules):
    # Disable only handles created by the previous application of this fragment.
    lines=['-- Wysun managed settings; user compositor files are never rewritten.',
           'for _, rule in ipairs(wysun_window_rules or {}) do rule:set_enabled(false) end',
           'wysun_window_rules = {}','hl.config('+lua(config(values))+')']
    for index,rule in enumerate(rules):
        entry=dict(name='wysun-settings-'+str(index),match={'class':rule['class']},float=rule['state']=='floating',
                   fullscreen=rule['state']=='fullscreen',center=bool(rule.get('center')))
        if not rule.get('border',True):entry['border_size']=0
        if rule.get('desktop'):entry['workspace']=rule['desktop'].lstrip('^')
        lines.append('table.insert(wysun_window_rules, hl.window_rule('+lua(entry)+'))')
    return '\n'.join(lines)+'\n'


class HyprDesktopSettings:
    def __init__(self,home,runner):
        self.home=Path(home);self.runner=runner;self.path=config_dir(self.home)/'orbit/hypr-desktop.json';self.script=config_dir(self.home)/'orbit/hypr-settings.lua';self.reload()
    def reload(self):
        self.observed=self.path.read_text() if self.path.exists() else ''
        self.saved=json.loads(self.observed) if self.observed else {'values':{},'rules':[]}
        from settings_data import SCHEMA
        self.values={k:str(self.saved.get('values',{}).get(k,'true' if t[1]=='bool' else t[2][0] if t[1]=='enum' else '#7AA2F7' if t[1]=='color' else t[2])) for k,t in SCHEMA.items()}  # theme-exception: valor por defecto del compositor
        for key,(section,name) in MAPPING.items():
            try:
                value=option(self.runner,section+':'+name)
                if key=='window_gap' and isinstance(value,str):value=float(value.split()[0])
                if key=='split_ratio':value=float(value)/2
                if key=='focus_follows_pointer':value='true' if value else 'false'
                elif key=='pointer_follows_focus':value='false' if value else 'true'
                if key=='window_gap':value=int(value)
                if value is not None:self.values[key]=str(value)
            except Exception:pass
        for key,name in COLOR_MAPPING.items():
            try:
                value=str(option(self.runner,'general:col.'+name));match=re.search(r'(?:rgba?\(|0x)([0-9a-fA-F]{6})',value)
                if match:self.values[key]='#'+match[1]
            except Exception:pass
    def apply(self,values,rules):
        from settings_data import DesktopSettings,backup_file,atomic_write
        # Reuse the existing validation without constructing an X11 settings model.
        clean=DesktopSettings.validate(self,values,rules)
        if (self.path.read_text() if self.path.exists() else '')!=self.observed:raise ValueError('Los ajustes cambiaron. Recarga antes de guardar.')
        unsupported=[k for k,v in clean.items() if k not in MAPPING and k not in COLOR_MAPPING and v!=self.values.get(k)]
        if unsupported:raise ValueError('Ajustes exclusivos de BSPWM: '+', '.join(unsupported))
        # Only controls explicitly changed by this save become owned overrides.
        # Otherwise saving a rule/gap would silently replace live theme borders.
        overrides=dict(self.saved.get('overrides',self.saved.get('values',{})))
        overrides.update({key:value for key,value in clean.items() if value!=self.values.get(key) and (key in MAPPING or key in COLOR_MAPPING)})
        text=script(overrides,rules);old=self.script.read_text() if self.script.exists() else None
        rollback=old or ('for _, rule in ipairs(wysun_window_rules or {}) do rule:set_enabled(false) end\nwysun_window_rules = {}\nhl.config('+lua(snapshot_config(self.runner,config(overrides)))+')')
        apply_fragment(self.runner,{self.script:text,self.path:json.dumps({'values':clean,'overrides':overrides,'rules':rules},indent=2)+'\n'},text,rollback)
        self.reload()


class HyprShortcutFile:
    native=True
    def __init__(self,home=None,runner=None):
        from desktop_backend import run
        self.home=Path(home or Path.home());self.runner=runner or run
        self.path=config_dir(self.home)/'orbit/hypr-shortcuts.json';self.script=config_dir(self.home)/'orbit/hypr-shortcuts.lua'
        self.reload()
    def reload(self):
        self.original=self.path.read_text() if self.path.exists() else ''
        self.rows=json.loads(self.original) if self.original else [];self.lines=[];self.existing=[]
        try:
            for entry in json.loads(self.runner(['hyprctl','-j','binds'])):
                mods=[name for mask,name in ((64,'super'),(4,'ctrl'),(8,'alt'),(1,'shift')) if entry.get('modmask',0)&mask]
                if entry.get('key'):self.existing.append(' + '.join(mods+[entry['key']]))
        except Exception:pass
    def conflicts(self):
        from settings_data import canonical
        seen={}
        for i,row in enumerate(self.rows):seen.setdefault(canonical(row['key']),[]).append(i)
        return {k:v for k,v in seen.items() if len(v)>1}
    def validate(self,key,command,index=None):
        from settings_data import canonical,expand_sequence
        if not command.strip() or any(c in command for c in '\n\r\0'):raise ValueError('Escribe un comando de una línea')
        if len(expand_sequence(key))!=1:raise ValueError('Hyprland guarda una combinación por fila')
        parts=[p.strip() for p in key.split('+')]
        if not parts or any(p.lower() not in ('super','ctrl','control','alt','shift') for p in parts[:-1]) or not re.fullmatch(r'[A-Za-z0-9_]+',parts[-1]):raise ValueError('Combinación inválida')
        normalized=canonical(key)
        if any(i!=index and canonical(r['key'])==normalized for i,r in enumerate(self.rows)):raise ValueError('La combinación ya existe')
        owned={canonical(r['key']) for r in self.rows}
        if normalized not in owned and normalized in {canonical(k) for k in self.existing}:raise ValueError('El compositor ya usa esta combinación; conserva o edita su origen antes')
        import subprocess
        result=subprocess.run(['/bin/sh','-n','-c',command],capture_output=True,timeout=2)
        if result.returncode:raise ValueError('El comando tiene un error de sintaxis')
    def save(self,key,command,index=None,title=None):
        self.validate(key,command,index);rows=copy.deepcopy(self.rows)
        row=dict(key=key,command=command,title=title or key)
        if index is None:rows.append(row)
        else:rows[index]=row
        return self._write(rows)
    def delete(self,index):
        rows=copy.deepcopy(self.rows);del rows[index];return self._write(rows)
    def _write(self,rows):
        from settings_data import backup_file,atomic_write
        if (self.path.read_text() if self.path.exists() else '')!=self.original:raise ValueError('Los atajos cambiaron fuera de Ajustes. Recarga antes de guardar.')
        text=['-- Wysun managed custom bindings','for _, bind in ipairs(wysun_shortcut_handles or {}) do bind:remove() end','wysun_shortcut_handles = {}']
        for row in rows:
            chord=' + '.join({'super':'SUPER','ctrl':'CTRL','control':'CTRL','shift':'SHIFT','alt':'ALT'}.get(p.strip().lower(),p.strip()) for p in row['key'].split('+'))
            text.append('table.insert(wysun_shortcut_handles, hl.bind('+lua(chord)+', hl.dsp.exec_cmd('+lua(row['command'])+')))')
        script='\n'.join(text)+'\n';old_script=self.script.read_text() if self.script.exists() else None
        backup=backup_file(self.path,self.home/'.local/share/orbit/settings-backups')
        rollback=old_script or 'for _, bind in ipairs(wysun_shortcut_handles or {}) do bind:remove() end; wysun_shortcut_handles = {}'
        apply_fragment(self.runner,{self.script:script,self.path:json.dumps(rows,ensure_ascii=False,indent=2)+'\n'},script,rollback)
        self.reload();return backup


def effects_script(values):
    def integer(key,low,high):
        value=int(values[key])
        if not low<=value<=high:raise ValueError('Efecto fuera de rango: '+key)
        return value
    opacity=float(values['shadow-opacity'])
    if not 0<=opacity<=1:raise ValueError('Opacidad inválida')
    decoration=dict(rounding=integer('corner-radius',0,20),
        shadow=dict(enabled=bool(values['shadow']),range=integer('shadow-radius',0,40),color='rgba(000000'+f'{round(opacity*255):02x}'+')'),  # theme-exception: sintaxis de color de Hyprland
        blur=dict(enabled=bool(values['blur-background']),size=integer('blur-strength',1,8)))
    duration=integer('duration',50,600)/100
    text='hl.config('+lua({'decoration':decoration})+')\n'
    for leaf in ('windows','fade'):
        text+='hl.animation('+lua(dict(leaf=leaf,enabled=bool(values['fading']),speed=duration,bezier='default'))+')\n'
    return text


def effects_state(runner):
    values={'corner-radius':int(option(runner,'decoration:rounding')),'shadow':bool(option(runner,'decoration:shadow.enabled')),
        'shadow-radius':int(option(runner,'decoration:shadow.range')),'blur-background':bool(option(runner,'decoration:blur.enabled')),
        'blur-strength':int(option(runner,'decoration:blur.size')),'vsync':True}
    raw=str(option(runner,'decoration:shadow.color'));match=re.search(r'(?:rgba\()?([a-fA-F0-9]{8})',raw)
    values['shadow-opacity']=int(match[1][-2:],16)/255 if match else .25
    animations=json.loads(runner(['hyprctl','-j','animations']))[0]
    selected=[a for a in animations if a['name'] in ('windows','fade')]
    if len(selected)!=2:raise RuntimeError('No se pudieron respaldar las animaciones actuales')
    fade=next(a for a in selected if a['name']=='fade')
    values.update(duration=round(float(fade['speed'])*100),fading=bool(fade['enabled']))
    shape=dict(decoration=dict(rounding=0,shadow=dict(enabled=False,range=0,color=''),blur=dict(enabled=False,size=0)))
    rollback='hl.config('+lua(snapshot_config(runner,shape))+')\n'
    # Restore every descendant because a parent update propagates into inherited leaves.
    for entry in animations:
        if entry['name'] in ('windows','fade') or entry['name'].startswith(('windows','fade')):
            rollback+='hl.animation('+lua(dict(leaf=entry['name'],enabled=entry['enabled'],speed=entry['speed'],bezier=entry['bezier'],style=entry['style']))+')\n'
    return values,rollback
