"""Wysun's theme without Qt: the mode the user chose, the wallpaper scheme and the tokens they give.

Wysun has one style, Material You. Colours come from the wallpaper
(<state>/wysun/scheme.json, written by ``wysun scheme``, which also resolves ``auto``
to light or dark); the user only chooses the mode in <config>/orbit/theme.json as
{"mode": "auto"|"light"|"dark"}. ``tokens.json`` holds the shape, type and motion
tokens, under the shell's names (``rounding``, ``spacing``, ``padding``, ``font``, ``anim``),
plus the base palette of each mode, used for every token the scheme does not
define and while no scheme exists. ``WYSUN_THEME=light|dark`` forces a base palette
(tests and screenshots).
"""
import datetime
import json
import os
import re
from pathlib import Path

from . import paths
from .jsonio import atomic_write_json, atomic_write_text

DATA_PATH = Path(__file__).with_name('tokens.json')
SHAPE_GROUPS = ('rounding', 'spacing', 'padding', 'font', 'anim', 'border', 'icon')
MODES = ('auto', 'light', 'dark')
DEFAULT_MODE = 'dark'           # what ``auto`` gives before the first scheme exists
_data = None
_signatures = {}                # path -> ((mtime_ns, size), parsed value)

MATERIAL_TOKEN_ROLES = {
    'background': 'canvas', 'onBackground': 'text',
    'surface': 'surface', 'onSurface': 'text', 'surfaceVariant': 'well',
    'onSurfaceVariant': 'muted', 'surfaceDim': 'canvas', 'surfaceBright': 'surface_raised',
    'surfaceContainerLowest': 'canvas', 'surfaceContainerLow': 'well',
    'surfaceContainer': 'surface', 'surfaceContainerHigh': 'surface_raised',
    'surfaceContainerHighest': 'menu_selected', 'outline': 'line_strong',
    'outlineVariant': 'line', 'inverseSurface': 'tooltip', 'inverseOnSurface': 'on_tooltip',
    'shadow': 'shadow', 'scrim': 'scrim',
    'surfaceTint': 'accent', 'primary': 'accent',
    'onPrimary': 'on_accent', 'secondary': 'accent_alt', 'onSecondary': 'accent_ink',
    'tertiary': 'warning', 'tertiaryDim': 'warning', 'success': 'success',
    'error': 'danger', 'errorContainer': 'danger_soft',
}


def data():
    global _data
    if _data is None:
        _data = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    return _data


def default_wallpaper():
    """File name of the wallpaper the distribution ships (and the base palettes go with)."""
    return data()['wallpaper']


def _root(home, kind):
    """XDG locations for the real HOME; plain dot directories for an injected one (tests, previews)."""
    if home is None or Path(home) == Path.home():
        return paths.config_home() if kind == 'config' else paths.state_home()
    return Path(home) / ('.config' if kind == 'config' else '.local/state')


def selection_path(home=None):
    return _root(home, 'config') / 'orbit/theme.json'


def scheme_path(home=None):
    return _root(home, 'state') / 'wysun/scheme.json'


def _signature(path):
    try:
        info = path.stat()
        return info.st_mtime_ns, info.st_size
    except OSError:
        return None


def _cached(path, parse):
    signature = _signature(path)
    cached = _signatures.get(path)
    if cached and cached[0] == signature:
        return cached[1]
    value = parse(path) if signature else None
    _signatures[path] = (signature, value)
    return value


def _parse_mode(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return 'auto'
    mode = value.get('mode') if isinstance(value, dict) else None
    return mode if mode in MODES else 'auto'


def read_mode(home=None):
    """'auto', 'light' or 'dark'; a missing, broken or old-format file means 'auto'."""
    return _cached(selection_path(home), _parse_mode) or 'auto'


def _valid_scheme(value):
    allowed = {'name', 'flavour', 'mode', 'variant', 'colours', 'wallpaper_hash'}
    colours = value.get('colours') if isinstance(value, dict) else None
    if (not isinstance(value, dict) or set(value) - allowed
            or not isinstance(value.get('name'), str) or not isinstance(value.get('flavour'), str)
            or value.get('mode') not in ('light', 'dark') or not isinstance(value.get('variant'), str)
            or not isinstance(colours, dict) or not colours
            or any(not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r'[0-9a-fA-F]{6}', v)
                   for k, v in colours.items())):
        return False
    digest = value.get('wallpaper_hash')
    if value['name'] == 'dynamic':
        return isinstance(digest, str) and bool(re.fullmatch(r'[0-9a-f]{64}', digest))
    return digest is None or isinstance(digest, str) and bool(re.fullmatch(r'[0-9a-f]{64}', digest))




