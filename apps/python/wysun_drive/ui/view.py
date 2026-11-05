"""Drawing of the Wysun Drive selector (layout B): header, breadcrumbs, the Archivos/Recientes pane,
the Detalle pane (preview, progress, links), the tray of chips and the key hints.

Everything is painted with palette roles; cells left on ``surface`` are transparent (the app is
``transparent``), so only the selected row, chips and previews carry a background of their own.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import urlsplit

from wysun_core.tui import Rect, kit
from wysun_core.tui.draw import bar, box, braille_graph, spinner_frame, truncate
from wysun_core.tui.kit import GLYPH, Painter  # noqa: F401  (Painter is part of this module's API)
from wysun_drive import account, history
from wysun_drive.cli import human_size
from wysun_drive.ui import preview
from wysun_drive.ui.preview import ICON, ROLE

NARROW = 100
DAYS = (None, 1, 7, 30)


# -- geometry -----------------------------------------------------------------
def panes(width, height, mode):
    """``(left, right)`` rects; one of them is None on a narrow terminal."""
    top, h = 2, max(3, height - 5)
    if width < NARROW:
        full = Rect(1, top, width - 2, h)
        return (None, full) if mode != 'idle' else (full, None)
    left_w = max(44, int(width * 0.55))
    return Rect(1, top, left_w, h), Rect(left_w + 2, top, width - left_w - 3, h)


# -- chrome -------------------------------------------------------------------
def header(app, c, s, width):
    if app.account:
        status = f'{app.account.user} · {urlsplit(app.account.server).hostname}'
        role = 'primary' if app.mode == 'uploading' else 'success'
    else:
        status, role = 'sin sesión', 'outline'
    tabs = None if app.tab == 'login' else ['Subir', 'Recientes']
    kit.header(c, s, 'Wysun Drive', GLYPH['cloud'], tabs=tabs, active=0 if app.tab == 'browse' else 1,
               status=status, status_role=role)


def crumbs(app, c, s, width):
    if app.tab == 'recent':
        parts = ['Wysun Drive', 'Recientes']
        right = f'{len(app.recent)} subidas · {sum(1 for e in app.recent if e.get("url"))} con link'
    else:
        home = str(Path.home())
        where = str(app.cwd)
        if where == home or where.startswith(home + '/'):
            parts = ['~'] + [p for p in where[len(home):].split('/') if p]
        else:
            parts = ['/'] + [p for p in where.split('/') if p]
        if app.mode == 'uploading':
            right = f'{GLYPH["up"]} subiendo · {app.upload_title}'
        else:
            right = app.quota_text
    if app.filtering or app.filter_text:
        right = f'{GLYPH["search"]} {app.filter_text}' + ('▏' if app.filtering else '')
    kit.crumbs(c, s, 1, parts, right, 'primary' if app.filtering else 'onSurfaceVariant')


def footer(app, c, s, items):
    kit.footer(c, s, items)      # a toast (kit.Toast layer) covers this row while it shows


def tray(app, c, s, width, height):
    y = height - 3
    x = 2
    if app.marked:
        dirs = sum(1 for p in app.marked if os.path.isdir(p))
        size = sum(app.marked_sizes.get(p, 0) for p in app.marked)
        extra = f' + {dirs} carpeta' + ('s' if dirs != 1 else '') if dirs else ''
        text = f' ● {len(app.marked)} marcado{"s" if len(app.marked) != 1 else ""} · {human_size(size)}{extra} '
        if dirs == len(app.marked):
            text = f' ● {len(app.marked)} marcado{"s" if len(app.marked) != 1 else ""}{extra} '
        c.text(x, y, text, s('onPrimaryContainer', 'primaryContainer', bold=True))
    else:
        text = ' nada marcado: u sube el elegido '
        c.text(x, y, text, s('onSurfaceVariant'))
    x += len(text) + 1
    days = DAYS[app.days_index]
    for on, text in ((app.with_link, f' {GLYPH["link"]} con link ' if app.with_link else f' {GLYPH["link"]} sin link '),
                     (app.with_password, f' {GLYPH["lock"]} contraseña '),
                     (days is not None, f' {GLYPH["clock"]} caduca {days} d ' if days else f' {GLYPH["clock"]} no caduca ')):
        if x + len(text) >= width - 12:
            break
        c.text(x, y, text, s('onPrimary', 'primary', bold=True) if on else s('onSurfaceVariant', 'surfaceContainerHigh'))
        x += len(text) + 1
    action = 'u subir'
    if x + len(action) < width - 2:
        c.text(width - 2 - len(action), y, 'u', s('primary', bold=True))
        c.text(width - len(action), y, 'subir', s('onSurfaceVariant'))


# -- panes --------------------------------------------------------------------
def row_columns(width):
    """Where size and date go inside a list row of ``width`` cells (date hidden when tight)."""
    show_date = width >= 52
    return show_date


def files_pane(app, c, s, rect):
    focused = app.mode == 'idle' and not app.help
    dim = app.mode == 'uploading'
    entries = app.visible_entries()
    title = [(' Archivos ', s('onSurface', bold=True)), (f'· {len(entries)} ', s('onSurfaceVariant'))]
    box(c, rect, s('outlineVariant'), title, selected_style=s('primary') if focused else None)
    rows = rect.h - 2
    if app.listing_error or not entries:
        message = app.listing_error or ('Nada coincide con el filtro' if app.filter_text else 'Carpeta vacía')
        c.text(rect.x + 3, rect.y + 2, truncate(message, rect.w - 6), s('onSurfaceVariant'))
        return
    app.cursor = max(0, min(app.cursor, len(entries) - 1))
    if app.cursor < app.top:
        app.top = app.cursor
    elif app.cursor >= app.top + rows:
        app.top = app.cursor - rows + 1
    show_date = row_columns(rect.w)
    for row, index in enumerate(range(app.top, min(len(entries), app.top + rows))):
        name, is_dir, size, mtime = entries[index]
        path = str(app.cwd / name)
        selected = index == app.cursor
        y = rect.y + 1 + row
        bg = 'secondaryContainer' if selected and not dim else None
        if bg:
            c.fill(Rect(rect.x + 1, y, rect.w - 2, 1), ' ', s(bg=bg))
        marked = path in app.marked
        kind = preview.kind_of(name, is_dir)
        main = 'outline' if dim else ('onSecondaryContainer' if selected else 'onSurface')
        meta = 'outline' if dim else 'onSurfaceVariant'
        c.text(rect.x + 2, y, '●' if marked else '○', s('outline' if dim else ('primary' if marked else 'outline'), bg))
        c.text(rect.x + 4, y, ICON[kind], s('outline' if dim else ROLE[kind], bg))
        date = preview.when(mtime) if show_date else ''
        size_text = '' if is_dir else human_size(size)
        right = (f'{size_text:>9}' + (f'  {date:>10}' if date else ''))
        label = name + ('/' if is_dir else '')
        c.text(rect.x + 6, y, truncate(label, rect.w - 9 - len(right)), s(main, bg, bold=is_dir and not dim))
        c.text(rect.x + rect.w - 2 - len(right), y, right, s(meta, bg))
    if len(entries) > rows:
        pos = f' {app.cursor + 1}/{len(entries)} '
        c.text(rect.x + 2, rect.y + rect.h - 1, pos, s('onSurfaceVariant'))
    dirs = sum(1 for e in entries if e[1])
    files = len(entries) - dirs
    total = sum(e[2] for e in entries if not e[1])
    summary = f' {dirs} carpeta{"s" if dirs != 1 else ""} · {files} archivo{"s" if files != 1 else ""} · {human_size(total)} '
    if len(summary) + 12 < rect.w:
        c.text(rect.x + rect.w - 2 - len(summary), rect.y + rect.h - 1, summary, s('onSurfaceVariant'))


def kv(c, s, x, y, key, value, role='onSurface', width=40):
    c.text(x, y, f'{key:<11}', s('onSurfaceVariant'))
    c.text(x + 11, y, truncate(value, max(0, width - 11)), s(role))


def draw_preview(app, c, s, x, y, cols, rows, path):
    """The preview of ``path`` at ``(x, y)``; returns the rows used."""
    item = app.previews.get(path, cols, rows)
    if item is None:
        c.text(x, y, f'{spinner_frame(app.spin)} preparando vista previa…', s('onSurfaceVariant'))
        return 1
    kind = item['kind']
    if kind == 'image':
        kit.pixels(c, x, y, item['pixels'])
        return len(item['pixels'])
    if kind == 'text':
        for r, line in enumerate(item['lines'][:rows]):
            c.text(x, y + r, truncate(line, cols), s('onSurfaceVariant'))
        return min(rows, len(item['lines']))
    if kind == 'dir':
        text = f'{item["dirs"]} carpetas · {item["files"]} archivos · {human_size(item["total"])}'
        c.text(x, y, truncate(text, cols), s('onSurfaceVariant'))
        return 1
    if item.get('text'):
        c.text(x, y, truncate(item['text'], cols), s('error' if kind == 'error' else 'onSurfaceVariant'))
        return 1
    return 0


def detail_pane(app, c, s, rect):
    box(c, rect, s('outlineVariant'), [(f' {GLYPH["eye"]} Detalle ', s('onSurface', bold=True))])
    entries = app.visible_entries()
    if not entries:
        return
    name, is_dir, size, mtime = entries[min(app.cursor, len(entries) - 1)]
    path = str(app.cwd / name)
    x, inner = rect.x + 3, rect.w - 6
    kind = preview.kind_of(name, is_dir)
    c.text(x, rect.y + 2, ICON[kind], s(ROLE[kind]))
    c.text(x + 2, rect.y + 2, truncate(name + ('/' if is_dir else ''), inner - 2), s('onSurface', bold=True))
    item = app.previews.get(path, inner, preview_rows(rect, inner))
    dims = item.get('dims') if item else None
    subtitle = preview.describe(name, is_dir) + (f' · {dims[0]} × {dims[1]}' if dims else '')
    c.text(x + 2, rect.y + 3, truncate(subtitle, inner - 2), s('onSurfaceVariant'))
    y = rect.y + 5
    used = draw_preview(app, c, s, x, y, inner, preview_rows(rect, inner), path)
    y += used + (1 if used else 0)
    bottom = rect.y + rect.h - 2
    lines = []
    if not is_dir:
        lines.append(('Tamaño', human_size(size), 'onSurface'))
    lines.append(('Modificado', preview.when(mtime), 'onSurface'))
    folder = account.settings()['folder']
    lines.append(('Irá a', f'{folder}/{name}' if folder else name, 'primary'))
    for key, value, role in lines:
        if y > bottom:
            return
        kv(c, s, x, y, key, value, role, inner)
        y += 1
    state = app.remote_state(name)
    if y <= bottom and state is not None:
        if state:
            c.text(x, y, GLYPH['warn'], s('tertiary'))
            c.text(x + 2, y, truncate('Ya existe en la nube: se subirá con «(2)»', inner - 2), s('tertiary'))
        else:
            c.text(x, y, GLYPH['ok'], s('success'))
            c.text(x + 2, y, 'No existe todavía en la nube', s('onSurfaceVariant'))


def preview_rows(rect, cols):
    return max(3, min(rect.h - 12, round(cols * 0.28)))


def upload_pane(app, c, s, rect):
    spin = spinner_frame(app.spin)
    box(c, rect, s('outlineVariant'), [(f' {spin} Subiendo ', s('primary', bold=True)),
                                       (f'a {account.settings()["folder"] or "la raíz"}/ ', s('onSurfaceVariant'))],
        selected_style=s('primary'))
    x, inner = rect.x + 3, rect.w - 6
    y = rect.y + 2
    bottom = rect.y + rect.h - 2
    items = list(app.progress_items)
    for item in items:
        if y + 2 > bottom - 7:
            rest = len(items) - items.index(item)
            c.text(x, y, f'… y {rest} más', s('onSurfaceVariant'))
            y += 2
            break
        name, done, total = item['name'], item['done'], item['total']
        kind = preview.kind_of(name, os.path.isdir(os.path.join(str(app.cwd), name)))
        frac = 1.0 if not total else min(1.0, done / total)
        finished = total and done >= total
        c.text(x, y, ICON[kind], s(ROLE[kind]))
        right = f'{GLYPH["ok"]} listo' if finished else f'{int(frac * 100)} %'
        c.text(x + 2, y, truncate(name, inner - 4 - len(right)), s('onSurface', bold=True))
        c.text(x + inner - len(right), y, right, s('success' if finished else 'primary', bold=True))
        filled, empty = bar(frac, inner)
        c.text(x, y + 1, filled, s('success' if finished else 'primary'))
        c.text(x + len(filled), y + 1, empty, s('outlineVariant'))
        c.text(x, y + 2, f'{human_size(done)} de {human_size(total)}', s('onSurfaceVariant'))
        y += 4
    if not items:
        c.text(x, y, f'{spin} preparando…', s('onSurfaceVariant'))
        y += 2
    done, total = app.overall
    if y + 1 <= bottom:
        c.text(x, y, 'Total', s('onSurfaceVariant'))
        right = f'{human_size(done)} de {human_size(total)}'
        c.text(x + inner - len(right), y, right, s('onSurface', bold=True))
        filled, empty = bar(done / total if total else 0.0, inner)
        c.text(x, y + 1, filled, s('primary'))
        c.text(x + len(filled), y + 1, empty, s('outlineVariant'))
        y += 3
    if y + 1 <= bottom:
        c.text(x, y, 'Velocidad', s('onSurfaceVariant'))
        speed = app.speed()
        eta = app.eta()
        right = f'{human_size(speed)}/s' + (f' · falta {eta}' if eta else '')
        c.text(x + inner - len(right), y, right, s('onSurface'))
        peak = max(app.speeds) if app.speeds else 0
        graph_rows = max(1, min(3, bottom - y - 2))
        for i, line in enumerate(braille_graph([v / peak if peak else 0 for v in app.speeds], inner, graph_rows)):
            c.text(x, y + 1 + i, line, s('primary'))
    if bottom - 1 > y:
        note = 'El link se copiará al terminar' if app.upload_link else 'b sigue en segundo plano (barra)'
        c.text(x, bottom, truncate(note, inner), s('onSurfaceVariant'))


def done_pane(app, c, s, rect):
    ok = [r for r in app.results if r.get('ok')]
    failed = not ok or app.upload_error or any(not r.get('ok') or r.get('link_error') for r in app.results)
    title_role = 'error' if not ok else ('tertiary' if failed else 'success')
    title = f' {GLYPH["ok"]} Listo ' if ok and not app.upload_error else (' No terminó ' if not ok else ' Listo con avisos ')
    box(c, rect, s('outlineVariant'), [(title, s(title_role, bold=True)),
                                       (f'· {len(ok)} subido{"s" if len(ok) != 1 else ""} ', s('onSurfaceVariant'))],
        selected_style=s(title_role))
    x, inner = rect.x + 3, rect.w - 6
    y = rect.y + 2
    bottom = rect.y + rect.h - 2
    if app.upload_error:
        c.text(x, y, truncate(app.upload_error, inner), s('error'))
        y += 2
    for result in app.results:
        if y + 2 > bottom - 5:
            break
        kind = preview.kind_of(result.get('name', ''), result.get('is_dir'))
        c.text(x, y, ICON[kind], s(ROLE[kind]))
        c.text(x + 2, y, truncate(result.get('name', ''), inner - 2), s('onSurface', bold=True))
        if result.get('ok'):
            c.text(x + 2, y + 1, truncate('→ ' + result.get('remote', ''), inner - 2), s('onSurfaceVariant'))
            if result.get('url'):
                c.text(x + 2, y + 2, GLYPH['link'], s('primary'))
                c.text(x + 4, y + 2, truncate(result['url'], inner - 4), s('primary', underline=True))
            elif result.get('link_error'):
                c.text(x + 2, y + 2, truncate('sin link: ' + result['link_error'], inner - 2), s('error'))
            else:
                c.text(x + 2, y + 2, human_size(result.get('size', 0)), s('onSurfaceVariant'))
        else:
            c.text(x + 2, y + 1, truncate(result.get('error') or '', inner - 2), s('error'))
        y += 4
    links = [r['url'] for r in app.results if r.get('url')]
    if links and y + 2 <= bottom:
        c.fill(Rect(x, y, inner, 3), ' ', s(bg='surfaceContainerHigh'))
        text = (f'{GLYPH["copy"]}  ' + ('Link copiado' if len(links) == 1 else f'{len(links)} links copiados')
                + ' al portapapeles') if app.upload_copied else f'{GLYPH["copy"]}  c copia los links'
        c.text(x + 2, y + 1, truncate(text, inner - 4), s('onSurface', 'surfaceContainerHigh', bold=True))
        y += 4
    passwords = {r.get('password') for r in app.results if r.get('password')}
    if links and y + 1 <= bottom:
        kv(c, s, x, y, 'Contraseña', next(iter(passwords)) if passwords else 'sin contraseña',
           'primary' if passwords else 'onSurface', inner)
        days = app.upload_days
        kv(c, s, x, y + 1, 'Caduca', f'en {days} días' if days else 'nunca', 'onSurface', inner)


def recent_pane(app, c, s, rect):
    entries = app.visible_recent()
    box(c, rect, s('outlineVariant'), [(' Recientes ', s('onSurface', bold=True)), (f'· {len(entries)} ', s('onSurfaceVariant'))],
        selected_style=s('primary'))
    if not entries:
        c.text(rect.x + 3, rect.y + 2, 'Nada coincide con el filtro' if app.filter_text else 'Aún no has subido nada',
               s('onSurfaceVariant'))
        return
    rows = []          # (kind, value): ('group', name) or ('entry', index)
    last = None
    for index, entry in enumerate(entries):
        group = preview.group_of(entry.get('at', 0))
        if group != last:
            if last is not None:
                rows.append(('gap', None))
            rows.append(('group', group))
            last = group
        rows.append(('entry', index))
    app.recent_cursor = max(0, min(app.recent_cursor, len(entries) - 1))
    cursor_row = next(i for i, r in enumerate(rows) if r == ('entry', app.recent_cursor))
    visible = rect.h - 2
    start = max(0, min(cursor_row - visible + 2, len(rows) - visible)) if cursor_row >= visible - 1 else 0
    show_date = rect.w >= 40
    for offset, (what, value) in enumerate(rows[start:start + visible]):
        y = rect.y + 1 + offset
        if what == 'group':
            c.text(rect.x + 2, y, value, s('primary', bold=True))
        elif what == 'entry':
            entry = entries[value]
            selected = value == app.recent_cursor
            bg = 'secondaryContainer' if selected else None
            if bg:
                c.fill(Rect(rect.x + 1, y, rect.w - 2, 1), ' ', s(bg=bg))
            kind = preview.kind_of(entry.get('name', ''), entry.get('is_dir'))
            c.text(rect.x + 4, y, ICON[kind], s(ROLE[kind], bg))
            stamp = time.strftime('%H:%M', time.localtime(entry.get('at', 0))) if preview.group_of(entry.get('at', 0)) in ('Hoy', 'Ayer') \
                else preview.when(entry.get('at', 0))
            right = (GLYPH['link'] if entry.get('url') else ' ') + (f'  {stamp:>8}' if show_date else '')
            c.text(rect.x + 6, y, truncate(entry.get('name', ''), rect.w - 9 - len(right)),
                   s('onSecondaryContainer' if selected else 'onSurface', bg))
            c.text(rect.x + rect.w - 2 - len(right), y, right[0], s('primary', bg))
            c.text(rect.x + rect.w - 1 - len(right), y, right[1:], s('onSurfaceVariant', bg))


def recent_detail(app, c, s, rect):
    entries = app.visible_recent()
    if not entries:
        box(c, rect, s('outlineVariant'), [(f' {GLYPH["eye"]} Detalle ', s('onSurface', bold=True))])
        return
    entry = entries[min(app.recent_cursor, len(entries) - 1)]
    kind = preview.kind_of(entry.get('name', ''), entry.get('is_dir'))
    box(c, rect, s('outlineVariant'), [(f' {ICON[kind]} ', s(ROLE[kind])), (truncate(entry.get('name', ''), rect.w - 10) + ' ',
                                                                             s('onSurface', bold=True))])
    x, inner = rect.x + 3, rect.w - 6
    y = rect.y + 2
    local = entry.get('local') or ''
    if local and os.path.exists(local):
        used = draw_preview(app, c, s, x, y, inner, preview_rows(rect, inner), local)
        y += used + (1 if used else 0)
    if entry.get('url'):
        c.text(x, y, GLYPH['link'], s('primary'))
        c.text(x + 2, y, truncate(entry['url'], inner - 2), s('primary', underline=True))
    else:
        c.text(x, y, truncate('Sin link · n crea uno con las opciones de la bandeja', inner), s('onSurfaceVariant'))
    y += 2
    rules = 'público · ' + ('con contraseña' if entry.get('password') else 'sin contraseña')
    lines = [('En la nube', entry.get('remote', ''), 'onSurface'),
             ('Subido', f'{preview.when(entry.get("at", 0))} · {history.SOURCES.get(entry.get("source"), "desde la terminal")}', 'onSurface'),
             ('Tamaño', human_size(entry.get('size') or 0) if not entry.get('is_dir') else 'carpeta', 'onSurface')]
    if entry.get('url'):
        lines.append(('Link', rules, 'onSurface'))
        if entry.get('password'):
            lines.append(('Contraseña', entry['password'], 'primary'))
    for key, value, role in lines:
        if y > rect.y + rect.h - 2:
            break
        kv(c, s, x, y, key, value, role, inner)
        y += 1


def help_lines(app):
    if app.tab == 'recent':
        return [('↑↓', 'elegir'), ('c', 'copiar el link (o crearlo)'), ('o', 'abrir el link'), ('k', 'quitar el link'),
                ('n', 'link nuevo con las opciones de la bandeja'), ('/', 'filtrar'), ('Tab · 1 · 2', 'pestañas'), ('q', 'salir')]
    return [('↑↓ · PgUp PgDn', 'moverse'), ('→ · ↵', 'entrar en la carpeta'), ('← · ⌫', 'carpeta superior'),
            ('espacio', 'marcar o desmarcar'), ('a', 'marcar todo lo visible'), ('u', 'subir lo marcado (o el elegido)'),
            ('l', 'con o sin link'), ('p', 'contraseña del link'), ('d', 'caducidad: no · 1 · 7 · 30 días'),
            ('/', 'filtrar'), ('.', 'archivos ocultos'), ('pegar rutas', 'las marca'), ('Tab · 1 · 2', 'pestañas'),
            ('Esc', 'cancelar la subida'), ('b', 'subida en segundo plano'), ('q', 'salir')]
