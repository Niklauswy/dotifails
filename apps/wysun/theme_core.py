"""Wysun theme selection and token resolution, without Qt.

The data lives in wysun_theme.json next to this file. Wysun Recorder/Screenshot
ship byte-identical copies of both files (tests/test_theme_tokens.py), so the
capture releases never import code from the installed launcher.

Selection precedence: WYSUN_THEME, ORBIT_THEME, then
$XDG_CONFIG_HOME/orbit/theme.json as {"style": ..., "variant": ...}. The old
{"id": ...} format and aliases remain valid. Dynamic Material roles are read
from $XDG_STATE_HOME/wysun/scheme.json only after an explicit selection.
Unknown or malformed state falls back without overwriting user data.
"""
import datetime
import json
import os
import re
import tempfile
import time
from pathlib import Path

DATA_PATH = Path(__file__).with_name('wysun_theme.json')
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


def variant_style(variant):
    """Style that owns a bare variant id, e.g. tokyo -> space-black."""
    for style, spec in styles().items():
        if variant in spec['variants']:
            return style
    return None


def normalize(style=None, variant=None):
    """Return a valid (style, variant). Mismatched variants use the style default."""
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
    """Parse a selection string: alias, variant id, style, 'style:variant' or 'style/variant'."""
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


def from_object(obj):
    """Selection from a theme.json object; (style, variant, legacy_format)."""
    if not isinstance(obj, dict):
        return default() + (False,)
    style, variant = obj.get('style'), obj.get('variant')
    if isinstance(style, str) and style in styles():
        return normalize(style, variant) + (False,)
    if isinstance(style, str) or isinstance(variant, str):
        parsed = parse(variant) if isinstance(variant, str) else None
        return (parsed or default()) + (False,)
    legacy = obj.get('id', obj.get('name'))
    parsed = parse(legacy) if isinstance(legacy, str) else None
    return (parsed or default()) + (True,)


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


def read_file(home=None):
    """Selection stored on disk, ignoring environment overrides."""
    try:
        obj = json.loads(selection_path(home).read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return default()
    return from_object(obj)[:2]


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
        wallpaper=chosen['wallpaper'], external=chosen['external'],
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
    return result


def resolve_active(style=None, variant=None, home=None):
    """Resolve preset geometry with dynamic colours only when explicitly selected."""
    style, variant = normalize(*(selection(home) if style is None else (style, variant)))
    values = resolve(style, variant)
    if environment_override() is None:
        values = overlay_material_roles(values, read_scheme(home))
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


def serialize(style, variant):
    style, variant = normalize(style, variant)
    return json.dumps({'style': style, 'variant': variant}, indent=2) + '\n'


def write_selection(style, variant, home=None):
    """Persist a selection atomically with private permissions and a backup."""
    path = selection_path(home)
    text = serialize(style, variant)
    try:
        if path.read_text(encoding='utf-8') == text:
            return path
    except OSError:
        pass
    _backup(path, home)
    _atomic_write(path, text)
    invalidate()
    return path


def write_selection_preserving(style, variant, home=None):
    """Update only the selection fields and retain unrelated theme.json data."""
    style, variant = normalize(style, variant)
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
    value = {key: item for key, item in value.items() if key not in ('id', 'name', 'style', 'variant')}
    value.update(style=style, variant=variant)
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
    """Rewrite a legacy {"id": ...} file in the new format. Returns True if changed."""
    path = selection_path(home)
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return False
    if not isinstance(obj, dict):
        return False
    style, variant, legacy = from_object(obj)
    if not legacy:
        return False
    write_selection(style, variant, home)
    return True
