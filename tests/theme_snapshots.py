#!/usr/bin/env python3
"""Render Wysun windows offscreen for theme before/after comparisons.

Usage:
  QT_QPA_PLATFORM=offscreen python3 tests/theme_snapshots.py OUT_DIR [--source apps/wysun] [--theme space-black:tokyo]
  python3 tests/theme_snapshots.py --compare BEFORE_DIR AFTER_DIR

Runs with a disposable HOME/XDG tree and synthetic data only. Clock, process and
battery figures are live, so small diffs in those regions are expected.
"""
import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(out, source, theme):
    home = Path(tempfile.mkdtemp(prefix='wysun-snap-'))
    for key, sub in (('XDG_CONFIG_HOME', '.config'), ('XDG_DATA_HOME', '.local/share'), ('XDG_STATE_HOME', '.local/state'),
                     ('XDG_CACHE_HOME', '.cache')):
        (home / sub).mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(home / sub)
    os.environ['HOME'] = str(home)
    os.environ['ORBIT_THEME'] = theme
    os.environ['WYSUN_THEME'] = theme
    os.environ['ORBIT_REDUCED_MOTION'] = '1'
    backgrounds = home / '.local/share/backgrounds'
    shutil.copytree(ROOT / 'assets/backgrounds', backgrounds)
    sys.path.insert(0, str(Path(source).resolve()))
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSize
    app = QApplication.instance() or QApplication(['snap'])
    app.setStyle('Fusion')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    def settle(ms=120):
        import time
        end = time.monotonic() + ms / 1000
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.005)

    def shot(name, widget, size=(1100, 720)):
        try:
            widget.resize(QSize(*size))
            widget.show()
            settle()
            widget.grab().save(str(out / (name + '.png')))
            print('ok', name)
        except Exception as error:
            print('fail', name, type(error).__name__, error)

    def attempt(name, factory, size=(1100, 720)):
        try:
            widget = factory()
        except Exception as error:
            print('fail', name, type(error).__name__, error)
            return None
        shot(name, widget, size)
        return widget

    import orbit
    try:
        orbit.apply_style(app, orbit.STYLE)
    except Exception as error:
        print('fail app-style', error)
    from desktop_v3 import OrbitV3
    launcher = OrbitV3(test=True)
    for mode in ('home', 'emoji', 'snippets', 'clipboard'):
        try:
            launcher.show_mode(mode)
            settle(200)
            launcher.grab().save(str(out / ('launcher-' + mode + '.png')))
            print('ok launcher', mode)
        except Exception as error:
            print('fail launcher', mode, error)
    launcher.hide()
    from utilities import NotesWindow, ColorWindow
    attempt('notes', lambda: NotesWindow(str(home / 'notes')))
    attempt('colors', lambda: ColorWindow(home / 'colors.json'))
    from power_window import PowerWindow
    attempt('power', lambda: PowerWindow(launcher))
    from tools_window import ToolsWindow
    attempt('tools', lambda: ToolsWindow(test=True))
    from music_app_window import MusicAppWindow
    attempt('music', lambda: MusicAppWindow(test=True))
    (home / 'Documentos').mkdir()
    (home / 'Documentos/nota.txt').write_text('hola')
    from files_window import FilesWindow
    attempt('files', lambda: FilesWindow([str(home / 'Documentos')]))
    from clipboard_window import ClipboardWindow
    attempt('clipboard', lambda: ClipboardWindow(launcher, test=True))
    settle(100)


def compare(before, after):
    from PySide6.QtGui import QImage, QGuiApplication
    QGuiApplication.instance() or QGuiApplication(['compare'])
    for path in sorted(Path(before).glob('*.png')):
        other = Path(after) / path.name
        if not other.exists():
            print(f'{path.stem:28} missing after')
            continue
        a, b = QImage(str(path)), QImage(str(other))
        if a.size() != b.size():
            print(f'{path.stem:28} size {a.size().toTuple()} -> {b.size().toTuple()}')
            continue
        total = a.width() * a.height()
        changed = 0
        worst = 0
        for y in range(0, a.height()):
            for x in range(0, a.width(), 1):
                p, q = a.pixel(x, y), b.pixel(x, y)
                if p != q:
                    delta = max(abs(((p >> s) & 255) - ((q >> s) & 255)) for s in (0, 8, 16, 24))
                    worst = max(worst, delta)
                    if delta > 2:
                        changed += 1
        print(f'{path.stem:28} {100 * changed / total:6.2f}% px >2 levels, max delta {worst}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('out', nargs='?')
    parser.add_argument('--source', default=str(ROOT / 'apps/wysun'))
    parser.add_argument('--theme', default='space-black')
    parser.add_argument('--compare', nargs=2)
    args = parser.parse_args()
    if args.compare:
        compare(*args.compare)
    else:
        render(args.out, args.source, args.theme)
