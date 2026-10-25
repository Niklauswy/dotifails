"""Playback benchmark for the video surfaces, on the real compositor with synthetic media.

    python3 tests/media_benchmark.py [--seconds 3] [--size 960x540] [--video FILE] [opengl] [software]

The previous software surface (``mpv_embed.py``, removed with the Wysun Player) measured 216-240 % CPU, 98 ms to
the first frame and 185 MiB on the reference machine (Intel i7-8565U, 1080p60 H.264 in a 960x540 window): these
numbers are what the new surfaces are compared with. Every run reports codec, resolution, renderer, decoder,
versions and hardware next to the figures, and each surface runs in its own process, one after another, so they
cannot disturb each other. CPU is the whole process (mpv's decoder and audio threads included); audio goes to
``ao=null`` so the sound server is not measured. ``WYSUN_PYSIDE_EXTRA=<dir>`` supplies PySide6 modules that are
extracted from packages instead of installed (QtOpenGLWidgets, for trying the OpenGL surface before installing it).
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'apps/wysun'
SURFACES = ('opengl', 'software')


def hardware():
    model = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), '?')
    return {'cpu': model, 'cores': os.cpu_count(), 'kernel': platform.release()}


def rss_mib():
    return int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE') / 2 ** 20


def run_child(kind, seconds, size, video):
    """One measured run; prints a JSON line. Needs a Wayland or X session."""
    sys.path.insert(0, str(APP))
    extra = os.environ.get('WYSUN_PYSIDE_EXTRA')
    if extra:
        import PySide6
        PySide6.__path__.append(extra)
    from PySide6 import QtCore
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])
    import media_host
    from wysun_media import mpv
    from wysun_media.session import MediaSession
    from wysun_media.source import open_source
    from wysun_media.video import GLVideoView, SoftwareVideoView
    media_host.install()
    width, height = (int(v) for v in size.split('x'))
    result = {'surface': kind, 'video': Path(video).name, 'window': size, 'pyside6': QtCore.__version__, 'qt': QtCore.qVersion(),
              'platform': app.platformName(), **hardware()}
    started = time.monotonic()
    marks = {}
    session = MediaSession(options={'ao': 'null', 'hwdec': 'auto-copy' if kind == 'opengl' else 'no'})
    surface = (GLVideoView if kind == 'opengl' else SoftwareVideoView)()
    surface.resize(width, height)
    surface.ready.connect(lambda: session.set_surface_ready(True))
    surface.failed.connect(lambda reason: (print(json.dumps({'error': reason})), app.quit()))
    surface.attach(session)
    surface.show()
    session.positionChanged.connect(lambda _: marks.setdefault('first_frame', time.monotonic()))
    marks['load'] = time.monotonic()
    session.open(open_source(video), paused=False)
    measured = {}

    def begin():
        measured.update(cpu=time.process_time(), wall=time.monotonic())

    def end():
        cpu, wall = time.process_time() - measured['cpu'], time.monotonic() - measured['wall']
        props = session.props
        result.update({'cpu_percent': round(cpu / wall * 100, 1), 'seconds': round(wall, 2), 'rss_mib': round(rss_mib(), 1),
                       'first_frame_ms': round((marks.get('first_frame', started) - marks['load']) * 1000),
                       'start_ms': round((marks['load'] - started) * 1000), 'played_to': props.get('time-pos'),
                       'decoder': props.get('hwdec-current') or 'software', 'codec': props.get('video-codec'),
                       'dropped': (props.get('vo-drop-frame-count') or 0) + (props.get('decoder-frame-drop-count') or 0)})
        print(json.dumps(result), flush=True)
        surface.release()
        session.close()
        mpv.wait_closed()
        app.quit()
    QTimer.singleShot(1500, begin)                       # warm-up: window mapped, first frames decoded
    QTimer.singleShot(1500 + int(seconds * 1000), end)
    QTimer.singleShot(60000, app.quit)
    app.exec()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('surfaces', nargs='*', choices=SURFACES)
    parser.add_argument('--seconds', type=float, default=3.0)
    parser.add_argument('--size', default='960x540')
    parser.add_argument('--video', help='defaults to a generated 1080p60 H.264 clip')
    parser.add_argument('--child', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        run_child(args.child, args.seconds, args.size, args.video)
        return
    video = args.video
    directory = None
    if not video:
        sys.path.insert(0, str(ROOT / 'tests'))
        from PySide6.QtGui import QGuiApplication
        import media_fixtures
        QGuiApplication(sys.argv[:1] + ['-platform', 'offscreen'])
        directory = tempfile.TemporaryDirectory(prefix='wysun-bench-')
        media_fixtures.video(Path(directory.name) / 'p1080.mp4', 'libx264', size='1920x1080', rate=60, seconds=10,
                             extra=('-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-g', '60'))
        video = str(Path(directory.name) / 'p1080.mp4')
    rows = []
    for surface in args.surfaces or SURFACES:
        done = subprocess.run([sys.executable, '-P', __file__, '--child', surface, '--seconds', str(args.seconds), '--size', args.size,
                               '--video', video], capture_output=True, text=True, timeout=120)
        line = next((l for l in done.stdout.splitlines() if l.startswith('{')), None)
        if line is None or 'error' in json.loads(line):
            print(f'{surface}: sin resultado\n{(line or done.stderr)[-400:]}', file=sys.stderr)
            continue
        rows.append(json.loads(line))
    for row in rows:
        print(json.dumps(row))
    print(f"\n{'surface':10} {'CPU %':>7} {'RSS MiB':>8} {'1st frame ms':>13} {'dropped':>8}  decoder")
    for row in rows:
        print(f"{row['surface']:10} {row['cpu_percent']:>7} {row['rss_mib']:>8} {row['first_frame_ms']:>13} {row['dropped']:>8}  {row['decoder']}")
    if directory is not None:
        directory.cleanup()


if __name__ == '__main__':
    main()
