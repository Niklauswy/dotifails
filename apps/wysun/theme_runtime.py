"""Backed-up, reversible theme application for Wysun/Hyprland.

The Wysun UI reads tokens live; this module only updates files owned by other
programs (terminal, prompt, editor, notifications, GTK, borders, wallpaper)
and the persisted selection.
"""
import colorsys,datetime,json,re
from pathlib import Path
import theme_core
from theme_tokens import invalidate
from settings_data import atomic_write
from environment_settings import set_ini,set_values,display_inventory,render_wallpaper,run


def replace_block(text,block):
    text=re.sub(r'\n?# BEGIN ORBIT THEME\n.*?# END ORBIT THEME\n?', '',text,flags=re.S)
    return text.rstrip()+'\n\n# BEGIN ORBIT THEME\n'+block+'\n# END ORBIT THEME\n'


def selection(key):
    """'tokyo', 'fluent:dark', aliases... -> (style, variant); ValueError if unknown."""
    if isinstance(key,(tuple,list)) and len(key)==2:parsed=theme_core.normalize(*key) if key[0] in theme_core.styles() else None
    else:parsed=theme_core.parse(key)
    if not parsed:raise ValueError('Elige un tema disponible.')
    return parsed


def editor_tint(value,tint):
    """Space Black variants keep tinting the editor's custom highlight colours."""
    if not re.fullmatch(r'#[\da-fA-F]{6}',value):return value
    red,green,blue=[int(value[n:n+2],16)/255 for n in (1,3,5)]
    hue,light,saturation=colorsys.rgb_to_hls(red,green,blue)
    if .46<=hue<=.83 or saturation<.16:
        if light<.035 or (saturation<.02 and light>.95):return value
        rgb=colorsys.hls_to_rgb(tint['hue'],light,tint['saturation'])
        return '#'+''.join(f'{round(v*255):02x}' for v in rgb)
    return value


def theme_colors():
    """Every theme-generated bar colour, to tell them apart from user choices.
    Includes the fixed defaults that older Settings versions always saved."""
    return {'#101118','#EBECF3','#B8C8FA'}|{style['variants'][v]['external'][k].upper() for style in theme_core.styles().values() for v in style['variants'] for k in ('background','foreground','accent')}  # theme-exception: valores antiguos que Ajustes guardaba siempre; sirven para reconocer colores generados


