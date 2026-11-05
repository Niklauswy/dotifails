"""A cell canvas: characters plus style, with clipping, blending and layers.

Every character occupies exactly one cell (wide characters are out of scope:
braille, box drawing and block elements are all single-width).
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Iterator

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Style:
    """How one cell is painted."""

    fg: RGB | None = None
    bg: RGB | None = None
    bold: bool = False
    dim: bool = False
    underline: bool = False


def _bounds(rect) -> tuple[int, int, int, int]:
    """Accept a ``Rect``-like object or a plain ``(x, y, w, h)`` tuple."""
    if all(hasattr(rect, name) for name in ('x', 'y', 'w', 'h')):
        return int(rect.x), int(rect.y), int(rect.w), int(rect.h)
    x, y, w, h = rect
    return int(x), int(y), int(w), int(h)


def _mix(value: RGB, toward: RGB, amount: float) -> RGB:
    return tuple(round(a + (b - a) * amount) for a, b in zip(value, toward))  # type: ignore[return-value]


def _intersect(first, second):
    if first is None:
        return second
    if second is None:
        return first
    x = max(first[0], second[0])
    y = max(first[1], second[1])
    right = min(first[0] + first[2], second[0] + second[2])
    bottom = min(first[1] + first[3], second[1] + second[3])
    return x, y, max(0, right - x), max(0, bottom - y)


class Canvas:
    """A flat grid of ``(char, Style)`` cells."""

    def __init__(self, width: int, height: int, bg: RGB):
        self.width = int(width)
        self.height = int(height)
        self.bg = tuple(bg)
        blank = Style(bg=self.bg)
        self._cells: list[tuple[str, Style]] = [(' ', blank) for _ in range(self.width * self.height)]
        # Visible rectangle as (x, y, w, h); None means the whole canvas.
        self._clip: tuple[int, int, int, int] | None = None

    # -- geometry ---------------------------------------------------------
    def _inside(self, x: int, y: int) -> bool:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        if self._clip is None:
            return True
        cx, cy, cw, ch = self._clip
        return cx <= x < cx + cw and cy <= y < cy + ch

    def _visible(self, rect) -> Iterator[tuple[int, int]]:
        x, y, w, h = _bounds(rect)
        area = _intersect((x, y, w, h), (0, 0, self.width, self.height))
        area = _intersect(area, self._clip)
        if area is None:
            return
        ax, ay, aw, ah = area
        for row in range(ay, ay + ah):
            for column in range(ax, ax + aw):
                yield column, row

    # -- painting ---------------------------------------------------------
    def put(self, x: int, y: int, char: str, style: Style | None = None) -> None:
        if not char or not self._inside(x, y):
            return
        index = y * self.width + x
        if style is None:
            style = Style(bg=self.bg)
        elif style.bg is None:
            # No background means "keep what is under it": never the terminal's default colour.
            style = replace(style, bg=self._cells[index][1].bg or self.bg)
        self._cells[index] = (char[0], style)

    def text(self, x: int, y: int, s: str, style: Style, max_width: int | None = None) -> int:
        written = 0
        for offset, char in enumerate(s):
            if max_width is not None and offset >= max_width:
                break
            column = x + offset
            if self._inside(column, y):
                self.put(column, y, char, style)
                written += 1
        return written

    def fill(self, rect, char: str = ' ', style: Style | None = None) -> None:
        if style is None:
            style = Style(bg=self.bg)
        for x, y in self._visible(rect):
            self.put(x, y, char, style)

    def blend(self, rect, toward: RGB, amount: float) -> None:
        amount = max(0.0, min(1.0, float(amount)))
        toward = tuple(toward)
        for x, y in self._visible(rect):
            char, style = self._cells[y * self.width + x]
            fg = _mix(style.fg, toward, amount) if style.fg is not None else None
            bg = _mix(style.bg, toward, amount) if style.bg is not None else None
            self._cells[y * self.width + x] = (
                char,
                Style(fg=fg, bg=bg, bold=style.bold, dim=style.dim, underline=style.underline),
            )

    def paste(self, other: 'Canvas', x: int, y: int, opacity: float = 1.0) -> None:
        """Copy ``other`` at ``(x, y)``; below 1.0 its colours mix toward what is underneath."""
        opacity = max(0.0, min(1.0, float(opacity)))
        if opacity <= 0.0:
            return
        fade = 1.0 - opacity
        for source_y in range(other.height):
            target_y = y + source_y
            for source_x in range(other.width):
                target_x = x + source_x
                if not self._inside(target_x, target_y):
                    continue
                index = target_y * self.width + target_x
                under = self._cells[index][1].bg or self.bg
                char, style = other.cell(source_x, source_y)
                bg = style.bg if style.bg is not None else under
                fg = style.fg
                if fade > 0.0:
                    fg = _mix(fg, under, fade) if fg is not None else None
                    bg = _mix(bg, under, fade)
                if bg != style.bg or fg != style.fg:
                    style = Style(fg=fg, bg=bg, bold=style.bold, dim=style.dim, underline=style.underline)
                self._cells[index] = (char, style)

    # -- reading ----------------------------------------------------------
    def cell(self, x: int, y: int) -> tuple[str, Style]:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return ' ', Style(bg=self.bg)
        return self._cells[y * self.width + x]

    def row_text(self, y: int) -> str:
        if not (0 <= y < self.height):
            return ''
        start = y * self.width
        return ''.join(char for char, _ in self._cells[start:start + self.width])

    # -- clipping ---------------------------------------------------------
    @contextmanager
    def clip(self, rect) -> Iterator[None]:
        previous = self._clip
        self._clip = _intersect(previous, _bounds(rect))
        try:
            yield
        finally:
            self._clip = previous
