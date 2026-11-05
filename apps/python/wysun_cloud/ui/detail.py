"""The VM detail screen: the data line, the seven tabs and their content.

Everything here is a pure function over a :class:`~wysun_core.tui.canvas.Canvas`, like
``mosaic``: the app owns the clock, the SSH probes and the animations, and these
functions only decide cells. ``body_lines`` returns a tab as a list of lines, each a list
of ``(text, Style)`` segments, so the app can reveal them one by one (14 ms apart, as the
prototype) and slide the whole body when the tab changes; ``draw_tab`` paints those lines
inside a rectangle, applying a row ``scroll`` and clipping what does not fit, and returns
the total height in rows so the caller can size its scrollbar.

Header geometry: the detail area starts at the rectangle the caller passes. ``HEADER_ROWS``
rows are the data line, one blank row, the numbered tabs and a rule; the body follows.

Data that has not arrived yet is ``None`` in :class:`DetailData` and renders «cargando…»;
an empty list means "loaded and empty" and renders a short Spanish line («sin reglas»).
A tab whose command failed renders the error text instead of its content, and a tab that
ran without sudo says «necesita permisos». Colours come only from palette roles.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from wysun_core.tui.canvas import Canvas, Style
from wysun_core.tui.draw import bar, braille_graph, tabs, truncate

from .. import pricing
from ..model import TabData
# Reused from the mosaic instead of copied: the Spanish number/uptime formatting, the
# prototype's colour ladder and the small segment writer (the last three are private
# there; they are imported on purpose, see the plan's "import and reuse them").
from .mosaic import (BUSY_TEXT, VmView, _clamp01, _level, _segments, _state_text,
                     fmt1, fmt2, format_uptime)

__all__ = ['TABS', 'HEADER_ROWS', 'DetailData', 'draw_detail_header', 'draw_tab', 'body_lines']

TABS = ['Resumen', 'Procesos', 'Disco', 'Red', 'Servicios', 'Registro', 'Historial']
HEADER_ROWS = 4                       # data line, blank, tabs, rule

SAFE_FIREWALL_PORTS = frozenset({'22', '80', '443'})
OPEN_ADDRESSES = frozenset({'0.0.0.0', '*', '::', '[::]'})
DAYS = ('lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom')
MONTHS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun',
          'jul', 'ago', 'sep', 'oct', 'nov', 'dic')

STATUS_TEXT = {
    'RUNNING': 'encendida',
    'TERMINATED': 'apagada',
    'STOPPED': 'apagada',
    'STOPPING': 'apagando…',
    'SUSPENDING': 'suspendiendo…',
    'SUSPENDED': 'suspendida',
    'STARTING': 'encendiendo…',
    'REPAIRING': 'reparando…',
    'PROVISIONING': 'preparando…',
    'STAGING': 'preparando…',
}

PORT_RE = re.compile(r'^(\S+):(\d+)$')        # 0.0.0.0:22, [::]:22, :::22, *:22
JOURNAL_SHOWN = 200                             # newest entries kept on screen (scrollable)
PROCESS_RE = re.compile(r'users:\(\("([^"]+)"')


@dataclass
class DetailData:
    """Everything the detail screen shows beyond the live ``VmView``.

    ``None`` means "not loaded yet" (the block says «cargando…»); an empty list or dict
    entry means "loaded and empty" (the block says «sin …»). ``errors`` uses the same
    block names: ``ports``, ``journal``, ``docker``, ``failed``, ``du``, ``history``,
    ``operations``, ``firewall`` and ``disks``.
    """

    tabs: dict[str, TabData] = field(default_factory=dict)
    history: dict[int, list[tuple[float, float]]] | None = None
    operations: list[dict] | None = None
    firewall: list[dict] | None = None
    disks: list[dict] | None = None
    errors: dict[str, str] = field(default_factory=dict)


# -- styles ---------------------------------------------------------------
def _text(palette):
    return Style(fg=palette['onSurface'])


def _muted(palette):
    return Style(fg=palette['onSurfaceVariant'])


def _bold(palette):
    return Style(fg=palette['onSurface'], bold=True)


def _dim(palette):
    return Style(fg=palette['onSurfaceVariant'], dim=True)


def _ok(palette):
    return Style(fg=palette['success'])


def _warn(palette):
    return Style(fg=palette['tertiary'])


def _block_error(data, kind):
    """A tab block's failure: ``DetailData.errors`` first, then the ``TabData.error`` of
    the command result, so a failed or missing command never reads as "nothing found"."""
    error = data.errors.get(kind)
    if error:
        return error
    tab = data.tabs.get(kind)
    return getattr(tab, 'error', None) or None


def _error(palette):
    return Style(fg=palette['error'])


def _accent(palette):
    return Style(fg=palette['primary'])


def _key(palette):
    return Style(fg=palette['primary'], bold=True)


def _level_style(palette, fraction):
    """The mosaic's ladder (error > 85 %, tertiary > 60 %, else primary)."""
    return Style(fg=palette[_level(fraction)])


def _outline(palette):
    return Style(fg=palette['outlineVariant'])


