"""Configuration of the programs that Wysun themes but does not draw.

The Wysun UI reads tokens live; this module only produces the files owned by
other programs (terminal, prompt, editor, GTK, borders) from the Material You
palette, and re-applies the border colours of the active scheme.
"""
import colorsys,json,re
from pathlib import Path
import theme_core
from environment_settings import set_values,run


def replace_block(text,block):
    text=re.sub(r'\n?# BEGIN ORBIT THEME\n.*?# END ORBIT THEME\n?', '',text,flags=re.S)
    return text.rstrip()+'\n\n# BEGIN ORBIT THEME\n'+block+'\n# END ORBIT THEME\n'


def editor_tint(value,tint):
    """Tint the editor's custom highlight colours towards the theme hue."""
    if not re.fullmatch(r'#[\da-fA-F]{6}',value):return value
    red,green,blue=[int(value[n:n+2],16)/255 for n in (1,3,5)]
    hue,light,saturation=colorsys.rgb_to_hls(red,green,blue)
    if .46<=hue<=.83 or saturation<.16:
        if light<.035 or (saturation<.02 and light>.95):return value
        rgb=colorsys.hls_to_rgb(tint['hue'],light,tint['saturation'])
        return '#'+''.join(f'{round(v*255):02x}' for v in rgb)
    return value


# Colours that the retired fixed themes (Space Black, Tokyo, Severance, Fluent) and older
# Settings versions saved into hypr-bar.json, so they are still told apart from user choices.
RETIRED_BAR_COLORS={'#101118','#EBECF3','#B8C8FA','#0C171C','#101012','#17131F','#1C2A3B','#202020','#2165D5','#76B4FF','#79C9DC','#BB9AF7','#CECED4','#D2E4E8','#E5DCFA','#E6E6E8','#F3F3F3','#F3F6FB'}  # theme-exception: valores de temas retirados; sirven para reconocer colores generados


def theme_colors():
    """Every theme-generated bar colour, to tell them apart from user choices."""
    return RETIRED_BAR_COLORS|{theme_core.styles()[style]['variants'][v]['external'][k].upper() for style in theme_core.styles() for v in theme_core.styles()[style]['variants'] for k in ('background','foreground','accent')}


def border_colors(theme):
    return {'active_border':'rgb('+theme['accent'][1:7]+')','inactive_border':'rgb('+theme['surface'][1:7]+')'}  # theme-exception: sintaxis de color de Hyprland


def theme_files(home,variant='dark'):
    """Files of the programs themed from the Material You palette, as {path: text}.

    ``variant`` picks the base palette (``light`` or ``dark``); the installer stages
    these before any wallpaper scheme exists, so they come from the shipped palette.
    """
    from hypr_settings import config_dir,lua
    style,variant=theme_core.normalize(None,variant)
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
    # The bundled GTK themes are dark: only the dark palette redefines window colours.
    gtk={'accent_color':theme['accent'],'accent_bg_color':theme['accent'],'accent_fg_color':theme['background']}
    if theme.get('gtk_dark',True):gtk={'theme_bg_color':theme['background'],'theme_fg_color':theme['foreground'],'theme_selected_bg_color':theme['accent'],'theme_selected_fg_color':theme['background'],**gtk}
    for relative in ('.config/gtk-3.0/gtk.css','.config/gtk-4.0/gtk.css'):
        path=config/relative.removeprefix('.config/');text=path.read_text() if path.exists() else ''
        text=re.sub(r'/\* BEGIN ORBIT THEME \*/.*?/\* END ORBIT THEME \*/\n?','',text,flags=re.S)
        files[path]=text.rstrip()+'\n/* BEGIN ORBIT THEME */\n'+''.join(f'@define-color {name} {value};\n' for name,value in gtk.items())+'/* END ORBIT THEME */\n'
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
    files[native/'hypr-theme.lua']='-- Wysun theme colors\nhl.config('+lua({'general':{'col':border_colors(theme)}})+')\n'
    return files


def restore_theme(home=None,runner=run):
    """Paint the compositor borders with the active scheme (the compositor forgets them on restart)."""
    from hypr_settings import lua
    values=theme_core.resolve_active(home=home)
    runner(['hyprctl','eval','hl.config('+lua({'general':{'col':border_colors(values)}})+')'])
