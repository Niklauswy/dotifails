"""Diff one canvas against the previous frame and write it as ANSI bytes.

The whole frame travels in one synchronized update (``CSI ? 2026 h`` … ``CSI ?
2026 l``), and only cells that changed are addressed, one cursor move per run
of consecutive changed cells.
"""
from __future__ import annotations

from functools import lru_cache

from .canvas import Canvas, Style

SYNC_BEGIN = '\x1b[?2026h'
SYNC_END = '\x1b[?2026l'
RESET = '\x1b[0m'

_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)


def _cube_palette() -> list[tuple[int, int, int]]:
    palette = []
    for index in range(216):
        palette.append((
            _CUBE_LEVELS[index // 36],
            _CUBE_LEVELS[(index // 6) % 6],
            _CUBE_LEVELS[index % 6],
        ))
    for step in range(24):
        grey = 8 + step * 10
        palette.append((grey, grey, grey))
    return palette


_PALETTE = _cube_palette()


@lru_cache(maxsize=4096)
def _nearest_256(rgb: tuple[int, int, int]) -> int:
    red, green, blue = rgb
    best = 0
    best_distance = None
    for index, (r, g, b) in enumerate(_PALETTE):
        distance = (r - red) ** 2 + (g - green) ** 2 + (b - blue) ** 2
        if best_distance is None or distance < best_distance:
            best = index
            best_distance = distance
    # The cube starts at xterm colour 16; the grey ramp follows it.
    return best + 16


class Screen:
    """Turn a canvas into the ANSI bytes that update the terminal."""

    def __init__(self, truecolor: bool = True):
        self.truecolor = bool(truecolor)

    def _colour(self, rgb: tuple[int, int, int], background: bool) -> str:
        if self.truecolor:
            return f'{48 if background else 38};2;{rgb[0]};{rgb[1]};{rgb[2]}'
        return f'{48 if background else 38};5;{_nearest_256(rgb)}'

    def _sgr(self, style: Style) -> str:
        parts = ['0']
        if style.bold:
            parts.append('1')
        if style.dim:
            parts.append('2')
        if style.underline:
            parts.append('4')
        if style.fg is not None:
            parts.append(self._colour(style.fg, False))
        if style.bg is not None:
            parts.append(self._colour(style.bg, True))
        return '\x1b[' + ';'.join(parts) + 'm'

    @staticmethod
    def _cell(canvas: Canvas, x: int, y: int) -> tuple[str, Style]:
        return canvas.cell(x, y)

    def render(self, prev: Canvas | None, cur: Canvas) -> bytes:
        out: list[str] = []
        full = prev is None or prev.width != cur.width or prev.height != cur.height
        painted = False

        if full:
            for y in range(cur.height):
                out.append(f'\x1b[{y + 1};1H')
                last_style: Style | None = None
                for x in range(cur.width):
                    char, style = self._cell(cur, x, y)
                    if style != last_style:
                        out.append(self._sgr(style))
                        last_style = style
                    out.append(char)
                    painted = True
        else:
            last_style = None
            for y in range(cur.height):
                x = 0
                while x < cur.width:
                    if self._cell(cur, x, y) == self._cell(prev, x, y):
                        x += 1
                        continue
                    start = x
                    while x < cur.width and self._cell(cur, x, y) != self._cell(prev, x, y):
                        x += 1
                    out.append(f'\x1b[{y + 1};{start + 1}H')
                    for column in range(start, x):
                        char, style = self._cell(cur, column, y)
                        if style != last_style:
                            out.append(self._sgr(style))
                            last_style = style
                        out.append(char)
                        painted = True

        if painted:
            out.append(RESET)
        return (SYNC_BEGIN + ''.join(out) + SYNC_END).encode('utf-8')
