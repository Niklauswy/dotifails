"""Wysun LANShare — share folders or files with the local network.

One page (static/) over a small JSON API. Video streams with Range (Safari/iPhone), thumbnails
and hover sprites (ffmpeg), folders and lists as .zip, uploads only when started with --subidas,
an optional password, and shutdown after a while without use. While it runs, the bar reads its
status file (status.py) and can stop it (`wysun lanshare --detener PID`).
"""
import errno
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import gzip
import hmac
import json
import mimetypes
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor

from wysun_core.jsonio import atomic_path
from wysun_lanshare import media, net, options as opts, status, webtheme
from wysun_lanshare.share import Share, clean_name, kind_of, unique_name

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
CHUNK = 1024 * 1024
PORT_TRIES = 20
MAX_FAILS = 5
BLOCK_SECONDS = 60
COOKIE = 'wysun_lanshare'

for _type, _ext in (('video/mp4', '.m4v'), ('video/x-matroska', '.mkv'), ('video/mp2t', '.ts'), ('text/plain', '.md'),
                    ('text/plain', '.log'), ('image/avif', '.avif'), ('image/heic', '.heic'), ('font/ttf', '.ttf')):
    mimetypes.add_type(_type, _ext)


class Incomplete(Exception):
    """An upload that did not arrive whole; its temporary file is discarded."""


class Gate:
    """The optional password: a random HttpOnly session per person who entered, failures limited per IP."""

    def __init__(self, password, clock=time.time):
        self.password = password
        self.clock = clock
        self.tokens = set()
        self.fails = {}
        self._lock = threading.Lock()

    def check(self, ip, attempt):
        """A new session token, None for a wrong password, or 'blocked' after too many failures."""
        with self._lock:
            count, until = self.fails.get(ip, (0, 0))
            if until > self.clock():
                return 'blocked'
            if hmac.compare_digest((attempt or '').strip().encode(), self.password.encode()):
                self.fails.pop(ip, None)
                token = secrets.token_urlsafe(24)
                self.tokens.add(token)
                return token
            count += 1
            if count >= MAX_FAILS:
                self.fails[ip] = (0, self.clock() + BLOCK_SECONDS)
                return 'blocked'
            self.fails[ip] = (count, 0)
            return None

    def allowed(self, cookie_header):
        if self.password is None:
            return True
        jar = cookies.SimpleCookie()
        try:
            jar.load(cookie_header or '')
        except cookies.CookieError:
            return False
        morsel = jar.get(COOKIE)
        return bool(morsel) and morsel.value in self.tokens


class App:
    """Everything one running LANShare knows; the handler reaches it as self.server.app."""

    def __init__(self, options, clock=time.time):
        self.options = options
        self.share = Share(options.paths)
        self.uploads = options.uploads and self.share.mode == 'folder'
        self.gate = Gate(options.password, clock)
        self.activity = status.Activity(options.idle, clock)
        self.host = socket.gethostname().split('.')[0] or 'Wysun'


def notify(name, where):
    """System notification for a received file (the server sends it: no shell needed)."""
    if not shutil.which('notify-send'):
        return
    argv = ['notify-send', '-a', 'Wysun LANShare', '-i', 'folder-download', 'Archivo recibido', f'{name} · {where}']

    def send():
        try:
            subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError):
            pass

    threading.Thread(target=send, daemon=True).start()


