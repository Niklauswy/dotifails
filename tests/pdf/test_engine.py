import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
AVAILABLE = importlib.util.find_spec('fitz') is not None
if AVAILABLE:
    import fitz
    from pdf_engine import PdfEngine, fingerprint


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

    def test_rotated_selection_and_native_annotations_roundtrip(self):
        for page in range(4):
            render = self.engine.render(page, 500)
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
        xref = self.engine.render(0, 300)['annotations'][0]['xref']
        self.engine.delete(0, xref)
        self.assertEqual(self.engine.render(0, 300)['annotations'], [])
        with self.assertRaises(Exception):
            self.engine.open(self.path.with_name('missing.pdf'))
        self.assertEqual(self.engine.doc.page_count, 4)

    def test_thumbnail_and_edit_note(self):
        thumb = self.engine.thumbnail(0)
        self.assertTrue(thumb['png'])
        self.engine.annotate(0, 'note', point=[100,100], text='first draft')
        xref = self.engine.render(0,300)['annotations'][0]['xref']
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
