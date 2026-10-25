"""Wysun theme selection and token resolution, without Qt.

Wysun has one style, Material You. Its colours always come from the wallpaper
($XDG_STATE_HOME/wysun/scheme.json, written by wysun_scheme); the only thing the
user chooses is the mode: ``auto`` (follows the wallpaper), ``light`` or ``dark``.

The data lives in wysun_theme.json next to this file. Wysun Recorder ships
byte-identical copies of both files (tests/test_theme_tokens.py), so the capture
releases never import code from the installed launcher. The two variants in the
data (``light``/``dark``) are base palettes: they cover the tokens Material does
not define and are the fallback while no scheme exists.

Selection precedence: WYSUN_THEME, ORBIT_THEME (``light``/``dark``), then
$XDG_CONFIG_HOME/orbit/theme.json as {"mode": "auto"|"light"|"dark"}. The older
formats ({"style", "variant"}, {"id"}, {"dynamic": {...}}) are still read and are
migrated by ``migrate``. Unknown or malformed state falls back without
overwriting user data.
"""
import datetime
import json
import os
import re
import tempfile
import time
from pathlib import Path

DATA_PATH = Path(__file__).with_name('wysun_theme.json')
MODES = ('auto', 'light', 'dark')
LEGACY_KEYS = ('id', 'name', 'style', 'variant', 'dynamic')
_data = None
_cache = {}
_scheme_cache = {}

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


def styles():
    return data()['styles']


def default():
    value = data()['default']
    return value['style'], value['variant']


def default_wallpaper():
    """File name of the wallpaper the distribution ships (and the fallback palette is built from)."""
    return data()['default']['wallpaper']


def variant_style(variant):
    """Style that owns a bare variant id, e.g. dark -> material-you."""
    for style, spec in styles().items():
        if variant in spec['variants']:
            return style
    return None


def normalize(style=None, variant=None):
    """Return a valid (style, variant). Unknown values use the defaults."""
    known = styles()
    if style not in known:
        owner = variant_style(variant) if isinstance(variant, str) else None
        if owner is None:
            return default()
        style = owner
    if variant not in known[style]['variants']:
        variant = known[style]['default_variant']
    return style, variant


