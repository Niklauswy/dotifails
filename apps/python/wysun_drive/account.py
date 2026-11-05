"""The one Nextcloud account Wysun Drive uploads to, and the optional settings.

The account (server, login name and the *app password* Nextcloud handed over in the
login flow) lives in ``~/.local/share/wysun/drive/account.json``: a private directory
(0700) and a private file (0600), never in the repository. The app password can be
revoked from Nextcloud's security settings at any time; ``wysun drive logout`` does it.

``~/.config/wysun/drive.json`` may set ``{"server": "https://…", "folder": "Wysun"}``.
"""
from dataclasses import dataclass, field

from wysun_core import paths
from wysun_core.jsonio import atomic_write_json, read_json

DEFAULT_SERVER = 'https://cloud.wysun.store'
DEFAULT_FOLDER = 'Wysun'


@dataclass(frozen=True)
class Account:
    server: str
    user: str
    password: str = field(repr=False)    # the app password: never printed, logged or shown


def directory():
    return paths.data('wysun', 'drive')


def account_path():
    return directory() / 'account.json'


def load():
    """The saved account, or None when there is none (or it is unreadable)."""
    data = read_json(account_path(), None)
    if not isinstance(data, dict):
        return None
    server, user, password = data.get('server'), data.get('user'), data.get('password')
    if not all(isinstance(value, str) and value for value in (server, user, password)):
        return None
    return Account(server.rstrip('/'), user, password)


def save(account):
    paths.private_dir(directory())
    atomic_write_json(account_path(), {'server': account.server, 'user': account.user,
                                       'password': account.password}, mode=0o600)


def forget():
    account_path().unlink(missing_ok=True)


def settings():
    """``{'server', 'folder'}``: the config file's values over the defaults."""
    data = read_json(paths.config('wysun', 'drive.json'), {})
    data = data if isinstance(data, dict) else {}
    server = data.get('server') if isinstance(data.get('server'), str) and data.get('server') else DEFAULT_SERVER
    folder = data.get('folder') if isinstance(data.get('folder'), str) else DEFAULT_FOLDER
    return {'server': server.rstrip('/'), 'folder': clean_folder(folder)}


def clean_folder(folder):
    """A remote folder relative to the root, without leading/trailing slashes or ``..``/``.`` parts."""
    parts = [part for part in str(folder).replace('\\', '/').split('/') if part and part not in ('.', '..')]
    return '/'.join(parts)
