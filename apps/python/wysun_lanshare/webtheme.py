"""The page's look: Wysun tokens as CSS variables, always light, with the wallpaper's colours.

Colours: scheme.json when it is already light; else the same wallpaper generated in light mode
(cached by wallpaper); else the light base palette of tokens.json. Fonts are the packaged ones,
served by the server itself (/fonts/…), so the page works without internet.
"""
import json
import os
import threading

from wysun_core import theme
from wysun_core.jsonio import atomic_path
from wysun_lanshare import media

FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'wysun_core', 'fonts')
FONTS = {'sans': 'GoogleSansFlex.ttf', 'icons': 'MaterialSymbolsRounded.ttf'}
_lock = threading.Lock()
_cache = {}


def _generated_light(scheme, home):
    """The wallpaper's scheme in light mode, cached under ~/.cache/wysun/lanshare."""
    from wysun_services import scheme as generator   # PIL; only when the shell's scheme is dark
    wallpaper = generator._current_wallpaper(home)
    digest = (scheme or {}).get('wallpaper_hash') or generator._file_hash(wallpaper)
    cached = os.path.join(media.cache_dir(), f'scheme-light-{digest}.json')
    try:
        with open(cached, encoding='utf-8') as stream:
            return json.load(stream)
    except (OSError, ValueError):
        pass
    colours = generator.generate_dynamic(wallpaper, mode='light', variant=(scheme or {}).get('variant'))['colours']
    try:
        with atomic_path(cached) as tmp:
            tmp.write_text(json.dumps(colours))
    except OSError:
        pass
    return colours


def light_colours(home=None):
    """Material roles (hex without '#') of the light scheme to use."""
    scheme = theme.read_scheme(home)
    if scheme and scheme['mode'] == 'light':
        return dict(scheme['colours'])
    try:
        return _generated_light(scheme, home)
    except Exception:   # no wallpaper, no PIL, unreadable image: the base palette is always there
        return dict(theme.data()['palettes']['light']['scheme'])


def _px(value):
    return '999px' if value > 10000 else f'{value}px'


def _variables(colours):
    data = theme.data()
    lines = [f'--{name}:{value};' for name, value in theme.m3_roles(colours).items()]
    for group in ('rounding', 'spacing', 'padding'):
        lines += [f'--{group}-{key}:{_px(value)};' for key, value in data[group].items()]
    for role in ('headline', 'title', 'body', 'label'):
        for size, spec in data['font'][role].items():
            lines.append(f'--font-{role}-{size}:{spec["weight"]} {spec["size"]}px/1.4 var(--font-sans);')
    family = data['font']['family']
    lines.append(f'--font-sans:"{family["sans"]}",system-ui,sans-serif;')
    lines.append(f'--font-icon:"{family["icon"]}";')
    for key, value in data['anim']['durations'].items():
        lines.append(f'--anim-{key}:{value}ms;')
    for key, points in data['anim']['curves'].items():
        if len(points) == 6:            # one cubic segment; CSS has no multi-segment Béziers
            lines.append(f'--ease-{key}:cubic-bezier({",".join(str(round(p, 4)) for p in points[:4])});')
    return lines


def css(home=None):
    """Stylesheet with :root variables and the @font-face rules; cached until the theme changes."""
    key = theme.revision(home)
    with _lock:
        if key in _cache:
            return _cache[key]
        family = theme.data()['font']['family']
        text = (
            f'@font-face{{font-family:"{family["sans"]}";src:url(/fonts/{FONTS["sans"]}) format("truetype");'
            'font-weight:100 1000;font-display:swap}\n'
            f'@font-face{{font-family:"{family["icon"]}";src:url(/fonts/{FONTS["icons"]}) format("truetype");'
            'font-weight:100 700;font-display:block}\n'
            ':root{color-scheme:light;\n' + '\n'.join(_variables(light_colours(home))) + '\n}\n')
        _cache.clear()
        _cache[key] = text
        return text
