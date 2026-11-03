#!/usr/bin/env python3
"""Wysun Player: the viewer for every image, video and audio file.

One process serves every window of the user. A second launch hands its files to the running one
and exits; the process ends with its last window, so nothing stays resident.

    wysun player [--paused] [--fullscreen] [--start SECONDS] [--] FILE...
"""
import argparse
import sys
import time

from wysun_player import client as player_client
from wysun_core.instance import release_on_termination

EXIT_MESSAGE = 'Wysun Player: no se pudo iniciar (¿otra instancia se está cerrando?)'


def parse(argv):
    parser = argparse.ArgumentParser(prog='wysun player', description='Visor de imágenes, video y audio de Wysun.')
    parser.add_argument('--paused', action='store_true', help='empezar en pausa')
    parser.add_argument('--fullscreen', action='store_true', help='abrir en pantalla completa')
    parser.add_argument('--start', type=float, metavar='SEGUNDOS', help='posición inicial de video o audio')
    parser.add_argument('files', nargs='*', metavar='ARCHIVO')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(sys.argv[1:] if argv is None else argv)
    payload = player_client.request(args.files, paused=args.paused, fullscreen=args.fullscreen, start=args.start)
    deadline = time.monotonic() + 3.0
    while True:
        # Wait for the reply until the deadline: a player that is still starting reads every request it
        # was sent, so reconnecting after a reply timeout would open the same files twice.
        if player_client.forward(payload, timeout=max(0.1, deadline - time.monotonic())):
            return 0
        # Serving needs the qml-runtime venv (PySide6 on the shell's Qt). Forwarding above works with any Python,
        # so opening a file in a running player never pays for the re-exec; the venv process runs this loop again.
        from wysun_qml import bootstrap
        bootstrap.ensure_runtime_python('wysun_player', sys.argv[1:] if argv is None else list(argv))
        from wysun_qml import naming
        naming.set_process_name('wysun-player')       # ps/top read the app, not `python3`
        owner = player_client.instance()
        if owner.claim():
            return serve(payload, owner)
        if time.monotonic() > deadline:
            print(EXIT_MESSAGE, file=sys.stderr)
            return 1
        time.sleep(0.05)            # an instance is starting or closing: try again shortly


def serve(first, owner):
    """Become the player process: import Qt only now, so a forwarded launch stays light."""
    release_on_termination(owner)            # until Qt takes over the signals in run()
    from wysun_qml import bootstrap
    bootstrap.require_qt()
    bootstrap.configure_qt()                 # plugins (wayland) before the application exists
    from wysun_player.quick.process import run
    return run(first, owner)


if __name__ == '__main__':
    raise SystemExit(main())
