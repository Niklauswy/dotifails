"""Wysun Player's QML process (venv Python): requests are parsed as before, each opens a window (the last one is
reused past the limit), a request without files asks for them, and the process quits a moment after its last
window closes unless a new request arrives meanwhile."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402


def fake_window_class():
    from PySide6.QtCore import QObject, Signal

    class FakeWindow(QObject):
        closed = Signal()

        def __init__(self):
            super().__init__()
            self.shown, self.presented, self.chosen = [], [], 0

        def show_files(self, files, paused=False, start=None):
            self.shown.append((list(files), paused, start))

        def present(self, fullscreen=False):
            self.presented.append(fullscreen)

        def choose(self):
            self.chosen += 1

        def shutdown(self):
            pass

    return FakeWindow


class ProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()

    def setUp(self):
        from wysun_core.instance import SingleInstance
        from wysun_player.quick import process
        self.process_module = process
        self.tmp = tempfile.TemporaryDirectory(prefix='player-proc-', dir=self.h.home)
        self.addCleanup(self.tmp.cleanup)
        owner = SingleInstance('wysun-player-test', directory=self.tmp.name)
        self.assertTrue(owner.claim())
        self.quits = []
        self.windows = []
        cls = fake_window_class()

        def factory():
            window = cls()
            self.windows.append(window)
            return window

        self.process = process.Process(lambda: self.quits.append(True), owner, factory)
        self.addCleanup(self.process.shutdown)

    def test_requests_are_parsed_as_before(self):
        parse = self.process_module.RequestServer.parse
        self.assertEqual(parse(b'{"files": ["/a", 3]}')['files'], ['/a', '3'])
        self.assertIsNone(parse(b'not json'))
        self.assertIsNone(parse(b'{"files": "x"}'))
        self.assertIsNone(parse(b'[1]'))

    def test_each_request_opens_a_window_with_its_options(self):
        self.process.show({'files': ['/a.mp4'], 'paused': True, 'start': 12.5, 'fullscreen': True})
        self.assertEqual(self.windows[0].shown, [(['/a.mp4'], True, 12.5)])
        self.assertEqual(self.windows[0].presented, [True])

    def test_past_the_limit_the_last_window_is_reused(self):
        limit = self.process_module.WINDOW_LIMIT
        for number in range(limit + 1):
            self.process.show({'files': [f'/{number}.png']})
        self.assertEqual(len(self.windows), limit)
        self.assertEqual(self.windows[-1].shown[-1][0], [f'/{limit}.png'])

    def test_a_request_without_files_asks_for_them(self):
        self.process.show({'files': []})
        self.assertEqual(self.windows[0].chosen, 1)
        self.assertEqual(self.windows[0].shown, [])

    def test_quits_after_the_last_window_unless_a_request_arrives(self):
        self.process.show({'files': ['/a.png']})
        self.windows[0].closed.emit()
        self.h.pump(self.process_module.GRACE_MS + 100)
        self.assertEqual(self.quits, [True])
        self.quits.clear()
        self.process.show({'files': ['/b.png']})
        self.windows[1].closed.emit()
        self.process.show({'files': ['/c.png']})              # within the grace period
        self.h.pump(self.process_module.GRACE_MS + 100)
        self.assertEqual(self.quits, [])

    def test_the_player_uses_the_basic_render_loop(self):
        source = (ROOT / 'apps/python/wysun_player/quick/process.py').read_text()
        self.assertIn("os.environ['QSG_RENDER_LOOP'] = 'basic'", source)


if __name__ == '__main__':
    unittest.main()
