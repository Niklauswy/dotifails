"""Lossless Hyprland shortcut edits and bounded compositor settings."""
import datetime, itertools, json, os, re, shutil, subprocess, tempfile
from pathlib import Path

HOME=Path.home()
SCHEMA={
 'window_gap':('Separación entre ventanas','int',0,80),
 'border_width':('Grosor del borde','int',0,12),
 'focused_border_color':('Borde de la ventana activa','color',None,None),
 'normal_border_color':('Borde de las demás ventanas','color',None,None),
 'split_ratio':('Proporción al dividir','float',.1,.9),
 'focus_follows_pointer':('Enfocar al pasar el puntero','bool',None,None),
 'pointer_follows_focus':('Mover el puntero con el foco','bool',None,None),
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
    """Compatibility facade returning the Hyprland binding model."""
    def __new__(cls,home=None,runner=None):
        from hypr_settings import HyprShortcutFile
        return HyprShortcutFile(home,runner)


class DesktopSettings:
    """Compatibility facade returning the Hyprland desktop settings model."""
    def __new__(cls,home=None,runner=checked):
        from hypr_settings import HyprDesktopSettings
        return HyprDesktopSettings(Path(home or HOME),runner)

    @staticmethod
    def validate(model,values,rules):
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


def reload_shortcuts():
    """Hyprland applies managed binds through hyprctl eval; no daemon signal needed."""
