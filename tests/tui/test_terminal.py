"""Raw terminal handling with guaranteed restore, and the in-memory terminal."""
import fcntl
import os
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from wysun_core.tui.canvas import Canvas, Style  # noqa: E402
from wysun_core.tui.screen import Screen  # noqa: E402
from wysun_core.tui.terminal import Terminal  # noqa: E402
from wysun_core.tui.testing import VirtualTerminal  # noqa: E402

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


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


class PtyTestCase(unittest.TestCase):
    def setUp(self):
        self.master, self.slave = pty.openpty()
        self.addCleanup(self._close)

    def _close(self):
        for fd in (self.master, self.slave):
            try:
                os.close(fd)
            except OSError:
                pass


class TerminalTests(PtyTestCase):
    def test_enters_raw_mode_and_writes_sequences(self):
        with Terminal(self.slave, self.slave) as term:
            inside = termios.tcgetattr(self.slave)
            self.assertFalse(inside[3] & termios.ICANON)
            self.assertFalse(inside[3] & termios.ECHO)
            written = drain(self.master)
            self.assertIn(b'\x1b[?1049h', written)
            self.assertIn(b'\x1b[?25l', written)
            self.assertIn(b'\x1b[?1000;1002;1006h', written)
            self.assertIn(b'\x1b[?2004h', written)

    def test_restores_on_exception(self):
        original = termios.tcgetattr(self.slave)
        with self.assertRaises(RuntimeError):
            with Terminal(self.slave, self.slave):
                raise RuntimeError('boom')
        self.assertEqual(termios.tcgetattr(self.slave), original)
        output = drain(self.master)
        self.assertIn(b'\x1b[?1049l', output)
        self.assertIn(b'\x1b[?25h', output)
        self.assertIn(b'\x1b[?1006l', output)
        self.assertIn(b'\x1b[?2004l', output)

    def test_restores_on_keyboard_interrupt(self):
        original = termios.tcgetattr(self.slave)
        with self.assertRaises(KeyboardInterrupt):
            with Terminal(self.slave, self.slave):
                raise KeyboardInterrupt
        self.assertEqual(termios.tcgetattr(self.slave), original)
        self.assertIn(b'\x1b[?1049l', drain(self.master))

    def test_sigterm_restores_and_exits_with_143(self):
        script = (
            'import os, signal\n'
            'from wysun_core.tui.terminal import Terminal\n'
            'with Terminal(0, 1):\n'
            '    os.kill(os.getpid(), signal.SIGTERM)\n'
            'raise SystemExit(0)\n'
        )
        environment = dict(os.environ)
        environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'apps/python')
        completed = subprocess.run(
            [python_executable(), '-c', script],
            stdin=self.slave, stdout=self.slave, stderr=subprocess.PIPE,
            env=environment, timeout=30,
        )
        self.assertEqual(completed.returncode, 143, completed.stderr.decode(errors='replace'))
        output = drain(self.master)
        self.assertIn(b'\x1b[?1049h', output)
        self.assertIn(b'\x1b[?1049l', output)
        self.assertIn(b'\x1b[?25h', output)

    def test_restore_is_idempotent(self):
        terminal = Terminal(self.slave, self.slave)
        with terminal:
            pass
        drain(self.master)
        terminal.restore()
        self.assertEqual(drain(self.master), b'')

    def test_size_comes_from_the_terminal(self):
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 100, 0, 0))
        with Terminal(self.slave, self.slave) as term:
            self.assertEqual(term.size(), (100, 40))

    def test_read_returns_data_and_empty_on_timeout(self):
        with Terminal(self.slave, self.slave) as term:
            self.assertEqual(term.read(0.02), b'')
            os.write(self.master, b'hi')
            self.assertEqual(term.read(1.0), b'hi')

    def test_write_reaches_the_other_side(self):
        with Terminal(self.slave, self.slave) as term:
            drain(self.master)
            term.write('ñ'.encode())
            self.assertEqual(drain(self.master), 'ñ'.encode())

    def test_sigwinch_calls_the_resize_listener_and_is_restored(self):
        if not hasattr(signal, 'SIGWINCH'):
            self.skipTest('no SIGWINCH on this platform')
        before = signal.getsignal(signal.SIGWINCH)
        calls = []
        with Terminal(self.slave, self.slave) as term:
            term.resize_listener = lambda: calls.append(1)
            self.assertIsNot(signal.getsignal(signal.SIGWINCH), before)
            signal.raise_signal(signal.SIGWINCH)
        self.assertEqual(calls, [1])
        self.assertEqual(signal.getsignal(signal.SIGWINCH), before)

    def test_sigterm_handler_is_installed_and_restored(self):
        before = signal.getsignal(signal.SIGTERM)
        with Terminal(self.slave, self.slave):
            inside = signal.getsignal(signal.SIGTERM)
            self.assertIsNot(inside, before)
            self.assertIsNot(inside, signal.SIG_DFL)
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)

    def test_non_tty_descriptors_are_supported(self):
        read_fd, write_fd = os.pipe()
        try:
            with Terminal(read_fd, write_fd) as term:
                self.assertTrue(drain(read_fd).startswith(b'\x1b[?1049h'))
                term.write(b'hola')
                self.assertEqual(len(term.size()), 2)
            self.assertEqual(
                drain(read_fd),
                b'hola\x1b[?2004l\x1b[?1006l\x1b[?1002l\x1b[?1000l\x1b[?25h\x1b[?1049l',
            )
        finally:
            os.close(read_fd)
            os.close(write_fd)


