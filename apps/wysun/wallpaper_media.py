"""Animated-wallpaper media helpers: detection, cached thumbnails and scheme frames.

Original Wysun code. The design (video/GIF wallpapers, thumbnails cached by file
identity, a representative frame feeding the Material You scheme) follows the
description in AdiAmbassador/caelestia-aw; no code was copied from it.

Everything generated lives under $XDG_CACHE_HOME/wysun/wallpapers, never in the repo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ANIMATED_EXTENSIONS = ('.mp4', '.webm', '.mkv', '.mov', '.gif')
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.avif', '.jxl', '.tif', '.tiff')
THUMB_SIZE = (480, 800)  # cards are tall; thumbnails are pre-cropped to the same 3:5 shape
FRAME_LONG_EDGE = 512


def is_animated(path):
    return Path(path).suffix.lower() in ANIMATED_EXTENSIONS


def is_wallpaper(path):
    return Path(path).suffix.lower() in ANIMATED_EXTENSIONS + IMAGE_EXTENSIONS


def cache_dir(home=None):
    base = os.environ.get('XDG_CACHE_HOME') or str(Path(home or Path.home()) / '.cache')
    return Path(base) / 'wysun' / 'wallpapers'


def identity(path):
    """Cheap, change-sensitive identity: path + size + mtime (not a content hash)."""
    path = Path(path)
    stat = path.stat()
    return hashlib.sha256(f'{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()[:24]


def content_hash(path):
    """Content identity for scheme caching; large videos only hash head, tail and size."""
    path = Path(path)
    digest = hashlib.sha256()
    size = path.stat().st_size
    with path.open('rb') as stream:
        if not is_animated(path) or size <= 8 * 1024 * 1024:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        else:
            digest.update(stream.read(4 * 1024 * 1024))
            stream.seek(-4 * 1024 * 1024, os.SEEK_END)
            digest.update(stream.read())
            digest.update(str(size).encode())
    return digest.hexdigest()


def _ffmpeg():
    return shutil.which('ffmpeg')


def duration(path):
    ffprobe = shutil.which('ffprobe')
    if not ffprobe:
        return 0.0
    try:
        result = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of',
                                 'default=nw=1:nk=1', str(path)], capture_output=True, text=True, timeout=15, check=False)
        return max(0.0, float(result.stdout.strip()))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0.0


def validate_animated(path):
    """Raise ValueError unless ffprobe can find a video stream in the file."""
    ffprobe = shutil.which('ffprobe')
    if not ffprobe:
        raise ValueError('ffprobe is needed to use video wallpapers.')
    try:
        result = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name',
                                 '-of', 'default=nw=1:nk=1', str(path)], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('The wallpaper video could not be read.') from error
    if not result.stdout.strip():
        raise ValueError('The wallpaper video could not be read.')


def _extract(path, target, vf, seek):
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        raise ValueError('ffmpeg is needed to use video wallpapers.')
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part' + target.suffix)
    for at in (seek, 0.0):
        command = [ffmpeg, '-v', 'error', '-y', '-ss', f'{at:.2f}', '-i', str(path), '-frames:v', '1', '-vf', vf, str(partial)]
        try:
            subprocess.run(command, capture_output=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if partial.is_file() and partial.stat().st_size:
            partial.replace(target)
            return target
    partial.unlink(missing_ok=True)
    raise ValueError('No frame could be extracted from ' + Path(path).name)


def _seek(path):
    return duration(path) * 0.25


def scheme_frame(path, home=None):
    """A representative still for Material You. Images are returned unchanged."""
    if not is_animated(path):
        return Path(path)
    target = cache_dir(home) / 'frames' / (identity(path) + '.png')
    if target.is_file():
        return target
    scale = f"scale='if(gt(iw,ih),{FRAME_LONG_EDGE},-2)':'if(gt(iw,ih),-2,{FRAME_LONG_EDGE})'"
    return _extract(path, target, scale, _seek(path))


def thumbnail(path, home=None):
    """Cached card thumbnail (JPEG, THUMB_SIZE cover crop); generated on first use."""
    path = Path(path)
    target = cache_dir(home) / 'thumbs' / (identity(path) + '.jpg')
    if target.is_file():
        return target
    width, height = THUMB_SIZE
    if is_animated(path):
        vf = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}'
        return _extract(path, target, vf, _seek(path))
    from PIL import Image, ImageOps
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(path) as source:
        source.draft('RGB', (width * 2, height * 2))
        image = ImageOps.fit(source.convert('RGB'), THUMB_SIZE, Image.Resampling.LANCZOS)
    partial = target.with_name(target.name + '.part.jpg')
    image.save(partial, 'JPEG', quality=85)
    partial.replace(target)
    return target


def cached_thumbnail(path, home=None):
    try:
        target = cache_dir(home) / 'thumbs' / (identity(path) + '.jpg')
    except OSError:
        return None
    return target if target.is_file() else None


def scan(directories, limit=5000):
    """Wallpaper files below the directories, sorted by name; each entry carries a cached thumbnail if any."""
    seen, entries = set(), []
    for directory in directories:
        root = Path(directory).expanduser()
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(name for name in dirnames if not name.startswith('.'))
            for name in sorted(filenames):
                full = Path(dirpath) / name
                if name.startswith('.') or not is_wallpaper(full):
                    continue
                key = str(full.resolve())
                if key in seen:
                    continue
                seen.add(key)
                cached = cached_thumbnail(full)
                entries.append({'path': str(full), 'name': full.stem, 'animated': is_animated(full),
                                'thumb': str(cached) if cached else ''})
                if len(entries) >= limit:
                    return entries
    entries.sort(key=lambda entry: entry['name'].casefold())
    return entries


def serve(stream_in, stream_out, home=None):
    """Thumbnail worker: one path per line in, 'path<TAB>thumb' (empty thumb on failure) per line out."""
    for line in stream_in:
        path = line.rstrip('\n')
        if not path:
            continue
        try:
            result = str(thumbnail(path, home))
        except (OSError, ValueError, RuntimeError):
            result = ''
        except Exception:  # a hostile file must not kill the worker
            result = ''
        stream_out.write(f'{path}\t{result}\n')
        stream_out.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(prog='wallpaper_media', description='Wysun wallpaper media helper')
    sub = parser.add_subparsers(dest='action', required=True)
    listing = sub.add_parser('list', help='print wallpapers below the directories as JSON')
    listing.add_argument('directories', nargs='*')
    sub.add_parser('serve', help='thumbnail worker reading paths from stdin')
    frame = sub.add_parser('frame', help='print the still used for the colour scheme')
    frame.add_argument('path')
    args = parser.parse_args(argv)
    if args.action == 'list':
        json.dump(scan(args.directories), sys.stdout)
        sys.stdout.write('\n')
    elif args.action == 'serve':
        serve(sys.stdin, sys.stdout)
    else:
        print(scheme_frame(args.path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
