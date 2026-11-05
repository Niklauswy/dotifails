"""`wysun drive` with no arguments: pick what to upload, watch it go, copy the links.

Two tabs. **Subir** browses from the current folder: ``↑↓`` move, ``→``/``↵`` enter a folder,
``←`` go up, ``espacio`` mark, ``u`` upload the marked items (or the one under the cursor),
``l`` toggle «con link», ``.`` hidden files. Pasting paths (or dropping files from Files on
the terminal) marks them. **Recientes** lists the history: ``c`` copy the link (making one
if needed), ``o`` open it in the browser. Without a session the body offers the login flow.
Colours come from the wallpaper (``Palette``), motion from the tokens.
"""
from __future__ import annotations

import os
import shlex
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from wysun_core.tui import App, Layer, Rect, Style
from wysun_core.tui.anim import Tween, curve, duration, reduced_motion
from wysun_core.tui.draw import bar, box, truncate
from wysun_drive import account, api, history, login, status
from wysun_drive.cli import copy, human_size, open_url
from wysun_drive.client import Cancelled, Client, DriveError

BROWSE_HINTS = [('espacio', 'marcar'), ('u', 'subir'), ('l', 'con link'), ('←→', 'carpetas'),
                ('Tab', 'Recientes'), ('q', 'salir')]
RECENT_HINTS = [('c', 'copiar link'), ('o', 'abrir'), ('Tab', 'Subir'), ('q', 'salir')]
UPLOAD_HINTS = [('Esc', 'cancelar')]
DONE_HINTS = [('c', 'copiar links'), ('↵', 'cerrar')]
LOGIN_HINTS = [('↵', 'iniciar sesión'), ('p', 'contraseña de aplicación'), ('s', 'cambiar servidor'), ('q', 'salir')]
MANUAL_HINTS = [('↵', 'siguiente'), ('Esc', 'cancelar')]
EDIT_HINTS = [('↵', 'guardar e iniciar sesión'), ('Esc', 'cancelar')]


def _paths_from_paste(text):
    """Paths in pasted text: ``file://`` URIs (one per line) or shell words; only existing ones."""
    found = []
    for line in text.replace('\r', '\n').split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('file://'):
            words = [unquote(urlsplit(word).path) for word in line.split()]
        else:
            try:
                words = shlex.split(line)
            except ValueError:
                words = [line]
        found += [os.path.abspath(os.path.expanduser(w)) for w in words if os.path.exists(os.path.expanduser(w))]
    return found


class _Overlay(Layer):
    def __init__(self, app):
        super().__init__(Rect(0, 0, 1, 1), z=50, visible=False)
        self.app = app

    def draw(self, canvas, palette):
        self.app._draw_overlay(canvas, palette)


