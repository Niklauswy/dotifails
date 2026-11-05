"""The terminal UI's palette: Material role names to RGB tuples, taken from the wallpaper.

The source of truth is ``wysun_core.theme``: the wallpaper's scheme when it exists and
its mode is the active one, else the base palette of the active mode. Roles a scheme does
not carry (``success``, ``scrim`` and friends) fall back to the base palette of that mode,
so a role is never missing for the UI. ``revision`` keeps what was read, and ``changed()``
tells the app when to reload and repaint (the shell rewrites ``scheme.json`` on a wallpaper
or mode change).
"""
import os

from .. import theme as core_theme

__all__ = ['Palette', 'parse_colour']


def parse_colour(value):
    """``'rrggbb'``, ``'#rrggbb'`` or ``'#rgb'`` from a scheme or a token, as ``(r, g, b)``."""
    text = str(value).strip()
    if text.startswith('#'):
        text = text[1:]
    if len(text) == 3:
        text = ''.join(char * 2 for char in text)
    if len(text) != 6:
        raise ValueError('Color inválido: ' + str(value))
    return tuple(int(text[index:index + 2], 16) for index in (0, 2, 4))


def _forced_mode(environ=None):
    """Whether ``WYSUN_THEME`` forces a base palette (same rule as ``theme.active_scheme``)."""
    env = os.environ if environ is None else environ
    return env.get('WYSUN_THEME', '').strip() in ('light', 'dark')


class Palette:
    """Role -> ``(r, g, b)``, the mode it came from and the theme revision it was read at.

    ``Palette.load(home)`` reads the wallpaper scheme (or the base palette) once; the app
    keeps the instance and calls ``changed(home)`` before a repaint to know whether to load
    a fresh one. ``palette[role]`` raises ``KeyError`` for an unknown role; ``get`` does not.
    """

    def __init__(self, mode, colours, revision):
        self.mode = mode
        self.colours = dict(colours)
        self.revision = revision

    @classmethod
    def load(cls, home=None):
        mode = core_theme.active_mode(home)
        scheme = core_theme.read_scheme(home)
        base = core_theme.data()['palettes'][mode]['scheme']
        values = dict(base)                      # role -> hex, the base every mode can rely on
        if scheme is not None and scheme['mode'] == mode and not _forced_mode():
            values.update(scheme['colours'])
        return cls(mode, {role: parse_colour(value) for role, value in values.items()},
                   core_theme.revision(home))

    def __getitem__(self, role):
        return self.colours[role]

    def __contains__(self, role):
        return role in self.colours

    def __iter__(self):
        return iter(self.colours)

    def __len__(self):
        return len(self.colours)

    def __repr__(self):
        return f'Palette(mode={self.mode!r}, roles={len(self.colours)})'

    def get(self, role, default=None):
        """The role's RGB, or ``default`` when neither the scheme nor the base palette has it."""
        return self.colours.get(role, default)

    def changed(self, home=None):
        """Whether the theme revision (mode, active mode, scheme file) moved since ``load``."""
        return core_theme.revision(home) != self.revision
