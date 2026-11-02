"""Wysun Files' preview bridge (venv Python): what the inspector shows for each kind (F-50…F-55): images with their
size, broken files, text (512 KB), code highlighted with theme colours, Markdown as HTML with links that resolve,
the first page of a PDF, media length and codecs, folder and multi-selection summaries, files without preview,
and only the latest selection when they change quickly."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

COLOURS = {'keyword': '#aa0000', 'string': '#00aa00', 'number': '#0000aa', 'comment': '#777777', 'function': '#aa00aa',
           'type': '#00aaaa', 'constant': '#aaaa00', 'key': '#123456', 'meta': '#654321', 'link': '#0055ff',
           'code_bg': '#eeeeee', 'code_fg': '#222222', 'muted': '#888888', 'mono': 'monospace', 'text': '#111111',
           'rule': '#cccccc'}


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()

    def setUp(self):
        from wysun_files.quick.preview import Preview
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        self.tmp = tempfile.TemporaryDirectory(prefix='files-prev-', dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.preview = Preview(cache=self.root / 'cache')
        self.preview.setColors(COLOURS)
        self.addCleanup(self.preview.close)

    def show(self, *names, ms=6000):
        self.preview.setSelection([str(self.root / n) for n in names])
        self.assertTrue(self.h.wait_for(lambda: not self.preview.property('loading')
                                        and self.preview.property('paths') == [str(self.root / n) for n in names], ms))
        return {row['label']: row['value'] for row in self.preview.property('meta')}

    def png(self, name, w, h):
        from PySide6.QtGui import QColor, QImage
        image = QImage(w, h, QImage.Format_RGB32)
        image.fill(QColor('#3366aa'))
        image.save(str(self.root / name))

    def test_image(self):
        self.png('playa.png', 600, 300)
        meta = self.show('playa.png')
        self.assertEqual(self.preview.property('kind'), 'image')
        self.assertEqual(self.preview.property('name'), 'playa.png')
        self.assertTrue(self.preview.property('imageUrl').endswith('/playa.png'))
        self.assertTrue(meta['Tamaño'].endswith('· 600 × 300'))
        self.assertIn('Modificado', meta)
        self.assertEqual(meta['Ruta'], str(self.root))

    def test_broken_image_says_so_and_keeps_the_selection(self):
        (self.root / 'roto.png').write_bytes(b'not a png at all')
        self.show('roto.png')
        self.assertEqual(self.preview.property('kind'), 'image')
        self.assertEqual(self.preview.property('error'), 'No se pudo abrir la imagen. El archivo sigue seleccionado.')

    def test_text_is_limited_to_512_kb(self):
        (self.root / 'largo.txt').write_text('x' * (600 * 1024))
        self.show('largo.txt')
        self.assertEqual(self.preview.property('kind'), 'text')
        self.assertEqual(len(self.preview.property('text')), 512 * 1024)
        self.assertTrue(self.preview.property('truncated'))

    def test_code_is_highlighted_with_the_given_colours(self):
        (self.root / 'main.py').write_text('import os\n\ndef main():\n    return "hola"  # fin\n')
        meta = self.show('main.py')
        self.assertEqual(self.preview.property('kind'), 'code')
        html = self.preview.property('html')
        self.assertIn('color:#aa0000', html)      # keyword
        self.assertIn('color:#00aa00', html)      # string
        self.assertEqual(meta['Tamaño'], '48 B · Python')
        self.assertEqual(self.preview.property('lineCount'), 4)

    def test_markdown_renders_and_its_links_resolve(self):
        (self.root / 'docs').mkdir()
        (self.root / 'notas.md').write_text('# Notas\n\nLee [el tema](docs/tema.md) y <https://example.org>.\n\n- uno\n- dos\n\n```py\nx = 1\n```\n')
        self.show('notas.md')
        self.assertEqual(self.preview.property('kind'), 'markdown')
        html = self.preview.property('html')
        self.assertIn('<h1', html)
        self.assertIn('<li', html)
        self.assertIn('href="docs/tema.md"', html)
        self.assertIn('# Notas', self.preview.property('text'))
        self.assertEqual(self.preview.resolveLink('docs/tema.md'), str(self.root / 'docs/tema.md'))
        self.assertEqual(self.preview.resolveLink('https://example.org'), 'https://example.org')
        self.assertEqual(self.preview.resolveLink('#ancla'), '')

    def test_pdf_first_page(self):
        from PySide6.QtGui import QPageSize, QPainter, QPdfWriter
        writer = QPdfWriter(str(self.root / 'tesis.pdf'))
        writer.setPageSize(QPageSize(QPageSize.A6))
        painter = QPainter(writer)
        painter.drawText(100, 100, 'Tesis')
        writer.newPage()
        painter.drawText(100, 100, 'Dos')
        painter.end()
        meta = self.show('tesis.pdf', ms=10000)
        self.assertEqual(self.preview.property('kind'), 'pdf')
        url = self.preview.property('imageUrl')
        self.assertTrue(url.startswith('file://') and url.endswith('.png'), url)
        self.assertTrue(Path(url[7:]).is_file())
        self.assertEqual(meta['Páginas'], '2')
        self.assertEqual((self.preview.property('page'), self.preview.property('pages')), (1, 2))
        self.preview.setPage(2)
        self.assertTrue(self.h.wait_for(lambda: not self.preview.property('loading') and self.preview.property('page') == 2, 10000))
        self.assertNotEqual(self.preview.property('imageUrl'), url)
        self.preview.setPage(9)
        self.h.pump(30)
        self.assertEqual(self.preview.property('page'), 2, 'out of range is ignored')
        self.preview.setSelection([])
        self.preview.setSelection([str(self.root / 'tesis.pdf')])
        self.assertTrue(self.h.wait_for(lambda: not self.preview.property('loading') and self.preview.property('page') == 1, 10000),
                        'a new selection starts on the first page')

    def test_video_length_codec_and_size(self):
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=duration=3:size=320x240:rate=10',
                        '-pix_fmt', 'yuv420p', str(self.root / 'clip.mp4')], check=True)
        meta = self.show('clip.mp4', ms=10000)
        self.assertEqual(self.preview.property('kind'), 'video')
        self.assertTrue(self.preview.property('mediaUrl').endswith('/clip.mp4'))
        self.assertEqual(meta['Duración'], '0:03 · H264 · 320 × 240')
        poster = self.preview.property('posterUrl')
        self.assertTrue(poster.endswith('.png') and Path(poster[7:]).is_file(), poster)

    def test_folder_summary(self):
        folder = self.root / 'clases'
        (folder / 'sub').mkdir(parents=True)
        (folder / 'a.png').write_bytes(b'x' * 1000)
        (folder / 'b.txt').write_bytes(b'x' * 500)
        meta = self.show('clases')
        self.assertEqual(self.preview.property('mode'), 'folder')
        self.assertEqual(meta['Contiene'], '1 carpeta · 2 archivos')
        self.assertEqual(meta['Tamaño'], '1,5 KB')
        self.assertEqual(meta['Imágenes'], '1')

    def test_multi_selection_summary(self):
        for name in ('a.jpg', 'b.png', 'c.pdf'):
            (self.root / name).write_bytes(b'x' * 1024)
        meta = self.show('a.jpg', 'b.png', 'c.pdf')
        self.assertEqual(self.preview.property('mode'), 'multi')
        self.assertEqual(self.preview.property('name'), '3 elementos')
        self.assertEqual(meta['Tamaño'], '3,0 KB')
        self.assertEqual(meta['Tipos'], '2 imágenes · 1 PDF')

    def test_file_without_preview(self):
        (self.root / 'r.zip').write_bytes(b'PK')
        self.show('r.zip')
        self.assertEqual(self.preview.property('kind'), '')
        self.assertEqual(self.preview.property('mode'), 'file')
        self.assertEqual(self.preview.property('subtitle'), 'Archivo comprimido · 2 B')

    def test_binary_text_has_no_preview(self):
        (self.root / 'b.txt').write_bytes(b'abc\0def')
        self.show('b.txt')
        self.assertEqual(self.preview.property('kind'), '')

    def test_only_the_latest_selection_shows(self):
        (self.root / 'a.txt').write_text('A')
        (self.root / 'b.txt').write_text('B')
        self.preview.setSelection([str(self.root / 'a.txt')])
        self.show('b.txt')
        self.h.pump(300)
        self.assertEqual(self.preview.property('text'), 'B')

    def test_empty_selection_clears(self):
        (self.root / 'a.txt').write_text('A')
        self.show('a.txt')
        self.preview.setSelection([])
        self.h.pump(50)
        self.assertEqual(self.preview.property('mode'), 'none')
        self.assertEqual(self.preview.property('text'), '')


if __name__ == '__main__':
    unittest.main()
