"""`wysun drive` with no arguments: the two-pane selector (layout B) on a transparent background.

**Subir** browses from the current folder (Archivos on the left, Detalle with a preview on the
right, the tray of chips below); **Recientes** lists the history with its links. Uploads run as a
child `wysun drive up … --resultado FILE` in its own session: the selector follows it through the
bar's status file, ``Esc`` cancels it (SIGTERM) and ``b``/``q`` leave it running in the background
(``RESULTADO.notificar`` tells it to notify when it ends). Without a session the body offers the browser login, an app
password (``p``) or another server (``s``). Keys: ``?`` in the app, or `docs/utilities.md`.
"""
from __future__ import annotations

import collections
import os
import shlex
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit

from wysun_core import launch
from wysun_core.tui import App, kit
from wysun_core.tui.draw import truncate
from wysun_drive import account, api, history, login, status
from wysun_drive.cli import copy, generate_password, human_size, open_url
from wysun_drive.client import Client, DriveError
from wysun_drive.ui import view
from wysun_drive.ui.preview import Previews

BROWSE_HINTS = [('espacio', 'marcar'), ('u', 'subir'), ('l', 'link'), ('p', 'contraseña'), ('d', 'caducidad'),
                ('/', 'filtrar'), ('Tab', 'Recientes'), ('?', 'teclas'), ('q', 'salir')]
RECENT_HINTS = [('c', 'copiar link'), ('o', 'abrir'), ('k', 'quitar link'), ('n', 'link nuevo'), ('/', 'filtrar'),
                ('Tab', 'Subir'), ('?', 'teclas'), ('q', 'salir')]
UPLOAD_HINTS = [('Esc', 'cancelar'), ('b', 'seguir en segundo plano (barra)'), ('q', 'salir y seguir subiendo')]
DONE_HINTS = [('c', 'copiar de nuevo'), ('o', 'abrir'), ('↵', 'seguir subiendo'), ('Tab', 'Recientes'), ('q', 'salir')]
LOGIN_HINTS = [('↵', 'iniciar sesión'), ('p', 'contraseña de aplicación'), ('s', 'cambiar servidor'), ('q', 'salir')]
EDIT_HINTS = [('↵', 'guardar e iniciar sesión'), ('Esc', 'cancelar')]
MANUAL_HINTS = [('↵', 'siguiente'), ('Esc', 'cancelar')]
FILTER_HINTS = [('↵', 'aplicar'), ('Esc', 'borrar el filtro')]
SPEED_SAMPLES = 60
POLL = 0.25


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