def _parse_scheme(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return value if _valid_scheme(value) else None


def read_scheme(home=None):
    """The shell's scheme contract, or None when it is missing or malformed."""
    return _cached(scheme_path(home), _parse_scheme)


def invalidate():
    _signatures.clear()


def _backup(path, home=None):
    target = _root(home, 'state') / 'orbit/theme-backups' / (
        'theme-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    atomic_write_text(target, path.read_text(encoding='utf-8', errors='replace'), mode=0o600)
    return target


def write_mode(mode, home=None):
    """Store the mode, keeping any other key of theme.json and a backup of the previous file.

    A file that is not a JSON object is replaced (its backup keeps the original bytes).
    """
    if mode not in MODES:
        raise ValueError('Modo desconocido: ' + str(mode))
    path = selection_path(home)
    try:
        original = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        original = None
    try:
        value = json.loads(original) if original is not None else {}
    except ValueError:
        value = None
    if not isinstance(value, dict):
        value = {}                  # a broken file is replaced; the backup below keeps its bytes
    value['mode'] = mode
    text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if text != original:
        if original is not None:
            _backup(path, home)
        atomic_write_text(path, text, mode=0o600)
    invalidate()
    return path


def write_scheme(scheme, home=None):
    """Publish a valid Material-role scheme contract."""
    if not _valid_scheme(scheme):
        raise ValueError('El esquema contiene roles Material inválidos.')
    path = atomic_write_json(scheme_path(home), scheme, mode=0o600, sort_keys=True)
    invalidate()
    return path


def _override(environ=None):
    value = (os.environ if environ is None else environ).get('WYSUN_THEME', '').strip()
    return value if value in ('light', 'dark') else None


def active_mode(home=None, environ=None):
    """'light' or 'dark': the override, else the scheme's resolved mode, else the chosen one."""
    forced = _override(environ)
    if forced:
        return forced
    scheme = read_scheme(home)
    if scheme is not None:
        return scheme['mode']
    mode = read_mode(home)
    return mode if mode != 'auto' else DEFAULT_MODE


def flatten(group, prefix):
    """``{'body': {'medium': {'size': 14}}}`` under ``'font'`` → ``{'font.body.medium.size': 14}``.

    The dotted names are the shell's paths (``Tokens.font.body.medium``); lists stay values.
    """
    flat = {}
    for key, value in group.items():
        name = prefix + '.' + key
        if isinstance(value, dict):
            flat.update(flatten(value, name))
        else:
            flat[name] = value
    return flat


def resolve(mode):
    """Flat tokens of a base palette ('light' or 'dark'): shape (dotted names), colours and metadata."""
    if mode not in ('light', 'dark'):
        raise ValueError('Paleta desconocida: ' + str(mode))
    palette = data()['palettes'][mode]
    tokens = {}
    for group in SHAPE_GROUPS:
        tokens.update(flatten(data()[group], group))
    tokens.update(palette['colors'])
    tokens.update(mode=mode, external=palette['external'], wallpaper=default_wallpaper(),
                  material=palette['material'], translucent=palette['translucent'])
    return tokens


def overlay_material_roles(tokens, scheme):
    """Map the Material You role names from scheme.json to Wysun's tokens."""
    if not isinstance(scheme, dict) or scheme.get('name') != 'dynamic':
        return tokens
    colours = scheme.get('colours', {})
    result = dict(tokens)
    for role, token in MATERIAL_TOKEN_ROLES.items():
        value = colours.get(role)
        if value and token in result:
            result[token] = '#' + value.lower()
    # outlineVariant is intentionally subtle in Material; Wysun uses its
    # stronger outline for interactive borders to keep the 3:1 UI contrast.
    if colours.get('outline'):
        result['line'] = result['line_strong'] = result['check_line'] = '#' + colours['outline'].lower()
    # Keep selection text readable on every surface; Material container roles
    # remain available in scheme.json for consumers that can pair them directly.
    if colours.get('surfaceContainerHigh'):
        result['selection'] = '#' + colours['surfaceContainerHigh'].lower()
        result['selection_text'] = result['text']
    # Several Material variants dim primary below readable text contrast;
    # preserve the accessible primary tone for hover and pressed controls.
    result['accent_hover'] = result['accent_pressed'] = result['accent']
    # The dynamic base surface and its text roles are the WCAG-checked pair.
    result['control_text'] = result['text']
    result['text_strong'] = result['text']
    result['subtle'] = result['muted']
    result['focus'] = result['accent']
    result['focus_input'] = result['accent']
    result['info'] = result['accent']
    result['glyph'] = result['muted']
    result['glyph_muted'] = result['muted']
    result['material_top'] = result['canvas']
    result['material_mid'] = result['surface']
    result['material_bottom'] = result['well']
    result['material_edge'] = result['line']
    # Interactive surfaces the table above does not cover would otherwise keep
    # the base palette's values (white light fills over a dark scheme).
    for token, role in (('fill', 'surfaceContainerHigh'), ('hover', 'surfaceContainerHighest'),
                        ('row_hover', 'surfaceContainerHigh'), ('row_selected', 'secondaryContainer'),
                        ('nav_selected', 'secondaryContainer'), ('tint', 'onSurface'),
                        ('card', 'surfaceContainerLow'), ('tile', 'surfaceContainer'),
                        ('tile_hover', 'surfaceContainerHigh'), ('chosen_fill', 'secondaryContainer')):
        if colours.get(role) and token in result:
            result[token] = '#' + colours[role].lower()
    # Code and terminal colours follow the wallpaper too.
    terminal = [colours.get(f'term{index}') for index in range(16)]
    if all(terminal) and isinstance(result.get('external'), dict):
        result['external'] = dict(result['external'], palette=['#' + value.lower() for value in terminal])
    return result



def resolve_active(home=None, environ=None):
    """Tokens of the active mode with the wallpaper's colours on top (none under WYSUN_THEME)."""
    values = resolve(active_mode(home, environ))
    if _override(environ) is None:
        values = overlay_material_roles(values, read_scheme(home))
    return values


def revision(home=None):
    """What a watcher compares to know the tokens changed."""
    return read_mode(home), active_mode(home), _signature(scheme_path(home))
