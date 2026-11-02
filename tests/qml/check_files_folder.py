"""Wysun Files' folder model and thumbnails for QML (venv Python): listing off the GUI thread, sorting, filters,
selection that survives refreshes, live changes applied in place, lazy details and freedesktop thumbnails."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402


def touch(path, data=b'', mtime=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def png(path, w=40, h=30, colour='#c05030'):
    from PySide6.QtGui import QColor, QImage
    image = QImage(w, h, QImage.Format_RGB32)
    image.fill(QColor(colour))
    path.parent.mkdir(parents=True, exist_ok=True)
    assert image.save(str(path))
    return path


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        cls.cache_dir = tempfile.TemporaryDirectory(prefix='files-cache-', dir=scratch)

    @classmethod
    def tearDownClass(cls):
        cls.cache_dir.cleanup()

    def setUp(self):
        from wysun_files.quick.folder import FolderModel
        from wysun_files.quick.thumbs import Thumbnails
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        self.tmp = tempfile.TemporaryDirectory(prefix='files-folder-', dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.thumbs = Thumbnails(cache=Path(self.cache_dir.name) / 'thumbnails')
        self.model = FolderModel(thumbs=self.thumbs)
        self.addCleanup(self.model.close)
        self.addCleanup(self.thumbs.close)

    def load(self, path=None, ok=True):
        self.assertEqual(self.model.setRoot(str(path or self.root)), ok)
        self.assertTrue(self.h.wait_for(lambda: not self.model.property('loading'), 4000), 'still loading')

    def names(self):
        return [self.model.pathAt(r).rsplit('/', 1)[-1] for r in range(self.model.rowCount())]

    def role(self, row, name):
        from PySide6.QtCore import Qt
        for number, role in self.model.roleNames().items():
            if bytes(role).decode() == name:
                return self.model.data(self.model.index(row), number)
        raise KeyError(name)


class GarbageCollectionTests(Base):
    def test_python_collects_on_the_gui_thread_only(self):
        # A collection started by a worker thread would destroy Qt objects there (their watchers' descriptors with them).
        import gc
        import threading
        from PySide6.QtCore import QObject
        self.assertFalse(gc.isenabled(), 'automatic collection may run in any thread')
        seen = []

        class Canary(QObject):
            def __del__(self):
                seen.append(threading.current_thread() is threading.main_thread())

        canary = Canary()
        canary.cycle = canary
        del canary

        def churn():
            for _ in range(5):
                _ = [[] for _ in range(100000)]

        worker = threading.Thread(target=churn)
        worker.start()
        worker.join()
        self.assertEqual(seen, [], 'collected by the worker')
        self.assertTrue(self.h.wait_for(lambda: bool(seen), 8000), 'never collected')
        self.assertEqual(seen, [True])


class ListingTests(Base):
    def fill(self):
        (self.root / 'Música').mkdir()
        (self.root / 'repos').mkdir()
        touch(self.root / 'repos/a.py', 'x')
        touch(self.root / 'tesis.pdf', b'%PDF' + b'0' * 2_516_578)
        touch(self.root / 'notas.md', '# Notas\nuno')
        touch(self.root / 'b10.txt', 'b')
        touch(self.root / 'b2.txt', 'b')
        touch(self.root / '.oculto', 'h')

    def test_lists_folders_first_natural_order_without_hidden(self):
        self.fill()
        self.load()
        self.assertEqual(self.names(), ['Música', 'repos', 'b2.txt', 'b10.txt', 'notas.md', 'tesis.pdf'])
        self.assertEqual(self.model.property('count'), 6)
        self.assertEqual(self.model.property('total'), 6)
        self.assertEqual(self.model.property('summary'), '2 carpetas · 4 archivos · 2,4 MB')
        self.assertEqual(self.model.property('root'), str(self.root))
        self.assertEqual(self.model.property('error'), '')

    def test_roles(self):
        self.fill()
        self.load()
        row = self.model.rowOf(str(self.root / 'tesis.pdf'))
        self.assertEqual((self.role(row, 'kind'), self.role(row, 'badge'), self.role(row, 'role')), ('pdf', 'PDF', 'error'))
        self.assertEqual(self.role(row, 'sizeText'), '2,4 MB')
        self.assertEqual(self.role(row, 'modifiedText'), 'hoy')
        self.assertEqual(self.role(row, 'label'), 'Documento PDF')
        self.assertEqual(self.role(row, 'name'), 'tesis.pdf')
        self.assertFalse(self.role(row, 'isDir'))
        music = self.model.rowOf(str(self.root / 'Música'))
        self.assertEqual((self.role(music, 'kind'), self.role(music, 'glyph')), ('folder', 'music_note'))
        self.assertEqual(self.model.rowOf('/no/such'), -1)

    def test_details_arrive_lazily(self):
        self.fill()
        self.load()
        repos, notes = self.model.rowOf(str(self.root / 'repos')), self.model.rowOf(str(self.root / 'notas.md'))
        self.role(repos, 'detail'), self.role(notes, 'snippet')          # asking starts the work
        self.assertTrue(self.h.wait_for(lambda: self.role(repos, 'detail') == '1 elemento', 3000))
        self.assertTrue(self.h.wait_for(lambda: list(self.role(notes, 'snippet') or []) == ['# Notas', 'uno'], 3000))
        self.assertEqual(self.role(notes, 'detail'), '11 B')

    def test_sort_and_reverse(self):
        self.fill()
        self.load()
        self.model.sortBy('size', True)
        self.assertEqual(self.names()[:3], ['repos', 'Música', 'tesis.pdf'])
        self.assertEqual(self.model.property('sortKey'), 'size')
        self.assertTrue(self.model.property('descending'))
        self.model.sortBy('name', False)
        self.assertEqual(self.names()[0], 'Música')

    def test_filters_and_hidden(self):
        self.fill()
        self.load()
        self.model.setFilterText('NOTA')
        self.assertEqual(self.names(), ['notas.md'])
        self.assertEqual(self.model.property('total'), 6)
        self.model.setFilterText('')
        self.model.setGroup('code')
        self.assertEqual(self.names(), ['Música', 'repos'])
        self.model.setGroup('documents')
        self.assertEqual(self.names(), ['Música', 'repos', 'b2.txt', 'b10.txt', 'notas.md', 'tesis.pdf'])
        self.model.setGroup('folders')
        self.assertEqual(self.names(), ['Música', 'repos'])
        self.model.setGroup('all')
        self.model.setShowHidden(True)
        self.assertIn('.oculto', self.names())
        self.assertEqual(self.model.property('total'), 7)

    def test_accept_predicate_for_the_chooser(self):
        self.fill()
        self.load()
        self.model.set_accept(lambda entry: entry.name.endswith('.md'))
        self.assertEqual(self.names(), ['Música', 'repos', 'notas.md'])
        self.model.set_accept(None)
        self.assertEqual(len(self.names()), 6)

    def test_missing_and_unreadable_folders(self):
        self.load(self.root / 'falta', ok=False)
        self.assertEqual(self.model.rowCount(), 0)
        self.assertIn('no existe', self.model.property('error'))
        locked = self.root / 'cerrada'
        locked.mkdir()
        locked.chmod(0)
        self.addCleanup(locked.chmod, 0o755)
        if os.access(locked, os.R_OK):
            self.skipTest('running as root')
        self.load(locked)
        self.assertIn('permiso', self.model.property('error'))
        self.load()
        self.assertEqual(self.model.property('error'), '')

    def test_a_file_root_is_refused(self):
        self.fill()
        self.load(self.root / 'notas.md', ok=False)

    def test_stale_listing_is_dropped(self):
        a, b = self.root / 'a', self.root / 'b'
        touch(a / 'solo-a')
        touch(b / 'solo-b')
        self.model.setRoot(str(a))
        self.model.setRoot(str(b))
        self.assertTrue(self.h.wait_for(lambda: not self.model.property('loading'), 3000))
        self.h.pump(100)
        self.assertEqual(self.names(), ['solo-b'])

    def test_large_folder_loads_off_the_gui_thread(self):
        big = self.root / 'grande'
        big.mkdir()
        for i in range(10000):
            (big / f'archivo-{i:05d}.txt').touch()
        started = time.perf_counter()
        self.model.setRoot(str(big))
        self.assertLess(time.perf_counter() - started, .05, 'setRoot blocked the GUI thread')
        self.assertTrue(self.model.property('loading'))
        self.assertTrue(self.h.wait_for(lambda: not self.model.property('loading'), 5000))
        self.assertEqual(self.model.rowCount(), 10000)
        self.assertEqual(self.names()[9999], 'archivo-09999.txt')


class SelectionTests(Base):
    def setUp(self):
        super().setUp()
        for name in ('a', 'b', 'c', 'd', 'e'):
            touch(self.root / f'{name}.txt', name)
        self.load()

    def selected(self):
        return [p.rsplit('/', 1)[-1] for p in self.model.property('selectedPaths')]

    def test_single_toggle_range(self):
        self.model.select(1, 'single')
        self.assertEqual(self.selected(), ['b.txt'])
        self.model.select(3, 'toggle')
        self.assertEqual(self.selected(), ['b.txt', 'd.txt'])
        self.model.select(1, 'toggle')
        self.assertEqual(self.selected(), ['d.txt'])
        self.model.select(1, 'single')
        self.model.select(3, 'range')
        self.assertEqual(self.selected(), ['b.txt', 'c.txt', 'd.txt'])
        self.assertTrue(self.role(2, 'selected'))
        self.assertEqual(self.model.property('selectionCount'), 3)
        self.model.selectAll()
        self.assertEqual(self.model.property('selectionCount'), 5)
        self.model.clearSelection()
        self.assertEqual(self.selected(), [])
        self.assertFalse(self.role(2, 'selected'))

    def test_selection_follows_paths_through_sort_and_filter(self):
        self.model.select(self.model.rowOf(str(self.root / 'c.txt')), 'single')
        self.model.select(self.model.rowOf(str(self.root / 'e.txt')), 'toggle')
        self.model.sortBy('name', True)
        self.assertEqual(self.selected(), ['e.txt', 'c.txt'], 'in view order')
        self.assertTrue(self.role(self.model.rowOf(str(self.root / 'e.txt')), 'selected'))
        self.model.setFilterText('c')
        self.assertEqual(self.selected(), ['c.txt'], 'filtered-out rows leave the selection')

    def test_select_paths(self):
        self.model.selectPaths([str(self.root / 'd.txt'), '/no/such'])
        self.assertEqual(self.selected(), ['d.txt'])
        self.assertEqual(self.model.property('currentRow'), self.model.rowOf(str(self.root / 'd.txt')))

    def test_cut_rows_are_flagged(self):
        self.model.setCut([str(self.root / 'a.txt')])
        self.assertTrue(self.role(0, 'cut'))
        self.assertFalse(self.role(1, 'cut'))
        self.model.setCut([])
        self.assertFalse(self.role(0, 'cut'))


class LiveTests(Base):
    def test_changes_on_disk_are_applied_in_place(self):
        for name in ('a', 'c', 'e'):
            touch(self.root / f'{name}.txt', name)
        self.load()
        resets, inserted, removed = [], [], []
        self.model.modelReset.connect(lambda: resets.append(1))
        self.model.rowsInserted.connect(lambda _p, first, last: inserted.append((first, last)))
        self.model.rowsRemoved.connect(lambda _p, first, last: removed.append((first, last)))
        self.model.select(self.model.rowOf(str(self.root / 'e.txt')), 'single')
        touch(self.root / 'b.txt', 'b')
        self.assertTrue(self.h.wait_for(lambda: 'b.txt' in self.names(), 3000))
        (self.root / 'a.txt').unlink()
        self.assertTrue(self.h.wait_for(lambda: 'a.txt' not in self.names(), 3000))
        self.assertEqual(self.names(), ['b.txt', 'c.txt', 'e.txt'])
        self.assertEqual(resets, [])
        self.assertEqual(inserted, [(1, 1)])
        self.assertEqual(removed, [(0, 0)])
        self.assertEqual([p.rsplit('/', 1)[-1] for p in self.model.property('selectedPaths')], ['e.txt'])

    def test_root_removed_reports_it(self):
        sub = self.root / 'sub'
        touch(sub / 'x')
        self.load(sub)
        (sub / 'x').unlink()
        sub.rmdir()
        self.assertTrue(self.h.wait_for(lambda: self.model.property('error') != '', 3000))
        self.assertEqual(self.model.rowCount(), 0)

    def test_loaded_signal_names_the_root(self):
        seen = []
        self.model.loaded.connect(seen.append)
        touch(self.root / 'x')
        self.load()
        self.assertEqual(seen, [str(self.root)])


class ThumbnailTests(Base):
    def thumb_of(self, name, timeout=5000):
        row = self.model.rowOf(str(self.root / name))
        self.role(row, 'thumb')
        self.h.wait_for(lambda: bool(self.role(self.model.rowOf(str(self.root / name)), 'thumb')), timeout)
        return self.role(self.model.rowOf(str(self.root / name)), 'thumb')

    def test_image_thumbnail_follows_the_freedesktop_cache(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QImage
        source = png(self.root / 'foto.png', 600, 300)
        self.load()
        url = self.thumb_of('foto.png')
        self.assertTrue(url.startswith('file://'), url)
        file = Path(QUrl(url).toLocalFile())
        uri = QUrl.fromLocalFile(str(source)).toString(QUrl.FullyEncoded)
        self.assertEqual(file.name, hashlib.md5(uri.encode()).hexdigest() + '.png')
        self.assertEqual(file.parent.name, 'large')
        image = QImage(str(file))
        self.assertEqual(max(image.width(), image.height()), 256)
        self.assertEqual(image.text('Thumb::URI'), uri)
        self.assertEqual(image.text('Thumb::MTime'), str(int(source.stat().st_mtime)))
        self.assertEqual(oct(file.stat().st_mode & 0o777), '0o600')

    def test_small_images_are_not_upscaled_and_stale_thumbnails_are_redone(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QImage
        source = png(self.root / 'chica.png', 40, 30)
        self.load()
        first = Path(QUrl(self.thumb_of('chica.png')).toLocalFile())
        self.assertEqual(QImage(str(first)).width(), 40)
        png(source, 80, 30, '#2050c0')
        os.utime(source, (time.time() + 5, time.time() + 5))
        self.model.refresh()
        self.assertTrue(self.h.wait_for(lambda: not self.model.property('loading'), 3000))
        self.thumb_of('chica.png')
        self.assertTrue(self.h.wait_for(lambda: QImage(str(first)).width() == 80, 3000))

    def test_broken_and_oversized_images_keep_their_icon(self):
        touch(self.root / 'rota.png', b'not a png')
        touch(self.root / 'enorme.jpg', b'\xff\xd8' + b'0' * (33 * 1024 * 1024))
        self.load()
        for name in ('rota.png', 'enorme.jpg'):
            with self.subTest(name=name):
                self.assertEqual(self.thumb_of(name, 1500), '')
        self.assertTrue((Path(self.cache_dir.name) / 'thumbnails/fail/wysun').is_dir())

    def test_video_thumbnail_and_duration(self):
        target = self.root / 'clip.mp4'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=duration=3:size=320x240:rate=10',
                        '-pix_fmt', 'yuv420p', str(target)], check=True)
        self.load()
        self.assertTrue(self.thumb_of('clip.mp4', 10000).startswith('file://'))
        self.assertEqual(self.role(self.model.rowOf(str(target)), 'duration'), '0:03')

    def test_thumbnails_are_not_made_inside_the_thumbnail_cache(self):
        cache = Path(self.cache_dir.name) / 'thumbnails/large'
        png(cache / 'otra.png')
        self.model.setRoot(str(cache))
        self.assertTrue(self.h.wait_for(lambda: not self.model.property('loading'), 3000))
        row = self.model.rowOf(str(cache / 'otra.png'))
        self.role(row, 'thumb')
        self.h.pump(300)
        self.assertEqual(self.role(row, 'thumb'), '')


if __name__ == '__main__':
    unittest.main()
