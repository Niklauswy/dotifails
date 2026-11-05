"""A tiny in-memory Nextcloud on 127.0.0.1 for Wysun Drive tests (WebDAV, chunks v2, OCS, login v2)."""
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

USER = 'nico'
PASSWORD = 'SYNTHETIC-app-password-123'     # synthetic: tests check it never leaks


class State:
    def __init__(self):
        self.files = {}          # remote path -> bytes
        self.dirs = {''}
        self.chunks = {}         # session -> {name: bytes}
        self.shares = {}
        self.requests = []       # (method, path, has_auth)
        self.fail_puts = 0       # fail the next N chunk PUTs with 500
        self.share_error = None  # (http status, ocs message)
        self.redirect = False
        self.login_polls = 0
        self.login_ready_after = 1
        self.lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    @property
    def state(self):
        return self.server.state

    def _body(self):
        length = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(length) if length else b''

    def _send(self, status, data=b'', headers=None):
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        token = base64.b64encode(f'{USER}:{self.server.password}'.encode()).decode()
        return self.headers.get('Authorization') == f'Basic {token}'

    def _dav(self, path):
        prefix = f'/remote.php/dav/files/{USER}/'
        return unquote(path[len(prefix):]).strip('/') if path.startswith(prefix) else None

    def _route(self):
        parts = urlsplit(self.path)
        self.state.requests.append((self.command, unquote(parts.path), 'Authorization' in self.headers))
        if self.state.redirect:
            body = self._body()
            del body
            return self._send(302, headers={'Location': 'https://elsewhere.example/'})
        if parts.path == '/index.php/login/v2':
            self._body()
            port = self.server.server_address[1]
            return self._send(200, json.dumps({'poll': {'token': 'tok', 'endpoint': f'http://127.0.0.1:{port}/login/v2/poll'},
                                               'login': f'http://127.0.0.1:{port}/login/v2/flow/abc'}).encode())
        if parts.path == '/login/v2/poll':
            self._body()
            self.state.login_polls += 1
            if self.state.login_polls <= self.state.login_ready_after:
                return self._send(404)
            port = self.server.server_address[1]
            return self._send(200, json.dumps({'server': f'http://127.0.0.1:{port}', 'loginName': USER,
                                               'appPassword': self.server.password}).encode())
        if not self._authorized():
            self._body()
            return self._send(401)
        handler = getattr(self, 'do_' + self.command + '_', None)
        if handler is None:
            return self._send(405)
        return handler(parts)

    for _method in ('GET', 'PUT', 'POST', 'DELETE', 'MKCOL', 'PROPFIND', 'MOVE'):
        locals()['do_' + _method] = lambda self: self._route()

    # -- WebDAV ---------------------------------------------------------
    def do_PROPFIND_(self, parts):
        body = self._body()
        remote = self._dav(parts.path)
        if b'quota' in body:
            xml = (b'<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"><d:response><d:propstat><d:prop>'
                   b'<d:quota-used-bytes>8800000000</d:quota-used-bytes>'
                   b'<d:quota-available-bytes>44200000000</d:quota-available-bytes>'
                   b'</d:prop></d:propstat></d:response></d:multistatus>')
            return self._send(207, xml)
        found = remote in self.state.dirs or remote in self.state.files
        return self._send(207 if found else 404, b'<d:multistatus xmlns:d="DAV:"/>' if found else b'')

    def do_MKCOL_(self, parts):
        self._body()
        if parts.path.startswith(f'/remote.php/dav/uploads/{USER}/'):
            self.state.chunks[parts.path] = {}
            return self._send(201)
        remote = self._dav(parts.path)
        if remote in self.state.dirs:
            return self._send(405)
        parent = remote.rpartition('/')[0]
        if parent not in self.state.dirs:
            return self._send(409)
        self.state.dirs.add(remote)
        return self._send(201)

    def do_PUT_(self, parts):
        data = self._body()
        if parts.path.startswith(f'/remote.php/dav/uploads/{USER}/'):
            session, _, name = parts.path.rpartition('/')
            with self.state.lock:
                if self.state.fail_puts > 0:
                    self.state.fail_puts -= 1
                    return self._send(500)
            self.state.chunks[session][name] = data
            return self._send(201)
        remote = self._dav(parts.path)
        if remote.rpartition('/')[0] not in self.state.dirs:
            return self._send(409)
        self.state.files[remote] = data
        return self._send(201)

    def do_MOVE_(self, parts):
        self._body()
        session = parts.path.rpartition('/')[0]
        chunks = self.state.chunks.pop(session)
        destination = urlsplit(self.headers['Destination']).path
        remote = self._dav(destination)
        self.state.files[remote] = b''.join(chunks[name] for name in sorted(chunks))
        return self._send(201)

    def do_DELETE_(self, parts):
        self._body()
        if parts.path.startswith('/ocs/v2.php/apps/files_sharing/api/v1/shares/'):
            share_id = parts.path.rpartition('/')[2]
            self.state.shares.pop(share_id, None)
            return self._ocs(200, {})
        if parts.path == '/ocs/v2.php/core/apppassword':
            return self._ocs(200, {})
        self.state.chunks.pop(parts.path, None)
        return self._send(204)

    # -- OCS --------------------------------------------------------------
    def _ocs(self, status, data, message='OK'):
        code = 200 if status == 200 else status
        body = json.dumps({'ocs': {'meta': {'status': 'ok' if code == 200 else 'failure', 'statuscode': code,
                                            'message': message}, 'data': data}}).encode()
        return self._send(status, body, {'Content-Type': 'application/json'})

    def do_POST_(self, parts):
        fields = {k: v[0] for k, v in parse_qs(self._body().decode()).items()}
        if self.headers.get('OCS-APIRequest') != 'true':
            return self._send(400)
        if self.state.share_error:
            status, message = self.state.share_error
            return self._ocs(status, [], message)
        path = fields['path'].strip('/')
        if path not in self.state.files and path not in self.state.dirs:
            return self._ocs(404, [], 'Wrong path, file/folder does not exist')
        share_id = str(len(self.state.shares) + 1)
        self.state.shares[share_id] = fields
        port = self.server.server_address[1]
        return self._ocs(200, {'id': int(share_id), 'url': f'http://127.0.0.1:{port}/s/tok{share_id}'})


class FakeNextcloud:
    def __init__(self, password=PASSWORD):
        self.state = State()
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.httpd.state = self.state
        self.httpd.password = password
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self):
        return f'http://127.0.0.1:{self.httpd.server_address[1]}'

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
