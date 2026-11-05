"""Project-column mosaic for Wysun Cloud: layout, live cards, off lines and navigation.

Everything here is a pure function over a :class:`~wysun_core.tui.canvas.Canvas`: the
layout only reads the size and the views, the draw functions only write cells, and
navigation only reads the ordered columns. Task 11 (``cloudapp``) owns the clock, the
probes and the animations; it calls these pieces for the static frame and for each
per-card layer.

Column geometry (120 columns, three projects): one 38-wide column per project at
``x = 1, 41, 81`` (one-cell margins, two-cell gaps), project names on row 2, cards
8 rows tall from row 4, off VMs as one-line rows at the end of their column. A single
project with more than one running VM spreads them over up to three columns. When the
columns would be narrower than 34 cells the projects stack vertically, each with its
own title band. Below 60x16 the App shows its own «Agranda la terminal» message; these
functions keep returning whatever fits instead of raising.

Scrolling: ``layout(..., scroll=...)`` takes a mapping of *column key* to a row offset.
The key is the project name for a normal/stacked column and ``project#n`` for the extra
columns of a project spread over several. When ``selected`` is given, the column that
holds it is scrolled (and clamped to the content) so the selected card is fully visible;
items that do not fit are omitted from the returned dict rather than placed off-screen.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from wysun_core.tui.anim import Rect
from wysun_core.tui.canvas import Canvas, Style
from wysun_core.tui.draw import bar, box, braille_graph, spinner_frame, truncate

from .. import pricing
from ..model import Instance, Sample

__all__ = ['VmView', 'layout', 'project_titles', 'draw_mosaic', 'draw_card', 'draw_off',
           'summary', 'navigate', 'format_uptime', 'fmt1']

GAP = 2
MIN_COLUMN_WIDTH = 34
CARD_HEIGHT = 8
TITLE_ROW = 2
CARDS_ROW = 4

BUSY_TEXT = {
    'encendiendo': 'encendiendo…',
    'apagando': 'apagando…',
    'reiniciando': 'reiniciando…',
}


@dataclass
class VmView:
    """Everything the mosaic needs about one VM, kept by the UI for its whole lifetime."""

    inst: Instance
    sample: Sample | None = None
    cpu_hist: deque = field(default_factory=lambda: deque(maxlen=120))
    state: str = 'conectando'             # 'conectando' | 'activo' | 'reconectando' | 'sin-ssh'
    reason: str = ''
    busy: str | None = None               # None | 'encendiendo' | 'apagando' | 'reiniciando'
    failed: str | None = None             # name of a failed systemd unit, when known


@dataclass
class _Column:
    """One visual column: a project's card stack or one band of a stacked layout."""

    key: str
    x: int
    w: int
    top: int                              # first content row (inclusive)
    bottom: int                           # last content row (exclusive)
    views: list[VmView]


# -- small pieces ---------------------------------------------------------
def fmt1(value: float) -> str:
    """One decimal with the Spanish comma: ``11.2`` -> ``11,2``."""
    return f'{float(value):.1f}'.replace('.', ',')


def fmt2(value: float) -> str:
    """Two decimals with the Spanish comma, for the approximate cost."""
    return f'{float(value):.2f}'.replace('.', ',')


def format_uptime(seconds: float) -> str:
    """``12 d`` / ``6 h`` / ``5 min``, as the card's network line shows it."""
    seconds = max(0, int(seconds))
    if seconds >= 86400:
        return f'{seconds // 86400} d'
    if seconds >= 3600:
        return f'{seconds // 3600} h'
    return f'{seconds // 60} min'


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _level(fraction: float) -> str:
    """The prototype's colour ladder: error over 85 %, tertiary over 60 %, else primary."""
    fraction = _clamp01(fraction)
    if fraction > 0.85:
        return 'error'
    if fraction > 0.6:
        return 'tertiary'
    return 'primary'


STACK_KEY = '__stack__'          # scroll key of the stacked (narrow) layout


def _column_views(views: Iterable[VmView], project: str) -> list[VmView]:
    """Running cards first, then off lines, preserving the caller's order inside each group."""
    of_project = [view for view in views if view.inst.project == project]
    return ([view for view in of_project if view.inst.running]
            + [view for view in of_project if not view.inst.running])


def _chunks(items: list[VmView], count: int) -> list[list[VmView]]:
    """Split ``items`` into ``count`` contiguous groups, the first ones one item longer."""
    base, extra = divmod(len(items), count)
    groups = []
    start = 0
    for index in range(count):
        size = base + (1 if index < extra else 0)
        groups.append(items[start:start + size])
        start += size
    return groups


