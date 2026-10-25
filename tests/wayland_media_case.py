"""Physical check of the media player on the live compositor (OpenGL path, hide/show, context loss, leaks).

    python3 tests/wayland_media_case.py [-v]

Opens small opaque windows with generated video on the running session, one at a time; run it serially and
never while recording. PySide6 modules that are not installed can be supplied with WYSUN_PYSIDE_EXTRA=<dir of
PySide6 *.so>, for trying python3-pyside6.qtopenglwidgets before installing it. Offscreen cannot do this:
QOpenGLWidget is unsupported on that platform, so the unit tests exercise the software surface instead.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
sys.path.insert(0, str(ROOT / 'tests'))
os.environ.pop('QT_QPA_PLATFORM', None)
if not os.environ.get('WAYLAND_DISPLAY'):
    raise SystemExit('wayland_media_case: no hay sesión Wayland activa')
os.environ['QT_QPA_PLATFORM'] = 'wayland'
os.environ.setdefault('ORBIT_REDUCED_MOTION', '1')
extra = os.environ.get('WYSUN_PYSIDE_EXTRA')
if extra:
    import PySide6
    PySide6.__path__.append(extra)

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402
import media_fixtures  # noqa: E402
import media_support as support  # noqa: E402
from wysun_media import mpv  # noqa: E402
from wysun_media.player import MediaPlayer  # noqa: E402
from wysun_media.video import GLVideoView, SoftwareVideoView, gl_available  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv[:1])
support._app = app
app.setStyle('Fusion')
import media_host  # noqa: E402
import theme_tokens  # noqa: E402
theme_tokens.apply_palette(app)
media_host.install()


def descriptors():
    return len(os.listdir('/proc/self/fd'))


def threads():
    return len(os.listdir('/proc/self/task'))


@unittest.skipUnless(gl_available(), 'falta python3-pyside6.qtopenglwidgets (o WYSUN_PYSIDE_EXTRA)')
class OpenGLCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix='wysun-wayland-media-'))
        pattern = cls.root / 'pattern.png'
        media_fixtures.pattern(640, 360).save(str(pattern))
        cls.clip = cls.root / 'marker.mp4'
        media_fixtures.ffmpeg('-loop', '1', '-i', str(pattern), '-f', 'lavfi', '-i', 'sine=frequency=330:duration=4', '-t', '4', '-r', '30',
                              '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-c:a', 'aac', '-shortest', str(cls.clip))
        cls.long = cls.root / 'long.mp4'
        media_fixtures.video(cls.long, 'libx264', seconds=10, extra=('-pix_fmt', 'yuv420p', '-g', '15'))

    def window(self, renderer='auto', size=(480, 300)):
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        player = MediaPlayer(mode='full', renderer=renderer, options={'ao': 'null'})
        layout.addWidget(player)
        holder.resize(*size)
        holder.show()
        self.addCleanup(self.close, holder, player)
        return holder, player

    def close(self, holder, player):
        player.shutdown()
        holder.close()
        holder.deleteLater()
        mpv.wait_closed()

    def play(self, player, path, **options):
        """Open and wait until the first picture is on screen (and, unless paused, the clock is running)."""
        player.open(path, **options)
        paused = options.get('paused')
        ready = lambda: player.session.state == ('paused' if paused else 'playing') and player.session.duration > 0 and (paused or player.session.position > .2)
        self.assertTrue(support.pump(ready, 10), player.session.state)

    def test_runs_on_native_wayland_with_opengl_and_hardware_or_software_decode(self):
        self.assertEqual(app.platformName(), 'wayland')
        _, player = self.window()
        self.assertEqual(player.renderer, 'opengl')
        self.assertIsInstance(player._ensure_video(), GLVideoView)
        self.play(player, self.clip)
        decoder = player.session.props.get('hwdec-current')
        print(f'  decodificador: {decoder or "software"} · renderizador: {player.renderer}')

    def test_first_frame_has_the_right_orientation_and_colours(self):
        _, player = self.window()
        self.play(player, self.clip, paused=True)
        support.settle(.4)
        frame = player._video.grabFramebuffer()
        width, height = frame.width(), frame.height()
        # The video is letterboxed; sample inside the picture, whose quadrants are red, green, blue, yellow.
        picture = [(.5, .5)]
        self.assertGreater(width, 100)
        quadrants = {(.35, .30): '#dd3333', (.65, .30): '#33dd33', (.35, .70): '#3333dd', (.65, .70): '#dddd33'}
        for (x, y), expected in quadrants.items():
            actual = frame.pixelColor(int(width * x), int(height * y))
            target = QColor(expected)
            distance = abs(actual.red() - target.red()) + abs(actual.green() - target.green()) + abs(actual.blue() - target.blue())
            self.assertLess(distance, 90, f'{(x, y)}: {actual.name()} vs {expected}')
        del picture

    def test_every_pixel_is_opaque(self):
        _, player = self.window()
        self.play(player, self.clip, paused=True)
        support.settle(.3)
        frame = player._video.grabFramebuffer()
        self.assertTrue(all(frame.pixelColor(x, y).alpha() == 255 for x in range(0, frame.width(), 41) for y in range(0, frame.height(), 33)))

    def test_seek_pause_and_resume(self):
        _, player = self.window()
        self.play(player, self.long)
        session = player.session
        session.seek(5.0)
        self.assertTrue(support.pump(lambda: abs(session.position - 5.0) < .6, 6))
        session.set_paused(True)
        self.assertTrue(support.pump(lambda: session.state == 'paused'))
        held = session.position
        support.settle(.6)
        self.assertAlmostEqual(session.position, held, delta=.05)
        session.set_paused(False)
        self.assertTrue(support.pump(lambda: session.position > held + .3, 6))

    def test_resize_hide_and_show_keep_playing_without_painting_while_hidden(self):
        holder, player = self.window()
        self.play(player, self.long)
        counted = []
        original = player._video.paintGL
        player._video.paintGL = lambda: (counted.append(1), original())[1]
        holder.resize(640, 400)
        support.settle(.3)
        self.assertGreater(len(counted), 3, 'a playing video repaints')
        holder.hide()
        support.settle(.3)
        counted.clear()
        support.settle(.8)
        self.assertEqual(len(counted), 0, 'a hidden video must not repaint')
        held = player.session.position
        holder.show()
        self.assertTrue(support.pump(lambda: player.session.position > held + .3, 6), 'playback continued while hidden')
        counted.clear()
        support.settle(.4)
        self.assertGreater(len(counted), 3, 'painting resumes when shown again')

    def test_paused_video_does_not_run_a_repaint_loop(self):
        _, player = self.window()
        self.play(player, self.long, paused=True)
        support.settle(.4)
        counted = []
        original = player._video.paintGL
        player._video.paintGL = lambda: (counted.append(1), original())[1]
        support.settle(1.0)
        self.assertLessEqual(len(counted), 2)

    def test_context_loss_keeps_position_and_paused_state(self):
        """Reparenting a GL widget to another window destroys its context; playback must carry on."""
        first, player = self.window()
        self.play(player, self.long)
        player.session.set_paused(True)
        support.pump(lambda: player.session.state == 'paused')
        position = player.session.position
        second = QWidget()
        second.resize(480, 300)
        layout = QVBoxLayout(second)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(player)
        second.show()
        self.second = second                       # the player now belongs to it: keep it alive until the test ends
        self.addCleanup(second.close)
        first.hide()
        support.settle(.8)
        self.assertEqual(player.session.state, 'paused')
        self.assertAlmostEqual(player.session.position, position, delta=.2)
        frame = player._video.grabFramebuffer()
        self.assertTrue(any(frame.pixelColor(x, y).lightness() > 30 for x in range(0, frame.width(), 20) for y in range(0, frame.height(), 20)),
                        'the frame is drawn again in the new context')
        player.session.set_paused(False)
        self.assertTrue(support.pump(lambda: player.session.position > position + .3, 6))

    def test_opengl_and_software_surfaces_show_the_same_picture(self):
        shots = {}
        for renderer in ('auto', 'software'):
            _, player = self.window(renderer)
            self.play(player, self.clip, paused=True)
            support.settle(.5)
            view = player._video
            shots[renderer] = view.grabFramebuffer() if isinstance(view, GLVideoView) else view.grab().toImage()
            self.assertIsInstance(view, GLVideoView if renderer == 'auto' else SoftwareVideoView)
        gl, sw = shots['auto'], shots['software']
        for x, y in ((.35, .3), (.65, .3), (.35, .7), (.65, .7)):
            a, b = gl.pixelColor(int(gl.width() * x), int(gl.height() * y)), sw.pixelColor(int(sw.width() * x), int(sw.height() * y))
            self.assertLess(abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()), 60)

    def test_repeated_open_and_close_leaves_no_descriptors_threads_or_children(self):
        support.settle(.3)
        before = (descriptors(), threads())
        for _ in range(100):
            holder = QWidget()
            layout = QVBoxLayout(holder)
            player = MediaPlayer(mode='full', options={'ao': 'null'})
            layout.addWidget(player)
            holder.resize(480, 300)
            holder.show()
            self.play(player, self.clip)
            player.shutdown()
            holder.close()
            holder.deleteLater()
            mpv.wait_closed()
            support.settle(.1)
        support.settle(.5)
        after = (descriptors(), threads())
        children = subprocess.run(['ps', '-o', 'pid=,args=', '--ppid', str(os.getpid())], capture_output=True, text=True).stdout.splitlines()
        children = [line for line in children if line.split(None, 2)[1:2] != ['ps']]       # the ps that is looking is not a leftover
        if support.bus is not None:
            # The shared test bus lives until process exit, independently of every player.
            children = [line for line in children if int(line.split()[0]) != support.bus.process.pid]
        self.assertLessEqual(after[0], before[0] + 3, f'descriptors {before[0]} -> {after[0]}')
        self.assertLessEqual(after[1], before[1] + 3, f'threads {before[1]} -> {after[1]}')
        self.assertEqual(children, [], 'no child process may outlive its player')


class SoftwareFallbackCase(unittest.TestCase):
    def test_forced_software_renderer_works_on_wayland(self):
        holder = QWidget()
        layout = QVBoxLayout(holder)
        player = MediaPlayer(mode='full', renderer='software', options={'ao': 'null'})
        layout.addWidget(player)
        holder.resize(480, 300)
        holder.show()
        clip = Path(tempfile.mkdtemp(prefix='wysun-wayland-media-')) / 'v.mp4'
        media_fixtures.video(clip, 'libx264', seconds=2, extra=('-pix_fmt', 'yuv420p'))
        try:
            player.open(clip)
            self.assertTrue(support.pump(lambda: player.session.position > .3, 10))
            self.assertEqual(player.renderer, 'software')
        finally:
            player.shutdown()
            holder.close()
            mpv.wait_closed()


if __name__ == '__main__':
    unittest.main()