class DriveApp(App):
    transparent = True

    def __init__(self, term=None, home=None, start=None):
        super().__init__(term=term, home=home)
        self.cwd = Path(start or os.getcwd()).absolute()
        self.account = account.current()
        self.tab = 'browse' if self.account else 'login'
        self.show_hidden = False
        self.entries: list[tuple[str, bool, int, float]] = []
        self.listing_error = ''
        self.cursor = 0
        self.top = 0
        self.marked: list[str] = []
        self.marked_sizes: dict[str, int] = {}
        self.with_link = False
        self.with_password = False
        self.days_index = 0
        self.filter_text = ''
        self.filtering = False
        self.help = False
        self.recent: list[dict] = []
        self.recent_cursor = 0
        self.spin = 0
        self.quota_text = ''
        self.previews = Previews(self.invalidate)
        self._remote: dict[str, bool | None] = {}
        self._remote_pending: set[str] = set()
        self._check_timer = None
        # upload (a child process)
        self.mode = 'idle'                  # idle | uploading | done
        self.child: subprocess.Popen | None = None
        self.result_path = ''
        self.upload_title = ''
        self.upload_link = False
        self.upload_days = None
        self.progress_items: list[dict] = []
        self.overall = (0, 0)
        self.speeds = collections.deque(maxlen=SPEED_SAMPLES)
        self._last_sample = None
        self.results: list[dict] = []
        self.upload_error = ''
        self.upload_copied = False
        self._poll_timer = None
        # login
        self.login_url = ''
        self.login_state = ''
        self.login_busy = False
        self.editing_server = False
        self.server_text = ''
        self.manual_step = None
        self.manual_user = ''
        self.manual_password = ''

    # -- lifecycle ---------------------------------------------------------
    def on_start(self):
        self.help_layer = kit.HelpLayer(lambda: view.help_lines(self))
        self.toast_layer = kit.Toast()
        self.layers.extend([self.help_layer, self.toast_layer])
        self._list()
        self.recent = history.load()
        self.every(0.12, self._tick)
        self._load_quota()

    def _tick(self):
        if self.mode == 'uploading' or self.login_busy or self.previews._pending:
            self.spin = (self.spin + 1) % 4
            self.invalidate()

    def on_theme(self):
        self.invalidate()

    def on_resize(self, width, height):
        self.toast_layer.place(self)
        if self.help:
            self.help_layer.place(self)
        self.invalidate()

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
                        info = entry.stat()
                    except OSError:
                        continue
                    entries.append((entry.name, is_dir, 0 if is_dir else info.st_size, info.st_mtime))
        except OSError as error:
            self.listing_error = f'No se pudo abrir la carpeta ({error.strerror})'
        entries.sort(key=lambda e: (not e[1], e[0].casefold()))
        self.entries = entries
        self.cursor = min(self.cursor, max(0, len(entries) - 1))
        self._schedule_check()
        self.invalidate()

    def visible_entries(self):
        if not self.filter_text:
            return self.entries
        needle = self.filter_text.casefold()
        return [e for e in self.entries if needle in e[0].casefold()]

    def visible_recent(self):
        if not self.filter_text:
            return self.recent
        needle = self.filter_text.casefold()
        return [e for e in self.recent if needle in str(e.get('name', '')).casefold() or needle in str(e.get('remote', '')).casefold()]

    def _current(self):
        entries = self.visible_entries()
        if not entries:
            return None
        name, is_dir, size, _mtime = entries[min(self.cursor, len(entries) - 1)]
        return str(self.cwd / name), is_dir, size

    def toast(self, text, seconds=3.0):
        self.toast_layer.show(self, text, seconds)

    @property
    def toast_text(self):
        layer = getattr(self, 'toast_layer', None)
        return layer.text if layer is not None and layer.visible else ''

    def _in_background(self, work, done=None, failed=None):
        """Run ``work()`` off the loop; ``done(result)`` / ``failed(message)`` back on it."""
        def run():
            try:
                result = work()
            except DriveError as error:
                message = str(error)
                if failed is not None:
                    self.after(0, lambda: failed(message))
                return
            except OSError as error:
                message = error.strerror or str(error)
                if failed is not None:
                    self.after(0, lambda: failed(message))
                return
            if done is not None:
                self.after(0, lambda: done(result))
        threading.Thread(target=run, daemon=True).start()

    def _load_quota(self):
        if not self.account:
            return
        acc = self.account

        def done(value):
            used, available = value
            if available is None:
                self.quota_text = f'{kit.GLYPH["cloud"]} {human_size(used)} usados'
            else:
                self.quota_text = f'{kit.GLYPH["cloud"]} {human_size(available)} libres de {human_size(used + available)}'
            self.invalidate()
        self._in_background(lambda: Client(acc).quota(), done, lambda message: None)

    # -- does it exist in the cloud? -----------------------------------------
    def remote_state(self, name):
        return self._remote.get(name)

    def _schedule_check(self):
        if self._check_timer is not None:
            self.cancel(self._check_timer)
        self._check_timer = self.after(0.25, self._check_current)

    def _check_current(self):
        self._check_timer = None
        current = self._current()
        if not current or not self.account:
            return
        name = os.path.basename(current[0])
        if name in self._remote or name in self._remote_pending:
            return
        self._remote_pending.add(name)
        folder, acc = account.settings()['folder'], self.account

        def done(found):
            self._remote_pending.discard(name)
            self._remote[name] = found
            self.invalidate()

        def failed(_message):
            self._remote_pending.discard(name)
        self._in_background(lambda: Client(acc).exists(f'{folder}/{name}' if folder else name), done, failed)

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
        if self.filtering:
            self.filter_text += event.text.strip()
            self.invalidate()
            return
        paths = _paths_from_paste(event.text)
        if not paths or self.tab == 'login' or self.mode == 'uploading':
            return
        for path in paths:
            self._mark(path, True)
        self.tab = 'browse'
        self.toast(f'{len(paths)} añadido' + ('s' if len(paths) != 1 else '') + ' · u para subir')

    def on_key(self, event):
        name, char = event.name, event.char
        if event.ctrl and name == 'c':
            self._leave()
            return
        if self.help:
            self.help = False
            self.help_layer.close(self)
            return
        if self.mode == 'uploading':
            if name == 'escape' and self.child is not None:
                self._signal_child(signal.SIGTERM)
                self.toast('Cancelando…')
            elif name == 'char' and char in ('b', 'q'):
                self._leave()
            return
        if self.editing_server:
            self._edit_key(name, char)
            return
        if self.manual_step:
            self._manual_key(name, char)
            return
        if self.filtering:
            self._filter_key(name, char)
            return
        if self.mode == 'done' and self.tab == 'browse':
            if name == 'char' and char == 'c':
                links = [r['url'] for r in self.results if r.get('url')]
                if links:
                    self.toast('Copiado' if copy('\n'.join(links)) else links[0])
                return
            if name == 'char' and char == 'o':
                link = next((r['url'] for r in self.results if r.get('url')), None)
                if link:
                    open_url(link)
                return
            if name in ('enter', 'escape'):
                self.mode = 'idle'
                self.invalidate()
                return
        if (name == 'char' and char == 'q') or (name == 'escape' and not self.filter_text):
            self.quit()
            return
        if name == 'escape' and self.filter_text:
            self.filter_text = ''
            self.invalidate()
            return
        if self.tab == 'login':
            self._login_key(name, char)
            return
        if name == 'char' and char == '?':
            self.help = True
            self.help_layer.open(self)
            return
        if name == 'char' and char == '/':
            self.filtering = True
            self.invalidate()
            return
        if name in ('tab', 'backtab') or (name == 'char' and char in '12'):
            target = {'1': 'browse', '2': 'recent'}.get(char) if name == 'char' else None
            self.tab = target or ('recent' if self.tab == 'browse' else 'browse')
            self.filter_text = ''
            if self.tab == 'recent':
                self.recent = history.load()
            self.invalidate()
            return
        if self.tab == 'browse':
            self._browse_key(name, char)
        else:
            self._recent_key(name, char)

    def _filter_key(self, name, char):
        if name == 'escape':
            self.filtering, self.filter_text = False, ''
        elif name == 'enter':
            self.filtering = False
        elif name == 'backspace':
            self.filter_text = self.filter_text[:-1]
        elif name == 'char' and char and char.isprintable():
            self.filter_text += char
        self.cursor = self.top = self.recent_cursor = 0
        self._schedule_check()
        self.invalidate()

    def on_mouse(self, event):
        if event.kind in ('wheelup', 'wheeldown') and self.mode != 'uploading':
            delta = -3 if event.kind == 'wheelup' else 3
            if self.tab == 'browse':
                self._move(delta)
            elif self.tab == 'recent':
                self._move_recent(delta)

    def _move(self, delta):
        entries = self.visible_entries()
        if entries:
            self.cursor = max(0, min(len(entries) - 1, self.cursor + delta))
            self._schedule_check()
            self.invalidate()

    def _move_recent(self, delta):
        entries = self.visible_recent()
        if entries:
            self.recent_cursor = max(0, min(len(entries) - 1, self.recent_cursor + delta))
            self.invalidate()

    def _mark(self, path, on=None):
        marked = path in self.marked
        on = not marked if on is None else on
        if on and not marked:
            self.marked.append(path)
            try:
                self.marked_sizes[path] = 0 if os.path.isdir(path) else os.path.getsize(path)
            except OSError:
                self.marked_sizes[path] = 0
        elif not on and marked:
            self.marked.remove(path)
            self.marked_sizes.pop(path, None)

    def _browse_key(self, name, char):
        rows = max(1, self.size[1] - 7)
        moves = {'up': -1, 'down': 1, 'pageup': -rows, 'pagedown': rows}
        entries = self.visible_entries()
        if name in moves:
            self._move(moves[name])
        elif name == 'home':
            self._move(-len(entries))
        elif name == 'end':
            self._move(len(entries))
        elif name in ('right', 'enter'):
            current = self._current()
            if current and current[1]:
                self.cwd, self.cursor, self.top, self.filter_text = Path(current[0]), 0, 0, ''
                self._list()
        elif name in ('left', 'backspace'):
            if self.cwd.parent != self.cwd:
                came_from = self.cwd.name
                self.cwd, self.filter_text = self.cwd.parent, ''
                self._list()
                self.cursor = next((i for i, e in enumerate(self.entries) if e[0] == came_from), 0)
        elif name == 'char' and char == ' ':
            current = self._current()
            if current:
                self._mark(current[0])
                self._move(1)
                self.invalidate()
        elif name == 'char' and char == 'a':
            paths = [str(self.cwd / e[0]) for e in entries]
            everything = paths and all(p in self.marked for p in paths)
            for path in paths:
                self._mark(path, not everything)
            self.invalidate()
        elif name == 'char' and char == 'l':
            self.with_link = not self.with_link
            self.toast('Se creará el link y se copiará' if self.with_link else 'Sin link')
        elif name == 'char' and char == 'p':
            self.with_password = not self.with_password
            self.with_link = self.with_link or self.with_password
            self.toast('El link tendrá una contraseña generada' if self.with_password else 'Link sin contraseña')
        elif name == 'char' and char == 'd':
            self.days_index = (self.days_index + 1) % len(view.DAYS)
            days = view.DAYS[self.days_index]
            self.with_link = self.with_link or days is not None
            self.toast(f'El link caducará en {days} días' if days else 'El link no caducará')
        elif name == 'char' and char == '.':
            self.show_hidden = not self.show_hidden
            self._list()
        elif name == 'char' and char == 'u':
            current = self._current()
            paths = list(self.marked) or ([current[0]] if current else [])
            if paths:
                self._start_upload(paths)

    def _recent_key(self, name, char):
        if name in ('up', 'down'):
            self._move_recent(1 if name == 'down' else -1)
            return
        entries = self.visible_recent()
        if not entries:
            return
        entry = entries[min(self.recent_cursor, len(entries) - 1)]
        if name == 'char' and char == 'c':
            if entry.get('url'):
                self.toast('Link copiado' if copy(entry['url']) else entry['url'])
            else:
                self._make_link(entry)
        elif name == 'char' and char == 'n':
            self._make_link(entry)
        elif name == 'char' and char == 'o' and entry.get('url'):
            open_url(entry['url'])
        elif name == 'char' and char == 'k' and entry.get('url'):
            self._remove_link(entry)

    # -- links from Recientes ---------------------------------------------------
    def _make_link(self, entry):
        self.toast('Creando link…')
        password = generate_password() if self.with_password else None
        days = view.DAYS[self.days_index]

        def done(share):
            copied = copy(share['url'])
            self.recent = history.load()
            self.toast(('Link creado y copiado' if copied else share['url']) + (f' · contraseña {password}' if password else ''), 6)
        self._in_background(lambda: api.make_link(entry['remote'], password=password, expire_days=days), done,
                            lambda message: self.toast(message, 5))

    def _remove_link(self, entry):
        self.toast('Quitando el link…')

        def done(_):
            self.recent = history.load()
            self.toast('Link quitado: el archivo sigue en la nube')
        self._in_background(lambda: api.remove_link(entry['remote']), done, lambda message: self.toast(message, 5))

    # -- upload as a child process ------------------------------------------------
    def _start_upload(self, paths):
        self.result_path = str(status.status_dir() / f'result-{uuid.uuid4().hex}.json')
        status.status_dir().mkdir(mode=0o700, parents=True, exist_ok=True)
        days = view.DAYS[self.days_index]
        args = ['up', '--resultado', self.result_path, '--origen', 'terminal']
        if self.with_link:
            args.append('--link')
        if self.with_password:
            args.append('--clave')
        if days:
            args += ['--caduca', f'{days}d']
        argv = launch.argv('wysun_drive', *args, '--', *paths)
        try:
            self.child = subprocess.Popen(argv, env=launch.environment(), cwd=str(self.cwd), start_new_session=True,
                                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as error:
            self.toast(f'No se pudo empezar la subida ({error.strerror})', 5)
            return
        names = [os.path.basename(p) for p in paths]
        self.upload_title = names[0] if len(names) == 1 else f'{len(names)} elementos'
        self.upload_link, self.upload_days = self.with_link, days
        self.mode = 'uploading'
        self.progress_items, self.overall, self.results, self.upload_error = [], (0, 0), [], ''
        self.speeds.clear()
        self._last_sample = (time.monotonic(), 0)
        self._poll_timer = self.every(POLL, self._poll_child)
        self.invalidate()

    def speed(self):
        """Bytes per second over the last few samples."""
        recent = list(self.speeds)[-6:]
        return sum(recent) / len(recent) if recent else 0.0

    def eta(self):
        done, total = self.overall
        speed = self.speed()
        if not total or speed <= 0 or done >= total:
            return ''
        seconds = int((total - done) / speed)
        return f'{seconds // 60}:{seconds % 60:02d}' if seconds < 3600 else f'{seconds // 3600} h {seconds % 3600 // 60} min'

    def _signal_child(self, number):
        try:
            if self.child is not None and self.child.poll() is None:
                self.child.send_signal(number)
        except OSError:
            pass

    def _poll_child(self):
        child = self.child
        if child is None:
            return
        from wysun_core.jsonio import read_json
        data = read_json(status.status_dir() / f'{child.pid}.json', None)
        if isinstance(data, dict):
            self.progress_items = [i for i in data.get('items', []) if isinstance(i, dict)]
            self.overall = (int(data.get('done') or 0), int(data.get('total') or 0))
        now = time.monotonic()
        if self._last_sample and now - self._last_sample[0] >= 0.5:
            then, before = self._last_sample
            self.speeds.append(max(0.0, (self.overall[0] - before) / (now - then)))
            self._last_sample = (now, self.overall[0])
        code = child.poll()
        if code is not None:
            self._child_done(code)
        self.invalidate()

    def _child_done(self, code):
        if self._poll_timer is not None:
            self.cancel(self._poll_timer)
            self._poll_timer = None
        from wysun_core.jsonio import read_json
        data = read_json(self.result_path, None)
        try:
            os.unlink(self.result_path)
        except OSError:
            pass
        pid = self.child.pid if self.child is not None else None
        self.child = None
        self.mode = 'done'
        if pid is not None:     # killed before its own cleanup: the bar must not show it any more
            (status.status_dir() / f'{pid}.json').unlink(missing_ok=True)
        if isinstance(data, dict):
            self.results = [r for r in data.get('results', []) if isinstance(r, dict)]
            self.upload_error = str(data.get('error') or '')
            self.upload_copied = bool(data.get('copied'))
        else:
            self.results, self.upload_copied = [], False
            self.upload_error = ('Subida cancelada' if code == -signal.SIGTERM
                                 else f'La subida terminó sin resultado (código {code})')
        if not self.upload_error and all(r.get('ok') for r in self.results):
            self.marked, self.marked_sizes = [], {}
        self._remote.clear()
        self.recent = history.load()
        self._load_quota()

    def _leave(self):
        """Quit; an upload in flight keeps going and notifies when it ends."""
        if self.mode == 'uploading' and self.child is not None:
            try:      # the child notifies at the end when this marker exists (see cli.NotifyLater)
                fd = os.open(self.result_path + '.notificar', os.O_WRONLY | os.O_CREAT, 0o600)
                os.close(fd)
            except OSError:
                pass
            self.left_running = self.upload_title
        self.quit()

    # -- login ---------------------------------------------------------------------
    def _login_key(self, name, char):
        if name == 'enter' and not self.login_busy:
            self._start_login()
        elif name == 'char' and char == 'p' and not self.login_busy:
            self.manual_step, self.manual_user, self.manual_password = 'user', '', ''
            self.login_state = ''
            self.invalidate()
        elif name == 'char' and char == 's' and not self.login_busy:
            self.editing_server, self.server_text = True, account.settings()['server']
            self.invalidate()

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

    def _logged_in(self, acc):
        self.account, self.login_busy, self.tab = acc, False, 'browse'
        self.toast(f'Sesión iniciada como {acc.user}')
        self._load_quota()

    def _login_failed(self, message):
        self.login_busy, self.login_state = False, message
        self.invalidate()

    def _start_manual_login(self):
        server = account.settings()['server']
        user, password = self.manual_user, self.manual_password
        self.manual_step, self.manual_password = None, ''
        self.login_busy, self.login_state = True, 'Comprobando…'

        def work():
            acc = login.manual(server, user, password)
            account.save(acc)
            return acc
        self._in_background(work, self._logged_in, self._login_failed)

    def _start_login(self):
        server = account.settings()['server']
        self.login_busy, self.login_state = True, f'Conectando con {urlsplit(server).hostname}…'
        self.invalidate()

        def work():
            url, poll = login.start(server)
            self.login_url = url
            self.login_state = 'Autoriza a Wysun Drive en el navegador que se abrió'
            open_url(url)
            self.invalidate()
            acc = login.wait(poll, server=server, cancelled=lambda: self._quitting)
            Client(acc).exists('')
            account.save(acc)
            return acc
        self._in_background(work, self._logged_in, self._login_failed)

    # -- drawing -------------------------------------------------------------------
    def draw(self, canvas):
        s = kit.Painter(self.palette)
        width, height = canvas.width, canvas.height
        view.header(self, canvas, s, width)
        if self.tab == 'login':
            self._draw_login(canvas, s, width, height)
            hints = EDIT_HINTS if self.editing_server else MANUAL_HINTS if self.manual_step else LOGIN_HINTS
        else:
            view.crumbs(self, canvas, s, width)
            left, right = view.panes(width, height, self.mode if self.tab == 'browse' else 'idle')
            if self.tab == 'browse':
                if left:
                    view.files_pane(self, canvas, s, left)
                if right:
                    {'idle': view.detail_pane, 'uploading': view.upload_pane, 'done': view.done_pane}[self.mode](
                        self, canvas, s, right)
                if self.mode == 'idle':
                    view.tray(self, canvas, s, width, height)
                hints = {'idle': BROWSE_HINTS, 'uploading': UPLOAD_HINTS, 'done': DONE_HINTS}[self.mode]
            else:
                if left:
                    view.recent_pane(self, canvas, s, left)
                if right:
                    view.recent_detail(self, canvas, s, right)
                hints = RECENT_HINTS
            if self.filtering:
                hints = FILTER_HINTS
        view.footer(self, canvas, s, hints)

    def _draw_login(self, canvas, s, width, height):
        server = urlsplit(account.settings()['server']).hostname or ''
        lines = [('Wysun Drive aún no tiene sesión', 'onSurface', True),
                 (f'↵ abre {server} en el navegador para autorizarlo;', 'onSurfaceVariant', False),
                 ('Nextcloud le da una contraseña de aplicación que puedes revocar.', 'onSurfaceVariant', False),
                 ('', 'onSurface', False),
                 (f'Servidor: {self.server_text}▏' if self.editing_server else f'Servidor: {account.settings()["server"]}',
                  'primary' if self.editing_server else 'onSurfaceVariant', self.editing_server),
                 ('', 'onSurface', False)]
        if self.manual_step:
            lines += [('Nextcloud › Ajustes personales › Seguridad › «Crear nueva contraseña de aplicación»', 'onSurfaceVariant', False),
                      (f'Usuario: {self.manual_user}' + ('▏' if self.manual_step == 'user' else ''), 'primary',
                       self.manual_step == 'user'),
                      ('Contraseña de aplicación: ' + '•' * len(self.manual_password)
                       + ('▏' if self.manual_step == 'password' else ''), 'primary', self.manual_step == 'password')]
        lines += [(self.login_state, 'primary', False), (self.login_url, 'onSurfaceVariant', False)]
        y = max(2, height // 2 - len(lines) // 2 - 1)
        for offset, (text, role, bold) in enumerate(lines):
            if text:
                text = truncate(text, width - 4)
                canvas.text(max(1, (width - len(text)) // 2), y + offset, text, s(role, bold=bold))


def main():
    app = DriveApp()
    code = app.run()
    title = getattr(app, 'left_running', None)
    if title:
        print(f'Wysun Drive sigue subiendo «{title}» en segundo plano: lo ves en la barra y te avisará al terminar.')
    return code
