"""Bounded file transfer server with authenticated LAN access and private uploads."""
from __future__ import annotations
import argparse
import base64
from functools import partial
import getpass
import hashlib
import hmac
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import sys
import tempfile
import threading
import time
import urllib.parse
from .common import ToolError, entry, port


def protected(path: Path) -> bool:
    return any(part.startswith(".") or part in {"node_modules", "__pycache__"}
               for part in path.parts if part not in {".", ".."})


def safe_filename(value: str) -> str:
    value = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not value or value in {".", ".."} or value.startswith(".") or len(value.encode()) > 240:
        raise ToolError("Nombre de archivo inválido o reservado.")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ToolError("El nombre contiene caracteres de control.")
    return value


def publish_upload(temporary: Path, folder: Path, name: str) -> Path:
    original = Path(safe_filename(name))
    for number in range(10000):
        candidate = folder / (original.stem + (f"_{number}" if number else "") + original.suffix)
        try:
            os.link(temporary, candidate)
            return candidate
        except FileExistsError:
            continue
    raise ToolError("Hay demasiados archivos con ese nombre.")


class TransferServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    block_on_close = False

    def __init__(self, address, root: Path, *, uploads: Path | None = None,
                 max_bytes=32 * 1024 * 1024, code: str | None = None,
                 static=False, quiet=False, clients=16):
        self.root = root.resolve()
        self.uploads = uploads.resolve() if uploads else None
        self.max_bytes = max_bytes
        self.code_digest = hashlib.sha256(code.encode()).digest() if code else None
        self.static, self.quiet = static, quiet
        self.slots = threading.BoundedSemaphore(clients)
        self.auth_failures = {}
        self.auth_lock = threading.Lock()
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(address, partial(TransferHandler, directory=str(self.root)))

    def enable_tls(self, context):
        # Handshakes run in bounded workers, never on the accepting thread.
        self.socket = context.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)

    def handle_error(self, request, client_address):
        error = sys.exception()
        if isinstance(error, (ConnectionError, TimeoutError, ssl.SSLError)):
            return
        if not self.quiet:
            print(f"Error al atender solicitud: {type(error).__name__}", file=sys.stderr)

    def process_request(self, request, client_address):
        request.settimeout(20)
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.0 503 Busy\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class TransferHandler(SimpleHTTPRequestHandler):
    server_version = "FileShare/1.0"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, format, *args):
        if not self.server.quiet:
            # Never persist Authorization, query strings or full request lines.
            print(f"HTTP {self.command} {getattr(self, '_status', '-')} · {self.client_address[0]}", flush=True)

    def send_response(self, code, message=None):
        self._status = code
        super().send_response(code, message)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        if not self.server.static and getattr(self, "_download_name", None):
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" +
                             urllib.parse.quote(self._download_name))
        super().end_headers()

    def authenticate(self) -> bool:
        if self.server.code_digest is None:
            return True
        address = self.client_address[0]
        with self.server.auth_lock:
            now = time.monotonic()
            # Expire old entries and bound the size of the per-address limiter.
            self.server.auth_failures = {ip: item for ip, item in self.server.auth_failures.items()
                                        if now - item[1] < 30}
            attempts, started = self.server.auth_failures.get(address, (0, now))
            if attempts >= 10:
                self.send_response(429)
                self.send_header("Retry-After", "30")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return False
        supplied = self.headers.get("Authorization", "")
        valid = False
        if supplied.startswith("Basic ") and len(supplied) < 8192:
            try:
                decoded = base64.b64decode(supplied[6:], validate=True).decode()
                user, secret = decoded.split(":", 1)
                valid = user == "orbit" and hmac.compare_digest(
                    hashlib.sha256(secret.encode()).digest(), self.server.code_digest)
            except (ValueError, UnicodeError):
                pass
        if valid:
            with self.server.auth_lock:
                self.server.auth_failures.pop(address, None)
            return True
        with self.server.auth_lock:
            if len(self.server.auth_failures) > 1024:
                self.server.auth_failures.clear()
            self.server.auth_failures[address] = (attempts + 1, started)
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="File Share", charset="UTF-8"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def allowed_path(self) -> Path | None:
        try:
            raw = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            relative = Path(raw.lstrip("/"))
            path = (self.server.root / relative).resolve()
            if ".." in relative.parts or protected(relative) or not path.is_relative_to(self.server.root):
                raise ValueError()
            if protected(path.relative_to(self.server.root)):
                raise ValueError()
            return path
        except (ValueError, OSError):
            self.send_error(403, "Ruta no compartida")
            return None

    def do_GET(self):
        if not self.authenticate():
            return
        path = self.allowed_path()
        if path is None:
            return
        self._download_name = path.name if path.is_file() else None
        super().do_GET()

    def do_HEAD(self):
        if not self.authenticate() or self.allowed_path() is None:
            return
        super().do_HEAD()

    def list_directory(self, path):
        from .transfer_page import render
        folder = Path(path)
        entries = []
        try:
            candidates = sorted(folder.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
            for item in candidates:
                resolved = item.resolve()
                if protected(item.relative_to(self.server.root)) or not resolved.is_relative_to(self.server.root):
                    continue
                if protected(resolved.relative_to(self.server.root)):
                    continue
                try:
                    entries.append((item.name,item.is_dir(),item.stat().st_size))
                except OSError:
                    continue
        except OSError:
            self.send_error(403, "No se puede leer la carpeta")
            return None
        nonce = secrets.token_urlsafe(18)
        data = render(folder,self.server.root,entries,uploads=bool(self.server.uploads),
                      max_bytes=self.server.max_bytes,nonce=nonce,authenticated=bool(self.server.code_digest))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; style-src 'unsafe-inline'; script-src 'nonce-" + nonce + "'")
        self.end_headers()
        return io.BytesIO(data)

    def do_PUT(self):
        if not self.authenticate():
            return
        if urllib.parse.urlsplit(self.path).path != "/api/upload" or not self.server.uploads:
            self.send_error(405, "Subidas desactivadas")
            return
        if self.headers.get("Transfer-Encoding"):
            self.send_error(400, "Usa Content-Length")
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            name = safe_filename(urllib.parse.unquote(self.headers.get("X-Filename", "")))
        except (ValueError, ToolError):
            self.send_error(400, "Longitud o nombre inválido")
            return
        if length < 0 or length > self.server.max_bytes:
            self.send_error(413, "El archivo supera el límite")
            return
        fd, tempname = tempfile.mkstemp(prefix=".upload-", dir=self.server.uploads)
        temporary = Path(tempname)
        try:
            with os.fdopen(fd, "wb") as output:
                remaining = length
                while remaining:
                    block = self.rfile.read(min(remaining, 65536))
                    if not block:
                        raise OSError("Carga incompleta")
                    output.write(block)
                    remaining -= len(block)
                output.flush()
                os.fsync(output.fileno())
            destination = publish_upload(temporary, self.server.uploads, name)
            payload = json.dumps({"name": destination.name, "bytes": length}).encode()
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (OSError, TimeoutError, ToolError):
            self.send_error(400, "Carga incompleta o no disponible")
        finally:
            temporary.unlink(missing_ok=True)


def server_flags(parser, *, uploads=True):
    parser.add_argument("legacy_port", type=port, nargs="?")
    parser.add_argument("--port", type=port, default=8000)
    parser.add_argument("-C", "--directory", type=Path, default=Path.cwd())
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--lan", action="store_true", help="Escuchar en la red local; requiere código de acceso")
    parser.add_argument("--public", action="store_true", help="Permitir acceso LAN sin autenticación explícitamente")
    parser.add_argument("--key-file", type=Path, help="Archivo privado que contiene el código de acceso")
    parser.add_argument("--ask-code", action="store_true", help="Introducir el código sin mostrarlo")
    parser.add_argument("--uploads", action="store_true", help="Permitir recibir archivos")
    parser.add_argument("--upload-dir", type=Path)
    parser.add_argument("--max-mb", type=int, default=32)
    parser.add_argument("--cert", type=Path)
    parser.add_argument("--key", type=Path)
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(static=not uploads)


def serve(args) -> int:
    root = args.directory.expanduser().resolve()
    if not root.is_dir():
        raise ToolError("La carpeta compartida no existe.")
    if not 1 <= args.max_mb <= 4096:
        raise ToolError("--max-mb debe estar entre 1 y 4096.")
    if bool(args.cert) != bool(args.key):
        raise ToolError("HTTPS requiere --cert y --key juntos.")
    bind = "0.0.0.0" if args.lan else args.bind
    local = bind in {"127.0.0.1", "::1", "localhost"}
    code = None
    if args.key_file:
        path = args.key_file.expanduser()
        if path.stat().st_mode & 0o077:
            raise ToolError("El archivo de acceso requiere permisos 600.")
        code = path.read_text().strip()
    elif args.ask_code or (not local and not args.public):
        if not sys.stdin.isatty():
            raise ToolError("Para acceso LAN no interactivo indica --key-file o --public.")
        code = getpass.getpass("Código de acceso (usuario orbit): ")
    if code is not None and (len(code) < 8 or len(code) > 4096 or ":" in code):
        raise ToolError("Usa un código de 8 a 4096 caracteres sin dos puntos.")
    upload_dir = None
    if args.uploads or args.upload_dir:
        upload_dir = (args.upload_dir or root / "uploads").expanduser().resolve()
        upload_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    selected_port = args.legacy_port or args.port
    with TransferServer((bind, selected_port), root, uploads=upload_dir,
                        max_bytes=args.max_mb * 1024 * 1024, code=code,
                        static=args.static, quiet=args.quiet) as server:
        scheme = "https" if args.cert else "http"
        if args.cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(args.cert, args.key)
            server.enable_tls(context)
        shown = f"[{bind}]" if ":" in bind else bind
        print(f"Servidor: {scheme}://{shown}:{selected_port}", flush=True)
        print(f"Carpeta: {root}", flush=True)
        if upload_dir:
            print(f"Subidas: {upload_dir} · límite {args.max_mb} MiB por archivo", flush=True)
        print("Acceso: usuario orbit y código" if code else "Acceso: sin autenticación", flush=True)
        print("Ctrl+C detiene el servidor.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="file-share", description="Compartir archivos y recibir subidas con límites y acceso LAN explícito.")
    server_flags(parser)
    return serve(parser.parse_args(argv))


if __name__ == "__main__":
    entry(main)
