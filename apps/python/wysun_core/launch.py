"""Start a Wysun module in a fresh interpreter, importing from the same package root as this one.

Every Wysun program runs as a module (``python3 -P -m wysun_music``) with the package root in
``PYTHONPATH``. ``-P`` keeps the current directory off ``sys.path``; the root is this copy of
``wysun_core``'s parent, so a Recorder release only ever starts code from its own release.
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Terminals Wysun opens for a command, best first (shared by Files and Cloud).
TERMINALS = ('ghostty', 'x-terminal-emulator', 'alacritty', 'kitty', 'xterm')


def environment(base=None):
    """``base`` (default: this process' environment) with ``PYTHONPATH`` set to the package root."""
    env = dict(os.environ if base is None else base)
    env['PYTHONPATH'] = str(ROOT)
    return env


def argv(module, *args, python=None):
    """argv that runs ``module`` with ``args``; pass it with ``env=environment()``."""
    return [python or sys.executable, '-P', '-m', module, *map(str, args)]


def terminal_argv(command):
    """argv that runs ``command`` in a new terminal window, or None when none is installed."""
    for name in TERMINALS:
        binary = shutil.which(name)
        if binary is None:
            continue
        # Ghostty's single instance would reuse the window wherever it runs, ignoring this one.
        if name == 'ghostty':
            return [binary, '--gtk-single-instance=false', '-e', *command]
        return [binary, '-e', *command]
    return None
