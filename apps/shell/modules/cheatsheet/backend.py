#!/usr/bin/env python3
"""Reads the active Hyprland Lua config and prints its real binds grouped for the cheat sheet.

Binds whose description marks them as having no Wysun equivalent (notification stubs) are skipped.
A bind whose description is "Wysun | <Category> | <text>" is listed under that category with that text;
unknown categories become new groups. Older provenance tags (equivalent, adapted, extra...) keep the
labels derived from the dispatcher. The file is read on every call, so nothing is cached.
"""
import json
import re
import sys
from pathlib import Path

BIND = re.compile(r'^hl\.bind\("([^"]+)",\s*(.*?),\s*\{description="([^"]*)"')
DIRECTIONS = {'left': '←', 'right': '→', 'up': '↑', 'down': '↓'}
MODS = {'SUPER': 'Super', 'ALT': 'Alt', 'CTRL': 'Ctrl', 'SHIFT': 'Shift'}
KEYS = {'Return': 'Enter', 'space': 'Space', 'period': '.', 'comma': ',', 'grave': '`', 'slash': '/',
        'bracketleft': '[', 'bracketright': ']', 'Escape': 'Esc', 'Print': 'PrtSc',
        'XF86AudioRaiseVolume': 'Vol +', 'XF86AudioLowerVolume': 'Vol −', 'XF86AudioMute': 'Mute',
        'XF86AudioMicMute': 'Mic mute', 'XF86AudioNext': 'Next', 'XF86AudioPrev': 'Previous',
        'XF86AudioPlay': 'Play', 'XF86AudioStop': 'Stop', 'XF86MonBrightnessUp': 'Bright +',
        'XF86MonBrightnessDown': 'Bright −', 'Left': '←', 'Right': '→', 'Up': '↑', 'Down': '↓'}
WYSUN = {'launcher': 'Open the launcher', 'toggle': 'Open the launcher', 'clipboard': 'Clipboard history',
         'calculator': 'Calculator', 'emoji': 'Emoji picker', 'processes': 'Processes',
         'colors': 'Colors', 'settings': 'Settings', 'files': 'Files',
         'music-mini': 'Wysun Music in the media widget', 'lock': 'Lock the screen', 'recover': 'Recover the shell',
         'cheatsheet': 'This cheat sheet'}
SHELL = {'overview': 'Workspace overview', 'session': 'Session panel', 'menu': 'Quick menu',
         'cheatsheet': 'This cheat sheet', 'reload-preferences': 'Reload shell preferences'}
# Provenance tags used by the stock config; they say where a bind came from, not how to list it.
PROVENANCE = {'adapted', 'cheatsheet', 'emoji', 'equivalent', 'extra', 'no-equivalent', 'overview', 'private', 'session'}
APPS = {'wysun-terminal': 'Terminal', 'brave-browser': 'Browser', 'discord': 'Discord'}


