#!/usr/bin/env python3
"""Claude Code status line hook: tells the AI usage panel which account this is and what its limits are.

Claude Code pipes a JSON document to its status line command on every refresh;
this reads it from stdin and prints nothing. Under $XDG_STATE_HOME/wysun/ai-usage it leaves:
  - claude-<home key>.json: the account's `rate_limits` and the folder it lives in, so the
    panel finds the account without any configuration. The key is a hash of the
    CLAUDE_CONFIG_DIR (default ~/.claude), the same one backend.py gives that home.
  - sessions/<session id>: the home key of the account that runs that session. Claude's session
    logs do not name their account, so this is how tokens are split between accounts, even
    when their homes share one projects folder.

Hooking up an account takes one step per Claude home (a CLAUDE_CONFIG_DIR), and nothing else:
  - With no status line yet, put this in <home>/settings.json (the status line stays empty; the panel works):
        {"statusLine": {"type": "command", "command": "python3 -I ~/.local/share/wysun/quickshell/modules/aiusage/statusline-hook.py"}}
  - With a status line script, keep its command in settings.json and add this line right after it reads
    its input (`input=$(cat)`):
        printf '%s' "$input" | python3 -I ~/.local/share/wysun/quickshell/modules/aiusage/statusline-hook.py 2>/dev/null &
The account then shows up in the panel after its first status line refresh; its limits appear once
Claude Code has answered at least once.
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

SESSION_ID = re.compile(r'[\w-]{1,128}')


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(text, encoding='utf-8')
    os.replace(temp, path)


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(payload, dict):
        return
    home = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude').expanduser().resolve()
    state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'wysun/ai-usage'
    key = hashlib.sha1(str(home).encode()).hexdigest()[:10]
    session = payload.get('session_id')
    if isinstance(session, str) and SESSION_ID.fullmatch(session):
        marker = state / 'sessions' / session
        try:
            known = marker.read_text(encoding='utf-8') == key
        except OSError:
            known = False
        if not known:
            write(marker, key)
    target = state / f'claude-{key}.json'
    limits = payload.get('rate_limits')
    if not limits:
        # A session answers with no limits until its first reply; keep what is already known.
        try:
            if json.loads(target.read_text(encoding='utf-8')).get('rate_limits'):
                return
        except (OSError, ValueError, AttributeError):
            pass
    model = payload.get('model')
    write(target, json.dumps({'rate_limits': limits or None, 'home': str(home), 'captured_at': time.time(),
                              'model': model.get('display_name') if isinstance(model, dict) else None}))


if __name__ == '__main__':
    main()
