"""Small drawing pieces shared by the terminal screens: boxes, graphs, bars and tabs.

Everything draws into a :class:`~wysun_core.tui.canvas.Canvas`; nothing here reads the
clock, the theme or the terminal size, so each piece is pure and easy to test.
"""
from __future__ import annotations

import math
from typing import Sequence

from .anim import Rect
from .canvas import Canvas, Style

__all__ = ['box', 'braille_graph', 'bar', 'tabs', 'spinner_frame', 'truncate']

# U+2800 BRAILLE PATTERN BLANK through the full cell: the prototype's five levels.
LEVELS = ('⠀', '⣀', '⣤', '⣶', '⣿')
SPINNER = '◐◓◑◒'
PARTIALS = '▏▎▍▌▋▊▉'

ROUNDED = ('╭', '╮', '╰', '╯', '─', '│')
HEAVY = ('┏', '┓', '┗', '┛', '━', '┃')


def _bounds(rect) -> tuple[int, int, int, int]:
    """Accept a ``Rect``-like object or a plain ``(x, y, w, h)`` tuple."""
    if all(hasattr(rect, name) for name in ('x', 'y', 'w', 'h')):
        return int(rect.x), int(rect.y), int(rect.w), int(rect.h)
    x, y, w, h = rect
    return int(x), int(y), int(w), int(h)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _round(value: float) -> int:
    """``Math.round`` behaviour for the non-negative values used here (half rounds up)."""
    return math.floor(value + 0.5)


def _draw_title(canvas: Canvas, x: int, y: int, width: int, border: Style,
                title_segments: Sequence[tuple[str, Style]]) -> None:
    """Paint the title over the top border, with one padding space on each side."""
    available = width - 4
    if available <= 0:
        return
    cells = [(char, cell_style)
             for text, cell_style in title_segments
             for char in str(text)]
    if not cells:
        return
    if len(cells) > available:
        # Truncate to the room left between the corner, both pads and the other corner;
        # the ellipsis inherits the style of the last title cell still visible.
        last_visible = available - 2 if available >= 2 else 0
        cells = cells[:available - 1] + [('…', cells[last_visible][1])]
    padding = Style(bg=border.bg)
    canvas.put(x + 1, y, ' ', padding)
    for offset, (char, cell_style) in enumerate(cells):
        canvas.put(x + 2 + offset, y, char, cell_style)
    canvas.put(x + 2 + len(cells), y, ' ', padding)


def box(canvas: Canvas, rect, style: Style,
        title_segments: Sequence[tuple[str, Style]] = (),
        selected_style: Style | None = None) -> None:
    """Draw a one-cell border, optionally with a title on the top edge.

    The border uses rounded glyphs (``╭╮╰╯─│``) painted with ``style``. When
    ``selected_style`` is given the heavy set (``┏┓┗┛━┃``) is used and every border
    glyph is painted with it. ``title_segments`` is a list of ``(text, style)`` pairs
    painted at ``x + 2`` (after one padding space), with one trailing padding space and
    the title truncated to ``rect.w - 4`` cells (the ellipsis keeps the style of the last
    visible segment). The interior is never filled.
    """
    x, y, width, height = _bounds(rect)
    if width <= 0 or height <= 0:
        return
    if selected_style is not None:
        border = selected_style
        top_left, top_right, bottom_left, bottom_right, horizontal, vertical = HEAVY
    else:
        border = style
        top_left, top_right, bottom_left, bottom_right, horizontal, vertical = ROUNDED

    right = x + width - 1
    bottom = y + height - 1

    for column in range(x + 1, right):
        canvas.put(column, y, horizontal, border)
        canvas.put(column, bottom, horizontal, border)
    for row in range(y + 1, bottom):
        canvas.put(x, row, vertical, border)
        canvas.put(right, row, vertical, border)
    canvas.put(x, y, top_left, border)
    if right != x:
        canvas.put(right, y, top_right, border)
    if bottom != y:
        canvas.put(x, bottom, bottom_left, border)
    if right != x and bottom != y:
        canvas.put(right, bottom, bottom_right, border)

    _draw_title(canvas, x, y, width, border, title_segments)


def braille_graph(values: Sequence[float], width: int, rows: int) -> list[str]:
    """The prototype's braille graph: one value per column, newest last.

    Values are clamped to 0..1 and the list is left-padded with zeros when it has fewer
    than ``width`` entries (or cut to the last ``width``). Each row has exactly ``width``
    cells, row 0 is the top and the bottom row always shows at least one level.
    """
    width = int(width)
    rows = int(rows)
    if rows <= 0:
        return []
    if width <= 0:
        return [''] * rows

    samples = [_clamp(value) for value in values][-width:]
    samples = [0.0] * (width - len(samples)) + samples

    out = [''] * rows
    for sample in samples:
        level = max(1, _round(_clamp(sample) * rows * 4))
        for row in range(rows - 1, -1, -1):
            out[row] += LEVELS[max(0, min(4, level))]
            level -= 4
    return out


def bar(fraction: float, width: int) -> tuple[str, str]:
    """A horizontal bar: filled ``█``, at most one partial cell and empty ``░`` cells.

    ``fraction`` is clamped to 0..1 and the returned strings always add up to ``width``
    cells. A remainder above 0.12 adds one partial glyph from ``▏▎▍▌▋▊▉`` (in eighths),
    matching the prototype's finer-grained partial cell.
    """
    width = int(width)
    if width <= 0:
        return '', ''
    amount = _clamp(fraction) * width
    full = int(amount)
    filled = '█' * full
    used = full
    remainder = amount - full
    if full < width and remainder > 0.12:
        index = min(6, max(0, int(remainder * 8) - 1))
        filled += PARTIALS[index]
        used += 1
    return filled, '░' * max(0, width - used)


def tabs(canvas: Canvas, x: int, y: int, labels: Sequence[str], active: int,
         styles: dict, badges: dict[int, tuple[str, Style]] | None = None) -> list[Rect]:
    """Draw numbered tabs left to right and return one hit box per label.

    Each label is painted as the prototype's ``" N label "`` chunk with
    ``styles['active']`` when it is the active one and ``styles['normal']`` otherwise,
    followed by a badge (``badges[index] = (text, style)``) when there is one and by one
    separator space. A hit box covers the chunk and its badge (not the separator), has
    height 1 and starts at the chunk's first cell.
    """
    active_style = styles.get('active') or styles.get('normal') or Style()
    normal_style = styles.get('normal') or Style()
    badges = {} if badges is None else badges
    boxes = []
    cursor = int(x)
    row = int(y)
    for index, label in enumerate(labels):
        chunk = f' {index + 1} {label} '
        canvas.text(cursor, row, chunk,
                    active_style if index == active else normal_style)
        width = len(chunk)
        badge = badges.get(index)
        if badge is not None:
            badge_text, badge_style = badge
            canvas.text(cursor + width, row, badge_text, badge_style)
            width += len(badge_text)
        boxes.append(Rect(cursor, row, width, 1))
        cursor += width
        canvas.put(cursor, row, ' ')
        cursor += 1
    return boxes


def spinner_frame(n: int) -> str:
    """The ``n``-th frame of the prototype's ``◐◓◑◒`` spinner."""
    return SPINNER[int(n) % len(SPINNER)]


def truncate(s: str, width: int) -> str:
    """Fit ``s`` in ``width`` cells, replacing the last one with ``…`` when it is long."""
    text = str(s)
    width = int(width)
    if width <= 0:
        return ''
    if len(text) <= width:
        return text
    return text[:width - 1] + '…'