class Counted:
    """A write-only stream that reports what goes through it (zip downloads)."""

    def __init__(self, raw, activity, tid):
        self.raw, self.activity, self.tid = raw, activity, tid

    def write(self, data):
        self.raw.write(data)
        self.activity.advance(self.tid, len(data))
        return len(data)

    def flush(self):
        self.raw.flush()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'WysunLANShare/2'

    @property
    def app(self):
        return self.server.app

    # -- helpers
    def send_bytes(self, data, ctype, status_code=200, extra=None):
        self.send_response(status_code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def send_json(self, obj, status_code=200, extra=None):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode(), 'application/json; charset=utf-8',
                        status_code, dict({'Cache-Control': 'no-store'}, **(extra or {})))

    def fail(self, status_code, message):
        self.send_json({'error': message}, status_code)

    def query(self):
        return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}

    def route(self):
        return urllib.parse.unquote(urllib.parse.urlparse(self.path).path)

    def ip(self):
        return self.client_address[0]

    def agent(self):
        return self.headers.get('User-Agent', '')

    def log_message(self, fmt, *args):
        pass

    def authorised(self):
        """True for someone who may see what is shared; counts as use. Otherwise answers 401."""
        if not self.app.gate.allowed(self.headers.get('Cookie')):
            self.send_json({'error': 'Hace falta la contraseña', 'locked': True}, 401)
            return False
        self.app.activity.touch(self.ip(), self.agent())
        return True

    # -- routing
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.route()
        try:
            if path == '/' or path.startswith('/b/'):
                return self.serve_static('index.html')
            if path.startswith('/static/'):
                return self.serve_static(path[len('/static/'):])
            if path.startswith('/fonts/'):
                return self.serve_font(path[len('/fonts/'):])
            if path == '/theme.css':
                return self.send_bytes(webtheme.css().encode(), 'text/css; charset=utf-8', extra={'Cache-Control': 'no-cache'})
            if path == '/api/info':
                return self.api_info()
            if not self.authorised():
                return None
            if path == '/api/ls':
                return self.api_ls()
            if path in ('/api/thumb', '/api/sprite'):
                return self.api_image(path.rsplit('/', 1)[1])
            if path.startswith('/raw/'):
                return self.serve_file(path[len('/raw/'):])
            if path == '/zip' or path.startswith('/zip/'):
                return self.serve_zip(path[len('/zip/'):])
            return self.fail(404, 'No encontrado')
        except (BrokenPipeError, ConnectionResetError):
            return None

    def do_PUT(self):
        if self.route() != '/api/upload':
            return self.fail(404, 'No encontrado')
        if self.authorised():
            self.api_upload()
        return None

    def do_POST(self):
        path = self.route()
        if path == '/api/login':
            return self.api_login()
        if path != '/api/mkdir':
            return self.fail(404, 'No encontrado')
        if self.authorised():
            self.api_mkdir()
        return None

    # -- public
    def serve_static(self, name):
        p = os.path.realpath(os.path.join(STATIC, name))
        if not p.startswith(STATIC + os.sep) or not os.path.isfile(p):
            return self.fail(404, 'No encontrado')
        with open(p, 'rb') as f:
            data = f.read()
        ctype = mimetypes.guess_type(p)[0] or 'application/octet-stream'
        if ctype.startswith('text/') or ctype.endswith('javascript'):
            ctype += '; charset=utf-8'
        return self.send_bytes(data, ctype, extra={'Cache-Control': 'no-cache'})

    def serve_font(self, name):
        if name not in webtheme.FONTS.values():
            return self.fail(404, 'No encontrado')
        source = os.path.join(webtheme.FONTS_DIR, name)
        extra = {'Cache-Control': 'public, max-age=31536000, immutable'}
        if 'gzip' in self.headers.get('Accept-Encoding', ''):
            packed = compressed(source)
            if packed:
                with open(packed, 'rb') as f:
                    return self.send_bytes(f.read(), 'font/ttf', extra=dict(extra, **{'Content-Encoding': 'gzip'}))
        with open(source, 'rb') as f:
            return self.send_bytes(f.read(), 'font/ttf', extra=extra)

    def api_info(self):
        app = self.app
        locked = not app.gate.allowed(self.headers.get('Cookie'))
        if not locked:
            app.activity.touch(self.ip(), self.agent())
        self.send_json({'host': app.host, 'title': app.share.title, 'mode': app.share.mode, 'uploads': app.uploads,
                        'locked': locked, 'password': app.gate.password is not None})

    def api_login(self):
        if self.app.gate.password is None:
            return self.send_json({'ok': True})
        try:
            length = min(int(self.headers.get('Content-Length', '0')), 4096)
            attempt = json.loads(self.rfile.read(length) or b'{}').get('clave', '')
        except (ValueError, AttributeError):
            attempt = ''
        result = self.app.gate.check(self.ip(), str(attempt))
        if result == 'blocked':
            return self.fail(429, 'Demasiados intentos. Espera un minuto.')
        if result is None:
            return self.fail(403, 'Contraseña incorrecta')
        self.app.activity.touch(self.ip(), self.agent())
        return self.send_json({'ok': True}, extra={'Set-Cookie': f'{COOKIE}={result}; HttpOnly; SameSite=Lax; Path=/'})

    # -- api
    def api_ls(self):
        rel = self.query().get('path', '')
        try:
            entries = self.app.share.listing(rel)
        except LookupError:
            return self.fail(404, 'Carpeta no encontrada')
        except PermissionError:
            return self.fail(403, 'Sin permiso')
        media_items = [e for e in entries if e['kind'] in ('video', 'audio')]
        if media_items and len(media_items) <= 500:
            base = rel.strip('/')
            with ThreadPoolExecutor(8) as pool:
                found = pool.map(lambda e: self.app.share.resolve(f'{base}/{e["name"]}' if base else e['name']), media_items)
                metas = pool.map(lambda p: media.probe(p) if p else {}, list(found))
                for entry, meta in zip(media_items, metas):
                    entry.update(meta)
        self.send_json({'path': rel.strip('/'), 'title': self.app.share.title, 'mode': self.app.share.mode,
                        'entries': entries, 'uploads': self.app.uploads})

    def api_image(self, kind):
        p = self.app.share.resolve(self.query().get('path', ''))
        wanted = ('video',) if kind == 'sprite' else ('video', 'image')
        if not p or not os.path.isfile(p) or kind_of(p) not in wanted:
            return self.fail(404, 'No encontrado')
        out = media.cached_image(p, kind)
        if not out:
            return self.fail(404, 'Sin vista previa')
        with open(out, 'rb') as f:
            data = f.read()
        return self.send_bytes(data, 'image/jpeg', extra={'Cache-Control': 'public, max-age=604800'})

    def upload_target(self):
        if not self.app.uploads:
            self.fail(403, 'Las subidas no están permitidas')
            return None, None
        q = self.query()
        directory = self.app.share.resolve(q.get('dir', ''))
        name = clean_name(q.get('name', ''))
        if not directory or not os.path.isdir(directory) or not name:
            self.fail(400, 'Destino inválido')
            return None, None
        return directory, name

    def api_upload(self):
        directory, name = self.upload_target()
        if not directory:
            return None
        try:
            length = int(self.headers.get('Content-Length', ''))
        except ValueError:
            return self.fail(411, 'Falta Content-Length')
        name = unique_name(directory, name)
        dest = os.path.join(directory, name)
        remaining = length
        tid = self.app.activity.begin(self.ip(), self.agent(), name, length, 'up')
        try:
            # Hidden temporary next to the destination; it becomes the file only when every byte arrived.
            with atomic_path(dest, mode=0o644) as tmp:
                with open(tmp, 'wb') as f:
                    while remaining > 0:
                        buf = self.rfile.read(min(CHUNK, remaining))
                        if not buf:
                            break
                        f.write(buf)
                        remaining -= len(buf)
                        self.app.activity.advance(tid, len(buf))
                if remaining:
                    raise Incomplete
        except Incomplete:
            self.close_connection = True
            return self.fail(400, 'Subida incompleta')
        except OSError as ex:
            return self.fail(500, f'No se pudo guardar: {ex.strerror}')
        finally:
            self.app.activity.end(tid)
        notify(name, self.app.share.display(self.query().get('dir', '')))
        return self.send_json({'ok': True, 'name': name})

    def api_mkdir(self):
        directory, name = self.upload_target()
        if not directory:
            return None
        target = os.path.join(directory, name)
        if os.path.lexists(target):
            return self.fail(409, 'Ya existe')
        try:
            os.mkdir(target)
        except OSError as ex:
            return self.fail(500, f'No se pudo crear: {ex.strerror}')
        return self.send_json({'ok': True, 'name': name})

    # -- transfers
    def serve_file(self, rel):
        p = self.app.share.resolve(rel)
        if not p or not os.path.isfile(p):
            return self.fail(404, 'Archivo no encontrado')
        size = os.path.getsize(p)
        start, end = 0, size - 1
        m = re.match(r'bytes=(\d*)-(\d*)$', self.headers.get('Range', '').strip())
        partial = False
        if m and (m.group(1) or m.group(2)):
            s, e = m.groups()
            if s:
                start = int(s)
                end = min(int(e), size - 1) if e else size - 1
            else:
                start = max(0, size - int(e))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                return self.end_headers()
            partial = True
        length = end - start + 1
        download = bool(self.query().get('dl'))
        self.send_response(206 if partial else 200)
        if partial:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        ctype = mimetypes.guess_type(p)[0] or 'application/octet-stream'
        if ctype.startswith('text/'):
            ctype += '; charset=utf-8'
        self.send_header('Content-Type', ctype)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(length))
        if download:
            fname = os.path.basename(p)
            ascii_name = fname.encode('ascii', 'replace').decode().replace('"', '')
            self.send_header('Content-Disposition',
                             f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{urllib.parse.quote(fname)}")
        self.end_headers()
        if self.command == 'HEAD':
            return None
        tid = self.app.activity.begin(self.ip(), self.agent(), os.path.basename(p), length, 'down' if download else 'view')
        try:
            with open(p, 'rb') as f:
                f.seek(start)
                while length > 0:
                    buf = f.read(min(CHUNK, length))
                    if not buf:
                        break
                    self.wfile.write(buf)
                    length -= len(buf)
                    self.app.activity.advance(tid, len(buf))
        finally:
            self.app.activity.end(tid)
        return None

    def serve_zip(self, rel):
        share = self.app.share
        if not share.is_dir(rel):
            return self.fail(404, 'Carpeta no encontrada')
        name = share.zip_name(rel)
        self.send_response(200)
        self.send_header('Content-Type', 'application/zip')
        self.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{urllib.parse.quote(name)}.zip")
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        if self.command == 'HEAD':
            return None
        tid = self.app.activity.begin(self.ip(), self.agent(), name + '.zip', None, 'down')
        try:
            with zipfile.ZipFile(Counted(self.wfile, self.app.activity, tid), 'w', zipfile.ZIP_STORED, allowZip64=True) as zf:
                for real, arcname in share.zip_members(rel):
                    try:
                        zf.write(real, arcname)
                    except OSError:
                        continue
        finally:
            self.app.activity.end(tid)
        return None


_packing = threading.Lock()


def compressed(source):
    """A gzip copy of a packaged font in the cache (made once), or None."""
    st = os.stat(source)
    target = os.path.join(media.cache_dir(), 'fonts', f'{os.path.basename(source)}.{st.st_mtime_ns}.gz')
    with _packing:
        if not os.path.exists(target):
            try:
                with atomic_path(target) as tmp, open(source, 'rb') as raw:
                    tmp.write_bytes(gzip.compress(raw.read(), 6))
            except OSError:
                return None
    return target


class Server(ThreadingHTTPServer):
    daemon_threads = True


def make_server(app, host='0.0.0.0', port=None):
    """Bind the asked port or, when it is taken, one of the next PORT_TRIES; (server, port)."""
    first = app.options.port if port is None else port
    for candidate in range(first, first + PORT_TRIES + 1):
        try:
            srv = Server((host, candidate), Handler)
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                continue
            raise
        srv.app = app
        return srv, candidate
    raise OSError(errno.EADDRINUSE, f'Los puertos {first}–{first + PORT_TRIES} están ocupados')


def _duration(seconds):
    if seconds % 3600 == 0:
        return f'{seconds // 3600} h'
    if seconds % 60 == 0:
        return f'{seconds // 60} min'
    return f'{seconds} s'


def _watch(srv, app, status_file, stopped):
    """Keep the status file fresh and stop the server once it is idle."""
    while not stopped.wait(0.5):
        try:
            status_file.write(app.activity)
        except OSError:
            pass
        if app.activity.expired():
            print(f'\nSin uso durante {_duration(app.options.idle)}: se detiene.', flush=True)
            srv.shutdown()
            return


def run(options):
    app = App(options)
    try:
        srv, port = make_server(app)
    except OSError as error:
        print(f'wysun lanshare: {error.strerror or error}', file=sys.stderr)
        return 1
    addresses = net.addresses()
    urls = [f'http://{a["ip"]}:{port}' for a in addresses]
    easy = net.easy_name(port)
    share = app.share
    print(f'Wysun LANShare · compartiendo {share.title}')
    for path in share.paths:
        print(f'  {path}')
    if port != options.port:
        print(f'El puerto {options.port} está ocupado; se usa el {port}.')
    print('Subidas permitidas' if app.uploads else 'Solo ver y descargar')
    if options.password:
        print(f'Contraseña: {options.password}')
    if easy:
        print(f'\n  → {easy}')
    named = len(addresses) > 1
    for address, url in zip(addresses, urls):
        print(f'  → {url}' + (f'   ({address["name"]})' if named and address['name'] else ''))
    limit = f'Se apaga tras {_duration(options.idle)} sin uso' if options.idle else 'Sin apagado automático'
    print(f'\n{limit} · Ctrl+C para detener', flush=True)

    status.prune()
    status_file = status.StatusFile(os.getpid(), {
        'paths': share.paths, 'title': share.title, 'mode': share.mode, 'host': app.host,
        'addresses': ([easy] if easy else []) + urls, 'port': port, 'password': options.password,
        'uploads': app.uploads, 'started': time.time()})
    stopped = threading.Event()

    def terminate(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGHUP, terminate)
    watcher = threading.Thread(target=_watch, args=(srv, app, status_file, stopped), daemon=True)
    try:
        status_file.write(app.activity, force=True)
        watcher.start()
        srv.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        stopped.set()
        status_file.remove()
        srv.server_close()
    return 0


def main(argv=None):
    options = opts.parse(argv)
    if options.stop is not None:
        if status.stop(options.stop):
            return 0
        print(f'wysun lanshare: {options.stop} no es un LANShare tuyo en ejecución', file=sys.stderr)
        return 1
    return run(options)


if __name__ == '__main__':
    sys.exit(main())
