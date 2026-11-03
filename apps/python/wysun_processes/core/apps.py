"""Pure layout logic of Wysun Processes' Apps section: one column per monitor in physical x order with a friendly
name, its windows grouped by workspace (only the non-empty ones), and the apps without a window split into the
user's own apps and the session plumbing that folds into «Sistema». Nothing here touches Qt or Hyprland."""
from collections import OrderedDict
import re

# Session services and plumbing: the only apps that fold into «Sistema». A process without a desktop entry is not
# plumbing by itself: it is something the user runs (a browser's background scope, the shell, a CLI agent).
SYSTEM_PREFIXES = ('dbus', 'pipewire', 'xdg-', 'gvfs', 'at-spi', 'gnome-keyring', 'polkit', 'dconf', 'systemd',
                   'mpris-', 'start-hyprland', 'chrome_crashpad', 'msedge_crashpad', 'memfd:')
SYSTEM_NAMES = frozenset({'wireplumber', 'swayidle', 'xwayland', 'sd-pam', '(sd-pam)', 'wl-paste', 'journalctl',
                          'timeout', 'cat', 'sh', 'zsh', 'bash', 'hyprland', 'nmcli', 'mainthread', 'node_repl',
                          'brave-browser-s', 'head', 'tail', 'sleep', 'grep', 'sed', 'awk', 'find', 'ls', 'rm', 'cp',
                          'mv', 'mkdir', 'tee', 'xargs', 'sort', 'uniq', 'curl', 'wget', 'watch', 'env', 'nohup',
                          'ps', 'pgrep', 'pkill', 'kill', 'du', 'df', 'date', 'echo', 'test'})
TECHNICAL_NAME = re.compile(r'^\d+(?:\.\d+)+$')
GENERIC_MAKE = frozenset({'unknown', 'generic', 'default', 'inc.', 'inc', 'ltd.', 'ltd', 'corp.', 'corporation',
                          'company', 'electronics'})


def monitor_name(make, model, connector):
    """The monitor's friendly name: the shortened make ("Philips Consumer Electronics Company" → "Philips",
    "LG Electronics" → "LG"), else the model's brand token, else the connector ("DP-1")."""
    for text in (make, model):
        word = (text or '').replace(',', ' ').split()
        if word and word[0].casefold() not in GENERIC_MAKE:
            return word[0]
    return (connector or '').strip() or 'Pantalla'


def monitor_side(index, total):
    """`izquierda`/`derecha` (or `centro`) when there is more than one monitor; nothing with only one."""
    if total <= 1:
        return ''
    if index <= 0:
        return 'izquierda'
    if index >= total - 1:
        return 'derecha'
    return 'centro'


def _space_id(monitor):
    active = monitor.get('activeWorkspace') or 0
    return active.get('id', 0) if isinstance(active, dict) else active


def _column(monitor, index, total, spaces):
    active = _space_id(monitor)
    workspaces = [dict(id=number, current=number == active, windows=windows)
                  for number, windows in sorted(spaces.items())]
    return dict(id=monitor.get('id'), connector=monitor.get('name') or '', x=monitor.get('x') or 0,
                y=monitor.get('y') or 0, activeWorkspace=active, count=sum(len(w) for w in spaces.values()),
                label=monitor_name(monitor.get('make'), monitor.get('model'), monitor.get('name')),
                side=monitor_side(index, total), workspaces=workspaces)


def _spaces(windows):
    out = OrderedDict()
    for window in windows:
        out.setdefault(window.get('workspace'), []).append(window)
    return out


def group_windows(monitors, windows):
    """Columns ordered by the monitor's physical x: one per monitor, its windows by workspace. A window whose
    monitor is not listed (an output closed mid-sample) goes to the first column instead of disappearing."""
    ordered = sorted(monitors, key=lambda m: (m.get('x') or 0, m.get('y') or 0, m.get('id') or 0))
    if not ordered:
        return [_column(dict(id=None, name='', make='', model='', x=0, y=0, activeWorkspace=0), 0, 1,
                        _spaces(windows))] if windows else []
    known = {m.get('id') for m in ordered}
    grouped = {m.get('id'): _spaces([w for w in windows if w.get('monitor') == m.get('id')]) for m in ordered}
    lost = [w for w in windows if w.get('monitor') not in known]
    for window in lost:
        grouped[ordered[0].get('id')].setdefault(window.get('workspace'), []).append(window)
    return [_column(monitor, index, len(ordered), grouped[monitor.get('id')])
            for index, monitor in enumerate(ordered)]


