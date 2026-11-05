"""Media details for the page: ffprobe metadata, thumbnails and hover sprites (ffmpeg), cached
under ~/.cache/wysun/lanshare."""
from concurrent.futures import Future
import hashlib
import json
import os
import queue
import subprocess
import threading
import time

from wysun_core import paths
from wysun_core.jsonio import atomic_path
from wysun_core import h264
from wysun_lanshare.share import kind_of

def cache_dir():
    return str(paths.cache('wysun', 'lanshare'))
FAIL_TTL = 24 * 3600      # a failed thumbnail or copy is tried again after a day
SPRITE_FRAMES = 10
SPRITE_W, SPRITE_H = 320, 180


class Incomplete(Exception):
    """A thumbnail that did not finish; its temporary file is discarded."""


def failed_recently(mark):
    """True while a failure mark is younger than FAIL_TTL (an older one is forgotten)."""
    try:
        return time.time() - os.stat(mark).st_mtime < FAIL_TTL
    except OSError:
        return False


def _mark_failed(mark):
    try:
        with atomic_path(mark) as tmp:
            tmp.write_bytes(b"")
    except OSError:
        pass


def file_key(path, kind):
    st = os.stat(path)
    raw = f"{path}|{st.st_size}|{st.st_mtime_ns}|{kind}".encode()
    return hashlib.sha1(raw).hexdigest()


# ---------------------------------------------------------------- metadata --

_meta_mem = {}
_meta_lock = threading.Lock()


def cached_probe(path):
    """The metadata already known for path (memory or disk), or None without running ffprobe."""
    try:
        key = file_key(path, "meta2")
    except OSError:
        return {}
    with _meta_lock:
        if key in _meta_mem:
            return _meta_mem[key]
    disk = os.path.join(cache_dir(), "meta", key[:2], key + ".json")
    try:
        with open(disk) as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    with _meta_lock:
        _meta_mem[key] = meta
    return meta


def probe(path):
    known = cached_probe(path)
    if known is not None:
        return known
    try:
        key = file_key(path, "meta2")   # meta2: with the H.264 level and frame rate
    except OSError:
        return {}
    disk = os.path.join(cache_dir(), "meta", key[:2], key + ".json")
    meta = {}
    durable = True          # an answer from ffprobe; a missing or stuck ffprobe is asked again later
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
                if s.get("level") not in (None, -99):
                    meta["level"] = s.get("level")
                try:
                    num, den = (s.get("avg_frame_rate") or "0/1").split("/")
                    meta["fps"] = round(int(num) / int(den), 2) if int(den) else 0
                except ValueError:
                    pass
                meta["width"] = s.get("width")
                meta["height"] = s.get("height")
            elif s.get("codec_type") == "audio" and "acodec" not in meta:
                meta["acodec"] = s.get("codec_name")
    except ValueError:
        pass
    except (OSError, subprocess.SubprocessError):
        durable = False
    if durable:
        try:
            with atomic_path(disk) as tmp:
                tmp.write_text(json.dumps(meta))
        except OSError:
            pass
        with _meta_lock:
            _meta_mem[key] = meta
    return meta


class _Probes:
    """ffprobe on daemon threads (a stop never waits for them), one run per file however often it is asked."""

    def __init__(self, workers):
        self._queue = queue.Queue()
        self._pending = {}
        self._lock = threading.Lock()
        for _ in range(workers):
            threading.Thread(target=self._work, daemon=True).start()

    def submit(self, path):
        with self._lock:
            future = self._pending.get(path)
            if future is None:
                future = self._pending[path] = Future()
                self._queue.put((path, future))
            return future

    def _work(self):
        while True:
            path, future = self._queue.get()
            try:
                future.set_result(probe(path))
            except Exception as error:     # never lose a worker
                future.set_exception(error)
            finally:
                with self._lock:
                    self._pending.pop(path, None)


_probes = None
_probes_lock = threading.Lock()


def probe_soon(path):
    """A Future with path's metadata; ffprobe runs in the background when it is not known yet."""
    global _probes
    future = Future()
    known = cached_probe(path)
    if known is not None:
        future.set_result(known)
        return future
    with _probes_lock:
        if _probes is None:
            _probes = _Probes(8)
    return _probes.submit(path)


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
    if failed_recently(fail):
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
            except FileNotFoundError:
                return None             # no ffmpeg (yet): nothing to remember
            except (OSError, subprocess.SubprocessError, Incomplete):
                pass
        _mark_failed(fail)
        return None


COMPAT_LIMIT = 2 * 1024 ** 3     # phone copies kept at most; the least recently watched go first


def trim(folder, limit, keep=None):
    """Delete finished .mp4 copies under folder, oldest use (mtime) first, until it holds at most limit bytes.
    keep is never deleted. A copy being streamed survives deletion: the open file stays readable."""
    copies = []
    for base, _, names in os.walk(folder):
        for name in names:
            if name.startswith('.') or not name.endswith('.mp4'):
                continue
            full = os.path.join(base, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            copies.append((st.st_mtime, st.st_size, full))
    total = sum(size for _, size, _ in copies)
    for _, size, full in sorted(copies):
        if total <= limit:
            break
        if full == keep:
            continue
        try:
            os.unlink(full)
            total -= size
        except OSError:
            pass


def _used(out):
    try:
        os.utime(out)
    except OSError:
        pass
    trim(os.path.join(cache_dir(), "compat"), COMPAT_LIMIT, keep=out)
    return out


def playable(path):
    """A copy phones can play when the video only declares a level they refuse (Recorder files say 6.2): the same
    streams, without re-encoding, with the level it really needs; cached. The original path otherwise."""
    meta = probe(path)
    if not h264.too_high(meta):
        return path
    level = h264.level_for(meta.get("width") or 0, meta.get("height") or 0, meta.get("fps") or 60)
    if not level:
        return path
    try:
        key = file_key(path, "compat-" + level)
    except OSError:
        return path
    out = os.path.join(cache_dir(), "compat", key[:2], key + ".mp4")
    if os.path.exists(out):
        return _used(out)
    if failed_recently(out + ".fail"):
        return path
    with _key_guard:
        lock = _key_locks.setdefault(out, threading.Lock())
    with lock:
        if os.path.exists(out):
            return _used(out)
        try:
            with atomic_path(out) as tmp:
                cmd = FF + ["-i", path, "-map", "0", "-c", "copy", "-bsf:v", f"h264_metadata=level={level}",
                            "-movflags", "+faststart", str(tmp)]
                if subprocess.run(cmd, capture_output=True, timeout=1800).returncode != 0 or not tmp.exists():
                    raise Incomplete
            return _used(out)
        except FileNotFoundError:
            return path
        except (OSError, subprocess.SubprocessError, Incomplete):
            _mark_failed(out + ".fail")
            return path
