"""Nextcloud Login Flow v2: the browser approves, Wysun receives an app password.

``start`` asks the server for a login URL and a poll token; the user opens the URL
(``xdg-open``), logs in and grants access; ``wait`` polls until Nextcloud hands over
``{server, loginName, appPassword}``. The poll endpoint must be HTTPS on the same host.
"""
import json
import time
from urllib.parse import urlencode, urlsplit

from wysun_drive.account import Account
from wysun_drive.client import AuthError, Cancelled, Client, DriveError, request, split_server

TIMEOUT = 20 * 60
INTERVAL = 2


def start(server):
    """``(login_url, poll)`` where ``poll`` is ``{'token', 'endpoint'}``."""
    split_server(server)
    status, _h, data = request(server.rstrip('/') + '/index.php/login/v2', 'POST', body=b'', timeout=30)
    if status != 200:
        raise DriveError(f'{urlsplit(server).hostname} no ofrece el inicio de sesión de Nextcloud ({status})')
    try:
        answer = json.loads(data)
        poll = {'token': str(answer['poll']['token']), 'endpoint': str(answer['poll']['endpoint'])}
        login_url = str(answer['login'])
    except (ValueError, KeyError, TypeError):
        raise DriveError('Respuesta inesperada del inicio de sesión de Nextcloud') from None
    if urlsplit(poll['endpoint']).hostname != urlsplit(server).hostname:
        raise DriveError('El inicio de sesión apunta a otro servidor; se canceló')
    split_server(poll['endpoint'])
    return login_url, poll


def wait(poll, server=None, timeout=TIMEOUT, interval=INTERVAL, sleep=time.sleep, cancelled=lambda: False):
    """Poll until the browser grants access; the new :class:`Account`.

    With ``server`` the account keeps the address the user asked for (Nextcloud may answer with
    another spelling of itself), so it matches the configured server.
    """
    deadline = time.monotonic() + timeout
    body = urlencode({'token': poll['token']}).encode()
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    while time.monotonic() < deadline:
        if cancelled():
            raise Cancelled()
        status, _h, data = request(poll['endpoint'], 'POST', body=body, headers=headers, timeout=30)
        if status == 200:
            try:
                answer = json.loads(data)
                account = Account((server or str(answer['server'])).rstrip('/'), str(answer['loginName']),
                                  str(answer['appPassword']))
            except (ValueError, KeyError, TypeError):
                raise DriveError('Respuesta inesperada del inicio de sesión de Nextcloud') from None
            split_server(account.server)
            return account
        if status != 404:
            raise DriveError(f'El inicio de sesión falló ({status})')
        sleep(interval)
    raise DriveError('Se acabó el tiempo para iniciar sesión; vuelve a intentarlo')


def manual(server, user, password):
    """An :class:`Account` from an app password made by hand in Nextcloud (Ajustes personales ›
    Seguridad › Crear contraseña de aplicación); checked against the server before it is kept."""
    user, password = str(user).strip(), str(password).strip()
    if not user or not password:
        raise DriveError('Faltan el usuario o la contraseña de aplicación', code=2)
    split_server(server)
    acc = Account(server.rstrip('/'), user, password)
    try:
        Client(acc).exists('')
    except AuthError:
        raise DriveError('Nextcloud rechazó el usuario o la contraseña de aplicación', code=3) from None
    return acc
