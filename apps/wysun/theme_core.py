"""Wysun theme selection and token resolution, without Qt.

The data lives in wysun_theme.json next to this file. Wysun Recorder/Screenshot
ship byte-identical copies of both files (tests/test_theme_tokens.py), so the
capture releases never import code from the installed launcher.

Selection precedence: WYSUN_THEME, ORBIT_THEME, then
$XDG_CONFIG_HOME/orbit/theme.json as {"style": ..., "variant": ...}. The old
{"id": ...} format and the aliases azul/morado/Tokyo/Severance remain valid.
Unknown values fall back without raising.
"""
import datetime
import json
import os
import tempfile
import time
from pathlib import Path

DATA_PATH = Path(__file__).with_name('wysun_theme.json')
_data = None
_cache = {}


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


def _atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def _backup(path, home=None):
    if not path.is_file():
        return None
    root = Path(home or Path.home()) / '.local/state/orbit/theme-backups'
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
