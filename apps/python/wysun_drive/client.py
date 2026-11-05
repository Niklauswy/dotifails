"""A small Nextcloud client: WebDAV to upload, OCS to make public links.

Only HTTPS (plain HTTP only to ``127.0.0.1``/``localhost``, for tests), redirects are
never followed, and the app password travels only in the ``Authorization`` header of
requests to the account's own host. No error, message or ``repr`` carries it.
"""
import base64
import http.client
import json
import os
import time
import uuid
from urllib.parse import quote, urlencode, urlsplit

USER_AGENT = 'Wysun Drive'
CHUNK_THRESHOLD = 64 * 1024 * 1024
CHUNK_SIZE = 16 * 1024 * 1024
CHUNK_RETRIES = 3
BLOCK = 256 * 1024
LOOPBACK = ('127.0.0.1', 'localhost', '::1')


class DriveError(Exception):
    """A failure to show as is (Spanish, no secrets); ``code`` is the exit status."""

    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


class AuthError(DriveError):
    def __init__(self, message='La sesión de Wysun Drive ya no es válida: ejecuta wysun drive login'):
        super().__init__(message, code=3)


class Cancelled(DriveError):
    def __init__(self):
        super().__init__('Subida cancelada', code=1)


def split_server(url):
    """``(scheme, host, port, prefix)`` of a server URL; refuses anything but HTTPS (or local HTTP)."""
    parts = urlsplit(str(url).strip())
    if parts.scheme not in ('https', 'http') or not parts.hostname:
        raise DriveError(f'Dirección de servidor no válida: {parts.scheme}://{parts.hostname or ""}', code=2)
    if parts.scheme == 'http' and parts.hostname not in LOOPBACK:
        raise DriveError('Wysun Drive solo se conecta por HTTPS', code=2)
    return parts.scheme, parts.hostname, parts.port, parts.path.rstrip('/')


def request(url, method='GET', body=None, headers=None, timeout=60, auth=None, length=None):
    """One request: ``(status, headers, data)``. ``body`` may be bytes or a file-like with ``length``.

    ``auth`` is ``(user, password)``; OSError becomes a DriveError naming only the host.
    """
    scheme, host, port, _prefix = split_server(url)
    parts = urlsplit(url)
    target = (parts.path or '/') + (f'?{parts.query}' if parts.query else '')
    conn_class = http.client.HTTPSConnection if scheme == 'https' else http.client.HTTPConnection
    sent = {'User-Agent': USER_AGENT}
    sent.update(headers or {})
    if auth is not None:
        token = base64.b64encode(f'{auth[0]}:{auth[1]}'.encode()).decode()
        sent['Authorization'] = f'Basic {token}'
    if body is not None and not isinstance(body, (bytes, bytearray)):
        sent['Content-Length'] = str(length)
    conn = conn_class(host, port, timeout=timeout)
    try:
        conn.request(method, target, body=body, headers=sent)
        response = conn.getresponse()
        data = response.read()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, data
    except Cancelled:
        raise
    except (OSError, http.client.HTTPException) as error:
        reason = getattr(error, 'strerror', None) or type(error).__name__
        raise DriveError(f'No se pudo conectar con {host} ({reason})') from None
    finally:
        conn.close()


class _Reader:
    """A file slice read in blocks that reports progress (and may raise Cancelled)."""

    def __init__(self, stream, length, progress):
        self.stream = stream
        self.left = length
        self.progress = progress

    def read(self, size=-1):
        if self.left <= 0:
            return b''
        size = BLOCK if size is None or size < 0 else min(size, BLOCK)
        data = self.stream.read(min(size, self.left))
        self.left -= len(data)
        if self.progress is not None and data:
            self.progress(len(data))
        return data


def _status_error(status, what):
    if status == 401:
        return AuthError()
    if status == 403:
        return DriveError(f'Nextcloud no permite {what}')
    if status == 507:
        return DriveError('No queda espacio en tu Nextcloud')
    if 300 <= status < 400:
        return DriveError(f'El servidor redirigió {what}; revisa la dirección del servidor')
    return DriveError(f'Nextcloud respondió {status} al {what}')


