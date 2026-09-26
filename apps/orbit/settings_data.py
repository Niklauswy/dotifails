"""Lossless shortcut edits and bounded BSPWM settings, with backups."""
import ctypes, ctypes.util, datetime, itertools, json, os, re, shlex, shutil, subprocess, tempfile
from pathlib import Path

HOME=Path.home()
SCHEMA={
 'window_gap':('Separación entre ventanas','int',0,80),
 'border_width':('Grosor del borde','int',0,12),
 'top_padding':('Margen superior','int',0,160),
 'bottom_padding':('Margen inferior','int',0,160),
 'left_padding':('Margen izquierdo','int',0,160),
 'right_padding':('Margen derecho','int',0,160),
 'focused_border_color':('Borde de la ventana activa','color',None,None),
 'normal_border_color':('Borde de las demás ventanas','color',None,None),
 'active_border_color':('Borde activo en otro monitor','color',None,None),
 'presel_feedback_color':('Color de preselección','color',None,None),
 'split_ratio':('Proporción al dividir','float',.1,.9),
 'focus_follows_pointer':('Enfocar al pasar el puntero','bool',None,None),
 'pointer_follows_focus':('Mover el puntero con el foco','bool',None,None),
 'pointer_follows_monitor':('Mover el puntero al cambiar de monitor','bool',None,None),
 'borderless_monocle':('Ocultar bordes en monóculo','bool',None,None),
 'gapless_monocle':('Sin separación en monóculo','bool',None,None),
 'paddingless_monocle':('Sin márgenes en monóculo','bool',None,None),
 'single_monocle':('Monóculo con una sola ventana','bool',None,None),
 'automatic_scheme':('Colocación de ventanas','enum',['longest_side','alternate','spiral'],None),
 'initial_polarity':('Posición inicial','enum',['first_child','second_child'],None),
 'pointer_modifier':('Tecla para mover con el ratón','enum',['mod4','mod1','control','shift'],None),
}

def checked(args):
    return subprocess.run(args,text=True,capture_output=True,timeout=4,check=True).stdout.strip()

