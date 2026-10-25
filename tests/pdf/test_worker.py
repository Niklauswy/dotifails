"""The transport against the real engine process. Run with QT_QPA_PLATFORM=offscreen."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
AVAILABLE = all(importlib.util.find_spec(m) for m in ('fitz', 'PySide6'))
if AVAILABLE:
    import fitz
    from PySide6.QtCore import QCoreApplication
    from pdf_worker import PdfWorker


@unittest.skipUnless(AVAILABLE, 'PySide6 and python3-fitz required')
class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'doc.pdf'
        doc = fitz.open()
        for n in range(6):
            doc.new_page().insert_text((72, 90), f'Page {n} worker test')
        doc.save(self.path); doc.close()
        self.worker = PdfWorker()
        self.replies = []
        self.worker.request('open', lambda reply: self.replies.append(('open', reply)), path=str(self.path))

    def tearDown(self):
        self.worker.stop()
        self.tmp.cleanup()

    def wait(self, condition, timeout=8):
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            self.app.processEvents(); time.sleep(.005)
        self.assertTrue(condition(), 'worker did not answer')

    def record(self, name):
        return lambda reply: self.replies.append((name, reply))

    def test_binary_frame_roundtrip(self):
        self.worker.request('render', self.record('render'), page=0, width=300)
        self.worker.request('page_info', self.record('info'), page=0)
        self.wait(lambda: len(self.replies) == 3)
        render = self.replies[1][1]['result']
        self.assertEqual(len(render['blob']), render['stride'] * render['height'])
        self.assertEqual(self.replies[2][1]['result']['words'][0][4], 'Page')

    def test_priority_runs_interactive_first(self):
        # 'open' is already in flight: everything below waits in the queue.
        self.worker.request('search', self.record('search'), priority=2, page=0, text='worker')
        self.worker.request('thumbnail', self.record('thumbnail'), priority=1, page=1)
        self.worker.request('render', self.record('render'), page=0, width=200)
        self.wait(lambda: len(self.replies) == 4)
        self.assertEqual([name for name, _ in self.replies], ['open', 'render', 'thumbnail', 'search'])

    def test_same_key_replaces_queued(self):
        self.worker.request('render', self.record('first'), key=('render', 2), page=2, width=200)
        self.worker.request('render', self.record('second'), key=('render', 2), page=2, width=240)
        self.assertEqual(self.worker.queued_keys(), {('render', 2)})
        self.wait(lambda: len(self.replies) == 2)
        self.assertEqual(self.replies[1][0], 'second')
        self.assertEqual(self.replies[1][1]['result']['width'], 240)

    def test_cancel_drops_queued_renders(self):
        for page in range(1, 6):
            self.worker.request('render', self.record(f'render{page}'), key=('render', page), page=page, width=200)
        removed = self.worker.cancel(lambda op, key: key is not None and key[1] != 3)
        self.assertEqual(removed, 4)
        self.wait(lambda: len(self.replies) == 2)
        self.app.processEvents()
        self.assertEqual([name for name, _ in self.replies], ['open', 'render3'])


if __name__ == '__main__':
    unittest.main()
