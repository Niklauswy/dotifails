"""Wysun LANShare — servidor de archivos para la red local.

Explorador de carpetas, miniaturas y previews de video (ffmpeg), streaming con
Range (Safari/iPhone), subida de archivos y descarga de carpetas en .zip.

Uso:
    wysun lanshare [CARPETA] [--port 8000] [--readonly]
"""
import argparse
import hashlib
import json
import mimetypes
import os
import re
import socket
import subprocess
import threading
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wysun_core import paths
from wysun_core.jsonio import atomic_path

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
CACHE = str(paths.cache("wysun", "lanshare"))

VIDEO = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".ts", ".flv", ".wmv"}
IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif", ".heic"}
AUDIO = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"}
TEXT = {".txt", ".md", ".log", ".json", ".csv", ".py", ".js", ".ts", ".html", ".css",
        ".sh", ".yml", ".yaml", ".toml", ".ini", ".xml", ".c", ".cpp", ".h", ".java", ".rs", ".go"}
ARCHIVE = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".xz", ".bz2"}

SPRITE_FRAMES = 10
SPRITE_W, SPRITE_H = 320, 180
CHUNK = 1024 * 1024

ROOT = ""
READONLY = False

mimetypes.add_type("video/mp4", ".m4v")
mimetypes.add_type("video/x-matroska", ".mkv")
mimetypes.add_type("video/mp2t", ".ts")
mimetypes.add_type("text/plain", ".md")
mimetypes.add_type("text/plain", ".log")
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/heic", ".heic")


class Incomplete(Exception):
    """A thumbnail or an upload that did not finish; its temporary file is discarded."""


def kind_of(name, is_dir=False):
    if is_dir:
        return "dir"
    ext = os.path.splitext(name)[1].lower()
    if ext in VIDEO:
        return "video"
    if ext in IMAGE:
        return "image"
    if ext in AUDIO:
        return "audio"
    if ext == ".pdf":
        return "pdf"
    if ext in TEXT:
        return "text"
    if ext in ARCHIVE:
        return "archive"
    return "file"


def safe(rel):
    """Ruta real dentro de ROOT o None (bloquea ../ y symlinks que escapan)."""
    rel = (rel or "").strip("/")
    if any(part.startswith(".") for part in rel.split("/") if part):
        return None
    p = os.path.realpath(os.path.join(ROOT, rel))
    if p != ROOT and not p.startswith(ROOT + os.sep):
        return None
    return p


def rel_of(p):
    r = os.path.relpath(p, ROOT)
    return "" if r == "." else r.replace(os.sep, "/")


def file_key(path, kind):
    st = os.stat(path)
    raw = f"{path}|{st.st_size}|{st.st_mtime_ns}|{kind}".encode()
    return hashlib.sha1(raw).hexdigest()


# ---------------------------------------------------------------- metadata --

_meta_mem = {}
_meta_lock = threading.Lock()


def probe(path):
    try:
        key = file_key(path, "meta")
    except OSError:
        return {}
    with _meta_lock:
        if key in _meta_mem:
            return _meta_mem[key]
    disk = os.path.join(CACHE, "meta", key[:2], key + ".json")
    if os.path.exists(disk):
        try:
            with open(disk) as f:
                meta = json.load(f)
            with _meta_lock:
                _meta_mem[key] = meta
            return meta
        except (OSError, ValueError):
            pass
    meta = {}
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True, timeout=20, check=False).stdout
        data = json.loads(out or b"{}")
        fmt = data.get("format", {})
        if fmt.get("duration"):
            meta["duration"] = float(fmt["duration"])
        for s in data.get("streams", []):
            if s.get("codec_type") == "video" and "vcodec" not in meta and s.get("disposition", {}).get("attached_pic") != 1:
                meta["vcodec"] = s.get("codec_name")
                meta["width"] = s.get("width")
                meta["height"] = s.get("height")
            elif s.get("codec_type") == "audio" and "acodec" not in meta:
                meta["acodec"] = s.get("codec_name")
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    os.makedirs(os.path.dirname(disk), exist_ok=True)
    try:
        with open(disk, "w") as f:
            json.dump(meta, f)
    except OSError:
        pass
    with _meta_lock:
        _meta_mem[key] = meta
    return meta


# -------------------------------------------------------- thumbnails/sprite --

