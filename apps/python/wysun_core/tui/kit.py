"""The shared look of Wysun terminal utilities (Drive, Cloud and the next ones).

Every utility is a transparent :class:`~wysun_core.tui.app.App` (``transparent = True``: the
canvas background is left to Ghostty's opacity and blur) drawn with palette roles only, and
reuses these pieces so they look and behave alike:

- :func:`header` — row 0: the app chip with its Nerd Font icon, tabs or a breadcrumb trail, and
  a status text with a coloured dot on the right.
- :func:`crumbs` — a breadcrumb row (``a › b › c``) with a right-aligned note.
- :func:`footer` — the last row: a toast when there is one, else ``key label`` hints.
- :func:`chip` — a pill that is on (``primary``) or off (``surfaceContainerHigh``).
- :class:`Toast` — a short message over the footer row that fades in and out by itself.
- :class:`HelpLayer` — the ``?`` overlay of keys, sliding and fading in with the motion tokens.
- :func:`pixels` — half-block pictures: ``▀`` with the top pixel as foreground and the bottom one
  as background (previews of the user's own images: content, not theme colours).
- :data:`GLYPH` — the Nerd Font glyphs (single cells in the packaged CaskaydiaCove).
"""
from __future__ import annotations

from .anim import Rect, Tween, curve, duration, fade_steps, reduced_motion
from .app import Layer
from .canvas import Style
from .draw import box, truncate

__all__ = ['GLYPH', 'HelpLayer', 'Painter', 'Toast', 'chip', 'crumbs', 'footer', 'header', 'hints', 'pixels']

GLYPH = {
    'cloud': '', 'drive': '', 'server': '', 'link': '', 'up': '', 'ok': '',
    'lock': '', 'clock': '', 'copy': '', 'warn': '', 'eye': '', 'search': '',
    'help': '', 'refresh': '', 'power': '', 'terminal': '', 'chart': '',
    'folder': '', 'file': '', 'money': '',
}


class Painter:
    """``s('primary', 'surfaceContainerHigh', bold=True)`` → a Style from palette roles."""

    def __init__(self, palette):
        self.palette = palette

    def __call__(self, fg=None, bg=None, **kw):
        return Style(fg=self.palette[fg] if fg else None, bg=self.palette[bg] if bg else None, **kw)


def chip(canvas, s, x, y, text, on=True, role='primary'):
    """`` text `` as a pill; returns its width."""
    label = f' {text} '
    if on:
        on_role = {'primary': 'onPrimary', 'primaryContainer': 'onPrimaryContainer',
                   'secondaryContainer': 'onSecondaryContainer', 'tertiary': 'onTertiary',
                   'error': 'onError'}.get(role, 'onPrimary')
        canvas.text(x, y, label, s(on_role, role, bold=True))
    else:
        canvas.text(x, y, label, s('onSurfaceVariant', 'surfaceContainerHigh'))
    return len(label)


def header(canvas, s, title, icon, tabs=None, active=None, trail=None, status='', status_role='success',
           note=''):
    """Row 0. ``tabs``: labels numbered 1…; ``trail``: breadcrumb parts; ``note``: muted text after them;
    ``status``: right-aligned text after a dot of ``status_role`` (``None`` hides the dot)."""
    width = canvas.width
    x = 1 + chip(canvas, s, 1, 0, f'{icon} {title}') + 1
    if tabs:
        for index, label in enumerate(tabs):
            text = f' {index + 1} {label} '
            canvas.text(x, 0, text, s('onSecondaryContainer', 'secondaryContainer', bold=True) if index == active
                        else s('onSurfaceVariant'))
            x += len(text) + 1
    right = len(status) + (2 if status_role else 0) + 2 if status else 0
    if trail:
        x += 1
        for index, part in enumerate(trail):
            last = index == len(trail) - 1
            room = width - right - x - 1
            if room <= 3:
                break
            text = truncate(part, room)
            canvas.text(x, 0, text, s('onSurface', bold=True) if last else s('onSurfaceVariant'))
            x += len(text)
            if not last:
                canvas.text(x, 0, ' › ', s('outline'))
                x += 3
    if note:
        room = width - right - x - 2
        if room > 3:
            canvas.text(x + 1, 0, truncate(note, room), s('onSurfaceVariant'))
            x += 1 + min(len(note), room)
    if status and x + right < width:
        canvas.text(width - 1 - len(status), 0, status, s('onSurfaceVariant'))
        if status_role:
            canvas.text(width - 3 - len(status), 0, '●', s(status_role))


def crumbs(canvas, s, y, parts, right='', right_role='onSurfaceVariant'):
    """``a › b › c`` from x=2 (the middle collapses to ``…`` when short of room) and a right note."""
    width = canvas.width
    room = max(10, width - len(right) - 6)
    shown = list(parts)
    while sum(len(p) + 3 for p in shown) > room and len(shown) > 2:
        del shown[1 if shown[1] != '…' else 2]
        if shown[1] != '…':
            shown.insert(1, '…')
    x = 2
    for index, part in enumerate(shown):
        last = index == len(shown) - 1
        text = truncate(part, room)
        canvas.text(x, y, text, s('onSurface', bold=True) if last else s('onSurfaceVariant'))
        x += len(text)
        if not last:
            canvas.text(x, y, ' › ', s('outline'))
            x += 3
    if right:
        right = truncate(right, max(0, width - x - 4))
        canvas.text(width - 2 - len(right), y, right, s(right_role))


