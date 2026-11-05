"""wysun_core.tui.app: one selectors loop for input, timers, children, layers and frames."""
import fcntl
import os
import pty
import select
import shutil
import struct
import sys
import tempfile
import termios
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from wysun_core import theme  # noqa: E402
from wysun_core.tui import anim, keys  # noqa: E402
from wysun_core.tui.app import App, Layer  # noqa: E402
from wysun_core.tui.canvas import Style  # noqa: E402
from wysun_core.tui.terminal import Terminal  # noqa: E402
from wysun_core.tui.testing import VirtualTerminal  # noqa: E402

LIGHT_SCHEME = {'name': 'dynamic', 'flavour': 'tonalspot', 'mode': 'light',
                'variant': 'tonalspot', 'wallpaper_hash': 'a' * 64,
                'colours': {'surface': 'abcdef', 'onSurface': '111111',
                            'primary': '334455'}}
DARK_SCHEME = {'name': 'dynamic', 'flavour': 'tonalspot', 'mode': 'dark',
               'variant': 'tonalspot', 'wallpaper_hash': 'b' * 64,
               'colours': {'surface': '101010', 'onSurface': 'eeeeee',
                           'primary': 'aabbcc'}}


def python_executable():
    """A real Python, even when the suite runs inside a bundled interpreter."""
    if os.path.basename(sys.executable).startswith('python'):
        return sys.executable
    return shutil.which('python3') or sys.executable


def drain(fd, timeout=0.2):
    """Read everything a pty master has pending, without blocking for long."""
    chunks = []
    while True:
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            break
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    return b''.join(chunks)


