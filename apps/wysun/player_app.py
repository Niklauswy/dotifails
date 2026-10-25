#!/usr/bin/env python3
"""Wysun Player: the viewer for every image, video and audio file.

One process serves every window of the user. A second launch hands its files to the running one
and exits; the process ends with its last window, so nothing stays resident.

    wysun player [--paused] [--fullscreen] [--start SECONDS] [--] FILE...
"""
import argparse
import signal
import sys
import time

import player_client

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
        if player_client.forward(payload):
            return 0
        owner = player_client.instance()
        if owner.claim():
            return serve(payload, owner)
        if time.monotonic() > deadline:
            print(EXIT_MESSAGE, file=sys.stderr)
            return 1
        time.sleep(0.05)            # an instance is starting or closing: try again shortly


def serve(first, owner):
    """Become the player process: import Qt only now, so a forwarded launch stays light."""
    def stop(*_):
        owner.close()
        raise SystemExit(0)
    # Until Qt takes over the signals (in run), a termination still removes the socket.
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, stop)
    from player_window import run
    return run(first, owner)


if __name__ == '__main__':
    raise SystemExit(main())
