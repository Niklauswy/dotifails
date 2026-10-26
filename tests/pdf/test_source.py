"""PageSource against a scripted worker: what gets requested, cancelled and kept."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
AVAILABLE = importlib.util.find_spec('PySide6') is not None
if AVAILABLE:
    from PySide6.QtWidgets import QApplication
    from pdf_source import PageSource


class FakeWorker:
    """Records requests like PdfWorker; ``answer`` replies to the oldest queued one."""

    def __init__(self):
        self.queue, self.active = [], None

    def request(self, op, callback, *, priority=0, key=None, **args):
        if key is not None:
            self.queue = [item for item in self.queue if item[4] != key]
        self.queue.append([priority, op, args, callback, key])

    def cancel(self, predicate):
        kept = [item for item in self.queue if not predicate(item[1], item[4])]
        removed, self.queue = len(self.queue) - len(kept), kept
        return removed

    def queued_keys(self):
        return {item[4] for item in self.queue if item[4] is not None}

    def take(self, op=None):
        item = next(i for i in self.queue if op is None or i[1] == op)
        self.queue.remove(item)
        self.active = item
        return item

    def reply(self, item, result):
        self.active = None
        item[3]({'result': result})

    @staticmethod
    def raster(item):
        width = item[2]['width']
        return {'page': item[2]['page'], 'width': width, 'height': 2, 'stride': width * 3, 'blob': bytes(width * 6)}


@unittest.skipUnless(AVAILABLE, 'PySide6 required')
class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.worker = FakeWorker()
        self.source = PageSource(self.worker)
        self.source.reset([[595.0, 842.0]] * 40)

    def renders(self):
        return sorted(item[2]['page'] for item in self.worker.queue if item[1] == 'render')

    def test_want_requests_renders_and_text_once(self):
        self.source.want([(3, 800), (4, 800)])
        self.source.want([(3, 800), (4, 800)])
        self.assertEqual(self.renders(), [3, 4])
        self.assertEqual(sorted(i[2]['page'] for i in self.worker.queue if i[1] == 'page_info'), [3, 4])
        self.assertEqual(self.source.requested, [(3, 800), (4, 800)])

    def test_want_cancels_stale_renders(self):
        self.source.want([(1, 800), (2, 800)])
        self.source.want([(20, 800)])
        self.assertEqual(self.renders(), [20])
        self.assertEqual(sorted(i[2]['page'] for i in self.worker.queue if i[1] == 'page_info'), [20])

    def test_width_is_capped_like_the_engine(self):
        self.source.want([(0, 9000)])
        self.assertEqual(self.worker.queue[0][2]['width'], 2377)

    def test_rendered_image_is_cached_and_announced(self):
        changed = []
        self.source.changed.connect(changed.append)
        self.source.want([(5, 800)])
        item = self.worker.take('render')
        self.worker.reply(item, FakeWorker.raster(item))
        self.assertEqual(changed, [5])
        image, exact = self.source.image(5, 800)
        self.assertTrue(exact)
        self.assertEqual(image.width(), 800)
        self.source.want([(5, 800)])
        self.assertNotIn(5, self.renders())

    def test_image_falls_back_to_nearest_width(self):
        self.source.want([(5, 800)])
        item = self.worker.take('render')
        self.worker.reply(item, FakeWorker.raster(item))
        image, exact = self.source.image(5, 1200)
        self.assertFalse(exact)
        self.assertEqual(image.width(), 800)

    def test_edit_revision_discards_inflight_render(self):
        self.source.want([(5, 800)])
        stale = self.worker.take('render')
        self.source.invalidate(5)
        self.worker.reply(stale, FakeWorker.raster(stale))
        self.assertEqual(self.source.image(5, 800), (None, False))
        self.source.want([(5, 800)])
        self.assertEqual(self.renders(), [5])

    def test_reset_discards_replies_of_the_previous_document(self):
        self.source.want([(5, 800)])
        old = self.worker.take('page_info')
        self.source.reset([[595.0, 842.0]] * 2)
        self.worker.reply(old, {'page': 5, 'words': [], 'links': [], 'annotations': []})
        self.assertIsNone(self.source.info(5))
        self.assertEqual(self.worker.queue, [])

    def test_info_is_cached_and_bounded(self):
        ready = []
        self.source.info_ready.connect(ready.append)
        for page in range(40):
            self.source.want([(page, 100)])
            item = self.worker.take('page_info')
            self.worker.reply(item, {'page': page, 'words': [[0, 0, 1, 1, 'w', 0, 0]], 'links': [], 'annotations': []})
        self.assertEqual(len(ready), 40)
        self.assertEqual(self.source.info(39)['words'][0][4], 'w')
        with unittest.mock.patch('pdf_source.INFO_LIMIT', 4):
            self.source.reset([[595.0, 842.0]] * 40)
            for page in range(6):
                self.source.want([(page, 100)])
                self.worker.reply(self.worker.take('page_info'), {'page': page, 'words': [], 'links': [], 'annotations': []})
            self.assertEqual(list(self.source.infos), [2, 3, 4, 5])


import unittest.mock  # noqa: E402

if __name__ == '__main__':
    unittest.main()
