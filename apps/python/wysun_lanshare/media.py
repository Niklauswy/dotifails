"""Media details for the page: ffprobe metadata, thumbnails and hover sprites (ffmpeg), cached
under ~/.cache/wysun/lanshare."""
import hashlib
import json
import os
import subprocess
import threading

from wysun_core import paths
from wysun_core.jsonio import atomic_path
from wysun_lanshare.share import kind_of

def cache_dir():
    return str(paths.cache('wysun', 'lanshare'))
SPRITE_FRAMES = 10
SPRITE_W, SPRITE_H = 320, 180


class Incomplete(Exception):
    """A thumbnail that did not finish; its temporary file is discarded."""


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
    disk = os.path.join(cache_dir(), "meta", key[:2], key + ".json")
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
    try:
        with atomic_path(disk) as tmp:
            tmp.write_text(json.dumps(meta))
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
    out = os.path.join(cache_dir(), kind, key[:2], key + ".jpg")
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
        try:
            with atomic_path(fail) as tmp:
                tmp.write_bytes(b"")
        except OSError:
            pass
        return None