def theme_files(home,key):
    from hypr_settings import config_dir
    style,variant=selection(key)
    home=Path(home);values=theme_core.resolve(style,variant);theme=values['external'];config=config_dir(home);files={}
    def put(relative,transform):
        path=config/relative.removeprefix('.config/') if relative.startswith('.config/') else home/relative
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
        preset=theme['nvim']
        text=re.sub(r'(\btheme\s*=\s*)[\"\'][^\"\']+[\"\']',lambda m:m[1]+'"'+preset+'"',text,count=1)
        text=re.sub(r'(theme_toggle\s*=\s*\{\s*)[\"\'][^\"\']+[\"\']',lambda m:m[1]+'"'+preset+'"',text,count=1)
        if 'editor_tint' not in theme:return text
        return re.sub(r'#[\da-fA-F]{6}(?![\da-fA-F])',lambda m:editor_tint(m[0],theme['editor_tint']),text)
    put('.config/nvim/lua/chadrc.lua',editor)
    def notices(text):
        # Dunst treats unquoted # as a comment and silently falls back to blue.
        quoted=lambda value:'"'+value+'"';colours=theme['notices']
        text=set_ini(text,'global',{'frame_color':quoted(colours['frame']),'highlight':quoted(colours['highlight']),'transparency':10,'corner_radius':16,'frame_width':1})
        for section in ('urgency_low','urgency_normal','urgency_critical'):text=set_ini(text,section,{'background':quoted(colours['background']),'foreground':quoted(colours['foreground']),'frame_color':quoted(colours['frame'])})
        return re.sub(r'\n{3,}','\n\n',text)
    dunst=config/'wysun/dunstrc'
    if dunst.is_file():files[dunst]=notices(dunst.read_text())
    # The bundled GTK themes are dark: only dark variants redefine window colours.
    gtk={'accent_color':theme['accent'],'accent_bg_color':theme['accent'],'accent_fg_color':theme['background']}
    if theme.get('gtk_dark',True):gtk={'theme_bg_color':theme['background'],'theme_fg_color':theme['foreground'],'theme_selected_bg_color':theme['accent'],'theme_selected_fg_color':theme['background'],**gtk}
    for relative in ('.config/gtk-3.0/gtk.css','.config/gtk-4.0/gtk.css'):
        path=config/relative.removeprefix('.config/');text=path.read_text() if path.exists() else ''
        text=re.sub(r'/\* BEGIN ORBIT THEME \*/.*?/\* END ORBIT THEME \*/\n?','',text,flags=re.S)
        files[path]=text.rstrip()+'\n/* BEGIN ORBIT THEME */\n'+''.join(f'@define-color {name} {value};\n' for name,value in gtk.items())+'/* END ORBIT THEME */\n'
    files[config/'orbit/theme.json']=theme_core.serialize(style,variant)
    from wysun_scheme import fixed_scheme
    files[theme_core.scheme_path(home)]=json.dumps(fixed_scheme(style,variant),ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    from hypr_settings import lua
    native=config/'orbit'
    bar_path=native/'hypr-bar.json'
    if bar_path.is_file():
        # Older versions stored the theme's colours here; drop them so the bar
        # follows the theme. Colours chosen by the user are kept.
        try:bar=json.loads(bar_path.read_text())
        except ValueError:bar=None
        if isinstance(bar,dict):
            generated=theme_colors()
            cleaned={k:v for k,v in bar.items() if not (k in ('background','foreground','accent') and str(v).upper() in generated)}
            if cleaned!=bar:files[bar_path]=json.dumps(cleaned,ensure_ascii=False,indent=2)+'\n'
    files[native/'hypr-theme.lua']='-- Wysun theme colors\nhl.config('+lua({'general':{'col':{'active_border':'rgb('+theme['accent'][1:]+')','inactive_border':'rgb('+theme['surface'][1:]+')'}}})+')\n'  # theme-exception: sintaxis de color de Hyprland
    borders={'focused_border_color':theme['accent'],'normal_border_color':theme['surface']}
    return files,borders


def apply_theme(home,key,runner=run):
    style,variant=selection(key)
    home=Path(home);values=theme_core.resolve(style,variant);wallpaper=home/'.local/share/backgrounds'/values['wallpaper']
    if not wallpaper.is_file():raise ValueError('No se encontró el fondo de '+values['name'])
    files,borders=theme_files(home,(style,variant))
    from hypr_settings import config_dir,lua,option,evaluate
    config=config_dir(home)
    envpath=config/'orbit/environment.json';environment=json.loads(envpath.read_text()) if envpath.exists() else {}
    environment.setdefault('wallpaper',{}).update(default=str(wallpaper),mode='fill',monitors={})
    files[envpath]=json.dumps(environment,indent=2)+'\n'
    backup=home/'.local/state/orbit/theme-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup.mkdir(parents=True,mode=0o700)
    originals={path:path.read_bytes() if path.exists() else None for path in files}
    def backup_relative(path):
        if path.is_relative_to(home):return path.relative_to(home)
        if path.is_relative_to(config):return Path('xdg-config')/path.relative_to(config)
        state=theme_core.state_root(home)
        if path.is_relative_to(state):return Path('xdg-state')/path.relative_to(state)
        raise ValueError('Ruta de tema fuera de HOME/XDG_CONFIG_HOME')
    for path,data in originals.items():
        if data is not None:
            dest=backup/backup_relative(path);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    atomic_write(backup/'changed.json',json.dumps({'theme':theme_core.key(style,variant),'paths':[str(backup_relative(path)) for path in files]},indent=2)+'\n')
    native_script=next((path for path in files if path.name=='hypr-theme.lua'),None)
    previous={}
    for name in ('active_border','inactive_border'):
        value=option(runner,'general:col.'+name)
        if not isinstance(value,str):raise RuntimeError('No se pudo respaldar el color de borde actual')
        previous[name]=value
    old_native='hl.config('+lua({'general':{'col':previous}})+')'
    def write_file(path,text):
        if path==theme_core.scheme_path(home):theme_core._atomic_write(path,text)
        else:atomic_write(path,text,0o600 if path.name=='theme.json' else None)
    try:
        for path,text in files.items():write_file(path,text)
        if (config/'ghostty/config').exists():runner(['ghostty','+validate-config'])
        evaluate(runner,files[native_script])
        render_wallpaper(environment['wallpaper'],display_inventory(runner),home,runner)
    except Exception:
        for path,data in originals.items():
            if data is None:path.unlink(missing_ok=True)
            else:write_file(path,data.decode())
        try:evaluate(runner,old_native)
        except Exception:pass
        invalidate();raise
    invalidate();warnings=[]
    commands=[['wysun','shell','reload-preferences'],['dunstctl','reload'],['gdbus','call','--session','--dest','com.mitchellh.ghostty','--object-path','/com/mitchellh/ghostty','--method','org.gtk.Actions.Activate','reload-config','[]','{}']]
    for command in commands:
        try:runner(command)
        except Exception:warnings.append(command[0])
    return {'theme':theme_core.key(style,variant),'style':style,'variant':variant,'name':values['style_name']+(' · '+values['name'] if values['name']!=values['style_name'] else ''),'backup':str(backup),'warnings':warnings}


def restore_theme(home=None,runner=run):
    theme=theme_core.resolve(*theme_core.selection(home))['external']
    from hypr_settings import lua
    runner(['hyprctl','eval','hl.config('+lua({'general':{'col':{'active_border':'rgb('+theme['accent'][1:]+')','inactive_border':'rgb('+theme['surface'][1:]+')'}}})+')'])  # theme-exception: sintaxis de color de Hyprland