def hints(canvas, s, y, items, x=2):
    """``key label`` pairs until the row is full."""
    for key, label in items:
        chunk = len(key) + len(label) + 3
        if x + chunk > canvas.width - 1:
            break
        canvas.text(x, y, key, s('primary', bold=True))
        canvas.text(x + len(key) + 1, y, label, s('onSurfaceVariant'))
        x += chunk


def footer(canvas, s, items, toast=''):
    """The last row: the toast (``● text``) when there is one, else the hints."""
    y = canvas.height - 1
    if toast:
        canvas.text(2, y, '●', s('primary'))
        canvas.text(4, y, truncate(toast, canvas.width - 6), s('onSurface'))
    else:
        hints(canvas, s, y, items)


def pixels(canvas, x, y, rows):
    """Paint ``rows`` of ``(top_rgb, bottom_rgb)`` pairs as half blocks (picture content)."""
    for r, line in enumerate(rows):
        for col, (top, bottom) in enumerate(line):
            canvas.put(x + col, y + r, '▀', Style(fg=top, bg=bottom))   # theme-exception: preview pixels


class HelpLayer(Layer):
    """The ``?`` overlay: a titled box of ``(key, label)`` lines that slides up and fades in.

    ``lines`` is a function so the content can follow the app's current screen. ``open(app)``
    places it in the middle of the terminal and animates it (instantly with reduced motion);
    ``close(app)`` hides it.
    """

    def __init__(self, lines, title='Teclas', z=120, key_width=16):
        super().__init__(Rect(0, 0, 1, 1), z=z, visible=False)
        self.lines = lines
        self.title = title
        self.key_width = key_width

    def place(self, app, t=1.0):
        width, height = app.size
        count = len(self.lines())
        w = max(20, min(66, width - 4))
        h = max(5, min(height - 2, count + 4))
        self.rect = Rect(max(0, (width - w) // 2), max(0, (height - h) // 2) + round((1 - t) * 2), w, h)
        self.opacity = max(0.0, min(1.0, t))

    def open(self, app):
        self.visible = True
        if reduced_motion():
            self.place(app)
        else:
            self.place(app, 0.0)
            app.animator.add(Tween(duration('expressiveFastEffects'), curve('emphasizedDecel'),
                                   lambda t: self.place(app, t)))
        app.invalidate()

    def close(self, app):
        self.visible = False
        app.invalidate()

    def draw(self, canvas, palette):
        s = Painter(palette)
        canvas.fill(Rect(0, 0, canvas.width, canvas.height), ' ', s(bg='surfaceContainerHigh'))
        box(canvas, Rect(0, 0, canvas.width, canvas.height), s('outlineVariant', 'surfaceContainerHigh'),
            [(f' {GLYPH["help"]} {self.title} ', s('onSurface', 'surfaceContainerHigh', bold=True))])
        for index, (key, label) in enumerate(self.lines()):
            y = 2 + index
            if y >= canvas.height - 1:
                break
            canvas.text(3, y, truncate(key, self.key_width), s('primary', 'surfaceContainerHigh', bold=True))
            canvas.text(4 + self.key_width, y, truncate(label, canvas.width - 6 - self.key_width),
                        s('onSurface', 'surfaceContainerHigh'))


class Toast(Layer):
    """A one-line message on the footer row (``● text``) that fades in, stays and fades out.

    ``show(app, text, seconds)`` replaces any message on screen; ``place(app)`` follows a resize.
    ``text`` stays readable while it is visible (tests and apps may check it).
    """

    def __init__(self, z=130):
        super().__init__(Rect(0, 0, 1, 1), z=z, visible=False)
        self.text = ''
        self._timer = None

    def place(self, app):
        width, height = app.size
        self.rect = Rect(0, max(0, height - 1), max(1, width), 1)

    def show(self, app, text, seconds=3.0):
        self.text = text
        self.place(app)
        self.visible = True
        self.opacity = 1.0
        if self._timer is not None:
            app.cancel(self._timer)
        if not reduced_motion():
            self.opacity = 0.0
            app.animator.add(Tween(duration('expressiveFastEffects'), curve('standardDecel'),
                                   lambda t: setattr(self, 'opacity', fade_steps(t))))
        self._timer = app.after(seconds, lambda: self.hide(app))
        app.invalidate()

    def hide(self, app):
        self._timer = None

        def done():
            self.visible, self.text = False, ''
            app.invalidate()
        if reduced_motion():
            done()
            return
        app.animator.add(Tween(duration('expressiveFastEffects'), curve('standardAccel'),
                               lambda t: setattr(self, 'opacity', fade_steps(1.0 - t)), done))

    def draw(self, canvas, palette):
        s = Painter(palette)
        canvas.text(2, 0, '●', s('primary'))
        canvas.text(4, 0, truncate(self.text, canvas.width - 6), s('onSurface'))
