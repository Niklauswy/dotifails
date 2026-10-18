"""Backed-up, reversible theme application without replacing user configuration."""
import copy,datetime,json,os,re,shlex,shutil,socket
from pathlib import Path
from theme_tokens import THEMES,normalize,invalidate
from settings_data import atomic_write
from environment_settings import set_ini,set_values,display_inventory,render_wallpaper,ROOT,run


def replace_block(text,block):
    text=re.sub(r'\n?# BEGIN ORBIT THEME\n.*?# END ORBIT THEME\n?', '',text,flags=re.S)
    return text.rstrip()+'\n\n# BEGIN ORBIT THEME\n'+block+'\n# END ORBIT THEME\n'


def theme_files(home,key):
    home=Path(home);theme=THEMES[key];config=home/'.config';files={}
    def put(relative,transform):
        path=home/relative
        if path.is_file():files[path]=transform(path.read_text())
    def terminal(text):
        text=re.sub(r'^\s*(palette|cursor-color|cursor-text|selection-background|selection-foreground)\s*=.*\n?','',text,flags=re.M)
        text=set_values(text,{'background':theme['background'][1:],'foreground':theme['foreground'][1:]})
        return text.rstrip()+'\n\ncursor-color = '+theme['accent'][1:]+'\nselection-background = '+theme['accent'][1:]+'\nselection-foreground = '+theme['background'][1:]+'\n'+''.join(f'palette = {i}={colour}\n' for i,colour in enumerate(theme['palette']))
    put('.config/ghostty/config',terminal)
    def starship(text):
        text=re.sub(r'^palette\s*=.*\n?','',text,flags=re.M)
        text=re.sub(r'\n\[palettes\.orbit\]\n.*?(?=\n\[|\Z)','',text,flags=re.S)
        palette=dict(black=theme['background'],white=theme['foreground'],green=theme['accent'],blue=theme['palette'][4],purple=theme['palette'][5],cyan=theme['accent'],yellow=theme['palette'][3],red=theme['palette'][1])
        return "palette = 'orbit'\n"+text.rstrip()+'\n\n[palettes.orbit]\n'+''.join(f"{name} = '{value}'\n" for name,value in palette.items())
    put('.config/starship.toml',starship)
    def editor(text):
        if 'M.base46' not in text:return text
        from theme_tokens import theme_color
        preset={'tokyo':'tokyonight','severance':'nord','space-black':'github_dark'}[key]
        text=re.sub(r'(\btheme\s*=\s*)[\"\'][^\"\']+[\"\']',lambda m:m[1]+'"'+preset+'"',text,count=1)
        text=re.sub(r'(theme_toggle\s*=\s*\{\s*)[\"\'][^\"\']+[\"\']',lambda m:m[1]+'"'+preset+'"',text,count=1)
        return re.sub(r'#[\da-fA-F]{6}(?![\da-fA-F])',lambda m:theme_color(m[0],key),text)
    put('.config/nvim/lua/chadrc.lua',editor)
    put('.config/bspwm/polybar/config',lambda text:set_ini(set_ini(text,'colors',{'bg':'#BD'+theme['background'][1:],'fg':theme['foreground'],'muted':theme['muted'],'accent':theme['accent']}),'bar/base',{'border-color':'#55'+theme['accent'][1:]}))
    def notices(text):
        # Dunst treats unquoted # as a comment and silently falls back to blue.
        quoted=lambda value:'"'+value+'"'
        text=set_ini(text,'global',{'frame_color':quoted('#676970'),'highlight':quoted('#c9cbd1'),'transparency':10,'corner_radius':16,'frame_width':1})
        for section in ('urgency_low','urgency_normal','urgency_critical'):text=set_ini(text,section,{'background':quoted('#18191d'),'foreground':quoted('#eeeef0'),'frame_color':quoted('#676970')})
        text=re.sub(r'\n{3,}','\n\n',text)
        return text
    put('.config/bspwm/dunstrc',notices)
    for relative in ('.config/gtk-3.0/gtk.css','.config/gtk-4.0/gtk.css'):
        path=home/relative;text=path.read_text() if path.exists() else ''
        text=re.sub(r'/\* BEGIN ORBIT THEME \*/.*?/\* END ORBIT THEME \*/\n?','',text,flags=re.S)
        files[path]=text.rstrip()+'\n/* BEGIN ORBIT THEME */\n'+''.join(f'@define-color {name} {value};\n' for name,value in {'theme_bg_color':theme['background'],'theme_fg_color':theme['foreground'],'theme_selected_bg_color':theme['accent'],'theme_selected_fg_color':theme['background'],'accent_color':theme['accent'],'accent_bg_color':theme['accent'],'accent_fg_color':theme['background']}.items())+'/* END ORBIT THEME */\n'
    colours=''.join(f'*.{name}: {value}\n' for name,value in {'background':theme['background'],'foreground':theme['foreground'],'cursorColor':theme['accent'],**{f'color{i}':value for i,value in enumerate(theme['palette'])}}.items())
    path=home/'.Xresources.d/colors';files[path]=colours
    # Preserve user effects and per-window exceptions; change only global timing.
    put('.config/bspwm/picom.conf',lambda text:re.sub(r'(duration\s*=\s*)[\d.]+',lambda m:m[1]+str(theme['enter']/1000),text))
    path=config/'orbit/desktop.json';desktop=json.loads(path.read_text()) if path.exists() else {'values':{},'rules':[]}
    borders={'focused_border_color':theme['accent'],'normal_border_color':theme['surface'],'active_border_color':theme['muted'],'presel_feedback_color':theme['accent']}
    desktop.setdefault('values',{}).update(borders);files[path]=json.dumps(desktop,indent=2)+'\n'
    script=config/'orbit/bspwm-settings.sh';text=script.read_text() if script.exists() else '#!/bin/sh\n'
    for name,value in borders.items():
        text=re.sub(r'^bspc config '+name+r' .*$','',text,flags=re.M)
        text+='\n'+shlex.join(['bspc','config',name,value])
    files[script]=text.rstrip()+'\n'
    files[config/'orbit/theme.json']=json.dumps({'id':key,'name':theme['name']},indent=2)+'\n'
    legacy=config/'dotifails/theme.json';previous=json.loads(legacy.read_text()) if legacy.exists() else {};previous.update(name=key,wallpaper=theme['wallpaper']);files[legacy]=json.dumps(previous,indent=2)+'\n'
    return files,borders


