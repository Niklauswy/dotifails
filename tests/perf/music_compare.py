"""Wysun Music, Widgets vs QML, in the real session: start-up until the window is mapped, and RSS/PSS idle.

    python3 tests/perf/music_compare.py [--tracks 3000] [--runs 3]

A private library (WYSUN_MUSIC_HOME), runtime dir (its own single instance, so the user's running Music is never
reached) and music folder under ~/.cache; three synthetic tones back every entry. Each window is closed by
killing only the process this script started. Prints JSON.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def library(folder, count):
    audio = folder / 'audio'
    audio.mkdir(parents=True)
    files = []
    for hz in (220, 330, 440):
        target = audio / f'tone-{hz}.ogg'
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', f'sine=frequency={hz}:duration=5',
                        str(target)], check=True)
        files.append(str(target))
    tracks = {}
    collections = {}
    for i in range(count):
        key = f'local-perf{i:05d}'
        tracks[key] = {'title': f'Canción {i}', 'artist': f'Artista {i % 150}', 'album': f'Álbum {i % 300}',
                       'duration': 5, 'status': 'ready', 'path': files[i % 3]}
    for a in range(300):
        collections[f'album-{a}'] = {'title': f'Álbum {a}', 'source': 'https://open.spotify.com/album/x',
                                     'tracks': [f'local-perf{i:05d}' for i in range(a, count, 300)]}
    state = folder / 'state'
    state.mkdir()
    (state / 'library.json').write_text(json.dumps({'version': 1, 'tracks': tracks, 'collections': collections}))


def mapped(pid):
    clients = json.loads(subprocess.run(['hyprctl', 'clients', '-j'], capture_output=True, text=True).stdout)
    return any(c.get('pid') == pid for c in clients)


def memory(pid):
    values = {}
    try:
        for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
            key, _, rest = line.partition(':')
            if key in ('Rss', 'Pss'):
                values[key.lower() + '_mb'] = round(int(rest.split()[0]) / 1024, 1)
    except OSError:
        pass
    return values


def run(ui, folder):
    env = dict(os.environ, WYSUN_MUSIC_UI=ui, WYSUN_MUSIC_HOME=str(folder / 'state'),
               WYSUN_MUSIC_LIBRARY=str(folder / 'audio'), XDG_RUNTIME_DIR=str(folder / 'run'),
               WYSUN_QML_LIB=str(ROOT / 'apps/qml'), PYTHONPATH=str(ROOT / 'apps/python'))
    env.pop('QT_QPA_PLATFORM', None)
    (folder / 'run').mkdir(exist_ok=True, mode=0o700)
    start = time.monotonic()
    process = subprocess.Popen([sys.executable, '-P', '-m', 'wysun_music'], env=env, cwd=ROOT,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    # The QML UI re-executes itself in the qml-runtime venv: the pid stays the same (execve).
    while not mapped(process.pid):
        if time.monotonic() - start > 30 or process.poll() is not None:
            process.kill()
            return {'error': 'no window'}
        time.sleep(0.01)
    shown = time.monotonic() - start
    time.sleep(3)
    result = {'window_s': round(shown, 3), **memory(process.pid)}
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
    time.sleep(0.5)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tracks', type=int, default=3000)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--ui', default='widgets,qml')
    args = parser.parse_args()
    scratch = Path.home() / '.cache/wysun-fase1/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='music-perf-', dir=scratch))
    try:
        library(folder, args.tracks)
        results = {ui: [run(ui, folder) for _ in range(args.runs)] for ui in args.ui.split(',')}
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    print(json.dumps({'tracks': args.tracks, **results}, indent=1))


if __name__ == '__main__':
    main()
