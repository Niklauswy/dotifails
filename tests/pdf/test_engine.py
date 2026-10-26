import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
AVAILABLE = importlib.util.find_spec('fitz') is not None
if AVAILABLE:
    import fitz
    from pdf_engine import PdfEngine, fingerprint
    from pdf_layout import raster_width


@unittest.skipUnless(AVAILABLE, 'python3-fitz is required')
class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'source.pdf'
        doc = fitz.open()
        for rotation in (0, 90, 180, 270):
            p = doc.new_page()
            p.insert_text((72, 90), 'Wysun reader annotation test')
            p.set_rotation(rotation)
        doc.set_toc([[1, 'Introduction', 1]])
        doc.save(self.path); doc.close()
        self.engine = PdfEngine()
        self.engine.open(self.path)

    def tearDown(self):
        if self.engine.doc:
            self.engine.doc.close()
        self.tmp.cleanup()

    def test_mupdf_messages_stay_off_the_protocol(self):
        # MuPDF reports repairs of damaged files on stdout by default; that would desynchronise every reply.
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), 'damaged')
        broken = Path(self.tmp.name) / 'broken.pdf'
        broken.write_bytes(doc.tobytes(deflate=False).replace(b'stream\n', b'stream\nGARBAGE((( ', 1))
        doc.close()
        engine = Path(__file__).resolve().parents[2] / 'apps/wysun/pdf_engine.py'
        requests = [{'op': 'open', 'args': {'path': str(broken)}}, {'op': 'render', 'args': {'page': 0, 'width': 120}},
                    {'op': 'page_info', 'args': {'page': 0}}]
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
        out = subprocess.run([sys.executable, str(engine)], input=''.join(json.dumps(r) + '\n' for r in requests).encode(),
                             capture_output=True, env=env, timeout=30, check=True).stdout
        replies = []
        while out:
            line, _, out = out.partition(b'\n')
            reply = json.loads(line)
            out = out[reply.get('blob', 0):]
            replies.append(reply)
        self.assertEqual([('error' in r) for r in replies], [False, False, False])
        self.assertEqual(replies[0]['result']['pages'], 1)
        self.assertIn('stride', replies[1]['result'])
        self.assertIn('words', replies[2]['result'])

    def test_rotated_selection_and_native_annotations_roundtrip(self):
        for page in range(4):
            render = self.engine.page_info(page)
            self.assertEqual(render['words'][0][4], 'Wysun')
            self.assertTrue(self.engine.search(page, 'reader')['hits'])
            for kind in ('highlight', 'underline'):
                self.engine.annotate(page, kind, rects=[render['words'][0][:4]], text='selected Wysun')
            self.engine.annotate(page, 'note', point=[100, 100], text='Remember this')
        dest = self.path.with_name('annotated.pdf')
        self.engine.save(dest)
        with fitz.open(dest) as doc:
            for i, p in enumerate(doc):
                annots = list(p.annots())
                self.assertEqual(len(annots), 3)
                self.assertEqual(annots[-1].info['content'], 'Remember this')
                self.assertTrue(annots[0].rect.intersects(p.search_for('Wysun')[0]))
        with fitz.open(self.path) as doc:
            self.assertEqual(list(doc[0].annots()), [])

    def test_open_reports_rotated_sizes(self):
        sizes = self.engine.open(self.path)['sizes']
        self.assertEqual(len(sizes), 4)
        width, height = sizes[0]
        self.assertGreater(height, width)
        self.assertEqual(sizes[1], [height, width])
        self.assertEqual(sizes[2], [width, height])

    def test_render_is_raw_rgb_within_the_raster_limit(self):
        result = self.engine.render(0, 5000)
        self.assertEqual(len(result['_blob']), result['stride'] * result['height'])
        width, height = self.engine.open(self.path)['sizes'][0]
        self.assertAlmostEqual(result['width'], raster_width(width, height, 5000), delta=1)
        self.assertLessEqual(result['width'], 2800)
        self.assertNotIn('png', result)

    def test_page_info_words_and_links(self):
        doc = fitz.open(self.path)
        doc[0].insert_link({'kind': fitz.LINK_GOTO, 'page': 2, 'from': fitz.Rect(72, 200, 200, 220), 'to': fitz.Point(0, 100)})
        doc[0].insert_link({'kind': fitz.LINK_URI, 'uri': 'https://example.org', 'from': fitz.Rect(72, 300, 200, 320)})
        linked = self.path.with_name('linked.pdf'); doc.save(linked); doc.close()
        self.engine.open(linked)
        info = self.engine.page_info(0)
        self.assertEqual([w[4] for w in info['words']][:2], ['Wysun', 'reader'])
        self.assertEqual(len(info['words'][0]), 7)
        internal = [link for link in info['links'] if 'page' in link]
        external = [link for link in info['links'] if 'uri' in link]
        self.assertEqual(internal[0]['page'], 2)
        self.assertAlmostEqual(internal[0]['rect'][1], 200, delta=1)
        self.assertEqual(external[0]['uri'], 'https://example.org')

    def test_links_follow_page_rotation(self):
        doc = fitz.open(self.path)
        doc[1].insert_link({'kind': fitz.LINK_URI, 'uri': 'https://example.org', 'from': fitz.Rect(72, 80, 200, 95)})
        linked = self.path.with_name('rotated.pdf'); doc.save(linked); doc.close()
        self.engine.open(linked)
        info = self.engine.page_info(1)
        link = fitz.Rect(info['links'][0]['rect'])
        self.assertTrue(link.intersects(fitz.Rect(info['words'][0][:4])))

    def test_search_returns_context(self):
        result = self.engine.search(0, 'annotation')
        self.assertEqual(len(result['hits']), 1)
        self.assertIn('annotation', result['contexts'][0])
        self.assertLessEqual(len(result['contexts'][0]), 120)

    def test_annotations_lists_whole_document(self):
        self.engine.annotate(0, 'note', point=[100, 100], text='first')
        self.engine.annotate(3, 'note', point=[100, 100], text='last')
        items = self.engine.annotations()['items']
        self.assertEqual([(i['page'], i['text']) for i in items], [(0, 'first'), (3, 'last')])

    def test_atomic_save_and_repeated_save(self):
        self.engine.annotate(0, 'note', point=[100, 100], text='first')
        self.engine.save(self.path)
        self.engine.annotate(0, 'note', point=[120, 120], text='second')
        self.engine.save(self.path)
        with fitz.open(self.path) as doc:
            self.assertEqual(len(list(doc[0].annots())), 2)
        self.assertFalse(self.engine.dirty)

    def test_external_change_refused_and_copy_allowed(self):
        self.engine.annotate(0, 'note', point=[100, 100], text='keep')
        with self.path.open('ab') as stream:
            stream.write(b'\n% external change\n')
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.engine.save(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(self.engine.dirty)
        self.engine.save(self.path.with_name('copy.pdf'))

    def test_existing_target_requires_expected_fingerprint(self):
        target = self.path.with_name('existing.pdf'); target.write_bytes(self.path.read_bytes())
        with self.assertRaises(ValueError):
            self.engine.save(target)
        self.engine.save(target, list(fingerprint(target)))

    def test_delete_and_failed_open_preserves_document(self):
        self.engine.annotate(0, 'note', point=[100, 100], text='remove')
        xref = self.engine.page_info(0)['annotations'][0]['xref']
        self.engine.delete(0, xref)
        self.assertEqual(self.engine.page_info(0)['annotations'], [])
        with self.assertRaises(Exception):
            self.engine.open(self.path.with_name('missing.pdf'))
        self.assertEqual(self.engine.doc.page_count, 4)

    def test_thumbnail_and_edit_note(self):
        thumb = self.engine.thumbnail(0)
        self.assertEqual(len(thumb['_blob']), thumb['stride'] * thumb['height'])
        self.assertLessEqual(thumb['width'], 120)
        self.engine.annotate(0, 'note', point=[100,100], text='first draft')
        xref = self.engine.page_info(0)['annotations'][0]['xref']
        self.engine.update_note(0,xref,'revised idea')
        self.engine.save(self.path)
        with fitz.open(self.path) as doc:
            self.assertEqual(next(doc[0].annots()).info['content'],'revised idea')

    def test_password_and_permissions(self):
        locked = self.path.with_name('locked.pdf')
        with fitz.open(self.path) as doc:
            doc.save(locked, encryption=fitz.PDF_ENCRYPT_AES_256,
                     owner_pw='owner', user_pw='reader', permissions=fitz.PDF_PERM_PRINT)
        self.assertTrue(self.engine.open(locked)['password_required'])
        self.assertFalse(self.engine.open(locked, 'reader')['editable'])
        with self.assertRaises(ValueError):
            self.engine.annotate(0, 'note', point=[100, 100], text='forbidden')
        self.assertTrue(self.engine.open(locked, 'owner')['editable'])
        self.engine.annotate(0, 'note', point=[100, 100], text='owner note')
        copy = self.path.with_name('encrypted-copy.pdf')
        self.engine.save(copy)
        with fitz.open(copy) as doc:
            self.assertTrue(doc.needs_pass)
            self.assertTrue(doc.authenticate('reader'))
            self.assertEqual(len(list(doc[0].annots())), 1)


if __name__ == '__main__':
    unittest.main()
