"""Terminal and editor command lines shared by the shell bridge (no Qt)."""
import shutil
from pathlib import Path


def terminal_args(command, title='Wysun · Terminal'):
    terminal = shutil.which('ghostty')
    if terminal:
        return [terminal, '--title='+title, '-e', *map(str, command)]
    terminal = shutil.which('x-terminal-emulator') or shutil.which('xterm')
    if not terminal:
        raise RuntimeError('No se encontró una terminal.')
    return [terminal, '-e', *map(str, command)]


def vim_args(path):
    editor = shutil.which('nvim') or shutil.which('vim')
    if not editor:
        raise RuntimeError('Instala Vim o Neovim para editar archivos.')
    p = Path(path).expanduser().absolute()
    return terminal_args([editor, '--', str(p)], 'Vim · '+p.name)
