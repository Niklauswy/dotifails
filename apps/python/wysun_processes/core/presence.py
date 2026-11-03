"""Whether the process monitor can be seen right now: the pure decision behind suspending sampling while every
output is off, or while the window is hidden or on a workspace no active output shows. Nothing here touches Qt or
Hyprland: the controller feeds it the monitor and client lists from `Hypr`."""

APP_ID = 'wysun-processes'


def lit_workspaces(monitors):
    """The workspaces shown by outputs that are on. An output without `dpms` is assumed on."""
    return {monitor.get('activeWorkspace') for monitor in monitors if monitor.get('dpms', True)}


def suspend_reason(monitors, windows, app_id=APP_ID):
    """`''` when the window can be seen; otherwise `'dpms'` (every output is off), `'workspace'` (the window is on
    a workspace no lit output shows) or `'window'` (it is not mapped: minimised, hidden or closed). Without monitor
    data (`hyprctl` unavailable) nothing can be decided and the window's own visibility is the only signal."""
    if not monitors:
        return ''
    lit = [monitor for monitor in monitors if monitor.get('dpms', True)]
    if not lit:
        return 'dpms'
    spaces = lit_workspaces(lit)
    own = [window for window in windows if window.get('app_id') == app_id]
    if not own:
        return 'window'
    return '' if any(window.get('workspace') in spaces for window in own) else 'workspace'
