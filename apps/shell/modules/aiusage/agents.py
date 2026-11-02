"""Running coding agents (Claude Code, Codex, OpenCode) of this user, read from /proc.

Of a process environment only CLAUDE_CONFIG_DIR and CODEX_HOME are looked at (to tell which
account runs it); nothing else is kept. Nothing is stored: the list is rebuilt on every refresh.
`windowPids` are the agent's ancestors, which the shell matches against Hyprland window pids.
"""
import os
from pathlib import Path

AGENTS = ('claude', 'codex', 'opencode')
HOME_VARIABLES = {'claude': 'CLAUDE_CONFIG_DIR', 'codex': 'CODEX_HOME'}
DEFAULT_HOMES = {'claude': '~/.claude', 'codex': '~/.codex'}


def _read(path, binary=False):
    try:
        return path.read_bytes() if binary else path.read_text(errors='replace')
    except OSError:
        return None


def _status(folder):
    fields = {}
    for line in (_read(folder / 'status') or '').splitlines():
        key, _, value = line.partition(':')
        fields[key] = value.strip()
    return fields


def _kind(folder):
    comm = (_read(folder / 'comm') or '').strip()
    argv = (_read(folder / 'cmdline', binary=True) or b'').split(b'\0')
    first = Path(argv[0].decode(errors='replace')).name if argv and argv[0] else ''
    for name in (comm, first):
        if name in AGENTS:
            return name
    # `node …/claude` style launchers.
    if comm == 'node' and len(argv) > 1:
        second = Path(argv[1].decode(errors='replace')).name
        if second in AGENTS:
            return second
    return None


def _home(folder, provider):
    variable = HOME_VARIABLES.get(provider)
    if not variable:
        return None
    prefix = variable.encode() + b'='
    for item in (_read(folder / 'environ', binary=True) or b'').split(b'\0'):
        if item.startswith(prefix):
            return item[len(prefix):].decode(errors='replace')
    return os.path.expanduser(DEFAULT_HOMES[provider])


def _branch(cwd):
    folder = Path(cwd)
    for candidate in (folder, *folder.parents):
        git = candidate / '.git'
        head = None
        if git.is_dir():
            head = _read(git / 'HEAD')
        elif git.is_file():
            pointer = (_read(git) or '').strip()
            if pointer.startswith('gitdir:'):
                head = _read((candidate / pointer[7:].strip()) / 'HEAD')
        if head is not None:
            head = head.strip()
            return head[len('ref: refs/heads/'):] if head.startswith('ref: refs/heads/') else head[:7] or None
    return None


def _boot(proc):
    for line in (_read(proc / 'stat') or '').splitlines():
        if line.startswith('btime '):
            return float(line.split()[1])
    return 0.0


def _started(folder, boot):
    raw = _read(folder / 'stat') or ''
    parts = raw.rpartition(')')[2].split()
    try:
        return boot + int(parts[19]) / os.sysconf('SC_CLK_TCK')
    except (IndexError, ValueError):
        return None


def scan(proc, homes, now, logs):
    """Agents as {pid, provider, accountId, cwd, branch, startedAt, model, tokens, cost, busy, windowPids}.

    homes maps (provider, resolved home) to an account id; logs(provider, accountId, cwd, startedAt)
    returns {model, tokens, cost, busy} from that session's log, or None.
    """
    proc = Path(proc)
    uid = os.getuid()
    parents, kinds = {}, {}
    for folder in proc.iterdir():
        if not folder.name.isdigit():
            continue
        status = _status(folder)
        try:
            parents[int(folder.name)] = int(status.get('PPid', '0'))
            owner = int(status.get('Uid', '-1').split()[0])
        except ValueError:
            continue
        if owner == uid:
            kind = _kind(folder)
            if kind:
                kinds[int(folder.name)] = kind
    boot = _boot(proc)
    found = []
    for pid, provider in sorted(kinds.items()):
        ancestors, parent = [], parents.get(pid, 0)
        while parent > 1 and parent not in ancestors:
            ancestors.append(parent)
            parent = parents.get(parent, 0)
        if any(a in kinds for a in ancestors):
            continue
        folder = proc / str(pid)
        try:
            cwd = os.readlink(folder / 'cwd')
        except OSError:
            continue
        home = _home(folder, provider)
        account = homes.get((provider, str(Path(home).resolve()))) if home else None
        started = _started(folder, boot)
        details = logs(provider, account, cwd, started) or {}
        found.append({'pid': pid, 'provider': provider, 'accountId': account, 'cwd': cwd, 'branch': _branch(cwd),
                      'startedAt': started, 'model': details.get('model'), 'tokens': details.get('tokens', 0),
                      'cost': details.get('cost', 0.0), 'busy': bool(details.get('busy')), 'windowPids': ancestors})
    return found
