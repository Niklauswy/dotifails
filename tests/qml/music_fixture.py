"""A private, synthetic Wysun Music library for the QML checks (venv Python only).

``setup()`` points WYSUN_MUSIC_HOME / WYSUN_MUSIC_LIBRARY at a temporary folder under ~/.cache (once per
process: wysun_music.data reads them at import), puts an mpv wrapper with ``--ao=null`` first on PATH, renders
three short sine tones with ffmpeg and imports them. ``app()`` builds Wysun Music with the QML window.
"""
import atexit
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

TITLES = (('first', 'Synth', 440), ('second', 'Synth, Noise', 220), ('third', 'Other', 330))
_state = {}


def setup():
    if _state:
        return _state
    scratch = Path.home() / '.cache/wysun-fase1/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='music-', dir=scratch))
    atexit.register(shutil.rmtree, folder, True)
    os.environ.update(WYSUN_MUSIC_HOME=str(folder / 'state'), WYSUN_MUSIC_LIBRARY=str(folder / 'audio'))
    binary = folder / 'mpv'
    binary.write_text('#!/bin/sh\nexec /usr/bin/mpv --ao=null "$@"\n')
    binary.chmod(0o755)
    os.environ['PATH'] = str(folder) + os.pathsep + os.environ['PATH']
    files = []
    for title, artist, hz in TITLES:
        target = folder / f'{title}.ogg'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                        f'sine=frequency={hz}:duration=12', '-metadata', 'title=' + title, '-metadata',
                        'artist=' + artist, '-metadata', 'album=Tonos', str(target)], check=True)
        files.append(target)
    from wysun_music import data as music_data
    assert Path(music_data.DATA) == folder / 'state', 'wysun_music.data was imported before setup()'
    music_data.import_files(files)
    _state.update(folder=folder, files=files)
    return _state


def app():
    """The MusicApp (QML window, no persistence, network or MPRIS), built once per process."""
    if 'app' not in _state:
        setup()
        from wysun_music.app import build
        _state['app'] = build(test=True, ui='qml')
    return _state['app']


def keys_by_title():
    library = app().library
    return {library.track(k)['title']: k for k in library.all_keys()}