def atomic_write(path,text,mode=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        os.fchmod(fd,mode or (path.stat().st_mode&0o777 if path.exists() else 0o600))
        with os.fdopen(fd,'w') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()

def backup_file(path,root=None):
    root=Path(root or HOME/'.local/share/orbit/settings-backups');root.mkdir(parents=True,exist_ok=True,mode=0o700)
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');dest=root/(stamp+'-'+Path(path).name)
    if Path(path).exists():shutil.copy2(path,dest);dest.chmod(0o600)
    return dest

def expand_sequence(text):
    match=re.search(r'(?<!\\)\{([^{}]*)\}',text)
    if not match:
        if re.search(r'(?<!\\)[{}]',text):raise ValueError('Llaves incompletas o anidadas.')
        return [text.replace(r'\{','{').replace(r'\}','}')]
    choices=[]
    for part in match[1].split(','):
        if re.fullmatch('[A-Za-z0-9]-[A-Za-z0-9]',part):
            start,end=ord(part[0]),ord(part[-1]);choices.extend(chr(i) for i in range(start,end+1))
        else:choices.append('' if part=='_' else part)
    tails=expand_sequence(text[match.end():]);rows=[text[:match.start()]+p+t for p,t in itertools.product(choices,tails)]
    if len(rows)>1000:raise ValueError('Demasiadas combinaciones.')
    return rows

def canonical(hotkey):
    aliases={'ctrl':'control','super':'mod4','alt':'mod1'};chords=[]
    for chord in re.split('[;:]',hotkey):
        parts=[x.strip() for x in chord.split('+')];chords.append('+'.join(sorted(aliases.get(x,x) for x in parts[:-1]))+'+'+parts[-1])
    return ';'.join(chords)

class ShortcutFile:
    def __init__(self,path=None):
        self.path=Path(path or HOME/'.config/sxhkd/sxhkdrc');self.reload()
    def reload(self):
        self.original=self.path.read_text();self.lines=self.original.splitlines(keepends=True);self.rows=[];i=0;comment=''
        while i<len(self.lines):
            line=self.lines[i]
            if line.startswith('#'):comment=line.lstrip('# ').strip();i+=1;continue
            if not line.strip() or line[0].isspace():i+=1;continue
            start=i;hot=line.strip();i+=1
            while hot.endswith('\\') and i<len(self.lines):hot=hot[:-1]+self.lines[i].strip();i+=1
            body=[]
            while i<len(self.lines) and self.lines[i][:1].isspace() and self.lines[i].strip():body.append(self.lines[i].strip());i+=1
            command='\n'.join(body);command=re.sub(r'\\\n\s*',' ',command)
            self.rows.append(dict(start=start,end=i,key=hot,command=command,title=comment or hot));comment=''
    def conflicts(self):
        seen={}
        for index,row in enumerate(self.rows):
            try:keys=expand_sequence(row['key'])
            except ValueError:continue
            for key in keys:seen.setdefault(canonical(key),[]).append(index)
        return {key:ids for key,ids in seen.items() if len(ids)>1}
    def validate(self,key,command,index=None):
        if not key.strip() or '\n' in key or not command.strip():raise ValueError('Escribe una combinación y un comando.')
        if '\n' in command:raise ValueError('Usa una sola línea; puedes separar comandos con punto y coma.')
        keys=expand_sequence(key);commands=expand_sequence(command)
        if len(commands) not in (1,len(keys)):raise ValueError('La cantidad de comandos no coincide con las combinaciones.')
        lib=ctypes.CDLL(ctypes.util.find_library('X11'));lib.XStringToKeysym.argtypes=[ctypes.c_char_p];lib.XStringToKeysym.restype=ctypes.c_ulong
        modifiers={'super','hyper','meta','alt','control','ctrl','shift','mode_switch','lock','mod1','mod2','mod3','mod4','mod5','any'}
        normalized=[]
        for value in keys:
            for chord in re.split('[;:]',value):
                parts=[p.strip() for p in chord.split('+')]
                if any(p not in modifiers for p in parts[:-1]):raise ValueError('Modificador desconocido.')
                name=parts[-1].lstrip('~@')
                if not lib.XStringToKeysym(name.encode()) and not re.fullmatch(r'button(?:[1-9]|1\d|2[0-4])',name):raise ValueError('Tecla desconocida: '+name)
            normalized.append(canonical(value))
        if len(set(normalized))!=len(normalized):raise ValueError('La combinación se repite dentro del grupo.')
        for i,row in enumerate(self.rows):
            if i==index:continue
            if set(normalized)&set(map(canonical,expand_sequence(row['key']))):raise ValueError('Ya existe una combinación igual: '+row['key'])
        shell=os.environ.get('SXHKD_SHELL') or os.environ.get('SHELL') or '/bin/sh'
        for cmd in commands:
            result=subprocess.run([shell,'-n','-c',cmd.lstrip(';')],capture_output=True,timeout=2)
            if result.returncode:raise ValueError('El comando tiene un error de sintaxis.')
    def save(self,key,command,index=None,title=None):
        self.validate(key,command,index)
        if self.path.read_text()!=self.original:raise ValueError('El archivo cambió fuera de Ajustes. Recarga antes de guardar.')
        replacement=key.strip()+'\n    '+command.strip()+'\n'
        lines=self.lines.copy()
        if index is None:lines+=['\n# '+(title or 'Atajo personalizado').replace('\n',' ')+'\n',replacement]
        else:
            row=self.rows[index]
            if title and title!=row['title']:
                previous=row['start']-1
                while previous>=0 and not lines[previous].strip():previous-=1
                if previous>=0 and lines[previous].startswith('#'):lines[previous]='# '+title.replace('\n',' ')+'\n'
                else:replacement='# '+title.replace('\n',' ')+'\n'+replacement
            lines[row['start']:row['end']]=[replacement]
        backup=backup_file(self.path);atomic_write(self.path,''.join(lines));self.reload();return backup
    def delete(self,index):
        if self.path.read_text()!=self.original:raise ValueError('El archivo cambió fuera de Ajustes. Recarga antes de guardar.')
        row=self.rows[index];lines=self.lines.copy();del lines[row['start']:row['end']];backup=backup_file(self.path);atomic_write(self.path,''.join(lines));self.reload();return backup

class DesktopSettings:
    def __init__(self,home=None,runner=checked):
        self.home=Path(home or HOME);self.runner=runner;self.path=self.home/'.config/orbit/desktop.json';self.script=self.home/'.config/orbit/bspwm-settings.sh';self.reload()
    def reload(self):
        self.observed=self.path.read_text() if self.path.exists() else ''
        self.saved=json.loads(self.observed) if self.observed else {'values':{},'rules':[]}
        self.values={}
        for key in SCHEMA:
            try:self.values[key]=self.runner(['bspc','config',key])
            except (OSError,subprocess.SubprocessError):self.values[key]=str(self.saved.get('values',{}).get(key,''))
    def validate(self,values,rules):
        clean={}
        for key,value in values.items():
            if key not in SCHEMA:raise ValueError('Ajuste desconocido.')
            title,kind,low,high=SCHEMA[key];value=str(value)
            if kind in ('int','float'):
                number=int(value) if kind=='int' else float(value)
                if not low<=number<=high:raise ValueError(title+': valor fuera de rango.')
                value=str(number)
            elif kind=='bool' and value not in ('true','false'):raise ValueError(title+': valor inválido.')
            elif kind=='color' and not re.fullmatch(r'#[0-9a-fA-F]{6}',value):raise ValueError(title+': usa #RRGGBB.')
            elif kind=='enum' and value not in low:raise ValueError(title+': opción inválida.')
            clean[key]=value
        for rule in rules:
            if not re.fullmatch(r'[A-Za-z0-9_.*:-]{1,120}',rule['class']):raise ValueError('La clase de la ventana no es válida.')
            if rule['state'] not in ('tiled','floating','fullscreen'):raise ValueError('Estado de ventana inválido.')
            if rule.get('desktop') and not re.fullmatch(r'[A-Za-z0-9_^.-]{1,40}',rule['desktop']):raise ValueError('Escritorio no válido.')
        if len({r['class'] for r in rules})!=len(rules):raise ValueError('Hay reglas repetidas para la misma clase.')
        return clean
    @staticmethod
    def rule_args(rule):
        return ['bspc','rule','-a',rule['class'],'state='+rule['state'],'center='+('true' if rule.get('center') else 'false'),'border='+('on' if rule.get('border',True) else 'off')]+(['desktop='+rule['desktop']] if rule.get('desktop') else [])
    def apply(self,values,rules):
        values=self.validate(values,rules)
        if (self.path.read_text() if self.path.exists() else '')!=self.observed:raise ValueError('Los ajustes cambiaron en otra ventana. Recarga primero.')
        old={k:self.runner(['bspc','config',k]) for k in values};applied=[]
        oldrules=self.saved.get('rules',[])
        old_script=self.script.read_text() if self.script.exists() else None
        old_json=self.path.read_text() if self.path.exists() else None
        try:
            for key,value in values.items():self.runner(['bspc','config',key,value]);applied.append(key)
            for rule in oldrules:self.runner(['bspc','rule','-r',rule['class']])
            for rule in rules:self.runner(self.rule_args(rule))
            if self.path.exists():backup_file(self.path)
            else:
                backup_root=self.home/'.local/share/orbit/settings-backups';backup_root.mkdir(parents=True,exist_ok=True,mode=0o700)
                baseline=backup_root/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'-desktop.json')
                atomic_write(baseline,json.dumps({'values':old,'rules':oldrules},indent=2)+'\n')
            backup_file(self.script)
            lines=['#!/bin/sh','# Gestionado por Órbita Ajustes.\n']
            lines += [shlex.join(['bspc','config',key,value]) for key,value in values.items()]
            lines += [shlex.join(self.rule_args(rule)) for rule in rules]
            atomic_write(self.script,'\n'.join(lines)+'\n',0o600)
            atomic_write(self.path,json.dumps({'values':values,'rules':rules},indent=2)+'\n')
        except Exception:
            for key in applied:
                try:self.runner(['bspc','config',key,old[key]])
                except Exception:pass
            for rule in rules:
                try:self.runner(['bspc','rule','-r',rule['class']])
                except Exception:pass
            for rule in oldrules:
                try:self.runner(self.rule_args(rule))
                except Exception:pass
            for path,content in ((self.script,old_script),(self.path,old_json)):
                try:
                    if content is None:path.unlink(missing_ok=True)
                    else:atomic_write(path,content)
                except OSError:pass
            raise
        self.reload()