# -- line helpers ---------------------------------------------------------
def _line(*segments):
    """One body line from ``(text, style)`` pieces, dropping the empty ones."""
    return [(str(text), style) for text, style in segments if str(text)]


def _fit(segments, width, ellipsis=False):
    """Truncate a line to ``width`` cells, optionally ending it with an ellipsis."""
    width = max(0, int(width))
    total = sum(len(str(text)) for text, _ in segments)
    shortened = ellipsis and total > width and width > 0
    limit = width - 1 if shortened else width
    out = []
    used = 0
    for text, style in segments:
        if used >= limit:
            break
        piece = str(text)[:limit - used]
        if piece:
            out.append((piece, style))
            used += len(piece)
    if shortened:
        out.append(('…', out[-1][1] if out else segments[0][1]))
    return out


def _merge_columns(left, right, left_width, width):
    """Pair two lists of lines into a left column of ``left_width`` and a right one."""
    right_width = max(0, int(width) - int(left_width) - 2)
    if right_width <= 0:
        return [_fit(line, left_width) for line in left]
    rows = []
    for index in range(max(len(left), len(right))):
        left_line = _fit(left[index], left_width) if index < len(left) else []
        right_line = _fit(right[index], right_width) if index < len(right) else []
        if not right_line:
            rows.append(left_line)
            continue
        used = sum(len(text) for text, _ in left_line)
        pad_style = left_line[-1][1] if left_line else right_line[0][1]
        rows.append(left_line + [(' ' * max(0, left_width - used) + '  ', pad_style)] + right_line)
    return rows


def _gb(value):
    """A whole number of GB without decimals when it is exact (``16`` not ``16,0``)."""
    value = float(value)
    if abs(value - round(value)) < 1e-9:
        return f'{int(round(value))}'
    return fmt1(value)


def _size_text(kilobytes):
    """``du`` kilobytes as ``41,2 GB`` / ``18,7 MB`` / ``900 kB``."""
    if kilobytes >= 1024 * 1024:
        return f'{fmt1(kilobytes / (1024 * 1024))} GB'
    if kilobytes >= 1024:
        return f'{fmt1(kilobytes / 1024)} MB'
    return f'{int(kilobytes)} kB'


def _parse_iso(text):
    """An ISO timestamp as seconds since the epoch, or None."""
    if not isinstance(text, str) or not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def _uptime(view):
    """``12 d`` from the live sample, else from the instance's start time."""
    if view.sample is not None:
        return format_uptime(view.sample.uptime_s)
    if view.inst.started:
        return format_uptime(max(0.0, time.time() - view.inst.started))
    return ''


def _age(timestamp):
    """``snapshot: hace 1 d`` / ``snapshot: nunca`` for a gcloud timestamp."""
    stamp = _parse_iso(timestamp)
    if stamp is None:
        return 'snapshot: —'
    return 'snapshot: hace ' + format_uptime(max(0.0, time.time() - stamp))


def _op_time(text):
    """``hoy 13:42`` / ``ayer 09:10`` / ``20 oct 10:00`` for an operation's insertTime."""
    stamp = _parse_iso(text)
    if stamp is None:
        return '—'
    moment = datetime.fromtimestamp(stamp)
    today = datetime.now()
    if moment.date() == today.date():
        return 'hoy ' + moment.strftime('%H:%M')
    if (today.date() - moment.date()).days == 1:
        return 'ayer ' + moment.strftime('%H:%M')
    return f'{moment.day:02d} {MONTHS[moment.month - 1]} {moment.strftime("%H:%M")}'


def _clock(stamp):
    return datetime.fromtimestamp(stamp).strftime('%H:%M')


# -- header ---------------------------------------------------------------
def _status_segments(view, palette):
    if view.busy:
        return [(BUSY_TEXT.get(view.busy, view.busy), _warn(palette))]
    if view.inst.running:
        return [('encendida', _ok(palette))]
    return [(STATUS_TEXT.get(view.inst.status, view.inst.status.lower() or 'desconocida'),
             _muted(palette))]


def _data_line(view, palette, width):
    """``name · status · type · zone · IPs · price · os · uptime``.

    The price comes before the OS and the uptime so a 120-column terminal still shows
    it; the rest truncates with the width.
    """
    inst = view.inst
    pieces = [(inst.name, _bold(palette)), ('  ', _muted(palette))]
    pieces.extend(_status_segments(view, palette))
    if inst.spot:
        pieces.append((' · spot', _warn(palette)))
    if inst.external_ip:
        addresses = f'{inst.external_ip} / {inst.internal_ip or "—"}'
    elif inst.internal_ip:
        addresses = f'sin IP externa / {inst.internal_ip}'
    else:
        addresses = 'sin IP'
    fields = [(inst.machine_type or 'tipo desconocido', _muted(palette)),
              (inst.zone or 'zona desconocida', _muted(palette)),
              (addresses, _muted(palette))]
    price = pricing.hourly(inst.machine_type, inst.zone)
    if price is None:
        fields.append(('precio desconocido', _muted(palette)))
    else:
        fields.append((f'≈ {fmt2(price)} US$/h', _accent(palette)))
    if inst.os:
        fields.append((inst.os, _muted(palette)))
    uptime = _uptime(view)
    if uptime:
        fields.append((f'arriba {uptime}', _muted(palette)))
    for text, style in fields:
        pieces.append((' · ', _muted(palette)))
        pieces.append((text, style))
    return _fit(pieces, width, ellipsis=True)