_gen_sem = threading.Semaphore(max(2, (os.cpu_count() or 4) // 2))
_key_locks = {}
_key_guard = threading.Lock()
FF = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]


def _build_thumb(path, out):
    kind = kind_of(path)
    if kind == "video":
        dur = probe(path).get("duration") or 0
        t = dur * 0.2 if dur > 10 else min(1.0, dur / 2)
        cmd = FF + ["-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
                    "-vf", "scale=640:-2", "-q:v", "4", out]
    else:
        cmd = FF + ["-i", path, "-frames:v", "1",
                    "-vf", "scale='min(640,iw)':-2", "-q:v", "4", out]
    return subprocess.run(cmd, capture_output=True, timeout=60).returncode == 0


def _build_sprite(path, out):
    dur = probe(path).get("duration") or 0
    if dur < 2:
        return False
    cmd = list(FF)
    chains = []
    for i in range(SPRITE_FRAMES):
        t = dur * (i + 1) / (SPRITE_FRAMES + 1)
        cmd += ["-ss", f"{t:.2f}", "-i", path]
        chains.append(
            f"[{i}:v:0]trim=end_frame=1,scale={SPRITE_W}:{SPRITE_H}:force_original_aspect_ratio=increase,"
            f"crop={SPRITE_W}:{SPRITE_H},setsar=1[f{i}]")
    graph = ";".join(chains) + ";" + "".join(f"[f{i}]" for i in range(SPRITE_FRAMES)) + \
        f"hstack=inputs={SPRITE_FRAMES}[out]"
    cmd += ["-filter_complex", graph, "-map", "[out]", "-frames:v", "1", "-q:v", "5", out]
    return subprocess.run(cmd, capture_output=True, timeout=180).returncode == 0


def cached_image(path, kind):
    try:
        key = file_key(path, kind)
    except OSError:
        return None
    out = os.path.join(CACHE, kind, key[:2], key + ".jpg")
    fail = out + ".fail"
    if os.path.exists(out):
        return out
    if os.path.exists(fail):
        return None
    with _key_guard:
        lock = _key_locks.setdefault(out, threading.Lock())
    with lock:
        if os.path.exists(out):
            return out
        with _gen_sem:
            builder = _build_sprite if kind == "sprite" else _build_thumb
            try:
                with atomic_path(out) as tmp:
                    if not builder(path, str(tmp)) or not tmp.exists() or tmp.stat().st_size == 0:
                        raise Incomplete
                return out
            except (OSError, subprocess.SubprocessError, Incomplete):
                pass
        open(fail, "w").close()
        return None


# ------------------------------------------------------------------ server --

def unique_name(directory, name):
    base, ext = os.path.splitext(name)
    cand, n = name, 1
    while os.path.exists(os.path.join(directory, cand)):
        cand = f"{base} ({n}){ext}"
        n += 1
    return cand


def clean_name(name):
    name = os.path.basename((name or "").replace("\\", "/")).strip()
    name = re.sub(r"[\x00-\x1f]", "", name).lstrip(".")
    return name[:240]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "lanshare/1.0"

    # -- helpers
    def send_bytes(self, data, ctype, status=200, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, obj, status=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8",
                        status, {"Cache-Control": "no-store"})

    def fail(self, status, msg):
        self.send_json({"error": msg}, status)

    def query(self):
        return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}

    def log_message(self, fmt, *args):
        pass

    # -- routing
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        try:
            if path == "/" or path.startswith("/browse") or path.startswith("/watch/"):
                return self.serve_static("index.html")
            if path.startswith("/static/"):
                return self.serve_static(path[len("/static/"):])
            if path == "/api/ls":
                return self.api_ls()
            if path in ("/api/thumb", "/api/sprite"):
                return self.api_image(path.rsplit("/", 1)[1])
            if path.startswith("/raw/"):
                return self.serve_file(path[len("/raw/"):])
            if path.startswith("/zip/") or path == "/zip":
                return self.serve_zip(path[len("/zip/"):])
            self.fail(404, "No encontrado")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/upload":
            return self.api_upload()
        self.fail(404, "No encontrado")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/mkdir":
            return self.api_mkdir()
        self.fail(404, "No encontrado")

    # -- static
    def serve_static(self, name):
        p = os.path.realpath(os.path.join(STATIC, name))
        if not p.startswith(STATIC + os.sep) or not os.path.isfile(p):
            return self.fail(404, "No encontrado")
        with open(p, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self.send_bytes(data, ctype, extra={"Cache-Control": "no-cache"})

    # -- api
    def api_ls(self):
        rel = self.query().get("path", "")
        d = safe(rel)
        if not d or not os.path.isdir(d):
            return self.fail(404, "Carpeta no encontrada")
        entries = []
        try:
            items = list(os.scandir(d))
        except PermissionError:
            return self.fail(403, "Sin permiso")
        for e in items:
            if e.name.startswith("."):
                continue
            try:
                real = os.path.realpath(e.path)
                if real != ROOT and not real.startswith(ROOT + os.sep):
                    continue
                is_dir = e.is_dir()
                st = e.stat()
            except OSError:
                continue
            item = {"name": e.name, "kind": kind_of(e.name, is_dir), "mtime": int(st.st_mtime)}
            if is_dir:
                try:
                    item["count"] = sum(1 for x in os.scandir(e.path) if not x.name.startswith("."))
                except OSError:
                    item["count"] = 0
            else:
                item["size"] = st.st_size
            entries.append(item)
        media = [it for it in entries if it["kind"] in ("video", "audio")]
        if media and len(media) <= 500:
            with ThreadPoolExecutor(8) as pool:
                metas = pool.map(lambda it: probe(os.path.join(d, it["name"])), media)
                for it, meta in zip(media, metas):
                    it.update(meta)
        self.send_json({"path": rel_of(d), "entries": entries, "readonly": READONLY})

    def api_image(self, kind):
        p = safe(self.query().get("path", ""))
        if not p or not os.path.isfile(p) or kind_of(p) not in (("video",) if kind == "sprite" else ("video", "image")):
            return self.fail(404, "No encontrado")
        out = cached_image(p, kind)
        if not out:
            return self.fail(404, "Sin vista previa")
        with open(out, "rb") as f:
            data = f.read()
        self.send_bytes(data, "image/jpeg", extra={"Cache-Control": "public, max-age=604800"})

    def api_upload(self):
        if READONLY:
            return self.fail(403, "Servidor en modo solo lectura")
        q = self.query()
        d = safe(q.get("dir", ""))
        name = clean_name(q.get("name", ""))
        if not d or not os.path.isdir(d) or not name:
            return self.fail(400, "Destino inválido")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.fail(411, "Falta Content-Length")
        name = unique_name(d, name)
        dest = os.path.join(d, name)
        remaining = length
        try:
            # Hidden temporary next to the destination; it replaces it only when every byte arrived.
            with atomic_path(dest, mode=0o644) as tmp:
                with open(tmp, "wb") as f:
                    while remaining > 0:
                        buf = self.rfile.read(min(CHUNK, remaining))
                        if not buf:
                            break
                        f.write(buf)
                        remaining -= len(buf)
                if remaining:
                    raise Incomplete
        except Incomplete:
            self.close_connection = True
            return self.fail(400, "Subida incompleta")
        except OSError as ex:
            return self.fail(500, f"No se pudo guardar: {ex.strerror}")
        self.send_json({"ok": True, "name": name})

    def api_mkdir(self):
        if READONLY:
            return self.fail(403, "Servidor en modo solo lectura")
        q = self.query()
        d = safe(q.get("dir", ""))
        name = clean_name(q.get("name", ""))
        if not d or not os.path.isdir(d) or not name:
            return self.fail(400, "Nombre inválido")
        target = os.path.join(d, name)
        if os.path.exists(target):
            return self.fail(409, "Ya existe")
        os.mkdir(target)
        self.send_json({"ok": True, "name": name})

    # -- files
    def serve_file(self, rel):
        p = safe(rel)
        if not p or not os.path.isfile(p):
            return self.fail(404, "Archivo no encontrado")
        size = os.path.getsize(p)
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", "").strip())
        partial = False
        if m and (m.group(1) or m.group(2)):
            s, e = m.groups()
            if s:
                start = int(s)
                end = min(int(e), size - 1) if e else size - 1
            else:
                start = max(0, size - int(e))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                return self.end_headers()
            partial = True
        length = end - start + 1
        self.send_response(206 if partial else 200)
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
        if ctype.startswith("text/"):
            ctype += "; charset=utf-8"
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if self.query().get("dl"):
            fname = os.path.basename(p)
            ascii_name = fname.encode("ascii", "replace").decode().replace('"', "")
            self.send_header("Content-Disposition",
                             f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{urllib.parse.quote(fname)}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(p, "rb") as f:
            f.seek(start)
            while length > 0:
                buf = f.read(min(CHUNK, length))
                if not buf:
                    break
                self.wfile.write(buf)
                length -= len(buf)

    def serve_zip(self, rel):
        d = safe(rel)
        if not d or not os.path.isdir(d):
            return self.fail(404, "Carpeta no encontrada")
        name = (os.path.basename(d) if d != ROOT else os.path.basename(ROOT)) or "archivos"
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition",
                         f"attachment; filename*=UTF-8''{urllib.parse.quote(name)}.zip")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        with zipfile.ZipFile(self.wfile, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
            for base, dirs, files in os.walk(d):
                dirs[:] = sorted(x for x in dirs if not x.startswith("."))
                for fn in sorted(files):
                    if fn.startswith("."):
                        continue
                    full = os.path.join(base, fn)
                    zf.write(full, os.path.join(name, os.path.relpath(full, d)))


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ips) or ["127.0.0.1"]


def main():
    global ROOT, READONLY
    ap = argparse.ArgumentParser(prog="wysun lanshare", description="Servidor de archivos para la red local")
    ap.add_argument("folder", nargs="?", default=".")
    ap.add_argument("-p", "--port", type=int, default=8000)
    ap.add_argument("--readonly", action="store_true", help="desactiva subidas y nuevas carpetas")
    args = ap.parse_args()
    ROOT = os.path.realpath(args.folder)
    READONLY = args.readonly
    os.makedirs(CACHE, exist_ok=True)
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    srv.daemon_threads = True
    print(f"Wysun LANShare · compartiendo {ROOT}")
    for ip in lan_ips():
        print(f"  → http://{ip}:{args.port}")
    print("  (Ctrl+C para detener)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