class DriveApp(App):
    def __init__(self, term=None, home=None, start=None):
        super().__init__(term=term, home=home)
        self.cwd = Path(start or os.getcwd()).absolute()
        self.account = account.current()
        self.tab = 'browse' if self.account else 'login'
        self.show_hidden = False
        self.entries: list[tuple[str, bool, int]] = []
        self.listing_error = ''
        self.cursor = 0
        self.top = 0
        self.marked: list[str] = []
        self.with_link = False
        self.recent: list[dict] = []
        self.recent_cursor = 0
        self.toast_text = ''
        self._toast_timer = None
        # upload overlay
        self.uploading = False
        self.finished = False
        self.progress: dict[str, tuple[int, int]] = {}
        self.overall = (0, 0)
        self.results = []
        self.upload_error = ''
        self._cancel = False
        self._lock = threading.Lock()
        # login
        self.login_url = ''
        self.login_state = ''
        self.login_busy = False
        self.editing_server = False
        self.server_text = ''
        self.manual_step = None          # None | 'user' | 'password'
        self.manual_user = ''
        self.manual_password = ''

    # -- lifecycle ---------------------------------------------------------
    def on_start(self):
        self.overlay = _Overlay(self)
        self.layers.append(self.overlay)
        self._list()
        self.recent = history.load()

    def on_theme(self):
        self.invalidate()

    def on_resize(self, width, height):
        self._place_overlay(1.0)

    # -- data --------------------------------------------------------------
    def _list(self):
        entries, self.listing_error = [], ''
        try:
            with os.scandir(self.cwd) as found:
                for entry in found:
                    if entry.name.startswith('.') and not self.show_hidden:
                        continue
                    try:
                        is_dir = entry.is_dir()
                        size = 0 if is_dir else entry.stat().st_size
                    except OSError:
                        continue
                    entries.append((entry.name, is_dir, size))
        except OSError as error:
            self.listing_error = f'No se pudo abrir la carpeta ({error.strerror})'
        entries.sort(key=lambda e: (not e[1], e[0].casefold()))
        self.entries = entries
        self.cursor = min(self.cursor, max(0, len(entries) - 1))
        self.invalidate()

    def _current(self):
        if not self.entries:
            return None
        name, is_dir, _size = self.entries[self.cursor]
        return str(self.cwd / name), is_dir

    def toast(self, text, seconds=3.0):
        self.toast_text = text
        if self._toast_timer is not None:
            self.cancel(self._toast_timer)
        self._toast_timer = self.after(seconds, self._clear_toast)
        self.invalidate()

    def _clear_toast(self):
        self.toast_text = ''
        self.invalidate()

    # -- input -------------------------------------------------------------
    def on_paste(self, event):
        if self.manual_step:
            field = 'manual_user' if self.manual_step == 'user' else 'manual_password'
            setattr(self, field, getattr(self, field) + event.text.strip())
            self.invalidate()
            return
        if self.editing_server:
            self.server_text += event.text.strip()
            self.invalidate()
            return
        paths = _paths_from_paste(event.text)
        if not paths or self.tab == 'login':
            return
        for path in paths:
            if path not in self.marked:
                self.marked.append(path)
        self.tab = 'browse'
        self.toast(f'{len(paths)} añadido' + ('s' if len(paths) != 1 else '') + ' · u para subir')

    def on_key(self, event):
        name, char = event.name, event.char
        if event.ctrl and name == 'c':
            self._cancel = True
            self.quit()
            return
        if self.uploading:
            if name == 'escape':
                self._cancel = True
                self.toast('Cancelando…')
            return
        if self.finished:
            if name == 'char' and char == 'c':
                self._copy_results()
            elif name in ('enter', 'escape') or (name == 'char' and char == 'q'):
                self._close_overlay()
            return
        if self.editing_server:
            self._edit_key(name, char)
            return
        if self.manual_step:
            self._manual_key(name, char)
            return
        if name == 'char' and char == 'q' or name == 'escape':
            self.quit()
            return
        if self.tab == 'login':
            if name == 'enter' and not self.login_busy:
                self._start_login()
            elif name == 'char' and char == 'p' and not self.login_busy:
                self.manual_step, self.manual_user, self.manual_password = 'user', '', ''
                self.login_state = ''
                self.invalidate()
            elif name == 'char' and char == 's' and not self.login_busy:
                self.editing_server, self.server_text = True, account.settings()['server']
                self.invalidate()
            return
        if name == 'tab' or name == 'backtab' or (name == 'char' and char in '12'):
            target = {'1': 'browse', '2': 'recent'}.get(char) if name == 'char' else None
            self.tab = target or ('recent' if self.tab == 'browse' else 'browse')
            if self.tab == 'recent':
                self.recent = history.load()
            self.invalidate()
            return
        if self.tab == 'browse':
            self._browse_key(name, char)
        else:
            self._recent_key(name, char)

    def _edit_key(self, name, char):
        if name == 'escape':
            self.editing_server = False
        elif name == 'backspace':
            self.server_text = self.server_text[:-1]
        elif name == 'char' and char and char.isprintable():
            self.server_text += char
        elif name == 'enter':
            try:
                from wysun_drive.client import split_server
                split_server(account.normalize_server(self.server_text))
            except DriveError as error:
                self.toast(str(error), 5)
                return
            account.save_settings(server=self.server_text)
            self.editing_server = False
            self._start_login()
        self.invalidate()

    def _manual_key(self, name, char):
        field = 'manual_user' if self.manual_step == 'user' else 'manual_password'
        if name == 'escape':
            self.manual_step, self.manual_password = None, ''
        elif name == 'backspace':
            setattr(self, field, getattr(self, field)[:-1])
        elif name == 'char' and char and char.isprintable():
            setattr(self, field, getattr(self, field) + char)
        elif name == 'enter' and self.manual_step == 'user' and self.manual_user.strip():
            self.manual_step = 'password'
        elif name == 'enter' and self.manual_step == 'password' and self.manual_password:
            self._start_manual_login()
        self.invalidate()

    def _start_manual_login(self):
        server = account.settings()['server']
        user, password = self.manual_user, self.manual_password
        self.manual_step, self.manual_password = None, ''
        self.login_busy, self.login_state = True, 'Comprobando…'

        def work():
            try:
                acc = login.manual(server, user, password)
                account.save(acc)
            except DriveError as error:
                message = str(error)

                def failed():
                    self.login_busy, self.login_state = False, message
                    self.invalidate()
                self.after(0, failed)
                return

            def done():
                self.account, self.login_busy, self.tab = acc, False, 'browse'
                self.toast(f'Sesión iniciada como {acc.user}')
            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def on_mouse(self, event):
        if event.kind in ('wheelup', 'wheeldown') and not self.uploading:
            delta = -3 if event.kind == 'wheelup' else 3
            if self.tab == 'browse':
                self._move(delta)
            elif self.tab == 'recent' and self.recent:
                self.recent_cursor = max(0, min(len(self.recent) - 1, self.recent_cursor + delta))
                self.invalidate()

    def _move(self, delta):
        if self.entries:
            self.cursor = max(0, min(len(self.entries) - 1, self.cursor + delta))
            self.invalidate()

    def _browse_key(self, name, char):
        rows = max(1, self.size[1] - 5)
        moves = {'up': -1, 'down': 1, 'pageup': -rows, 'pagedown': rows}
        if name in moves:
            self._move(moves[name])
        elif name == 'home':
            self._move(-len(self.entries))
        elif name == 'end':
            self._move(len(self.entries))
        elif name in ('right', 'enter'):
            current = self._current()
            if current and current[1]:
                self.cwd, self.cursor, self.top = Path(current[0]), 0, 0
                self._list()
        elif name in ('left', 'backspace'):
            if self.cwd.parent != self.cwd:
                came_from = self.cwd.name
                self.cwd = self.cwd.parent
                self._list()
                self.cursor = next((i for i, e in enumerate(self.entries) if e[0] == came_from), 0)
        elif name == 'char' and char == ' ':
            current = self._current()
            if current:
                if current[0] in self.marked:
                    self.marked.remove(current[0])
                else:
                    self.marked.append(current[0])
                self._move(1)
                self.invalidate()
        elif name == 'char' and char == 'l':
            self.with_link = not self.with_link
            self.toast('Se creará el link y se copiará' if self.with_link else 'Sin link')
        elif name == 'char' and char == '.':
            self.show_hidden = not self.show_hidden
            self._list()
        elif name == 'char' and char == 'u':
            paths = list(self.marked) or ([self._current()[0]] if self._current() else [])
            if paths:
                self._start_upload(paths)

    def _recent_key(self, name, char):
        if name in ('up', 'down') and self.recent:
            self.recent_cursor = max(0, min(len(self.recent) - 1, self.recent_cursor + (1 if name == 'down' else -1)))
            self.invalidate()
            return
        if not self.recent:
            return
        entry = self.recent[self.recent_cursor]
        if name == 'char' and char == 'c':
            if entry.get('url'):
                self.toast('Link copiado' if copy(entry['url']) else entry['url'])
            else:
                self._make_link(entry)
        elif name == 'char' and char == 'o' and entry.get('url'):
            open_url(entry['url'])

    # -- background work ---------------------------------------------------
    def _make_link(self, entry):
        self.toast('Creando link…')

        def work():
            try:
                share = api.make_link(entry['remote'])
            except DriveError as error:
                message = str(error)
                self.after(0, lambda: self.toast(message, 5))
                return
            copied = copy(share['url'])

            def apply():
                self.recent = history.load()
                self.toast('Link creado y copiado' if copied else share['url'])
            self.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def _start_login(self):
        server = account.settings()['server']
        self.login_busy, self.login_state = True, f'Conectando con {urlsplit(server).hostname}…'
        self.invalidate()

        def work():
            try:
                url, poll = login.start(server)
                self.login_url = url
                self.login_state = 'Autoriza a Wysun Drive en el navegador que se abrió'
                open_url(url)
                self.invalidate()
                acc = login.wait(poll, server=server, cancelled=lambda: self._quitting)
                Client(acc).exists('')
                account.save(acc)
            except DriveError as error:
                message = str(error)

                def failed():
                    self.login_busy, self.login_state = False, message
                    self.invalidate()
                self.after(0, failed)
                return

            def done():
                self.account, self.login_busy, self.tab = acc, False, 'browse'
                self.toast(f'Sesión iniciada como {acc.user}')
            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _start_upload(self, paths):
        self.uploading, self.finished, self._cancel = True, False, False
        self.progress, self.overall, self.results, self.upload_error = {}, (0, 0), [], ''
        names = [os.path.basename(p) for p in paths]
        tracker = status.StatusFile(os.getpid(), names[0] if len(names) == 1 else f'{len(names)} elementos')
        self._open_overlay()

        def on_plan(plan):
            with self._lock:
                self.progress = {top.name: (0, top.size) for top in plan.tops}
                self.overall = (0, plan.total)
            self.invalidate()

        def on_progress(name, done, total, all_done, all_total):
            tracker.progress(name, done, total, all_done, all_total)
            with self._lock:
                self.progress[name] = (done, total)
                self.overall = (all_done, all_total)
            self.invalidate()

        def work():
            tracker.start()
            error = ''
            results = []
            try:
                results = api.upload(paths, link=self.with_link, on_plan=on_plan, on_progress=on_progress,
                                     cancelled=lambda: self._cancel)
            except Cancelled:
                error = 'Subida cancelada'
            except DriveError as failure:
                error = str(failure)
            finally:
                tracker.remove()
            links = [r.url for r in results if r.url]
            copied = bool(links) and copy('\n'.join(links))

            def done():
                self.uploading, self.finished = False, True
                self.results, self.upload_error = results, error
                if not error:
                    self.marked = []
                self.recent = history.load()
                if copied:
                    self.toast('Link copiado' if len(links) == 1 else 'Links copiados')
                self.invalidate()
            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _copy_results(self):
        links = [r.url for r in self.results if r.url]
        if links:
            self.toast('Copiado' if copy('\n'.join(links)) else links[0])

    # -- overlay -----------------------------------------------------------
    def _overlay_size(self):
        width, height = self.size
        w = max(40, min(76, width - 6))
        lines = 6 + max(len(self.progress), len(self.results)) * 2
        h = max(8, min(height - 4, lines))
        return w, h

    def _place_overlay(self, t, redraw=True):
        if not getattr(self, 'overlay', None):
            return
        width, height = self.size
        w, h = self._overlay_size()
        final_y = max(1, (height - h) // 2)
        offset = int(round((1 - t) * 2))
        self.overlay.rect = Rect(max(0, (width - w) // 2), final_y + offset, w, h)
        self.overlay.opacity = max(0.0, min(1.0, t))
        if redraw:
            self.invalidate()

    def _open_overlay(self):
        self.overlay.visible = True
        if reduced_motion():
            self._place_overlay(1.0)
            return
        self._place_overlay(0.0)
        self.animator.add(Tween(duration('expressiveFastEffects'), curve('emphasizedDecel'), self._place_overlay))

    def _close_overlay(self):
        self.finished = False
        self.overlay.visible = False
        self.invalidate()

    # -- drawing -----------------------------------------------------------
    def _style(self, palette, role, **kw):
        return Style(fg=palette[role], **kw)

    def draw(self, canvas):
        palette = self.palette
        width, height = canvas.width, canvas.height
        if self.overlay.visible:     # its height follows the number of items
            self._place_overlay(self.overlay.opacity, redraw=False)
        self._draw_header(canvas, palette, width)
        if self.tab == 'login':
            self._draw_login(canvas, palette, width, height)
            hints = LOGIN_HINTS
        elif self.tab == 'browse':
            self._draw_browse(canvas, palette, width, height)
            hints = BROWSE_HINTS
        else:
            self._draw_recent(canvas, palette, width, height)
            hints = RECENT_HINTS
        if self.editing_server:
            hints = EDIT_HINTS
        if self.manual_step:
            hints = MANUAL_HINTS
        if self.uploading:
            hints = UPLOAD_HINTS
        elif self.finished:
            hints = DONE_HINTS
        self._draw_footer(canvas, palette, width, height, hints)

    def _draw_header(self, canvas, palette, width):
        chip = ' ☁ Wysun Drive '
        canvas.text(1, 0, chip, Style(fg=palette['onPrimary'], bg=palette['primary'], bold=True))
        x = 2 + len(chip)
        if self.tab != 'login':
            for key, label, tab in (('1', 'Subir', 'browse'), ('2', 'Recientes', 'recent')):
                text = f' {key} {label} '
                style = (Style(fg=palette['onSecondaryContainer'], bg=palette['secondaryContainer'], bold=True)
                         if self.tab == tab else self._style(palette, 'onSurfaceVariant'))
                canvas.text(x, 0, text, style)
                x += len(text) + 1
        who = f'{self.account.user} · {urlsplit(self.account.server).hostname}' if self.account else 'sin sesión'
        if x + len(who) + 2 < width:
            canvas.text(width - 1 - len(who), 0, who, self._style(palette, 'onSurfaceVariant'))

    def _draw_footer(self, canvas, palette, width, height, hints):
        y = height - 1
        if self.toast_text:
            canvas.text(1, y, '●', self._style(palette, 'primary'))
            canvas.text(3, y, truncate(self.toast_text, width - 4), self._style(palette, 'onSurface'))
            return
        x = 1
        for key, label in hints:
            chunk = len(key) + len(label) + 3
            if x + chunk > width:
                break
            canvas.text(x, y, key, self._style(palette, 'primary', bold=True))
            canvas.text(x + len(key) + 1, y, label, self._style(palette, 'onSurfaceVariant'))
            x += chunk

    def _draw_browse(self, canvas, palette, width, height):
        home = str(Path.home())
        where = str(self.cwd)
        where = '~' + where[len(home):] if where == home or where.startswith(home + '/') else where
        canvas.text(1, 1, truncate(where, width - 30), self._style(palette, 'onSurface', bold=True))
        info = (f'{len(self.marked)} marcado' + ('s' if len(self.marked) != 1 else '')) if self.marked else ''
        info += ('  · ' if info else '') + ('con link' if self.with_link else 'sin link')
        canvas.text(width - 1 - len(info), 1, info,
                    self._style(palette, 'primary' if self.with_link else 'onSurfaceVariant'))
        top_y, rows = 3, max(1, height - 5)
        if self.listing_error or not self.entries:
            canvas.text(3, top_y, self.listing_error or 'Carpeta vacía', self._style(palette, 'onSurfaceVariant'))
            return
        if self.cursor < self.top:
            self.top = self.cursor
        elif self.cursor >= self.top + rows:
            self.top = self.cursor - rows + 1
        for row, index in enumerate(range(self.top, min(len(self.entries), self.top + rows))):
            name, is_dir, size = self.entries[index]
            path = str(self.cwd / name)
            selected = index == self.cursor
            y = top_y + row
            bg = palette['secondaryContainer'] if selected else None
            if selected:
                canvas.fill(Rect(1, y, width - 2, 1), ' ', Style(bg=bg))
            fg_role = 'onSecondaryContainer' if selected else 'onSurface'
            mark = '●' if path in self.marked else '○'
            canvas.text(2, y, mark, Style(fg=palette['primary' if path in self.marked else 'outline'], bg=bg))
            icon = '▸' if is_dir else ' '
            canvas.text(4, y, icon, Style(fg=palette['primary'], bg=bg))
            right = '' if is_dir else human_size(size)
            label = name + ('/' if is_dir else '')
            canvas.text(6, y, truncate(label, width - 10 - len(right)), Style(fg=palette[fg_role], bg=bg, bold=is_dir))
            if right:
                canvas.text(width - 2 - len(right), y, right, Style(fg=palette['onSurfaceVariant'], bg=bg))

    def _draw_recent(self, canvas, palette, width, height):
        canvas.text(1, 1, 'Subidos recientemente', self._style(palette, 'onSurface', bold=True))
        if not self.recent:
            canvas.text(3, 3, 'Aún no has subido nada', self._style(palette, 'onSurfaceVariant'))
            return
        rows = max(1, (height - 5) // 2)
        start = max(0, min(self.recent_cursor - rows + 1, len(self.recent) - rows))
        for row, index in enumerate(range(start, min(len(self.recent), start + rows))):
            entry = self.recent[index]
            y = 3 + row * 2
            selected = index == self.recent_cursor
            bg = palette['secondaryContainer'] if selected else None
            if selected:
                canvas.fill(Rect(1, y, width - 2, 2), ' ', Style(bg=bg))
            when = time.strftime('%d/%m %H:%M', time.localtime(entry.get('at', 0)))
            canvas.text(3, y, truncate(entry.get('name', ''), width - 10 - len(when)),
                        Style(fg=palette['onSecondaryContainer' if selected else 'onSurface'], bg=bg, bold=True))
            canvas.text(width - 2 - len(when), y, when, Style(fg=palette['onSurfaceVariant'], bg=bg))
            detail = entry.get('url') or f'{entry.get("remote", "")} · sin link (c lo crea)'
            canvas.text(3, y + 1, truncate(detail, width - 6),
                        Style(fg=palette['primary' if entry.get('url') else 'onSurfaceVariant'], bg=bg))

    def _draw_login(self, canvas, palette, width, height):
        server = urlsplit(account.settings()['server']).hostname or ''
        y = max(2, height // 2 - 4)
        lines = [('Wysun Drive aún no tiene sesión', 'onSurface', True),
                 (f'↵ abre {server} en el navegador para autorizarlo;', 'onSurfaceVariant', False),
                 ('Nextcloud le da una contraseña de aplicación que puedes revocar.', 'onSurfaceVariant', False),
                 ('', 'onSurface', False),
                 (f'Servidor: {self.server_text}▏' if self.editing_server else f'Servidor: {account.settings()["server"]}',
                  'primary' if self.editing_server else 'onSurfaceVariant', self.editing_server),
                 ('', 'onSurface', False),
                 *((('Nextcloud › Ajustes personales › Seguridad › «Crear nueva contraseña de aplicación»', 'onSurfaceVariant', False),
                    (f'Usuario: {self.manual_user}' + ('▏' if self.manual_step == 'user' else ''), 'primary', self.manual_step == 'user'),
                    ('Contraseña de aplicación: ' + '•' * len(self.manual_password) + ('▏' if self.manual_step == 'password' else ''),
                     'primary', self.manual_step == 'password')) if self.manual_step else ()),
                 (self.login_state, 'primary', False),
                 (self.login_url, 'onSurfaceVariant', False)]
        for offset, (text, role, bold) in enumerate(lines):
            if text:
                text = truncate(text, width - 4)
                canvas.text(max(1, (width - len(text)) // 2), y + offset, text, self._style(palette, role, bold=bold))

    def _draw_overlay(self, canvas, palette):
        w, h = canvas.width, canvas.height
        canvas.fill(Rect(0, 0, w, h), ' ', Style(bg=palette['surfaceContainerHigh']))
        title = 'Subiendo…' if self.uploading else ('Listo' if not self.upload_error else 'No terminó')
        box(canvas, Rect(0, 0, w, h), Style(fg=palette['outlineVariant'], bg=palette['surfaceContainerHigh']),
            [(title, Style(fg=palette['onSurface'], bg=palette['surfaceContainerHigh'], bold=True))])
        bg = palette['surfaceContainerHigh']
        y = 2
        inner = w - 4
        if self.uploading:
            with self._lock:
                items = list(self.progress.items())
                all_done, all_total = self.overall
            for name, (done, total) in items[: max(0, (h - 6) // 2)]:
                canvas.text(2, y, truncate(name, inner), Style(fg=palette['onSurface'], bg=bg))
                filled, empty = bar(done / total if total else 1.0, inner - 6)
                canvas.text(2, y + 1, filled, Style(fg=palette['primary'], bg=bg))
                canvas.text(2 + len(filled), y + 1, empty, Style(fg=palette['outlineVariant'], bg=bg))
                percent = f'{int(done * 100 / total) if total else 100:3d}%'
                canvas.text(w - 2 - len(percent), y + 1, percent, Style(fg=palette['onSurfaceVariant'], bg=bg))
                y += 2
            summary = f'{human_size(all_done)} de {human_size(all_total)}'
            canvas.text(2, h - 2, truncate(summary, inner), Style(fg=palette['onSurfaceVariant'], bg=bg))
            return
        if self.upload_error:
            canvas.text(2, y, truncate(self.upload_error, inner), Style(fg=palette['error'], bg=bg))
            y += 2
        for result in self.results[: max(0, (h - 4) // 2)]:
            ok = result.ok and not result.link_error
            canvas.text(2, y, '✓' if ok else '✗', Style(fg=palette['primary' if ok else 'error'], bg=bg, bold=True))
            canvas.text(4, y, truncate(f'{result.name} → {result.remote}' if result.ok else result.name, inner - 2),
                        Style(fg=palette['onSurface'], bg=bg))
            detail = result.url or result.error or result.link_error or human_size(result.size)
            if result.url and result.password:
                detail += f'  · contraseña: {result.password}'
            role = 'primary' if result.url else ('error' if not ok else 'onSurfaceVariant')
            canvas.text(4, y + 1, truncate(detail, inner - 2), Style(fg=palette[role], bg=bg))
            y += 2
