"""Uploading to the user's Nextcloud from other Wysun code.

Other programs should prefer the command, which also shows progress in the bar and can be
cancelled from it::

    wysun drive up --link --json -- RUTA…     # one JSON object per line: {ok, name, remote, url, …}

Python code inside Wysun may call :func:`upload` directly::

    from wysun_drive.api import upload
    [result] = upload(['informe.pdf'], link=True)
    result.url          # public link (None without link=True or on error)

It raises ``AuthError`` (``code == 3``) when there is no session (``wysun drive login``).
"""
import os

from wysun_drive import account, history, upload as uploader
from wysun_drive.client import AuthError, Client, DriveError

__all__ = ['AuthError', 'DriveError', 'upload', 'make_link']


def client(acc=None):
    acc = acc or account.current()
    if acc is None:
        stale = account.load()
        if stale is not None:
            raise AuthError(f'La sesión es de {stale.server}; inicia sesión en {account.settings()["server"]}: '
                            'wysun drive login')
        raise AuthError('Inicia sesión primero: wysun drive login')
    return Client(acc)


def upload(paths, link=False, folder=None, name=None, password=None, expire_days=None,
           on_progress=None, cancelled=lambda: False, acc=None, on_plan=None):
    """Upload ``paths`` (files or folders) and return one ``upload.Result`` per path.

    ``folder`` is the remote folder (default: the configured one, ``Wysun``). With ``link`` each
    uploaded path gets a public read-only link (``password``/``expire_days`` optional). Paths that
    could not be planned (missing, special files) come back as results with ``error``.
    """
    drive = client(acc)
    target = account.clean_folder(account.settings()['folder'] if folder is None else folder)
    plan = uploader.plan(drive, list(paths), target, name=name)
    if on_plan is not None:
        on_plan(plan)
    results = uploader.run(drive, plan, on_progress=on_progress, cancelled=cancelled)
    if link:
        for result in results:
            if result.ok:
                try:
                    share = drive.share(result.remote, password=password, expire_days=expire_days)
                except AuthError:
                    raise
                except DriveError as error:
                    result.link_error = str(error)
                    continue
                result.url, result.share_id, result.password = share['url'], share['id'], password
    history.add(results, server=drive.server)
    rejected = [uploader.Result(raw, '', os.path.basename(raw.rstrip('/')) or raw, 0, False, error=message)
                for raw, message in plan.rejected]
    return results + rejected


def make_link(remote, password=None, expire_days=None, acc=None):
    """A public link to something already uploaded (the history's entries)."""
    share = client(acc).share(remote, password=password, expire_days=expire_days)
    history.set_link(remote, share['url'], share['id'], password)
    return share