def _segments(canvas: Canvas, x: int, y: int, width: int, segments) -> int:
    """Draw ``(text, style)`` pieces clipped to ``width`` cells; returns columns used."""
    cursor = x
    remaining = max(0, int(width))
    for text, style in segments:
        if remaining <= 0:
            break
        piece = str(text)[:remaining]
        canvas.text(cursor, y, piece, style)
        cursor += len(piece)
        remaining -= len(piece)
    return cursor - x


# -- geometry -------------------------------------------------------------
def _geometry(views: list[VmView], projects: list[str], width: int, height: int):
    """Columns, title positions and title widths for the current size."""
    projects = list(dict.fromkeys(projects))
    columns: list[_Column] = []
    titles: dict[str, tuple[int, int]] = {}
    widths: dict[str, int] = {}
    if not projects or width <= 0 or height <= 0:
        return columns, titles, widths

    available = max(0, width - 2)
    count = len(projects)

    if count == 1:
        project = projects[0]
        project_views = _column_views(views, project)
        running = [view for view in project_views if view.inst.running]
        stopped = [view for view in project_views if not view.inst.running]
        spread = min(3, len(running))
        while spread > 1 and (available - GAP * (spread - 1)) // spread < MIN_COLUMN_WIDTH:
            spread -= 1
        if spread <= 1:
            column_width = max(1, available)
            keys = [project]
            groups = [project_views]
        else:
            column_width = max(1, (available - GAP * (spread - 1)) // spread)
            keys = [f'{project}#{index}' for index in range(spread)]
            groups = _chunks(running, spread)
            if stopped:
                groups[-1] = groups[-1] + stopped
        for index, (key, group) in enumerate(zip(keys, groups)):
            columns.append(_Column(key, 1 + index * (column_width + GAP), column_width,
                                   CARDS_ROW, max(CARDS_ROW, height - 1), group))
        titles[project] = (1, TITLE_ROW)
        widths[project] = column_width
        return columns, titles, widths

    column_width = (available - GAP * (count - 1)) // count
    if available > 0 and column_width >= MIN_COLUMN_WIDTH:
        for index, project in enumerate(projects):
            x = 1 + index * (column_width + GAP)
            columns.append(_Column(project, x, column_width, CARDS_ROW,
                                   max(CARDS_ROW, height - 1), _column_views(views, project)))
            titles[project] = (x, TITLE_ROW)
            widths[project] = column_width
        return columns, titles, widths

    # Narrow terminal: projects stacked in one scrollable list (see _stack).
    return columns, titles, widths


def _stacked(projects: list[str], width: int) -> bool:
    """Whether the projects no longer fit side by side and are stacked vertically."""
    count = len(dict.fromkeys(projects))
    if count <= 1:
        return False
    available = max(0, width - 2)
    return available <= 0 or (available - GAP * (count - 1)) // count < MIN_COLUMN_WIDTH


def _stack(views: list[VmView], projects: list[str], width: int, height: int,
           scroll: dict[str, int] | None, selected: str | None):
    """Stacked layout: every project's title and items in one list that scrolls as a whole.

    The list scrolls (key ``STACK_KEY`` in ``scroll``) so the selected item is fully
    visible; titles and items that do not fit the viewport are omitted.
    Returns ``(rects, titles, widths)``.
    """
    projects = list(dict.fromkeys(projects))
    inner = max(1, width - 2)
    entries = []                        # (kind, project|view, virtual y, height)
    cursor = 0
    for project in projects:
        entries.append(('title', project, cursor, 1))
        cursor += 2                         # title row + one blank row, like the columns
        for view in _column_views(views, project):
            item = CARD_HEIGHT if view.inst.running else 1
            entries.append(('view', view, cursor, item))
            cursor += item
        cursor += 1                         # gap before the next project
    total = cursor
    viewport = max(0, height - 1 - TITLE_ROW)
    offset = max(0, int((scroll or {}).get(STACK_KEY, 0)))
    offset = min(offset, max(0, total - viewport))
    for kind, value, y, item in entries:
        if kind == 'view' and value.inst.alias == selected:
            if y < offset or y + item > offset + viewport:
                offset = min(y, max(0, total - viewport))
            break
    rects: dict[str, Rect] = {}
    titles: dict[str, tuple[int, int]] = {}
    widths: dict[str, int] = {}
    for kind, value, y, item in entries:
        start = y - offset
        if start < 0 or start + item > viewport:
            continue
        row = TITLE_ROW + start
        if kind == 'title':
            titles[value] = (1, row)
            widths[value] = inner
        elif value.inst.running:
            rects[value.inst.alias] = Rect(1, row, inner, item)
        else:
            rects[value.inst.alias] = Rect(2, row, max(1, inner - 1), 1)
    return rects, titles, widths


def project_titles(views: list[VmView], projects: list[str], width: int,
                   height: int, scroll: dict[str, int] | None = None,
                   selected: str | None = None) -> dict[str, tuple[int, int]]:
    """Where each project name goes: ``{project: (x, y)}``, row 2 in the normal layout."""
    if _stacked(projects, width):
        return _stack(views, projects, width, height, scroll, selected)[1]
    return _geometry(views, projects, width, height)[1]


def _place(column: _Column, selected: str | None, scroll: dict[str, int] | None,
           rects: dict[str, Rect]) -> None:
    """Place a column's items, scrolling the selected one into view when needed."""
    heights = [CARD_HEIGHT if view.inst.running else 1 for view in column.views]
    total = sum(heights)
    viewport = max(0, column.bottom - column.top)
    offset = max(0, int((scroll or {}).get(column.key, 0)))
    offset = min(offset, max(0, total - viewport))

    aliases = [view.inst.alias for view in column.views]
    if selected in aliases:
        index = aliases.index(selected)
        top = sum(heights[:index])
        bottom = top + heights[index]
        if top < offset or bottom > offset + viewport:
            offset = min(top, max(0, total - viewport))

    cursor = 0
    for view, height in zip(column.views, heights):
        start = cursor - offset
        end = start + height
        cursor += height
        if start < 0 or end > viewport:
            continue                        # omitted, not parked off-screen
        if view.inst.running:
            rects[view.inst.alias] = Rect(column.x, column.top + start, column.w, height)
        else:
            rects[view.inst.alias] = Rect(column.x + 1, column.top + start,
                                          max(1, column.w - 1), 1)


def layout(views: list[VmView], projects: list[str], width: int, height: int,
           scroll: dict[str, int] | None = None,
           selected: str | None = None) -> dict[str, Rect]:
    """The rectangle of every visible card and off line, keyed by ``inst.alias``.

    See the module docstring for the column rules, the ``scroll`` keys and the promise
    that a column containing ``selected`` scrolls until that item is fully visible.
    Items that do not fit are omitted.
    """
    if _stacked(projects, width):
        return _stack(views, projects, width, height, scroll, selected)[0]
    columns, _, _ = _geometry(views, projects, width, height)
    rects: dict[str, Rect] = {}
    for column in columns:
        _place(column, selected, scroll, rects)
    return rects


# -- card rendering -------------------------------------------------------
def _title_segments(view: VmView, palette, spin: int):
    inst = view.inst
    muted = Style(fg=palette['onSurfaceVariant'])
    if view.busy:
        dot = (spinner_frame(spin), Style(fg=palette['tertiary']))
        extra = (BUSY_TEXT.get(view.busy, view.busy), Style(fg=palette['tertiary']))
    elif view.state in ('conectando', 'reconectando'):
        label = 'conectando…' if view.state == 'conectando' else 'reconectando…'
        dot = (spinner_frame(spin), Style(fg=palette['tertiary']))
        extra = (label, Style(fg=palette['tertiary']))
    elif view.failed:
        dot = ('▲', Style(fg=palette['tertiary']))
        extra = (inst.machine_type, muted)
    else:
        dot = ('●', Style(fg=palette['success']))
        extra = (inst.machine_type, muted)
    segments = [dot, (' ', Style(fg=palette['onSurface'])),
                (inst.name, Style(fg=palette['onSurface'], bold=True))]
    if extra[0]:
        segments.extend([(' ', Style(fg=palette['onSurface'])), extra])
    return segments


def _mount_of(sample: Sample):
    """The root mount when present, else the first one; ``None`` when the probe sent none."""
    for mount in sample.mounts:
        if mount[0] == '/':
            return mount
    return sample.mounts[0] if sample.mounts else None


def _state_text(view: VmView):
    """The single line a card shows before it has a sample."""
    if view.state == 'sin-ssh':
        reason = f' · {view.reason}' if view.reason else ''
        return f'sin SSH{reason}'
    if view.state == 'reconectando':
        return 'reconectando…'
    return 'conectando…'


def draw_card(canvas: Canvas, rect: Rect, view: VmView, palette, selected: bool,
              spin: int) -> None:
    """Draw one live VM card: border with title, CPU graph, RAM, root disk, net and top."""
    if rect.w <= 0 or rect.h <= 0:
        return
    surface = palette['surface']
    canvas.fill(rect, ' ', Style(bg=surface))
    border = Style(fg=palette['outlineVariant'])
    box(canvas, rect, border, title_segments=_title_segments(view, palette, spin),
        selected_style=Style(fg=palette['primary']) if selected else None)

    inner_x = rect.x + 2
    inner_w = max(0, rect.w - 4)
    if inner_w <= 0 or rect.h < 2:
        return
    sample = view.sample
    if sample is None:
        message = _state_text(view)
        style = Style(fg=palette['error'] if view.state == 'sin-ssh'
                      else palette['onSurfaceVariant'])
        _segments(canvas, inner_x, rect.y + 1, inner_w, [(message, style)])
        return

    busy = view.busy is not None
    text = palette['onSurface']
    muted = palette['onSurfaceVariant']
    dim = Style(dim=busy)
    row = rect.y + 1

    cpu = _clamp01(sample.cpu)
    graph_width = max(4, min(inner_w - 5, rect.w - 10))
    history = list(view.cpu_hist) or [cpu]
    graph = braille_graph(history, graph_width, 2)
    colour = Style(fg=palette[_level(cpu)], dim=busy)
    percent = '  —' if busy else f'{round(cpu * 100):3d}%'

    if row < rect.y + rect.h - 1:
        _segments(canvas, inner_x, row, inner_w,
                  [(graph[0], colour), (' ', dim), (percent, colour)])
    row += 1
    if row < rect.y + rect.h - 1:
        _segments(canvas, inner_x, row, inner_w,
                  [(graph[1], colour), (' ', dim), ('CPU', Style(fg=muted, dim=busy))])

    ram = _clamp01(sample.ram_used_gb / sample.ram_total_gb) if sample.ram_total_gb else 0.0
    bar_width = max(3, min(21, inner_w - 13))
    ram_fill, ram_empty = bar(ram, bar_width)
    total_gb = (f'{int(round(sample.ram_total_gb))}'
                if abs(sample.ram_total_gb - round(sample.ram_total_gb)) < 1e-9
                else fmt1(sample.ram_total_gb))
    row += 1
    if row < rect.y + rect.h - 1:
        _segments(canvas, inner_x, row, inner_w,
                  [('RAM ', Style(fg=muted, dim=busy)),
                   (ram_fill, Style(fg=palette[_level(ram)], dim=busy)),
                   (ram_empty, Style(fg=palette['outlineVariant'], dim=busy)),
                   (' ', dim),
                   (f'{fmt1(sample.ram_used_gb)}/{total_gb}G',
                    Style(fg=muted, dim=busy))])

    mount = _mount_of(sample)
    used, size = (mount[1], mount[2]) if mount else (0.0, 0.0)
    disk = _clamp01(used / size) if size else 0.0
    disk_fill, disk_empty = bar(disk, bar_width)
    warning = disk > 0.85
    row += 1
    if row < rect.y + rect.h - 1:
        value = f'{round(disk * 100)}%' + (' ▲' if warning else '')
        _segments(canvas, inner_x, row, inner_w,
                  [('/   ', Style(fg=muted, dim=busy)),
                   (disk_fill, Style(fg=palette[_level(disk)], dim=busy)),
                   (disk_empty, Style(fg=palette['outlineVariant'], dim=busy)),
                   (' ', dim),
                   (value, Style(fg=palette['error'] if warning else muted, dim=busy))])

    row += 1
    if row < rect.y + rect.h - 1:
        _segments(canvas, inner_x, row, inner_w,
                  [(f'↓{fmt1(sample.rx_mbs)} ↑{fmt1(sample.tx_mbs)} MB/s · '
                    f'{format_uptime(sample.uptime_s)}', Style(fg=muted, dim=busy))])

    row += 1
    if row < rect.y + rect.h - 1:
        pieces = [('top ', Style(fg=muted, dim=busy))]
        if sample.top:
            _, top_cpu, _, command = sample.top[0]
            pieces.extend([(f'{command} {round(top_cpu)}%', Style(fg=text, dim=busy))])
        if view.failed:
            pieces.extend([(' · ', Style(fg=muted, dim=busy)),
                           (f'{view.failed} ✗', Style(fg=palette['error'], dim=busy))])
        _segments(canvas, inner_x, row, inner_w, pieces)


def draw_off(canvas: Canvas, rect: Rect, view: VmView, palette, selected: bool,
             spin: int) -> None:
    """Draw an off VM as one line: ``○ name  zone  apagada`` or a start spinner."""
    if rect.w <= 0 or rect.h <= 0:
        return
    background = palette['primaryContainer'] if selected else palette['surface']
    canvas.fill(rect, ' ', Style(bg=background))
    base = palette['onPrimaryContainer'] if selected else palette['onSurfaceVariant']
    head_style = Style(fg=base, dim=not selected)
    inst = view.inst

    label = BUSY_TEXT.get(view.busy or '', 'apagada')
    if view.busy:
        prefix = f'{spinner_frame(spin)} {inst.name}  {inst.zone}'
    else:
        prefix = f'○ {inst.name}  {inst.zone}'
    label_style = Style(fg=palette['tertiary'] if view.busy else base,
                        bold=selected, dim=not selected and not view.busy)
    head_width = max(1, rect.w - len(label) - 1)
    head = truncate(prefix, head_width)
    _segments(canvas, rect.x, rect.y, rect.w,
              [(head, head_style), (' ', head_style), (label, label_style)])


# -- header and footer ----------------------------------------------------
def summary(views: list[VmView]) -> str:
    """``4 encendidas · 3 apagadas · ≈ 0,29 USD/h`` for the header."""
    running = [view for view in views if view.inst.running]
    stopped = len(views) - len(running)
    cost = sum(pricing.hourly(view.inst.machine_type, view.inst.zone) or 0.0
               for view in running if not view.inst.spot)
    return f'{len(running)} encendidas · {stopped} apagadas · ≈ {fmt2(cost)} USD/h'


# -- the whole static mosaic ----------------------------------------------
def draw_mosaic(canvas: Canvas, views: list[VmView], projects: list[str], palette,
                selected: str | None, spin: int,
                scroll: dict[str, int] | None = None) -> None:
    """Draw the project titles and every visible card/off line at its layout rect."""
    if _stacked(projects, canvas.width):
        rects, titles, widths = _stack(views, projects, canvas.width, canvas.height,
                                       scroll, selected)
    else:
        _, titles, widths = _geometry(views, projects, canvas.width, canvas.height)
        rects = layout(views, projects, canvas.width, canvas.height, scroll, selected)

    for project, (x, y) in titles.items():
        if y < 0 or y >= canvas.height:
            continue
        canvas.text(x, y, truncate(project, widths.get(project, canvas.width - x)),
                    Style(fg=palette['onSurface'], bold=True))

    for view in views:
        rect = rects.get(view.inst.alias)
        if rect is None:
            continue
        if view.inst.running:
            draw_card(canvas, rect, view, palette, view.inst.alias == selected, spin)
        else:
            draw_off(canvas, rect, view, palette, view.inst.alias == selected, spin)


# -- keyboard navigation --------------------------------------------------
def navigate(views: list[VmView], projects: list[str], selected_alias: str | None,
             key_name: str, width: int = 200, height: int = 60) -> str:
    """Move the selection the way the mosaic is drawn at ``width`` × ``height``.

    Columns are the drawn ones (a single project spread over several columns counts as
    several); inside one, running cards come first, then off lines. Left/right go to the
    same index of the neighbour column; up/down stay in the column. In the stacked
    narrow layout everything is one list and left/right behave like up/down.
    Movement clamps at every edge; ``home``/``end`` jump within the column.
    """
    projects = list(dict.fromkeys(projects))
    if _stacked(projects, width):
        flat = [view for project in projects for view in _column_views(views, project)]
        columns = [flat] if flat else []
        key_name = {'left': 'up', 'right': 'down'}.get(key_name, key_name)
    else:
        columns = [column.views for column in _geometry(views, projects, width, height)[0]]
    columns = [column for column in columns if column]
    if not columns:
        return selected_alias or ''

    aliases = [[view.inst.alias for view in column] for column in columns]
    current_column = 0
    current_index = 0
    found = False
    for index, column in enumerate(aliases):
        if selected_alias in column:
            current_column = index
            current_index = column.index(selected_alias)
            found = True
            break
    if not found:
        return aliases[0][0]

    if key_name == 'up':
        current_index = max(0, current_index - 1)
    elif key_name == 'down':
        current_index = min(len(aliases[current_column]) - 1, current_index + 1)
    elif key_name == 'home':
        current_index = 0
    elif key_name == 'end':
        current_index = len(aliases[current_column]) - 1
    elif key_name in ('left', 'right'):
        step = -1 if key_name == 'left' else 1
        target = max(0, min(len(aliases) - 1, current_column + step))
        if target != current_column:
            current_column = target
            current_index = min(current_index, len(aliases[current_column]) - 1)
    return aliases[current_column][current_index]
