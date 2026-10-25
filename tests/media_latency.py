"""Latency of Wysun Player on the real compositor: cold start, a second window, seeks and image navigation.

    python3 tests/media_latency.py [--seeks 30] [--samples 20]

Targets (see docs/multimedia-architecture-plan.md §8): a window with its first picture or frame in under 1 s from a cold
start and under 300 ms when the process is already running; seeks under 300 ms at p95; an already-decoded neighbour image
in under 50 ms. Synthetic media only. ``WYSUN_PYSIDE_EXTRA`` supplies uninstalled PySide6 OpenGL modules.
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

T0 = time.monotonic()
IMPORTED = [T0]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
sys.path.insert(0, str(ROOT / 'tests'))
os.environ.setdefault('WYSUN_MPV_OPTIONS', 'ao=null')


def percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * share))]


def run(seeks, samples):
    extra = os.environ.get('WYSUN_PYSIDE_EXTRA')
    if extra:
        import PySide6
        PySide6.__path__.append(extra)
    import media_fixtures
    import media_support  # private D-Bus, fixed before the first player connects
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])
    import media_host
    import player_window
    media_host.install()
    IMPORTED[0] = time.monotonic()
    directory = Path(tempfile.mkdtemp(prefix='wysun-latency-'))
    big = directory / 'p1080.mp4'
    media_fixtures.video(big, 'libx264', size='1920x1080', rate=60, seconds=20, extra=('-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-g', '60'))
    for name in ('a', 'b', 'c'):
        media_fixtures.pattern(1600, 1200).save(str(directory / f'{name}.jpg'), 'JPEG', 90)
    from PySide6.QtCore import QCoreApplication, QEvent
    import time as clock

    def pump(predicate, timeout=10):
        end = clock.monotonic() + timeout
        while clock.monotonic() < end:
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            if predicate():
                return clock.monotonic()
            clock.sleep(.001)
        raise TimeoutError

    results = {'hardware': next(l.split(':', 1)[1].strip() for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name'))}
    # Observe completed paint calls, not metadata (which can precede the first frame).
    from wysun_media.image import ImageView, jobs
    from wysun_media.video import GLVideoView
    from wysun_media.source import open_source
    from wysun_media import mpv
    image_paints, video_paints = {}, {}
    original_image_paint = ImageView.paintEvent
    def image_paint(view, event):
        original_image_paint(view, event)
        if view.frame is not None:
            image_paints.setdefault(view.frame.fingerprint, clock.monotonic())
    ImageView.paintEvent = image_paint
    if GLVideoView is not None:
        original_gl_paint = GLVideoView.paintGL
        def gl_paint(view):
            updates = original_gl_paint(view)
            if updates and updates & mpv.RENDER_UPDATE_FRAME and view.session.props.get('video-params'):
                video_paints.setdefault(id(view), clock.monotonic())
        GLVideoView.paintGL = gl_paint
    process_started = clock.monotonic()
    process = player_window.Process(app.quit)
    results['process_setup_ms'] = round((clock.monotonic() - process_started) * 1000, 1)
    results['measurement'] = 'completed Qt paint; excludes compositor scanout'
    # Cold start: interpreter and imports are already behind us here; report them with the first window.
    started = clock.monotonic()
    window = process.show({'files': [str(directory / 'a.jpg')]})
    window.player.collection.set_explicit([directory / 'a.jpg', directory / 'b.jpg', directory / 'c.jpg'])
    first = open_source(directory / 'a.jpg').fingerprint
    pump(lambda: first in image_paints)
    results['first_image_ms'] = round((image_paints[first] - started) * 1000, 1)
    results['cold_imports_ms'] = round((IMPORTED[0] - T0) * 1000)
    results['cold_image_total_ms'] = round(results['cold_imports_ms'] + results['process_setup_ms'] + results['first_image_ms'], 1)
    navigation = []
    for index in range(samples):
        step = 1 if index % 2 == 0 else -1
        target = open_source(directory / ('b.jpg' if step == 1 else 'a.jpg'))
        # A sleep does not process Qt's resize/collection events. Require an actual
        # cache hit at the current viewport before calling this a preloaded image.
        window.player._images.prefetch([target])
        pump(lambda: jobs().lookup(target, window.player._images._want()) is not None)
        image_paints.pop(target.fingerprint, None)
        start = clock.monotonic()
        window.player.step_collection(step)
        pump(lambda: target.fingerprint in image_paints)
        navigation.append((image_paints[target.fingerprint] - start) * 1000)
    results.update(next_image_ms=[round(v, 1) for v in navigation], next_image_p95_ms=round(percentile(navigation, .95), 1))
    start = clock.monotonic()
    second = process.show({'files': [str(directory / 'c.jpg')]})
    fingerprint = open_source(directory / 'c.jpg').fingerprint
    pump(lambda: fingerprint in image_paints)
    results['second_window_image_ms'] = round((image_paints[fingerprint] - start) * 1000, 1)
    # First video frame and seeks.
    if os.environ.get('WYSUN_STALL_LOG'):         # a stalled interface thread shows up as repeated stack dumps
        import faulthandler
        faulthandler.dump_traceback_later(5, repeat=True, file=open(os.environ['WYSUN_STALL_LOG'], 'a'))
    openings = []
    for index in range(samples):
        start = clock.monotonic()
        video = process.show({'files': [str(big)], 'paused': True})
        if video.player.renderer != 'opengl':
            raise RuntimeError('This visible-frame benchmark requires OpenGL')
        view_id = id(video.player._video)
        pump(lambda: view_id in video_paints)
        openings.append((video_paints.pop(view_id) - start) * 1000)
        if index < samples - 1:
            video.close()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            mpv.wait_closed()
    results.update(first_video_frame_ms=[round(v, 1) for v in openings], video_open_p95_ms=round(percentile(openings, .95), 1))
    results['renderer'] = video.player.renderer
    session = video.player.session
    pump(lambda: session.duration > 15)
    times, targets = [], [(i * 7.3) % 18 + .5 for i in range(seeks)]
    for target in targets:
        start = clock.monotonic()
        session.seek(target)
        pump(lambda: abs(session.position - target) < .1 and not session.seeking, 5)
        times.append((clock.monotonic() - start) * 1000)
    results.update(seek_p50_ms=round(statistics.median(times)), seek_p95_ms=round(percentile(times, .95)), seeks=len(times))
    process.shutdown()
    for w in list(process.windows):
        w.close()
    print(json.dumps(results, indent=1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seeks', type=int, default=30)
    parser.add_argument('--samples', type=int, default=20)
    args = parser.parse_args()
    if args.seeks < 1 or args.samples < 1:
        parser.error('seeks and samples must be positive')
    display = os.environ.get('WAYLAND_DISPLAY')
    if not display:
        parser.error('an active Wayland session is required')
    display = str(Path(os.environ['XDG_RUNTIME_DIR']) / display) if not display.startswith('/') else display
    with tempfile.TemporaryDirectory(prefix='wysun-latency-home-') as home:
        os.environ.update(HOME=home, WAYLAND_DISPLAY=display, QT_QPA_PLATFORM='wayland')
        for key, name in [('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'), ('XDG_CACHE_HOME', 'cache'),
                          ('XDG_STATE_HOME', 'state'), ('XDG_RUNTIME_DIR', 'runtime')]:
            folder = Path(home) / name
            folder.mkdir(mode=0o700)
            os.environ[key] = str(folder)
        run(args.seeks, args.samples)
