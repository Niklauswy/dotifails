"""`wysun drive …`: upload from the terminal, log in and out, recent uploads, bar actions."""
import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from wysun_core import launch
from wysun_drive import account, api, history, login, status
from wysun_drive.client import AuthError, Cancelled, Client, DriveError, split_server

HELP = '''Wysun Drive · tu Nextcloud
Uso: wysun drive [ORDEN] [opciones]

  (sin orden)              selector en la terminal: marca y sube, y Recientes con sus links
  up RUTA… [opciones]      sube archivos o carpetas (por defecto a Wysun/)
      --link               crea el link público, lo copia y lo imprime
      --clave [CLAVE]      link con contraseña (sin valor: genera una)
      --caduca 7d          el link caduca en N días
      --a CARPETA          carpeta de destino en tu Nextcloud
      --nombre NOMBRE      nombre en la nube (solo con un archivo)
      --json               una línea JSON por elemento (para otras herramientas)
      --notificar          el resultado como notificación
      --sin-copiar         no copiar el link al portapapeles
  login [SERVIDOR]         inicia sesión desde el navegador (con SERVIDOR, también lo guarda)
  logout                   cierra la sesión y revoca la contraseña de aplicación
  recientes [--json]       lo subido y sus links
  ajustes [--servidor URL] [--carpeta NOMBRE]
                           cambia tu Nextcloud o la carpeta de destino (también en Ajustes › Wysun Drive)
  estado [--json]          servidor, carpeta y sesión

Servidor por defecto: https://cloud.wysun.store. Al cambiarlo hay que iniciar sesión otra vez.
'''
PASSWORD_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'


class Usage(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)


def human_size(n):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            text = f'{n:.0f}' if unit == 'B' else f'{n:.1f}'.replace('.', ',')
            return f'{text} {unit}'
        n /= 1024


def generate_password(length=10):
    return ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


def parse_days(text):
    value = str(text).strip().lower().removesuffix('d')
    if not value.isdigit() or int(value) < 1:
        raise Usage(f'--caduca espera días, por ejemplo 7d (no «{text}»)')
    return int(value)