def describe(action):
    """Returns (category, label) for a dispatcher expression, or None to hide it."""
    if 'Atajo sin equivalente' in action or 'notify-send' in action:
        return None
    m = re.match(r'hl\.dsp\.exec_cmd\("(.*)"\)$', action)
    if m:
        cmd = m.group(1).split()
        if cmd[:2] == ['sh', '-c'] and 'wysun recover' in m.group(1):
            return ('Session', 'Recover desktop: relaunch shell and reload Hyprland')
        if cmd == ['wysun']:
            return ('Shell', 'Open the launcher')
        if cmd[0] == 'wysun' and len(cmd) > 1:
            if cmd[1] == 'shell' and len(cmd) > 2 and cmd[2] in SHELL:
                return ('Shell', SHELL[cmd[2]])
            if cmd[1] == 'recorder':
                return ('Capture', 'Screen recorder')
            if cmd[1] == 'screenshot':
                return ('Capture', 'Screenshot' if '--accept-on-select' not in m.group(1) else 'Screenshot to clipboard')
            if cmd[1] in WYSUN:
                return ('Shell' if cmd[1] in ('recover', 'cheatsheet', 'lock') else 'Apps', WYSUN[cmd[1]])
        if cmd[0] == 'wysun-terminal':
            return ('Apps', 'Terminal')
        if cmd[0] in APPS:
            return ('Apps', APPS[cmd[0]])
        if cmd[0] == 'wysun-control':
            return ('Media', {'volume-up': 'Volume up', 'volume-down': 'Volume down', 'volume-mute': 'Mute',
                              'mic-mute': 'Mute microphone', 'media-next': 'Next track',
                              'media-previous': 'Previous track', 'media-play-pause': 'Play / pause',
                              'media-stop': 'Stop', 'brightness-up': 'Brightness up',
                              'brightness-down': 'Brightness down'}.get(cmd[1], cmd[1]))
        if cmd[0] == 'wysun-wm':
            return ('Windows', {'biggest-swap': 'Swap with the largest tile', 'history-older': 'Previous in focus history',
                                'history-newer': 'Next in focus history', 'pin': 'Pin floating window',
                                'move': 'Move floating window (arrow keys)', 'resize': 'Resize window (arrow keys)'}.get(
                                    re.sub(r'-(left|right|up|down)$', '', cmd[1]), cmd[1]))
        if cmd[0] == 'hyprctl' and cmd[1:] == ['reload']:
            return ('Session', 'Reload the Hyprland config')
        return None
    if action.startswith('hl.dsp.window.close'):
        return ('Windows', 'Close window')
    if action.startswith('hl.dsp.window.kill'):
        return ('Windows', 'Force close window')
    if action.startswith('hl.dsp.window.fullscreen'):
        return ('Windows', 'Fullscreen')
    if action.startswith('hl.dsp.window.float'):
        state = re.search(r'action="(\w+)"', action).group(1)
        return ('Windows', {'enable': 'Make floating', 'disable': 'Make tiled', 'toggle': 'Toggle floating'}[state])
    if action.startswith('hl.dsp.window.cycle_next'):
        return ('Windows', 'Focus next window' if 'true' in action else 'Focus previous window')
    if action.startswith('hl.dsp.window.swap'):
        return ('Windows', 'Swap window (arrow keys)')
    if action.startswith('hl.dsp.window.move') and 'workspace' in action:
        return ('Workspaces', 'Send window to workspace')
    if action.startswith('hl.dsp.focus'):
        if 'last=true' in action:
            return ('Windows', 'Focus last window')
        if 'direction' in action:
            return ('Windows', 'Focus window (arrow keys)')
        if '"-1"' in action:
            return ('Workspaces', 'Previous workspace')
        if '"+1"' in action:
            return ('Workspaces', 'Next workspace')
        if 'workspace' in action:
            return ('Workspaces', 'Go to workspace')
    if action.startswith('hl.dsp.exit'):
        return ('Session', 'Exit the Hyprland session')
    return None


def explicit(description):
    """Returns (category, text) for a "Wysun | <Category> | <text>" description, else None."""
    parts = [p.strip() for p in description.split('|', 2)]
    if len(parts) != 3 or parts[0].lower() != 'wysun' or not parts[1] or not parts[2]:
        return None
    if parts[1].lower() in PROVENANCE:
        return None
    return parts[1], parts[2]


def keycaps(spec):
    parts = [p.strip() for p in spec.split('+')]
    return [MODS.get(p, KEYS.get(p, p.upper() if len(p) == 1 else p)) for p in parts]


def collect(text):
    seen, rows, bound = set(), [], {}
    for line in text.splitlines():
        m = BIND.match(line.strip())
        if not m:
            continue
        spec, action, description = m.groups()
        if re.search(r'KP_', spec):
            continue
        info = explicit(description) or describe(action)
        if info is None:
            continue
        keys = keycaps(spec)
        category, label = info
        if explicit(description):
            row = {'category': category, 'keys': keys, 'label': label}
            if spec in bound:  # a later bind on the same keys replaces the earlier one
                rows[bound[spec]] = row
            else:
                bound[spec] = len(rows)
                rows.append(row)
            continue
        if re.search(r'\(arrow keys\)$', label) or label in ('Go to workspace', 'Send window to workspace'):
            key = (category, label, tuple(keys[:-1]))
            if key in seen:
                continue
            seen.add(key)
            tail = '1 – 9' if 'workspace' in label.lower() and re.fullmatch(r'\d', spec[-1]) else '← ↑ ↓ →'
            keys = keys[:-1] + [tail]
            label = label.replace(' (arrow keys)', '')
        rows.append({'category': category, 'keys': keys, 'label': label})
    order = ['Shell', 'Apps', 'Windows', 'Workspaces', 'Capture', 'Media', 'Session']
    groups = {c: [] for c in order}
    for row in rows:
        groups.setdefault(row['category'], []).append({'keys': row['keys'], 'label': row['label']})
    return [{'category': c, 'items': items} for c, items in groups.items() if items]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / '.config/wysun/hyprland.lua'
    try:
        print(json.dumps(collect(path.read_text(encoding='utf-8'))))
    except OSError as error:
        print(json.dumps([]))
        print(f'wysun cheatsheet: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
