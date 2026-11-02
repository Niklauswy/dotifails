"""What `wysun lanshare` was asked to do (command line → Options)."""
import argparse
from dataclasses import dataclass
import os
import re
import secrets

# Easy to dictate: lowercase and digits without l/1/o/0.
ALPHABET = 'abcdefghijkmnpqrstuvwxyz23456789'
DEFAULT_PORT = 8000
DEFAULT_IDLE = 3600
_GENERATE = object()

EPILOG = '''ejemplos:
  wysun lanshare                         carpeta actual, solo ver y descargar
  wysun lanshare informe.pdf             comparte solo ese archivo
  wysun lanshare ~/Videos --subidas      permite subir archivos y crear carpetas
  wysun lanshare ~/Videos --clave        genera una contraseña corta
  wysun lanshare ~/Videos --clave gato123
  wysun lanshare ~/Videos --inactivo 3h  se apaga tras 3 h sin uso (por defecto 1 h)
  wysun lanshare --detener PID           detiene un LANShare (lo usa la barra)'''


@dataclass
class Options:
    paths: list
    uploads: bool = False
    password: str | None = None
    port: int = DEFAULT_PORT
    port_given: bool = False
    idle: int | None = DEFAULT_IDLE
    stop: int | None = None


def make_password(rng=secrets):
    return ''.join(rng.choice(ALPHABET) for _ in range(6))


def parse_duration(text):
    """'30m', '2h', '45s' or bare minutes → seconds; ValueError otherwise."""
    match = re.fullmatch(r'\s*(\d+)\s*([smh]?)\s*', text or '')
    if not match or int(match.group(1)) <= 0:
        raise ValueError(text)
    return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600, '': 60}[match.group(2)]


def _parser():
    ap = argparse.ArgumentParser(
        prog='wysun lanshare', description='Comparte carpetas o archivos con la red local.',
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='*', metavar='RUTA', help='carpeta o archivos (por defecto, la carpeta actual)')
    ap.add_argument('--subidas', action='store_true', help='permite subir archivos y crear carpetas (solo con una carpeta)')
    ap.add_argument('--clave', nargs='?', const=_GENERATE, default=None, metavar='CLAVE',
                    help='pide contraseña; sin valor genera una corta')
    ap.add_argument('--puerto', '--port', '-p', type=int, default=None, metavar='N', help='puerto (por defecto 8000)')
    ap.add_argument('--inactivo', metavar='DURACIÓN', help='se apaga tras ese tiempo sin uso: 30m, 2h (por defecto 1h)')
    ap.add_argument('--sin-limite', action='store_true', help='nunca se apaga solo')
    ap.add_argument('--readonly', action='store_true', help=argparse.SUPPRESS)   # old alias: read-only is the default
    ap.add_argument('--detener', type=int, metavar='PID', help='detiene el LANShare con ese PID')
    return ap


def parse(argv=None, rng=secrets):
    ap = _parser()
    args = ap.parse_args(argv)
    paths = list(args.paths)
    password = args.clave
    # `--clave RUTA`: an existing path after a bare --clave is a path, not the password.
    if isinstance(password, str) and os.path.exists(password):
        paths.insert(0, password)
        password = _GENERATE
    if password is _GENERATE:
        password = make_password(rng)
    if password is not None and not password.strip():
        ap.error('la contraseña no puede estar vacía')
    if args.detener is not None:
        return Options(paths=[], stop=args.detener)
    resolved = []
    for path in paths or ['.']:
        real = os.path.realpath(os.path.expanduser(path))
        if not os.path.exists(real):
            ap.error(f'no existe: {path}')
        resolved.append(real)
    if args.subidas and (len(resolved) != 1 or not os.path.isdir(resolved[0])):
        ap.error('--subidas solo se puede usar al compartir una sola carpeta')
    idle = DEFAULT_IDLE
    if args.sin_limite:
        idle = None
    elif args.inactivo is not None:
        try:
            idle = parse_duration(args.inactivo)
        except ValueError:
            ap.error(f'duración no válida: {args.inactivo} (usa por ejemplo 30m o 2h)')
    port = args.puerto if args.puerto is not None else DEFAULT_PORT
    if not 0 < port < 65536:
        ap.error(f'puerto no válido: {port}')
    return Options(paths=resolved, uploads=args.subidas, password=password, port=port,
                   port_given=args.puerto is not None, idle=idle)
