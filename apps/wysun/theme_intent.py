"""Persisted colour intent in theme.json (dynamic Material You vs fixed preset).

theme_core.py is shared byte for byte with the capture releases, so the
additive ``dynamic`` block of theme.json is read and written here. Nothing in
this module generates colour: wysun_scheme remains the only producer and
scheme.json keeps its format. Unknown keys of theme.json are always kept.
"""
import json
import re

import theme_core


def _selection_object(home=None):
    """theme.json as an object; ({}, None) when absent. Malformed data raises."""
    path = theme_core.selection_path(home)
    try:
        original = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return {}, None
    except (OSError, UnicodeError) as error:
        raise ValueError('theme.json no se pudo leer; se conservó el archivo.') from error
    try:
        value = json.loads(original)
    except ValueError as error:
        raise ValueError('No se reemplazó theme.json porque no es un objeto JSON válido.') from error
    if not isinstance(value, dict):
        raise ValueError('No se reemplazó theme.json porque no es un objeto JSON válido.')
    return value, original


def dynamic_intent(home=None):
    """What the user wants the colour authority to produce.

    theme.json may carry an additive ``dynamic`` object::

        {"enabled": bool, "mode": "light"|"dark", "variant": <Material variant>,
         "seed": "#rrggbb"}

    Every key but ``enabled`` is optional (absent mode/variant mean "derive
    them from the wallpaper"; absent seed means "use the wallpaper"). Without
    the object, a profile with no explicit fixed selection - a new one - is
    dynamic; a pre-existing dynamic scheme.json keeps counting as dynamic;
    an explicit fixed selection stays fixed. An unreadable file is never
    dynamic, so a bad theme.json is never rewritten by a refresh.
    """
    try:
        value, _ = _selection_object(home)
    except ValueError:
        return dict(enabled=False)
    block = value.get('dynamic')
    if isinstance(block, dict) and isinstance(block.get('enabled'), bool):
        intent = dict(enabled=block['enabled'])
        if block.get('mode') in ('light', 'dark'):
            intent['mode'] = block['mode']
        if isinstance(block.get('variant'), str):
            intent['variant'] = block['variant']
        if isinstance(block.get('seed'), str) and re.fullmatch(r'#[0-9a-fA-F]{6}', block['seed']):
            intent['seed'] = block['seed'].lower()
        return intent
    explicit = any(isinstance(value.get(key), str) for key in ('id', 'style', 'variant', 'name'))
    if not explicit:
        return dict(enabled=True)
    current = theme_core.read_scheme(home)
    return dict(enabled=bool(current and current.get('name') == 'dynamic'))


def dynamic_text(intent, home=None):
    """theme.json text with only the dynamic block replaced (other keys kept)."""
    value, _ = _selection_object(home)
    block = {'enabled': bool(intent.get('enabled'))}
    for key in ('mode', 'variant', 'seed'):
        if intent.get(key) is not None:
            block[key] = intent[key]
    value['dynamic'] = block
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def write_dynamic(intent, home=None):
    """Persist the dynamic intent atomically, with backup and unknown keys kept."""
    path = theme_core.selection_path(home)
    text = dynamic_text(intent, home)
    _, original = _selection_object(home)
    if text == original:
        return path
    if original is not None:
        theme_core._backup(path, home)
    theme_core._atomic_write(path, text)
    theme_core.invalidate()
    return path


def selection_text(style, variant, home=None):
    """theme.json text for a fixed choice, preserving unknown keys."""
    style, variant = theme_core.normalize(style, variant)
    value, _ = _selection_object(home)
    value = {key: item for key, item in value.items() if key not in ('id', 'name', 'style', 'variant')}
    value.update(style=style, variant=variant)
    if isinstance(value.get('dynamic'), dict):
        value['dynamic'] = dict(value['dynamic'], enabled=False)
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def write_fixed(style, variant, home=None):
    """Persist an explicit fixed choice (atomic, backed up, unknown keys kept)."""
    path = theme_core.selection_path(home)
    text = selection_text(style, variant, home)
    _, original = _selection_object(home)
    if text == original:
        return path
    if original is not None:
        theme_core._backup(path, home)
    theme_core._atomic_write(path, text)
    theme_core.invalidate()
    return path
