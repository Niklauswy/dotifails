"""Configuration of the programs that Wysun themes but does not draw.

The Wysun UI reads tokens live; this module only produces the files owned by
other programs (terminal, prompt, editor, GTK, borders) from the Material You
palette, and re-applies the border colours of the active scheme.
"""
import colorsys,json,re
from pathlib import Path
from wysun_core.theme import resolve, resolve_active
from wysun_settings.environment import set_values,run


def replace_block(text,block):
    text=re.sub(r'\n?# BEGIN WYSUN THEME\n.*?# END WYSUN THEME\n?', '',text,flags=re.S)
    return text.rstrip()+'\n\n# BEGIN WYSUN THEME\n'+block+'\n# END WYSUN THEME\n'


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


def theme_colors():
    """Every bar colour the base palettes generate, to tell them apart from user choices."""
    return {resolve(mode)['external'][key].upper() for mode in ('light','dark') for key in ('background','foreground','accent')}


def border_colors(theme):
    return {'active_border':'rgb('+theme['accent'][1:7]+')','inactive_border':'rgb('+theme['surface'][1:7]+')'}  # theme-exception: sintaxis de color de Hyprland


def theme_files(home,mode='dark'):
    """Files of the programs themed from the Material You palette, as {path: text}.

    ``mode`` picks the base palette (``light`` or ``dark``); the installer stages
    these before any wallpaper scheme exists, so they come from the shipped palette.
    """
    from wysun_settings.hypr import config_dir,lua
    home=Path(home);values=resolve(mode);theme=values['external'];config=config_dir(home);files={}
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
        text=re.sub(r'\n\[palettes\.wysun\]\n.*?(?=\n\[|\Z)','',text,flags=re.S)
        palette=dict(black=theme['background'],white=theme['foreground'],green=theme['accent'],blue=theme['palette'][4],purple=theme['palette'][5],cyan=theme['accent'],yellow=theme['palette'][3],red=theme['palette'][1])
        return "palette = 'wysun'\n"+text.rstrip()+'\n\n[palettes.wysun]\n'+''.join(f"{name} = '{value}'\n" for name,value in palette.items())
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
        text=re.sub(r'/\* BEGIN WYSUN THEME \*/.*?/\* END WYSUN THEME \*/\n?','',text,flags=re.S)
        files[path]=text.rstrip()+'\n/* BEGIN WYSUN THEME */\n'+''.join(f'@define-color {name} {value};\n' for name,value in gtk.items())+'/* END WYSUN THEME */\n'
    native=config/'wysun'
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
    from wysun_settings.hypr import lua
    values=resolve_active(home)
    runner(['hyprctl','eval','hl.config('+lua({'general':{'col':border_colors(values)}})+')'])


def main(argv=None):
    """`python3 -m wysun_settings.theme_runtime render HOME`: write the themed files under HOME (the installer's staging tree)."""
    import argparse
    parser=argparse.ArgumentParser(prog='wysun_settings.theme_runtime')
    parser.add_argument('action',choices=('render',))
    parser.add_argument('home',type=Path)
    args=parser.parse_args(argv)
    for path,text in theme_files(args.home).items():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