class Client:
    """WebDAV and OCS calls of one account. Remote paths are relative to the user's root."""

    def __init__(self, account, timeout=60, chunk_threshold=CHUNK_THRESHOLD, chunk_size=CHUNK_SIZE):
        self.account = account
        self.timeout = timeout
        self.chunk_threshold = chunk_threshold
        self.chunk_size = chunk_size
        split_server(account.server)
        self.server = account.server.rstrip('/')
        self._dirs = set()

    # -- plumbing -----------------------------------------------------------
    def _auth(self):
        return (self.account.user, self.account.password)

    def dav_url(self, remote):
        return f'{self.server}/remote.php/dav/files/{quote(self.account.user, safe="")}/{quote(remote.strip("/"), safe="/")}'

    def _call(self, url, method, what, ok, body=None, headers=None, length=None):
        status, response_headers, data = request(url, method, body=body, headers=headers, timeout=self.timeout,
                                                 auth=self._auth(), length=length)
        if status not in ok:
            raise _status_error(status, what)
        return status, response_headers, data

    # -- WebDAV -------------------------------------------------------------
    def exists(self, remote):
        status, _headers, _data = request(self.dav_url(remote), 'PROPFIND', body=b'', timeout=self.timeout,
                                          auth=self._auth(), headers={'Depth': '0'})
        if status == 404:
            return False
        if status == 207:
            return True
        raise _status_error(status, f'buscar «{remote}»')

    def mkdirs(self, remote):
        """Create ``remote`` and its parents; existing ones are fine."""
        built = ''
        for part in [p for p in remote.strip('/').split('/') if p]:
            built = f'{built}/{part}' if built else part
            if built in self._dirs:
                continue
            self._call(self.dav_url(built), 'MKCOL', f'crear la carpeta «{built}»', (201, 405))
            self._dirs.add(built)

    def put(self, remote, path, progress=None):
        """Upload the local file ``path`` to ``remote``; ``progress(bytes)`` after every block."""
        size = os.path.getsize(path)
        if size >= self.chunk_threshold:
            return self._put_chunked(remote, path, size, progress)
        headers = {'X-OC-Mtime': str(int(os.path.getmtime(path))), 'Content-Type': 'application/octet-stream'}
        with open(path, 'rb') as stream:
            self._call(self.dav_url(remote), 'PUT', f'subir «{remote}»', (200, 201, 204),
                       body=_Reader(stream, size, progress), headers=headers, length=size)

    def _put_chunked(self, remote, path, size, progress):
        """Nextcloud chunked upload v2: MKCOL a session, PUT each chunk (retried), MOVE ``.file``."""
        user = quote(self.account.user, safe='')
        session = f'{self.server}/remote.php/dav/uploads/{user}/wysun-{uuid.uuid4().hex}'
        destination = {'Destination': self.dav_url(remote)}
        self._call(session, 'MKCOL', f'preparar la subida de «{remote}»', (201,), headers=destination)
        try:
            with open(path, 'rb') as stream:
                offset, number = 0, 1
                while offset < size:
                    length = min(self.chunk_size, size - offset)
                    for attempt in range(CHUNK_RETRIES):
                        stream.seek(offset)
                        sent = []
                        try:
                            self._call(f'{session}/{number:05d}', 'PUT', f'subir «{remote}»', (201, 204),
                                       body=_Reader(stream, length, lambda n: (sent.append(n), progress and progress(n))),
                                       headers=dict(destination, **{'OC-Total-Length': str(size)}), length=length)
                            break
                        except (AuthError, Cancelled):
                            raise
                        except DriveError:
                            if progress and sent:
                                progress(-sum(sent))
                            if attempt == CHUNK_RETRIES - 1:
                                raise
                            time.sleep(1 + attempt)
                    offset += length
                    number += 1
            headers = dict(destination, **{'OC-Total-Length': str(size), 'X-OC-Mtime': str(int(os.path.getmtime(path)))})
            self._call(f'{session}/.file', 'MOVE', f'terminar «{remote}»', (201, 204), headers=headers)
        except BaseException:
            try:
                request(session, 'DELETE', timeout=self.timeout, auth=self._auth())
            except DriveError:
                pass
            raise

    # -- OCS shares ---------------------------------------------------------
    def _ocs(self, method, path, fields=None, what='crear el link'):
        url = f'{self.server}/ocs/v2.php/apps/files_sharing/api/v1/shares{path}?format=json'
        body = urlencode(fields).encode() if fields is not None else None
        headers = {'OCS-APIRequest': 'true', 'Accept': 'application/json'}
        if body is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        status, _h, data = request(url, method, body=body, headers=headers, timeout=self.timeout, auth=self._auth())
        if status == 401:
            raise AuthError()
        try:
            ocs = json.loads(data or b'{}').get('ocs', {})
        except ValueError:
            ocs = {}
        meta = ocs.get('meta', {}) if isinstance(ocs, dict) else {}
        if status >= 300 or meta.get('statuscode', status) not in (100, 200):
            message = str(meta.get('message') or '').strip()
            raise DriveError(f'Nextcloud no pudo {what}' + (f': {message}' if message else f' ({status})'))
        return ocs.get('data')

    def share(self, remote, password=None, expire_days=None):
        """A public link (read only) to ``remote``: ``{'id', 'url'}``."""
        fields = {'path': '/' + remote.strip('/'), 'shareType': '3', 'permissions': '1'}
        if password:
            fields['password'] = password
        if expire_days:
            fields['expireDate'] = time.strftime('%Y-%m-%d', time.localtime(time.time() + int(expire_days) * 86400))
        data = self._ocs('POST', '', fields)
        if not isinstance(data, dict) or not data.get('url'):
            raise DriveError('Nextcloud no devolvió el link')
        return {'id': str(data.get('id', '')), 'url': str(data['url'])}

    def unshare(self, share_id):
        self._ocs('DELETE', f'/{quote(str(share_id), safe="")}', what='quitar el link')

    def revoke(self):
        """Delete this app password on the server (logout); best effort."""
        url = f'{self.server}/ocs/v2.php/core/apppassword?format=json'
        status, _h, _d = request(url, 'DELETE', headers={'OCS-APIRequest': 'true'}, timeout=self.timeout,
                                 auth=self._auth())
        return status in (200, 204)
