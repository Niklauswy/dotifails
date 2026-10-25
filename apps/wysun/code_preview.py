#!/usr/bin/env python3
"""Code preview for the shell launcher: the first lines of a text file and their Neovim-coloured HTML.

Kept apart from launcher_data.py so a preview only pays for Python itself: results are cached by file,
modification time and Neovim theme, and a cached file is answered without importing Pygments.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import nvim_theme  # noqa: E402

# Bumped whenever the output format changes, so older cached answers are not reused.
VERSION = 4
MAX_BYTES = 12000
# About four screens of the preview pane; laying out more costs frames and is rarely scrolled to.
MAX_LINES = 120
CACHE = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'wysun/code-preview'
CACHE_KEEP = 300


def build(path):
    with open(path, 'rb') as handle:
        raw = handle.read(MAX_BYTES)
        if b'\0' in raw:
            return {}
        # The line count of the whole file for the preview's chip (first 4 MB; the answer is cached).
        count, last = raw.count(b'\n'), raw[-1:]
        for _ in range(256):
            chunk = handle.read(1 << 14)
            if not chunk:
                break
            count += chunk.count(b'\n')
            last = chunk[-1:]
    text = raw.decode('utf-8', errors='replace')
    lines = text.split('\n')
    if len(lines) > MAX_LINES:
        text = '\n'.join(lines[:MAX_LINES])
    result = {'text': text, 'lines': count + (1 if last and last != b'\n' else 0)}
    try:
        result.update(nvim_theme.render(path, MAX_LINES) or nvim_theme.highlight(path, text) or {})
    except Exception:  # a broken lexer or theme file must never blank the preview
        pass
    return result


def cache_file(path):
    st = os.stat(path)
    key = f'{VERSION}|{os.path.realpath(path)}|{st.st_mtime_ns}|{st.st_size}|{nvim_theme.stamp()}'
    return CACHE / (hashlib.sha1(key.encode()).hexdigest() + '.json')


def prune():
    entries = sorted(CACHE.glob('*.json'), key=lambda p: p.stat().st_mtime)
    for old in entries[:-CACHE_KEEP]:
        old.unlink(missing_ok=True)


def preview(path):
    """Cached answer when the file and the theme are unchanged; built (and stored) otherwise."""
    target = cache_file(path)
    try:
        cached = json.loads(target.read_text())
        target.touch()  # recently used entries survive pruning
        return cached
    except (OSError, ValueError):
        pass
    result = build(path)
    try:
        CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = target.with_name(f'{target.stem}.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(result, ensure_ascii=False))
        tmp.replace(target)
        if len(os.listdir(CACHE)) > CACHE_KEEP + 50:
            prune()
    except OSError:  # a read-only or full cache only costs the next preview its speed
        pass
    return result


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('usage: code_preview.py <file>', file=sys.stderr)
        sys.exit(2)
    try:
        print(json.dumps(preview(sys.argv[1]), ensure_ascii=False))
    except OSError:
        print('{}')
