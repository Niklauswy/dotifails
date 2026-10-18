#!/usr/bin/env python3
"""Select native or terminal installation without changing scripted invocations."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    source = Path(__file__).resolve().parent.parent
    graphical = bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
    explicit_gui = '--gui' in args
    explicit_cli = '--cli' in args
    if explicit_gui and explicit_cli:
        print('Elige --gui o --cli, no ambos.', file=sys.stderr)
        return 2
    if explicit_cli:
        args.remove('--cli')
    if explicit_gui:
        args.remove('--gui')
    gui = explicit_gui or (not args and graphical and not explicit_cli)
    if gui:
        if args:
            print('Usa --gui sin opciones de instalación; elige los componentes en la ventana.', file=sys.stderr)
            return 2
        if not graphical:
            print('No hay sesión gráfica. Usa ./instalar.sh --cli o abre una sesión de escritorio.', file=sys.stderr)
            return 1
        try:qt_available=importlib.util.find_spec('PySide6.QtWidgets') is not None
        except ModuleNotFoundError:qt_available=False
        if not qt_available:
            print('La interfaz necesita python3-pyside6.qtwidgets. La preparación instala únicamente su entorno gráfico.')
            if not sys.stdin.isatty():
                print('Abre ./instalar.sh en una terminal para preparar la interfaz, o usa --cli.', file=sys.stderr)
                return 1
            from main import host_supported
            host_supported()
            answer = input('¿Preparar la interfaz con sudo? [s/N] ').strip().lower()
            if answer not in ('s', 'si', 'sí', 'y', 'yes'):
                return 0
            subprocess.run(['sudo','apt-get','update'],check=True)
            subprocess.run(['sudo','apt-get','install','--yes','--no-install-recommends','python3-pyside6.qtwidgets'],check=True)
        os.execv('/usr/bin/python3', ['/usr/bin/python3', str(source/'installer/main.py'), 'gui', '--source', str(source)])
    os.execv('/usr/bin/python3', ['/usr/bin/python3', str(source/'installer/main.py'), 'install', '--source', str(source), *args])


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print('No se pudo iniciar el instalador: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