def parse(value):
    """Parse a variant string: ``light``, ``dark``, ``material-you[:variant]`` or a retired theme id.

    The retired fixed-theme ids (tokyo, fluent:dark...) only map to light or dark.
    ``auto`` is not a variant and gives ``None``.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    value = data()['aliases'].get(value, value)
    for separator in (':', '/'):
        if separator in value:
            style, variant = value.split(separator, 1)
            if style in styles():
                return normalize(style, variant)
            return None
    if value in styles():
        return normalize(value, None)
    owner = variant_style(value)
    if owner:
        return owner, value
    return None


def mode_from_object(obj):
    """(mode, legacy) for a theme.json object; ``legacy`` is True when it still carries old keys."""
    if not isinstance(obj, dict):
        return 'auto', False
    legacy = any(key in obj for key in LEGACY_KEYS)
    if obj.get('mode') in MODES:
        return obj['mode'], legacy
    block = obj.get('dynamic')
    if isinstance(block, dict) and block.get('enabled') is True and block.get('mode') in ('light', 'dark'):
        return block['mode'], True
    # A retired fixed theme becomes the automatic mode: the wallpaper decides.
    return 'auto', legacy


def config_root(home=None):
    """Same rule as hypr_settings.config_dir: XDG only for the real HOME."""
    home = Path(home or Path.home())
    if home == Path.home():
        return Path(os.environ.get('XDG_CONFIG_HOME', str(home / '.config')))
    return home / '.config'


def selection_path(home=None):
    return config_root(home) / 'orbit/theme.json'


def state_root(home=None):
    home = Path(home or Path.home())
    if home == Path.home():
        return Path(os.environ.get('XDG_STATE_HOME', str(home / '.local/state')))
    return home / '.local/state'


def scheme_path(home=None):
    return state_root(home) / 'wysun/scheme.json'


def visual_key(home=None):
    """Revision watched by Qt apps for both selection and shell colour state."""
    path = scheme_path(home)
    try:
        stat = path.stat()
        revision = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        revision = None
    return selection(home), revision


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


def read_scheme(home=None):
    """Read the shell contract, ignoring malformed or unsupported state."""
    path = scheme_path(home)
    try:
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = _scheme_cache.get(path)
        if cached and cached[0] == signature:
            return cached[1]
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        _scheme_cache.pop(path, None)
        return None
    if not _valid_scheme(value):
        _scheme_cache.pop(path, None)
        return None
    _scheme_cache[path] = (signature, value)
    return value


def environment_override(environ=None):
    environ = os.environ if environ is None else environ
    for key in ('WYSUN_THEME', 'ORBIT_THEME'):
        parsed = parse(environ.get(key, ''))
        if parsed:
            return parsed
    return None


def read_mode(home=None):
    """Mode stored on disk (``auto``, ``light`` or ``dark``), ignoring environment overrides."""
    try:
        obj = json.loads(selection_path(home).read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return 'auto'
    return mode_from_object(obj)[0]


def mode_variant(mode, home=None):
    """Base variant for a mode; ``auto`` follows the published scheme, then the default."""
    style, fallback = default()
    variants = styles()[style]['variants']
    if mode in variants:
        return mode
    scheme = read_scheme(home)
    if scheme is not None and scheme['mode'] in variants:
        return scheme['mode']
    return fallback


def read_file(home=None):
    """Selection stored on disk as (style, variant), ignoring environment overrides."""
    return default()[0], mode_variant(read_mode(home), home)


def selection(home=None, environ=None):
    override = environment_override(environ)
    if override:
        return override
    path = selection_path(home)
    now = time.monotonic()
    cached = _cache.get(path)
    if cached and now - cached[0] < .25:
        return cached[1]
    value = read_file(home)
    _cache[path] = (now, value)
    return value


def invalidate():
    _cache.clear()
    _scheme_cache.clear()


def key(style, variant):
    return style + ':' + variant


def resolve(style=None, variant=None):
    """Flat token dictionary for a selection: shape, colours and metadata."""
    if style is None:
        style, variant = selection()
    style, variant = normalize(style, variant)
    spec = styles()[style]
    chosen = spec['variants'][variant]
    tokens = dict(spec['shape'])
    tokens.update(chosen['colors'])
    tokens.update(
        style=style, variant=variant, key=key(style, variant),
        style_name=spec['name'], name=chosen['name'], description=chosen['description'],
        material=chosen.get('material', spec['shape']['material']),
        translucent=chosen.get('translucent', spec['shape']['translucent']),
        wallpaper=default_wallpaper(), external=chosen['external'],
    )
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


def resolve_active(style=None, variant=None, home=None):
    """Base palette and shape for the selection, with the wallpaper's colours on top."""
    style, variant = normalize(*(selection(home) if style is None else (style, variant)))
    scheme = read_scheme(home) if environment_override() is None else None
    if (isinstance(scheme, dict) and scheme.get('name') == 'dynamic'
            and scheme.get('mode') in styles().get(style, {}).get('variants', {})):
        # The scheme brings its own light/dark mode: start from the base palette
        # of that mode so tokens the scheme does not define stay coherent.
        variant = scheme['mode']
    values = resolve(style, variant)
    if scheme is not None:
        values = overlay_material_roles(values, scheme)
    return values


def _atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def _backup(path, home=None):
    if not path.is_file():
        return None
    root = state_root(home) / 'orbit/theme-backups'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / ('theme-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    _atomic_write(target, path.read_text(encoding='utf-8', errors='replace'))
    return target


def serialize(mode='auto'):
    if mode not in MODES:
        raise ValueError('Modo desconocido: ' + str(mode))
    return json.dumps({'mode': mode}, indent=2) + '\n'


def write_mode(mode, home=None):
    """Persist the mode atomically with private permissions and a backup.

    Only the mode changes: unrelated keys of theme.json are kept and the keys of
    the retired fixed-theme formats are dropped.
    """
    if mode not in MODES:
        raise ValueError('Modo desconocido: ' + str(mode))
    path = selection_path(home)
    try:
        original = path.read_text(encoding='utf-8')
        value = json.loads(original)
    except FileNotFoundError:
        original, value = None, {}
    except (OSError, ValueError, TypeError) as error:
        raise ValueError('No se reemplazó theme.json porque no es un objeto JSON válido.') from error
    if not isinstance(value, dict):
        raise ValueError('No se reemplazó theme.json porque no es un objeto JSON válido.')
    value = {key: item for key, item in value.items() if key not in LEGACY_KEYS}
    value['mode'] = mode
    text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if text == original:
        return path
    if original is not None:
        _backup(path, home)
    _atomic_write(path, text)
    invalidate()
    return path


def write_scheme(scheme, home=None):
    """Atomically publish a valid Material-role scheme contract."""
    if not _valid_scheme(scheme):
        raise ValueError('El esquema contiene roles Material inválidos.')
    path = scheme_path(home)
    _atomic_write(path, json.dumps(scheme, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    invalidate()
    return path


def migrate(home=None):
    """Rewrite a theme.json in an old format as {"mode": ...}. Returns True if changed."""
    path = selection_path(home)
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return False
    if not isinstance(obj, dict):
        return False
    mode, legacy = mode_from_object(obj)
    if not legacy:
        return False
    write_mode(mode, home)
    return True