def apply_theme(home,key,runner=run):
    if key not in THEMES:raise ValueError('Elige un tema disponible.')
    home=Path(home);theme=THEMES[key];wallpaper=home/'.local/share/backgrounds'/theme['wallpaper']
    if not wallpaper.is_file():raise ValueError('No se encontró el fondo de '+theme['name'])
    files,borders=theme_files(home,key)
    envpath=home/'.config/orbit/environment.json';environment=json.loads(envpath.read_text()) if envpath.exists() else {}
    environment.setdefault('wallpaper',{}).update(default=str(wallpaper),mode='fill',monitors={})
    files[envpath]=json.dumps(environment,indent=2)+'\n'
    backup=home/'.local/state/orbit/theme-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup.mkdir(parents=True,mode=0o700)
    originals={path:path.read_bytes() if path.exists() else None for path in files}
    for path,data in originals.items():
        if data is not None:
            dest=backup/path.relative_to(home);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    atomic_write(backup/'changed.json',json.dumps({'theme':key,'paths':[str(path.relative_to(home)) for path in files]},indent=2)+'\n')
    old_borders={key:runner(['bspc','config',key]).strip() for key in borders}
    try:
        for path,text in files.items():atomic_write(path,text)
        if (home/'.config/ghostty/config').exists():runner(['ghostty','+validate-config'])
        for name,value in borders.items():runner(['bspc','config',name,value])
        render_wallpaper(environment['wallpaper'],display_inventory(runner),home,runner)
    except Exception:
        for path,data in originals.items():
            if data is None:path.unlink(missing_ok=True)
            else:atomic_write(path,data.decode())
        for name,value in old_borders.items():
            try:runner(['bspc','config',name,value])
            except Exception:pass
        invalidate();raise
    invalidate();warnings=[]
    commands=[['xrdb','-merge',str(home/'.Xresources.d/colors')],['dunstctl','reload',str(home/'.config/bspwm/dunstrc')],[str(ROOT/'desktop-bar')],['gdbus','call','--session','--dest','com.mitchellh.ghostty','--object-path','/com/mitchellh/ghostty','--method','org.gtk.Actions.Activate','reload-config','[]','{}']]
    for command in commands:
        try:runner(command)
        except Exception:warnings.append(command[0])
    # Reuse the managed compositor wrapper; do not restart the desktop session.
    compositor=home/'.local/bin/desktop-compositor'
    if compositor.exists():
        try:
            runner(['pkill','-TERM','-u',str(os.getuid()),'-x','picom'])
            import time;time.sleep(.15);runner([str(compositor)])
        except Exception:warnings.append('picom')
    return {'theme':key,'backup':str(backup),'warnings':warnings}


def restore_theme(home=None,runner=run):
    from theme_tokens import theme_id
    theme=THEMES[theme_id(home)]
    for key,value in {'focused_border_color':theme['accent'],'normal_border_color':theme['surface'],'active_border_color':theme['muted'],'presel_feedback_color':theme['accent']}.items():runner(['bspc','config',key,value])