def is_system(app):
    """True only for the session's plumbing (`SYSTEM_PREFIXES`/`SYSTEM_NAMES`) and technical helper names. Anything
    else the user runs is a user app, even when it has no desktop entry (Brave's background scope, the shell, a
    CLI agent)."""
    name = (app or '').strip().casefold()
    if not name:
        return True
    if name in SYSTEM_NAMES or any(name.startswith(prefix) for prefix in SYSTEM_PREFIXES):
        return True
    return bool(TECHNICAL_NAME.match(name))


def windowless_groups(rows, windowed):
    """`(user apps, system apps)` from the processes of apps without a window, grouped by app and sorted by memory
    (then CPU, then name). `windowed` holds the app keys of the processes that own a window: a different app key
    (a browser's background scope) is still listed, and the caller marks it as `· segundo plano`."""
    groups = {}
    for row in rows:
        app = row.get('app') or ''
        if not app or app in windowed:
            continue
        group = groups.setdefault(app, dict(app=app, cpu=0.0, mem=0, count=0))
        group['cpu'] += row.get('cpu') or 0
        group['mem'] += row.get('mem') or 0
        group['count'] += 1
    user, system = [], []
    for app, group in groups.items():
        (system if is_system(app) else user).append(group)
    order = lambda group: (-group['mem'], -group['cpu'], group['app'].casefold())
    return sorted(user, key=order), sorted(system, key=order)


def system_summary(groups):
    """The folded «Sistema · N procesos» line: process count and totals of its apps."""
    return dict(count=sum(g['count'] for g in groups), mem=sum(g['mem'] for g in groups),
                cpu=sum(g['cpu'] for g in groups), apps=list(groups))


def preferred_app(app_id, app, entry_of):
    """The app that names and paints a window: the desktop entry of its class first (Brave, Wysun Processes), else
    the process' own app (chromium, python3). `entry_of(app)` returns the desktop entry or None. An entry only
    counts when it really is the class: application shortcuts (a Brave PWA) also register the browser's Exec name."""
    for candidate in (app_id, app):
        if candidate and entry_matches(candidate, entry_of(candidate)):
            return candidate
    return app or app_id or ''


def entry_matches(app_id, entry):
    """True when `entry` is the desktop file of `app_id` itself, not an alias another entry claimed (its Exec
    basename or StartupWMClass): `brave-browser.desktop` for `brave-browser`, `ghostty` for
    `com.mitchellh.ghostty`."""
    if not app_id or not entry:
        return False
    app = app_id.casefold()
    desktop = (entry.get('desktop') or '').casefold()
    return desktop == app or desktop.rsplit('.', 1)[-1] == app.rsplit('.', 1)[-1]


def brand_name(app_id):
    """A readable fallback from a window class when no desktop entry really belongs to it: `brave-browser` →
    `Brave`, `org.gnome.Nautilus` → `Nautilus`, `orca.AppImage` → `Orca`."""
    text = (app_id or '').strip()
    last = text.rsplit('.', 1)[-1]
    if '.' in text and last.casefold() in ('appimage', 'bin', 'exe', 'sh', 'py', 'run'):
        text = text.rsplit('.', 2)[-2] if text.count('.') >= 2 else text.rsplit('.', 1)[0]
    else:
        text = last
    words = [word for word in re.split(r'[-_\s]+', text) if word]
    if len(words) > 1 and words[-1].casefold() in ('browser', 'desktop', 'client', 'bin'):
        words.pop()
    if not words:
        return text
    return words[0][:1].upper() + words[0][1:]


def app_label(app_id, app, entry_of):
    """The name of a window's app: the desktop entry of its class, the process app's entry, or the class itself.
    This is what keeps a Brave window named Brave (the browser's entry) and Wysun Processes named that (its own
    entry) instead of Chromium and python3."""
    for candidate in (app_id, app):
        if not candidate:
            continue
        entry = entry_of(candidate)
        if entry_matches(candidate, entry):
            return entry.get('name') or candidate
    return brand_name(app_id) or brand_name(app) or 'Aplicación'
