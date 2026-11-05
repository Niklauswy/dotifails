"""What to upload where, and doing it.

``plan`` turns local paths into remote ones under the target folder. A top-level name
that already exists remotely becomes ``nombre (2).ext``, ``(3)``… (never replaced);
inside a new folder nothing can clash. A symlink the user named is followed; symlinks
and special files inside a folder are skipped and reported. ``run`` uploads a plan and
returns one :class:`Result` per top-level path.
"""
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

from wysun_drive.client import AuthError, Cancelled, DriveError


@dataclass
class Top:
    """One path the user asked for, and where it goes."""
    local: str
    remote: str
    name: str
    is_dir: bool
    size: int = 0
    dirs: list = field(default_factory=list)      # remote folders to create, parents first
    files: list = field(default_factory=list)     # (local, remote, size)


@dataclass
class Result:
    local: str
    remote: str
    name: str
    size: int
    is_dir: bool
    url: str | None = None
    share_id: str | None = None
    password: str | None = None
    error: str | None = None          # the upload failed
    link_error: str | None = None     # uploaded, but the link could not be made

    @property
    def ok(self):
        return self.error is None

    def to_json(self):
        data = asdict(self)
        data['ok'] = self.ok
        return data


@dataclass
class Plan:
    folder: str
    tops: list
    problems: list                    # warnings: things skipped inside folders
    rejected: list = field(default_factory=list)   # (path as given, message): not uploaded at all

    @property
    def total(self):
        return sum(top.size for top in self.tops)


def numbered(name, n, is_dir):
    if is_dir:
        return f'{name} ({n})'
    stem, dot, ext = name.rpartition('.')
    return f'{stem} ({n}).{ext}' if dot and stem else f'{name} ({n})'


def free_name(client, folder, name, is_dir, taken):
    candidate, n = name, 1
    while candidate in taken or client.exists(f'{folder}/{candidate}' if folder else candidate):
        n += 1
        candidate = numbered(name, n, is_dir)
    taken.add(candidate)
    return candidate


def _walk(root, remote_root, top, problems):
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        relative = os.path.relpath(current, root)
        base = remote_root if relative == '.' else f'{remote_root}/{relative.replace(os.sep, "/")}'
        top.dirs.append(base)
        for name in sorted(dirnames):
            if os.path.islink(os.path.join(current, name)):
                problems.append(f'Se omitió el enlace {os.path.join(current, name)}')
        dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(current, d)))
        for name in sorted(filenames):
            local = os.path.join(current, name)
            try:
                info = os.lstat(local)
            except OSError as error:
                problems.append(f'No se pudo leer {local} ({error.strerror})')
                continue
            if not stat.S_ISREG(info.st_mode):
                problems.append(f'Se omitió {local} (no es un archivo normal)')
                continue
            top.files.append((local, f'{base}/{name}', info.st_size))
            top.size += info.st_size


def plan(client, paths, folder, name=None):
    """A :class:`Plan` of ``paths`` into remote ``folder``; ``name`` renames a single top path."""
    tops, problems, rejected, taken = [], [], [], set()
    for raw in paths:
        path = Path(os.path.expanduser(str(raw))).absolute()
        try:
            info = path.stat()
        except OSError:
            rejected.append((str(raw), f'No existe {raw}'))
            continue
        is_dir = stat.S_ISDIR(info.st_mode)
        if not is_dir and not stat.S_ISREG(info.st_mode):
            rejected.append((str(raw), f'Se omitió {raw} (no es un archivo normal)'))
            continue
        wanted = (name if name and len(paths) == 1 else path.name) or 'raiz'
        remote_name = free_name(client, folder, wanted, is_dir, taken)
        remote = f'{folder}/{remote_name}' if folder else remote_name
        top = Top(str(path), remote, remote_name, is_dir)
        if is_dir:
            _walk(str(path), remote, top, problems)
        else:
            top.files.append((str(path), remote, info.st_size))
            top.size = info.st_size
        tops.append(top)
    return Plan(folder, tops, problems, rejected)


def run(client, plan, on_progress=None, cancelled=lambda: False):
    """Upload ``plan``; ``on_progress(name, done, total, all_done, all_total)``. AuthError/Cancelled propagate."""
    all_total, state = plan.total, {'all': 0}
    if plan.folder:
        client.mkdirs(plan.folder)
    results = []
    for top in plan.tops:
        done = {'n': 0}

        def advance(count, top=top, done=done):
            if cancelled():
                raise Cancelled()
            done['n'] += count
            state['all'] += count
            if on_progress is not None:
                on_progress(top.name, done['n'], top.size, state['all'], all_total)

        result = Result(top.local, top.remote, top.name, top.size, top.is_dir)
        try:
            for remote in top.dirs:
                client.mkdirs(remote)
            for local, remote, _size in top.files:
                client.put(remote, local, progress=advance)
            if on_progress is not None and not top.files:
                on_progress(top.name, 0, 0, state['all'], all_total)
        except (AuthError, Cancelled):
            raise
        except DriveError as error:
            result.error = str(error)
        except OSError as error:
            result.error = f'No se pudo leer {top.local} ({error.strerror})'
        results.append(result)
    return results