class VirtualTerminalTests(unittest.TestCase):
    def test_size_fileno_and_close(self):
        term = VirtualTerminal(20, 5)
        try:
            self.assertEqual(term.size(), (20, 5))
            self.assertIsInstance(term.fileno(), int)
            self.assertGreaterEqual(term.fileno(), 0)
        finally:
            term.close()
            term.close()

    def test_feed_input_is_readable_once(self):
        term = VirtualTerminal(10, 2)
        try:
            self.assertEqual(term.read(0.01), b'')
            term.feed_input(b'\x1b[A')
            self.assertEqual(term.read(1.0), b'\x1b[A')
            self.assertEqual(term.read(0.01), b'')
        finally:
            term.close()

    def test_resize_resets_the_grid_and_notifies(self):
        term = VirtualTerminal(4, 2)
        calls = []
        try:
            term.resize_listener = lambda: calls.append(term.size())
            term.write(b'\x1b[1;1HAB')
            self.assertEqual(term.canvas_text(), ['AB  ', '    '])
            term.resize(2, 3)
            self.assertEqual(calls, [(2, 3)])
            self.assertEqual(term.canvas_text(), ['  ', '  ', '  '])
        finally:
            term.close()

    def test_output_keeps_every_byte(self):
        term = VirtualTerminal(4, 2)
        try:
            term.write(b'abc')
            term.write(b'\x1b[1;1H')
            self.assertEqual(bytes(term.output), b'abc\x1b[1;1H')
        finally:
            term.close()

    def test_ignores_sgr_and_private_modes(self):
        term = VirtualTerminal(6, 1)
        try:
            term.write(b'\x1b[?2026h\x1b[38;2;1;2;3mhi\x1b[0m\x1b[?2026l')
            self.assertEqual(term.canvas_text(), ['hi    '])
        finally:
            term.close()

    def test_clears_on_2j(self):
        term = VirtualTerminal(4, 2)
        try:
            term.write(b'\x1b[1;1HAB\x1b[2;2HCD')
            self.assertEqual(term.canvas_text(), ['AB  ', ' CD '])
            term.write(b'\x1b[2J')
            self.assertEqual(term.canvas_text(), ['    ', '    '])
        finally:
            term.close()

    def test_canvas_roundtrip_full_and_diff(self):
        term = VirtualTerminal(20, 3)
        screen = Screen()
        try:
            first = Canvas(20, 3, BLACK)
            first.text(0, 0, 'hola', Style(fg=WHITE))
            first.text(0, 1, 'mundo', Style(fg=WHITE))
            first.fill((0, 2, 20, 1), '─', Style(fg=WHITE))
            term.write(screen.render(None, first))
            self.assertEqual(term.canvas_text(), [first.row_text(y) for y in range(3)])

            second = Canvas(20, 3, BLACK)
            second.text(0, 0, 'hola', Style(fg=WHITE))
            second.text(0, 1, 'mundo', Style(fg=WHITE))
            second.fill((0, 2, 20, 1), '─', Style(fg=WHITE))
            second.put(5, 1, 'X', Style(fg=WHITE, bold=True))
            second.text(1, 0, 'ADIÓS', Style(fg=WHITE))
            term.write(screen.render(first, second))
            self.assertEqual(term.canvas_text(), [second.row_text(y) for y in range(3)])
        finally:
            term.close()

    def test_context_manager_closes_the_pipe(self):
        with VirtualTerminal(4, 2) as term:
            term.write(b'x')
            self.assertEqual(bytes(term.output), b'x')
        self.assertTrue(term.closed)


if __name__ == '__main__':
    unittest.main()