class Recording(App):
    """An app that records events and paints a recognisable background."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key_events = []
        self.mouse_events = []
        self.paste_events = []
        self.resizes = []
        self.drawn = 0

    def on_key(self, event):
        self.key_events.append(event)

    def on_mouse(self, event):
        self.mouse_events.append(event)

    def on_paste(self, event):
        self.paste_events.append(event)

    def on_resize(self, width, height):
        self.resizes.append((width, height))

    def draw(self, canvas):
        self.drawn += 1
        canvas.text(0, 0, 'hola', Style(fg=self.palette['onSurface']))


class FillLayer(Layer):
    """A layer that fills its rectangle with one character."""

    def __init__(self, rect, char, **kwargs):
        super().__init__(rect, **kwargs)
        self.char = char

    def draw(self, canvas, palette):
        canvas.fill((0, 0, canvas.width, canvas.height), self.char,
                    Style(fg=palette['onSurface']))


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('WYSUN_THEME', None)
        os.environ.pop('WYSUN_REDUCED_MOTION', None)
        theme.invalidate()
        self.addCleanup(theme.invalidate)

    def make(self, width=80, height=24, cls=App):
        term = VirtualTerminal(width, height)
        self.addCleanup(term.close)
        app = cls(term=term, home=self.home)
        self.addCleanup(app.close)
        return app, term


class InputTests(AppTestCase):
    def test_key_reaches_on_key(self):
        app, term = self.make(cls=Recording)
        term.feed_input(b'\x1b[A')
        app.step()
        self.assertEqual(app.key_events, [keys.Key('up')])
        self.assertIn('hola', term.canvas_text()[0])

    def test_mouse_and_paste_reach_handlers(self):
        app, term = self.make(cls=Recording)
        term.feed_input(b'\x1b[<0;10;5M')
        app.step()
        term.feed_input(b'\x1b[200~hola\x1b[201~')
        app.step()
        self.assertEqual(app.mouse_events, [keys.Mouse('press', 0, 9, 4)])
        self.assertEqual(app.paste_events, [keys.Paste('hola')])

    def test_lone_escape_is_flushed_after_thirty_milliseconds(self):
        app, term = self.make(cls=Recording)
        term.feed_input(b'\x1b')
        app.step()
        self.assertEqual(app.key_events, [])
        app.run_for(0.1)
        self.assertEqual(app.key_events, [keys.Key('escape')])

    def test_ctrl_c_quits_by_default(self):
        app, term = self.make()
        term.feed_input(b'\x03')
        app.step()
        started = time.monotonic()
        app.run_for(0.5)
        self.assertLess(time.monotonic() - started, 0.2)


class TimerTests(AppTestCase):
    def test_after_and_every_fire_in_order(self):
        app, term = self.make()
        order = []
        cancelled = []
        app.after(0.07, lambda: order.append('late'))
        app.after(0.02, lambda: order.append('early'))
        app.every(0.05, lambda: order.append('tick'))
        app.after(0.12, app.quit)
        handle = app.after(0.01, lambda: cancelled.append(True))
        app.cancel(handle)
        app.run_for(1.0)
        self.assertEqual(order, ['early', 'tick', 'late', 'tick'])
        self.assertEqual(cancelled, [])

    def test_after_from_thread_wakes_loop(self):
        app, term = self.make()
        fired = []
        app.step()  # settle the first frame so the next step really blocks

        def worker():
            time.sleep(0.15)
            app.after(0, lambda: (fired.append(True), app.quit()))

        thread = threading.Thread(target=worker)
        thread.start()
        self.addCleanup(thread.join, 2.0)
        started = time.monotonic()
        app.step(1.0)
        elapsed = time.monotonic() - started
        self.assertEqual(fired, [True])
        self.assertLess(elapsed, 0.6)


class ChildTests(AppTestCase):
    def test_spawn_reads_lines_and_exit_code(self):
        app, term = self.make()
        lines, codes = [], []
        app.spawn([python_executable(), '-c', 'print("a"); print("b")'],
                  lines.append, lambda code: (codes.append(code), app.quit()))
        app.run_for(10.0)
        self.assertEqual(lines, ['a', 'b'])
        self.assertEqual(codes, [0])

    def test_spawn_stderr_tail_and_stdin(self):
        app, term = self.make()
        lines, errors, codes = [], [], []
        script = ('import sys\n'
                  'data = sys.stdin.read()\n'
                  'print("got", len(data))\n'
                  'for index in range(25):\n'
                  '    print("err%d" % index, file=sys.stderr)\n')
        child = app.spawn(
            [python_executable(), '-c', script], lines.append,
            lambda code: (codes.append(code), app.quit()),
            stdin=b'x' * 200000, on_err_line=errors.append)
        app.run_for(10.0)
        self.assertEqual(lines, ['got 200000'])
        self.assertEqual(errors, [f'err{index}' for index in range(25)])
        self.assertEqual(child.stderr_tail, [f'err{index}' for index in range(5, 25)])
        self.assertEqual(codes, [0])
        self.assertFalse(child.running)

    def test_kill_stops_a_child_and_delivers_exit(self):
        app, term = self.make()
        codes = []
        child = app.spawn([python_executable(), '-c', 'import time; time.sleep(30)'],
                          lambda line: None,
                          lambda code: (codes.append(code), app.quit()))
        app.step(0.05)
        self.assertTrue(child.running)
        child.kill()
        app.run_for(0.5)
        self.assertEqual(codes, [-15])
        self.assertFalse(child.running)


class FrameTests(AppTestCase):
    def test_layers_paint_in_z_order_with_opacity(self):
        app, term = self.make(cls=Recording)
        app.layers.append(FillLayer(anim.Rect(1, 1, 3, 2), 'A', z=0))
        app.layers.append(FillLayer(anim.Rect(2, 1, 3, 2), 'B', z=5, opacity=0.5))
        app.layers.append(FillLayer(anim.Rect(0, 3, 4, 1), 'C', visible=False))
        app.step()
        rows = term.canvas_text()
        self.assertEqual(rows[1][1:5], 'ABBB')
        self.assertEqual(rows[2][1:5], 'ABBB')
        self.assertNotIn('C', ''.join(rows))
        # Opacity blends the layer's foreground toward the main canvas background.
        on_surface = app.palette['onSurface']
        self.assertEqual(app._prev.cell(1, 1)[1].fg, on_surface)
        self.assertNotEqual(app._prev.cell(4, 1)[1].fg, on_surface)

    def test_tiny_terminal_message(self):
        app, term = self.make(40, 10, cls=Recording)
        app.layers.append(FillLayer(anim.Rect(0, 0, 40, 10), 'X'))
        app.step()
        rows = term.canvas_text()
        self.assertEqual(len(rows), 10)
        message = 'Agranda la terminal'
        row = next(line for line in rows if message in line)
        self.assertEqual(row.index(message), (40 - len(message)) // 2)
        self.assertEqual(app.drawn, 0)  # neither draw() nor the layers run
        self.assertNotIn('X', ''.join(rows))

    def test_resize_during_animation_snaps_and_redraws(self):
        app, term = self.make(cls=Recording)
        app.step()
        values = []
        app.animator.add(anim.Tween(1.0, lambda t: t, values.append))
        app.step(0.05)
        app.step(0.05)
        self.assertTrue(app.animator)
        term.resize(100, 30)
        app.step()
        self.assertFalse(app.animator)
        self.assertEqual(values[-1], 1.0)
        self.assertEqual(app.size, (100, 30))
        self.assertEqual(app.resizes, [(100, 30)])
        rows = term.canvas_text()
        self.assertEqual(len(rows), 30)
        self.assertTrue(rows[0].startswith('hola'))


class ThemeTests(AppTestCase):
    def test_theme_change_triggers_on_theme(self):
        theme.write_scheme(dict(LIGHT_SCHEME), self.home)
        app, term = self.make(cls=Recording)
        calls = []
        app.on_theme = lambda: calls.append(app.palette['primary'])
        app.step()
        self.assertEqual(app.palette['primary'], (0x33, 0x44, 0x55))
        theme.write_scheme(dict(DARK_SCHEME), self.home)
        app.run_for(1.8)
        self.assertEqual(calls, [(0xAA, 0xBB, 0xCC)])
        self.assertEqual(app.palette['primary'], (0xAA, 0xBB, 0xCC))
        self.assertIn('hola', term.canvas_text()[0])


class LifecycleTests(AppTestCase):
    def test_run_returns_zero_and_uses_the_terminal_context(self):
        class QuitAtStart(App):
            def on_start(self):
                self.quit()

        term = VirtualTerminal(80, 24)
        app = QuitAtStart(term=term, home=self.home)
        self.addCleanup(app.close)
        self.assertEqual(app.run(), 0)
        self.assertTrue(term.closed)

    def test_exception_in_handler_restores_terminal_and_reraises(self):
        master, slave = pty.openpty()
        self.addCleanup(self._close, master, slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
        original = termios.tcgetattr(slave)

        class Boom(App):
            def on_key(self, event):
                raise RuntimeError('boom')

        app = Boom(term=Terminal(slave, slave), home=self.home)
        self.addCleanup(app.close)
        timer = threading.Timer(0.05, self._type, args=(master,))
        timer.start()
        self.addCleanup(timer.cancel)
        with self.assertRaises(RuntimeError):
            app.run()
        self.assertEqual(termios.tcgetattr(slave), original)
        output = drain(master)
        self.assertIn(b'\x1b[?1049l', output)
        self.assertIn(b'\x1b[?25h', output)

    @staticmethod
    def _type(fd):
        try:
            os.write(fd, b'x')
        except OSError:
            pass

    @staticmethod
    def _close(*fds):
        for fd in fds:
            try:
                os.close(fd)
            except OSError:
                pass


if __name__ == '__main__':
    unittest.main()