def draw_detail_header(canvas: Canvas, rect, view: VmView, palette, tab: int,
                       badges=None) -> list:
    """Draw the data line, the numbered tabs and a rule; return the tab hit boxes."""
    x, y, width, height = int(rect.x), int(rect.y), int(rect.w), int(rect.h)
    if width <= 0 or height <= 0:
        return []
    _segments(canvas, x, y, width, _data_line(view, palette, width))
    boxes = []
    if height >= 3:
        index = max(0, min(len(TABS) - 1, int(tab)))
        styles = {'active': Style(fg=palette['onPrimary'], bg=palette['primary'], bold=True),
                  'normal': _muted(palette)}
        boxes = tabs(canvas, x, y + 2, TABS, index, styles, badges)
    if height >= 4:
        canvas.text(x, y + 3, '─' * width, _outline(palette))
    return boxes


# -- Resumen --------------------------------------------------------------
def _red_line(view, sample, palette, width):
    """The one-row network line; graphs only when the view carries rate histories."""
    graph_width = max(4, (width - 32) // 2)
    pieces = [('RED   ', _bold(palette)), ('↓ ', _ok(palette))]
    rx_history = getattr(view, 'rx_hist', None)
    if rx_history:
        pieces.append((braille_graph(list(rx_history), graph_width, 1)[0], _ok(palette)))
    pieces.append((f'{fmt1(sample.rx_mbs)} MB/s    ', _text(palette)))
    pieces.append(('↑ ', _warn(palette)))
    tx_history = getattr(view, 'tx_hist', None)
    if tx_history:
        pieces.append((braille_graph(list(tx_history), graph_width, 1)[0], _warn(palette)))
    pieces.append((f'{fmt1(sample.tx_mbs)} MB/s', _text(palette)))
    return _line(*pieces)


def _failed_name(raw):
    return str(raw).strip().split(None, 1)[0] if str(raw).strip() else ''


def _docker_items(lines):
    """``(running names, other names)`` from ``docker ps -a --format {{json .}}``."""
    running, other = [], []
    for raw in lines:
        try:
            item = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(item, dict):
            continue
        name = str(item.get('Names') or item.get('Name') or '?')
        if str(item.get('State') or '') == 'running':
            running.append(name)
        else:
            other.append(name)
    return running, other


def _health_lines(view, data, palette):
    """The Salud block: systemd, docker and the journal, with loading/empty/error states."""
    out = []
    error = _block_error(data, 'failed')
    tab = data.tabs.get('failed')
    if error:
        out.append(_line(('✗ ', _error(palette)), (truncate(error, 44), _error(palette))))
    elif tab is None:
        out.append(_line(('· systemd ', _muted(palette)), ('cargando…', _muted(palette))))
    elif tab.lines:
        out.append(_line(('✗ ', _error(palette)), (_failed_name(tab.lines[0]), _error(palette)),
                         (' falló', _muted(palette))))
    else:
        out.append(_line(('✓ ', _ok(palette)), ('systemd: sin fallos', _text(palette))))

    error = _block_error(data, 'docker')
    tab = data.tabs.get('docker')
    if error:
        out.append(_line(('✗ ', _error(palette)), (truncate(error, 44), _error(palette))))
    elif tab is None:
        out.append(_line(('· docker ', _muted(palette)), ('cargando…', _muted(palette))))
    else:
        running, other = _docker_items(tab.lines)
        if other:
            out.append(_line(('○ ', _error(palette)), ('docker: ', _muted(palette)),
                             (truncate(' · '.join(other), 30), _error(palette))))
        elif running:
            out.append(_line(('● ', _ok(palette)), ('docker: ', _muted(palette)),
                             (truncate(' · '.join(running), 32), _text(palette))))
        else:
            out.append(_line(('○ ', _muted(palette)), ('docker: sin contenedores', _muted(palette))))
        if tab.limited:
            out.append(_line(('⚠ necesita permisos', _warn(palette))))

    error = _block_error(data, 'journal')
    tab = data.tabs.get('journal')
    if error:
        out.append(_line(('✗ ', _error(palette)), (truncate(error, 44), _error(palette))))
    elif tab is None:
        out.append(_line(('· journal ', _muted(palette)), ('cargando…', _muted(palette))))
    elif tab.lines:
        out.append(_line((f'{len(tab.lines)} ', _warn(palette)),
                         ('errores en el journal (1 h)', _text(palette))))
    else:
        out.append(_line(('✓ ', _ok(palette)), ('journal sin errores', _text(palette))))
    if tab is not None and tab.limited:
        out.append(_line(('⚠ necesita permisos', _warn(palette))))
    return out


def _resumen(view, data, palette, width, range_hours, sort):
    sample = view.sample
    if sample is None:
        style = _error(palette) if view.state == 'sin-ssh' else _muted(palette)
        return [_line((_state_text(view), style))]

    two_columns = width >= 100
    left_width = min(78, width - 38) if two_columns else width
    left = []
    cpu = _clamp01(sample.cpu)
    graph = braille_graph(list(view.cpu_hist) or [cpu], max(8, left_width), 6)
    load = sample.load if sample.load else (0.0, 0.0, 0.0)
    left.append(_line(('CPU ', _bold(palette)),
                      (f'{round(cpu * 100)} %', _level_style(palette, cpu)),
                      (f'  · carga {fmt1(load[0])} {fmt1(load[1])} {fmt1(load[2])} · últimos 2 min',
                       _muted(palette))))
    for row in graph:
        left.append(_line((row, _level_style(palette, cpu))))
    axis = '−2 min'
    left.append(_line((axis, _dim(palette)),
                      (' ' * max(1, left_width - len(axis) - len('ahora')), _dim(palette)),
                      ('ahora', _dim(palette))))
    left.append([])

    ram = _clamp01(sample.ram_used_gb / sample.ram_total_gb) if sample.ram_total_gb else 0.0
    ram_width = max(6, min(50, left_width - 55)) if left_width > 65 else max(4, left_width // 3)
    filled, empty = bar(ram, ram_width)
    left.append(_line(('RAM   ', _bold(palette)), (filled, _level_style(palette, ram)),
                      (empty, _outline(palette)),
                      (f' {fmt1(sample.ram_used_gb)} / {_gb(sample.ram_total_gb)} GB', _text(palette)),
                      (f' · caché {fmt1(sample.cache_gb)} GB · '
                       f'swap {fmt1(sample.swap_used_gb)}/{fmt1(sample.swap_total_gb)} GB',
                       _muted(palette))))
    left.append([])
    left.append(_line(('DISCO', _bold(palette))))
    disk_width = max(6, min(40, left_width - 60)) if left_width > 60 else max(4, left_width // 3)
    for index, (mount, used, size) in enumerate(sample.mounts or [('/', 0.0, 0.0)]):
        fraction = _clamp01(used / size) if size else 0.0
        filled, empty = bar(fraction, disk_width)
        pieces = [(mount.ljust(7), _muted(palette)), (filled, _level_style(palette, fraction)),
                  (empty, _outline(palette)),
                  (f' {fmt1(used)} / {fmt1(size)} GB', _text(palette))]
        if fraction > 0.85:
            pieces.append((' ▲', _error(palette)))
        if index == 0:
            pieces.append((f'   lee {fmt1(sample.read_mbs)} MB/s · '
                           f'escribe {fmt1(sample.write_mbs)} MB/s', _muted(palette)))
        left.append(_line(*pieces))
    left.append([])
    left.append(_red_line(view, sample, palette, left_width))
    left.append([])
    process_header = len(left)
    left.append(_line(('PROCESOS', _bold(palette)), ('   CPU      RAM', _muted(palette))))
    top = sorted(sample.top, key=lambda row: row[1], reverse=True)[:5]
    for _pid, pcpu, ram_gb, command in top:
        left.append(_line((truncate(command, 28).ljust(28), _text(palette)),
                          (f'{fmt1(pcpu)}%'.rjust(7), _level_style(palette, pcpu / 100)),
                          (f'{fmt1(ram_gb)} G'.rjust(9), _muted(palette))))
    if not top:
        left.append(_line(('sin procesos', _muted(palette))))

    health = [_line(('SALUD', _bold(palette)))] + _health_lines(view, data, palette)
    if not two_columns:
        cores = _line(('NÚCLEOS ', _bold(palette)),
                      (' · '.join(f'cpu{index} {round(_clamp01(value) * 100)}%'
                                  for index, value in enumerate(sample.cores[:8]))
                       or 'sin datos', _muted(palette)))
        left[2 + len(graph):2 + len(graph)] = [cores, []]
        left.extend([[]] + health)
        return left

    right_width = width - left_width - 2
    cores = [_line(('NÚCLEOS', _bold(palette)))]
    core_width = max(4, min(30, right_width - 13))
    for index, value in enumerate(sample.cores[:6]):
        value = _clamp01(value)
        filled, empty = bar(value, core_width)
        cores.append(_line((f'cpu{index} ', _muted(palette)), (filled, _level_style(palette, value)),
                           (empty, _outline(palette)),
                           (f' {round(value * 100):3d}%', _text(palette))))
    if not sample.cores:
        cores.append(_line(('sin datos', _muted(palette))))
    while len(cores) < process_header:
        cores.append([])
    cores.extend(health)
    return _merge_columns(left, cores, left_width, width)


# -- Procesos -------------------------------------------------------------
def _procesos(view, data, palette, width, range_hours, sort):
    sample = view.sample
    if sample is None:
        style = _error(palette) if view.state == 'sin-ssh' else _muted(palette)
        return [_line((_state_text(view), style))]
    rows = list(sample.top)
    rows.sort(key=(lambda row: row[2]) if sort == 'ram' else (lambda row: row[1]), reverse=True)
    command_width = max(8, width - 26)
    out = [_line((f'{"PID".rjust(6)}  {"COMANDO".ljust(command_width)}'
                  f'{"CPU%".rjust(7)}  {"RAM".rjust(9)}', _muted(palette)))]
    for pid, pcpu, ram_gb, command in rows:
        out.append(_line((str(pid).rjust(6), _muted(palette)),
                         ('  ' + truncate(command, command_width).ljust(command_width), _text(palette)),
                         (f'{fmt1(pcpu)}%'.rjust(7), _level_style(palette, pcpu / 100)),
                         ('  ' + f'{fmt1(ram_gb)} G'.rjust(9), _muted(palette))))
    if not rows:
        out.append(_line(('sin procesos', _muted(palette))))
    out.append([])
    out.append(_line(('ordenar: ', _dim(palette)), ('c', _key(palette)), (' CPU · ', _dim(palette)),
                     ('m', _key(palette)), (' RAM', _dim(palette))))
    return out


# -- Disco ----------------------------------------------------------------
def _du_lines(data, palette, width):
    error = _block_error(data, 'du')
    tab = data.tabs.get('du')
    if error:
        return [_line((truncate(error, width), _error(palette)))]
    if tab is None:
        return [_line(('cargando…', _muted(palette)))]
    path_width = max(8, width - 18)
    out = []
    for raw in tab.lines[:12]:
        parts = str(raw).strip().split('\t')
        if len(parts) < 2:
            parts = str(raw).strip().split(None, 1)
        if len(parts) < 2:
            continue
        try:
            kilobytes = int(parts[0])
        except ValueError:
            continue
        out.append(_line(('  ', _muted(palette)),
                         (truncate(parts[1], path_width).ljust(path_width), _text(palette)),
                         (_size_text(kilobytes), _warn(palette))))
    if tab.limited:
        out.append(_line(('⚠ necesita permisos', _warn(palette))))
    if not out:
        out.append(_line(('sin datos', _muted(palette))))
    return out


def _disk_lines(view, data, palette, width):
    error = data.errors.get('disks')
    if error:
        return [_line((truncate(error, width), _error(palette)))]
    if data.disks is None:
        return [_line(('cargando…', _muted(palette)))]
    if not data.disks:
        return [_line(('sin discos', _muted(palette)))]
    boot = view.inst.disks[0] if view.inst.disks else ''
    out = []
    for disk in data.disks:
        if not isinstance(disk, dict):
            continue
        name = str(disk.get('name') or '?')
        kind = str(disk.get('type') or '').rstrip('/').rsplit('/', 1)[-1]
        size = str(disk.get('sizeGb') or '?')
        snapshot = disk.get('lastSnapshot') or {}
        pieces = [('  ', _muted(palette)), (truncate(name, 20).ljust(20), _text(palette)),
                  (kind.ljust(13), _muted(palette)), (f'{size} GB'.rjust(7), _text(palette)),
                  ('  arranque' if name == boot else '', _muted(palette)),
                  ('   ' + _age(snapshot.get('timestamp')), _dim(palette))]
        out.append(_line(*pieces))
    return out


def _disco(view, data, palette, width, range_hours, sort):
    out = []
    sample = view.sample
    if sample is None:
        style = _error(palette) if view.state == 'sin-ssh' else _muted(palette)
        out.append(_line((_state_text(view), style)))
    else:
        out.append(_line(('PARTICIONES', _bold(palette)),
                         ('   usado · lee · escribe', _muted(palette))))
        disk_width = max(6, min(30, width - 40)) if width > 50 else max(4, width // 3)
        for index, (mount, used, size) in enumerate(sample.mounts or [('/', 0.0, 0.0)]):
            fraction = _clamp01(used / size) if size else 0.0
            filled, empty = bar(fraction, disk_width)
            pieces = [(mount.ljust(11), _muted(palette)), (filled, _level_style(palette, fraction)),
                      (empty, _outline(palette)),
                      (f'  {fmt1(used)} / {fmt1(size)} GB'.ljust(20), _text(palette))]
            if index == 0:
                pieces.append((f'lee {fmt1(sample.read_mbs)} MB/s · '
                               f'escribe {fmt1(sample.write_mbs)} MB/s', _muted(palette)))
            out.append(_line(*pieces))
    out.append([])
    out.append(_line(('LO QUE MÁS OCUPA EN /', _bold(palette)),
                     ('  (du bajo demanda · d para recalcular)', _dim(palette))))
    out.extend(_du_lines(data, palette, width))
    out.append([])
    out.append(_line(('DISCOS DE GCP', _bold(palette)), ('  (gcloud)', _dim(palette))))
    out.extend(_disk_lines(view, data, palette, width))
    return out


# -- Red ------------------------------------------------------------------
def _parse_ports(lines):
    """``(port, address, process)`` from ``ss -tlnp`` lines."""
    found = []
    for raw in lines:
        text = str(raw).strip()
        if not text or text.lower().startswith('state'):
            continue
        local = next((field for field in text.split() if PORT_RE.match(field)), None)
        if local is None:
            continue
        address, _, port = local.rpartition(':')
        match = PROCESS_RE.search(text)
        found.append((port, address or '*', match.group(1) if match else '—'))
    return found


def _ports_block(data, palette):
    out = [_line(('PUERTOS ABIERTOS', _bold(palette)), ('  (ss -tlnp)', _dim(palette)))]
    error = _block_error(data, 'ports')
    tab = data.tabs.get('ports')
    if error:
        out.append(_line((truncate(error, 60), _error(palette))))
        return out
    if tab is None:
        out.append(_line(('cargando…', _muted(palette))))
        return out
    ports = _parse_ports(tab.lines)
    for port, address, process in ports:
        style = _warn(palette) if address in OPEN_ADDRESSES else _muted(palette)
        out.append(_line(('  ', _muted(palette)), (port.rjust(5), _text(palette)),
                         ('  ', _muted(palette)), (address.ljust(11), style),
                         (truncate(process, 24), _muted(palette))))
    if tab.limited:
        out.append(_line(('⚠ necesita permisos', _warn(palette))))
    if not ports:
        out.append(_line(('sin puertos a la escucha', _muted(palette))))
    return out


def _rule_ports(rule):
    ports = []
    for allowed in rule.get('allowed') or []:
        for port in allowed.get('ports') or []:
            ports.append(str(port))
        if not allowed.get('ports'):
            ports.append('todos')
    return ','.join(dict.fromkeys(ports)) or 'todos'


def _rule_text(rule):
    """``(flagged, name, detail)``: an enabled ingress allow from ``0.0.0.0/0`` outside
    22/80/443 is flagged; deny and disabled rules are shown as such, never as exposure."""
    sources = [str(item) for item in rule.get('sourceRanges') or []]
    name = str(rule.get('name') or '?')
    if rule.get('denied') and not rule.get('allowed'):
        ports = ','.join(dict.fromkeys(str(port) for denied in rule.get('denied') or []
                                       for port in (denied.get('ports') or ['todos'])))
        return False, name, f'deniega {ports or "todos"} desde {", ".join(sources) or "todas"}'
    ports = _rule_ports(rule)
    detail = f'{ports} desde {", ".join(sources) or "todas"}'
    if rule.get('disabled'):
        return False, name, detail + '  (desactivada)'
    if str(rule.get('direction') or 'INGRESS').upper() != 'INGRESS':
        return False, name, detail + '  (salida)'
    exposed = [port for port in ports.split(',') if port not in SAFE_FIREWALL_PORTS]
    flagged = '0.0.0.0/0' in sources and bool(exposed)
    if flagged:
        detail += '  ⚠ expuesta'
    return flagged, name, detail


def _firewall_block(view, data, palette):
    tags = ', '.join(view.inst.tags) or 'todas'
    out = [_line(('FIREWALL DE GCP', _bold(palette)), (f'  (etiquetas: {tags})', _dim(palette)))]
    error = data.errors.get('firewall')
    if error:
        out.append(_line((truncate(error, 60), _error(palette))))
        return out
    if data.firewall is None:
        out.append(_line(('cargando…', _muted(palette))))
        return out
    for rule in data.firewall:
        if not isinstance(rule, dict):
            continue
        flagged, name, detail = _rule_text(rule)
        mark, style = ('! ', _warn(palette)) if flagged else ('✓ ', _ok(palette))
        out.append(_line((mark, style), (truncate(name, 22).ljust(22), _text(palette)),
                         (detail, _muted(palette))))
    if not data.firewall:
        out.append(_line(('sin reglas', _muted(palette))))
    return out


def _red(view, data, palette, width, range_hours, sort):
    inst = view.inst
    out = [_line(('INTERFAZ ', _bold(palette)),
                 (f'  interna {inst.internal_ip or "—"} · externa '
                  f'{inst.external_ip or "sin IP externa"} · red {inst.network or "—"}',
                  _muted(palette)))]
    sample = view.sample
    if sample is None:
        style = _error(palette) if view.state == 'sin-ssh' else _muted(palette)
        out.append(_line((_state_text(view), style)))
    else:
        graph_width = max(4, min(40, width // 3))
        pieces = [('↓ ', _ok(palette))]
        rx_history = getattr(view, 'rx_hist', None)
        if rx_history:
            pieces.append((braille_graph(list(rx_history), graph_width, 1)[0], _ok(palette)))
        pieces.append((f'{fmt1(sample.rx_mbs)} MB/s    ', _text(palette)))
        pieces.append(('↑ ', _warn(palette)))
        tx_history = getattr(view, 'tx_hist', None)
        if tx_history:
            pieces.append((braille_graph(list(tx_history), graph_width, 1)[0], _warn(palette)))
        pieces.append((f'{fmt1(sample.tx_mbs)} MB/s', _text(palette)))
        out.append(_line(*pieces))
    out.append([])
    ports = _ports_block(data, palette)
    firewall = _firewall_block(view, data, palette)
    if width >= 70:
        out.extend(_merge_columns(ports, firewall, max(28, width // 2), width))
    else:
        out.extend(ports)
        out.append([])
        out.extend(firewall)
    return out


# -- Servicios ------------------------------------------------------------
def _failed_fields(raw):
    fields = str(raw).split(None, 4)
    unit = fields[0] if fields else ''
    state = fields[3] if len(fields) > 3 else 'failed'
    description = fields[4] if len(fields) > 4 else ''
    return unit, state, description


def _servicios(view, data, palette, width, range_hours, sort):
    out = [_line(('SYSTEMD', _bold(palette)), ('  (servicios con fallo primero)', _dim(palette)))]
    error = _block_error(data, 'failed')
    tab = data.tabs.get('failed')
    if error:
        out.append(_line((truncate(error, width), _error(palette))))
    elif tab is None:
        out.append(_line(('cargando…', _muted(palette))))
    else:
        for raw in tab.lines[:12]:
            unit, state, description = _failed_fields(raw)
            out.append(_line(('  ', _muted(palette)), ('✗ ', _error(palette)),
                             (truncate(unit, 28).ljust(28), _text(palette)),
                             (state, _error(palette)),
                             (f'   {truncate(description, 44)}', _muted(palette))))
        if tab.limited:
            out.append(_line(('⚠ necesita permisos', _warn(palette))))
        if not tab.lines:
            out.append(_line(('✓ sin servicios con fallo', _ok(palette))))

    out.append([])
    out.append(_line(('CONTENEDORES', _bold(palette)), ('  (docker ps -a)', _dim(palette))))
    error = _block_error(data, 'docker')
    tab = data.tabs.get('docker')
    if error:
        out.append(_line((truncate(error, width), _error(palette))))
    elif tab is None:
        out.append(_line(('cargando…', _muted(palette))))
    else:
        rows = 0
        for raw in tab.lines[:12]:
            try:
                item = json.loads(raw)
            except (TypeError, ValueError):
                item = None
            if not isinstance(item, dict):
                out.append(_line(('  ', _muted(palette)), (truncate(str(raw), width - 2), _muted(palette))))
                rows += 1
                continue
            running = str(item.get('State') or '') == 'running'
            mark, style = (('● ', _ok(palette)) if running else ('○ ', _error(palette)))
            out.append(_line(('  ', _muted(palette)), (mark, style),
                             (truncate(str(item.get('Names') or '?'), 12).ljust(12), _text(palette)),
                             (truncate(str(item.get('Image') or ''), 24).ljust(24), _muted(palette)),
                             (truncate(str(item.get('Status') or ''), 20).ljust(20),
                              _ok(palette) if running else _error(palette)),
                             (truncate(str(item.get('Ports') or ''), 20), _muted(palette))))
            rows += 1
        if tab.limited:
            out.append(_line(('⚠ necesita permisos', _warn(palette))))
        if not rows:
            out.append(_line(('○ sin contenedores', _muted(palette))))
    return out


# -- Registro -------------------------------------------------------------
def _journal_fields(raw):
    parts = str(raw).split(None, 3)
    if len(parts) >= 4:
        stamp, unit, message = parts[0], parts[2], parts[3]
        when = stamp[11:19] if len(stamp) >= 19 and 'T' in stamp else stamp[-8:]
        return when, unit.split('[')[0].rstrip(':'), message
    return '', '', str(raw).strip()


def _journal_style(message, palette):
    lowered = message.lower()
    if any(word in lowered for word in ('error', 'failed', 'fatal', 'refused', 'panic')):
        return _error(palette)
    if any(word in lowered for word in ('warn', 'flood', 'too frequently', 'timeout')):
        return _warn(palette)
    return _text(palette)


def _registro(view, data, palette, width, range_hours, sort):
    out = [_line(('JOURNAL', _bold(palette)),
                 ('  prioridad ≤ advertencia · última hora · l en vivo', _dim(palette)))]
    error = _block_error(data, 'journal')
    tab = data.tabs.get('journal')
    if error:
        out.append(_line((truncate(error, width), _error(palette))))
        return out
    if tab is None:
        out.append(_line(('cargando…', _muted(palette))))
        return out
    entries = [raw for raw in tab.lines if str(raw).strip() and not str(raw).startswith('-- ')]
    if len(entries) > JOURNAL_SHOWN:
        out.append(_line((f'… {len(entries) - JOURNAL_SHOWN} entradas anteriores ocultas', _dim(palette))))
        entries = entries[-JOURNAL_SHOWN:]
    for raw in entries:
        when, unit, message = _journal_fields(raw)
        out.append(_line(('  ', _muted(palette)), (when.ljust(9), _dim(palette)),
                         (truncate(unit, 10).ljust(10), _text(palette)),
                         (truncate(message, max(8, width - 23)), _journal_style(message, palette))))
    if tab.limited:
        out.append(_line(('⚠ necesita permisos', _warn(palette))))
    if not tab.lines:
        out.append(_line(('sin entradas', _muted(palette))))
    return out


# -- Historial ------------------------------------------------------------
def _time_axis(points, hours, width):
    if not points:
        return ''
    first = points[0][0]
    if hours == 24:
        left, right = _clock(first), 'ahora'
    else:
        left, right = DAYS[datetime.fromtimestamp(first).weekday()], 'hoy'
    return left + ' ' * max(1, width - len(left) - len(right)) + right


def _operation_markers(operations, points, width, palette):
    """One line with a ``▲ type HH:MM`` mark per operation inside the graph's range."""
    if not operations or not points:
        return None
    start, end = points[0][0], points[-1][0]
    if end <= start:
        return None
    width = max(0, int(width))
    cells = [' '] * width
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        stamp = _parse_iso(operation.get('insertTime'))
        if stamp is None or not start <= stamp <= end:
            continue
        label = f'▲ {operation.get("operationType") or "?"} {_clock(stamp)}'
        if len(label) > width:
            continue
        room = width - len(label)
        column = max(0, min(room, int((stamp - start) / (end - start) * room)))
        if any(cells[column + offset] != ' ' for offset in range(len(label))):
            continue
        for offset, char in enumerate(label):
            cells[column + offset] = char
    text = ''.join(cells).rstrip()
    return _line((text, _warn(palette))) if text.strip() else None


def _historial(view, data, palette, width, range_hours, sort):
    hours = 168 if int(range_hours) >= 48 else 24
    title = 'últimas 24 h' if hours == 24 else 'últimos 7 días'
    points = (data.history or {}).get(hours)
    error = data.errors.get('history')
    out = []
    if error:
        out.append(_line((f'CPU · {title}', _bold(palette))))
        out.append(_line((truncate(error, width), _error(palette))))
    elif points is None:
        out.append(_line((f'CPU · {title}', _bold(palette))))
        out.append(_line(('cargando…', _muted(palette))))
    elif not points:
        out.append(_line((f'CPU · {title}', _bold(palette))))
        out.append(_line(('sin datos de Monitoring', _muted(palette))))
    else:
        values = [_clamp01(value) for _stamp, value in points]
        average = sum(values) / len(values)
        peak = max(values)
        out.append(_line((f'CPU · {title}', _bold(palette)),
                         (f'  (Cloud Monitoring, sin agente) · promedio '
                          f'{round(average * 100)} % · pico {round(peak * 100)} %', _muted(palette))))
        graph_width = max(4, width - 6)
        for index, row in enumerate(braille_graph(values, graph_width, 9)):
            label = '100%' if index == 0 else (' 50%' if index == 4 else '    ')
            out.append(_line((label, _dim(palette)), (' ', _dim(palette)),
                             (row, _accent(palette))))
        out.append(_line((_time_axis(points, hours, graph_width + 6), _dim(palette))))
        markers = _operation_markers(data.operations, points, graph_width + 6, palette)
        if markers:
            out.append(markers)

    out.append([])
    out.append(_line(('OPERACIONES DE GCP', _bold(palette)),
                     ('  (gcloud: quién encendió, apagó o reinició)', _dim(palette))))
    error = data.errors.get('operations')
    if error:
        out.append(_line((truncate(error, width), _error(palette))))
    elif data.operations is None:
        out.append(_line(('cargando…', _muted(palette))))
    elif not data.operations:
        out.append(_line(('sin operaciones', _muted(palette))))
    else:
        for operation in data.operations[:10]:
            if not isinstance(operation, dict):
                continue
            out.append(_line(('  ', _muted(palette)),
                             (_op_time(operation.get('insertTime')).ljust(13), _dim(palette)),
                             (str(operation.get('operationType') or '?').ljust(8), _accent(palette)),
                             (truncate(str(operation.get('user') or '—'), 40), _muted(palette))))
    out.append([])
    out.append(_line(('RAM y disco históricos aparecen aquí si la VM tiene Ops Agent.',
                      _dim(palette))))
    return out


# -- the tab body ---------------------------------------------------------
_BUILDERS = (_resumen, _procesos, _disco, _red, _servicios, _registro, _historial)


def body_lines(tab: int, view: VmView, data: DetailData, palette, width: int,
               range_hours: int = 24, sort: str = 'cpu') -> list[list[tuple[str, Style]]]:
    """The tab's content as lines of styled segments, independent of the visible height."""
    data = DetailData() if data is None else data
    width = max(1, int(width))
    if not 0 <= int(tab) < len(_BUILDERS):
        return []
    return _BUILDERS[int(tab)](view, data, palette, width, range_hours, sort)


def draw_tab(canvas: Canvas, rect, tab: int, view: VmView, data: DetailData, palette,
             range_hours: int = 24, sort: str = 'cpu', scroll: int = 0) -> int:
    """Draw the tab inside ``rect`` from ``scroll`` and return its total height in rows."""
    x, y, width, height = int(rect.x), int(rect.y), int(rect.w), int(rect.h)
    lines = body_lines(tab, view, data, palette, max(1, width), range_hours, sort)
    total = len(lines)
    if width <= 0 or height <= 0:
        return total
    start = max(0, int(scroll))
    with canvas.clip(rect):
        for offset in range(min(total - start, height)):
            _segments(canvas, x, y + offset, width, lines[start + offset])
    return total