def copy(text):
    """Put ``text`` on the Wayland clipboard; False when wl-copy is missing or fails."""
    binary = shutil.which('wl-copy')
    if binary is None:
        return False
    try:
        subprocess.run([binary, '--', text], check=True, timeout=5, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def notify(title, body='', critical=False):
    binary = shutil.which('notify-send')
    if binary is None:
        return
    argv = [binary, '-a', 'Wysun Drive', '-i', 'folder-remote']
    if critical:
        argv += ['-u', 'critical']
    try:
        subprocess.run([*argv, '--', title, body], timeout=5, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        pass


def open_terminal(command=('wysun', 'drive')):
    argv = launch.terminal_argv(list(command))
    if argv is None:
        return False
    subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    return True


def open_url(url):
    binary = shutil.which('xdg-open')
    if binary is None:
        return False
    subprocess.Popen([binary, url], start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    return True


class Progress:
    """A one-line progress readout on stderr (only on a terminal)."""

    def __init__(self, stream=sys.stderr):
        self.stream = stream
        self.enabled = stream.isatty()

    def __call__(self, name, done, total, all_done, all_total):
        if not self.enabled:
            return
        percent = 100 if not all_total else int(all_done * 100 / all_total)
        line = f'  {name[:40]}  {percent:3d} %  {human_size(all_done)} / {human_size(all_total)}'
        self.stream.write('\r\033[K' + line)
        self.stream.flush()

    def clear(self):
        if self.enabled:
            self.stream.write('\r\033[K')
            self.stream.flush()


def up(argv, out=sys.stdout, err=sys.stderr):
    parser = Parser(prog='wysun drive up', add_help=False)
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--link', action='store_true')
    parser.add_argument('--clave', nargs='?', const='')
    parser.add_argument('--caduca')
    parser.add_argument('--a', dest='folder')
    parser.add_argument('--nombre')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--notificar', action='store_true')
    parser.add_argument('--sin-copiar', dest='no_copy', action='store_true')
    args = parser.parse_args(argv)
    if not args.paths:
        raise Usage('falta qué subir: wysun drive up RUTA…')
    if args.nombre and len(args.paths) != 1:
        raise Usage('--nombre solo sirve con un archivo')
    if args.nombre and ('/' in args.nombre or args.nombre in ('.', '..')):
        raise Usage('--nombre no puede llevar «/»')
    link = args.link or args.clave is not None or args.caduca is not None
    password = (args.clave or generate_password()) if args.clave is not None else None
    days = parse_days(args.caduca) if args.caduca is not None else None

    if account.current() is None:
        message = 'Inicia sesión primero: wysun drive login'
        try:
            api.client()
        except AuthError as error:
            message = str(error)
        print(message, file=err)
        if args.notificar:
            notify('Wysun Drive no tiene sesión', 'Inicia sesión en la terminal que se abrió.', critical=True)
            open_terminal()
        return 3

    cancelled = {'flag': False}
    signal.signal(signal.SIGTERM, lambda *_: cancelled.update(flag=True))
    names = [Path(p).name or p for p in args.paths]
    title = names[0] if len(names) == 1 else f'{len(names)} elementos'
    tracker = status.StatusFile(os.getpid(), title)
    progress = Progress(err) if not args.json else None

    def on_progress(*values):
        tracker.progress(*values)
        if progress is not None:
            progress(*values)

    tracker.start()
    try:
        results = api.upload(args.paths, link=link, folder=args.folder, name=args.nombre, password=password,
                             expire_days=days, on_progress=on_progress, cancelled=lambda: cancelled['flag'])
    except Cancelled as error:
        if progress:
            progress.clear()
        print(str(error), file=err)
        if args.notificar:
            notify('Subida cancelada', title)
        return 1
    except DriveError as error:
        if progress:
            progress.clear()
        print(str(error), file=err)
        if args.notificar:
            notify('No se pudo subir', str(error), critical=True)
        return error.code
    finally:
        tracker.remove()
    if progress:
        progress.clear()

    links = [r.url for r in results if r.url]
    copied = bool(links) and not args.no_copy and copy('\n'.join(links))
    for result in results:
        if args.json:
            print(json.dumps(result.to_json(), ensure_ascii=False), file=out)
        elif result.ok:
            print(f'✓ {result.name}  →  {result.remote}  ({human_size(result.size)})', file=out)
            if result.url:
                print(f'  {result.url}' + (f'  · contraseña: {result.password}' if result.password else ''), file=out)
            if result.link_error:
                print(f'  sin link: {result.link_error}', file=err)
        else:
            print(f'✗ {result.name}: {result.error}', file=err)
    if copied and not args.json:
        print('Link copiado al portapapeles' if len(links) == 1 else 'Links copiados al portapapeles', file=err)
    failed = [r for r in results if not r.ok or (link and r.link_error)]
    if args.notificar:
        if links:
            body = links[0] if len(links) == 1 else '\n'.join(links)
            if password:
                body += f'\nContraseña: {password}'
            notify('Link copiado' if copied else 'Link listo', body)
        elif any(r.ok for r in results):
            done = [r.name for r in results if r.ok]
            notify('Subido a Wysun Drive', done[0] if len(done) == 1 else f'{len(done)} elementos')
        if failed:
            notify('No se pudo subir todo', '\n'.join(f'{r.name}: {r.error or r.link_error}' for r in failed[:3]),
                   critical=True)
    return 1 if failed else 0


def do_login(argv, out=sys.stdout, err=sys.stderr):
    server = account.normalize_server(argv[0] if argv else account.settings()['server'])
    try:
        url, poll = login.start(server)
        print(f'Abre esta dirección y autoriza a Wysun Drive:\n  {url}', file=out, flush=True)
        open_url(url)
        print('Esperando al navegador… (Ctrl+C cancela)', file=out, flush=True)
        acc = login.wait(poll, server=server)
        Client(acc).exists('')
    except KeyboardInterrupt:
        print('\nCancelado', file=err)
        return 1
    except DriveError as error:
        print(str(error), file=err)
        return error.code
    account.save(acc)
    if argv:
        account.save_settings(server=server)
    print(f'Sesión iniciada como {acc.user} en {acc.server}', file=out)
    return 0


def ajustes(argv, out=sys.stdout):
    parser = Parser(prog='wysun drive ajustes', add_help=False)
    parser.add_argument('--servidor')
    parser.add_argument('--carpeta')
    args = parser.parse_args(argv)
    if args.servidor is not None:
        try:
            split_server(account.normalize_server(args.servidor))
        except DriveError as error:
            raise Usage(str(error)) from None
    if args.carpeta is not None and not account.clean_folder(args.carpeta) and args.carpeta.strip('/ '):
        raise Usage('carpeta no válida')
    current = account.save_settings(server=args.servidor, folder=args.carpeta)
    print(f'Servidor: {current["server"]}\nCarpeta: {current["folder"] or "(raíz)"}', file=out)
    if account.load() is not None and account.current() is None:
        print('La sesión guardada es de otro servidor: ejecuta wysun drive login', file=out)
    return 0


def estado(argv, out=sys.stdout):
    current = account.settings()
    acc, saved = account.current(), account.load()
    data = {'server': current['server'], 'folder': current['folder'], 'user': acc.user if acc else None,
            'other_server': saved.server if saved is not None and acc is None else None}
    if '--json' in argv:
        print(json.dumps(data, ensure_ascii=False), file=out)
        return 0
    print(f'Servidor: {data["server"]}\nCarpeta: {data["folder"] or "(raíz)"}', file=out)
    print(f'Sesión: {acc.user}' if acc else 'Sin sesión (wysun drive login)', file=out)
    return 0


def do_logout(out=sys.stdout):
    acc = account.load()   # whatever server it belongs to
    if acc is None:
        print('No había sesión', file=out)
        return 0
    try:
        Client(acc).revoke()
    except DriveError:
        pass
    account.forget()
    print('Sesión cerrada', file=out)
    return 0


def recientes(argv, out=sys.stdout):
    entries = history.load()
    if '--json' in argv:
        for entry in entries:
            print(json.dumps(entry, ensure_ascii=False), file=out)
        return 0
    if not entries:
        print('Aún no has subido nada', file=out)
    for entry in entries[:30]:
        print(f'{entry["name"]}  →  {entry["remote"]}' + (f'\n  {entry["url"]}' if entry.get('url') else ''), file=out)
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if not args:
            from wysun_drive.ui.app import DriveApp
            return DriveApp().run()
        command, rest = args[0], args[1:]
        if command in ('-h', '--help', 'ayuda'):
            print(HELP, end='')
            return 0
        if command == 'up':
            return up(rest)
        if command == 'login':
            return do_login(rest)
        if command == 'logout':
            return do_logout()
        if command == 'recientes':
            return recientes(rest)
        if command == 'ajustes':
            return ajustes(rest)
        if command == 'estado':
            return estado(rest)
        if command == '--terminal':
            return 0 if open_terminal() else 1
        if command == '--detener' and len(rest) == 1 and rest[0].isdigit():
            return 0 if status.stop(int(rest[0])) else 1
        raise Usage(f'orden desconocida: {command}')
    except Usage as error:
        print(f'Wysun Drive: {error}. Consulta `wysun drive --help`.', file=sys.stderr)
        return 2
    except AuthError as error:
        print(str(error), file=sys.stderr)
        return 3
