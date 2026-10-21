#!/usr/bin/env python3
"""Reads the active Hyprland Lua config and prints its real binds grouped for the cheat sheet.

Binds whose description marks them as having no Wysun equivalent (notification stubs) are skipped.
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
         'calculator': 'Calculator', 'emoji': 'Emoji picker', 'processes': 'Processes', 'connections': 'Connections',
         'notes': 'Notes', 'colors': 'Colors', 'settings': 'Settings', 'files': 'Files', 'snippets': 'Snippets',
         'tools': 'Tools', 'music-mini': 'Mini music player', 'lock': 'Lock the screen', 'recover': 'Recover the shell',
         'windows': 'Window switcher', 'cheatsheet': 'This cheat sheet'}
SHELL = {'overview': 'Workspace overview', 'session': 'Session panel', 'menu': 'Quick menu',
         'cheatsheet': 'This cheat sheet', 'reload-preferences': 'Reload shell preferences'}
APPS = {'wysun-terminal': 'Terminal', 'brave-browser': 'Browser', 'discord': 'Discord'}


def describe(action):
    """Returns (category, label) for a dispatcher expression, or None to hide it."""
    if 'Atajo sin equivalente' in action or 'dunstify' in action:
        return None
    m = re.match(r'hl\.dsp\.exec_cmd\("(.*)"\)$', action)
    if m:
        cmd = m.group(1).split()
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
                return ('Shell' if cmd[1] in ('windows', 'recover', 'cheatsheet', 'lock') else 'Apps', WYSUN[cmd[1]])
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


def keycaps(spec):
    parts = [p.strip() for p in spec.split('+')]
    return [MODS.get(p, KEYS.get(p, p.upper() if len(p) == 1 else p)) for p in parts]


def collect(text):
    seen, rows = set(), []
    for line in text.splitlines():
        m = BIND.match(line.strip())
        if not m:
            continue
        spec, action, _ = m.groups()
        info = describe(action)
        if info is None or re.search(r'KP_', spec):
            continue
        keys = keycaps(spec)
        category, label = info
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
