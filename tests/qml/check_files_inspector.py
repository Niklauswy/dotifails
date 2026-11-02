"""Wysun Files' inspector and expanded preview in the QML window (venv Python, offscreen): shown by itself on wide
windows when something is selected, Ctrl+I, Markdown view ⇄ source with links that navigate, Space for the
expanded view with ← / → and Escape, one media player that stops when the file changes, «Seguir en Wysun
Player», and a broken picture that keeps the selection (F-50…F-55)."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402


class InspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QSettings, Qt
        from PySide6.QtGui import QColor, QImage
        from wysun_files.quick.window import QmlFilesWindow
        cls.Qt = Qt
        cls.h = support.Harness.get()
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        cls.tmp = tempfile.TemporaryDirectory(prefix='files-insp-', dir=scratch)
        cls.root = Path(cls.tmp.name) / 'casa'
        (cls.root / 'docs').mkdir(parents=True)
        (cls.root / 'docs/tema.md').write_text('# Tema')
        for name, colour in (('a.png', '#aa3311'), ('b.png', '#1133aa')):
            image = QImage(80, 60, QImage.Format_RGB32)
            image.fill(QColor(colour))
            image.save(str(cls.root / name))
        (cls.root / 'roto.png').write_bytes(b'nope')
        (cls.root / 'notas.md').write_text('# Notas\n\nVer [el tema](docs/tema.md).\n')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=duration=4:size=160x120:rate=10',
                        '-pix_fmt', 'yuv420p', str(cls.root / 'clip.mp4')], check=True)
        cls.win = QmlFilesWindow([str(cls.root)], settings=QSettings(str(Path(cls.tmp.name) / 's.ini'), QSettings.IniFormat),
                                 thumbnails=False)
        cls.warnings = []
        cls.win.engine.warnings.connect(lambda errors: cls.warnings.extend(e.toString() for e in errors))
        cls.win.bridge.setReducedMotion(True)
        cls.window = cls.win.window
        cls.win.present()
        cls.window.resize(1280, 800)
        cls.files, cls.preview = cls.win.files, cls.win.preview
        cls.order = cls.files.settings
        cls.h.pump(100)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.win.close()
        cls.h.pump(30)
        cls.tmp.cleanup()

    def setUp(self):
        self.files.setInspector(True)
        self.window.resize(1280, 800)
        if self.window.property('expanded'):
            self.h.call(self.window, 'closePreview')
        self.tab().navigate(str(self.root))
        self.model().sortBy('name', False)
        self.assertTrue(self.h.wait_for(lambda: not self.model().property('loading'), 3000))
        self.model().clearSelection()
        self.warnings.clear()
        self.h.pump(50)

    def tab(self):
        return self.files.property('current')

    def model(self):
        return self.tab().property('model')

    def find(self, name):
        return self.h.find_in(self.window.contentItem(), name)

    def select(self, name):
        self.model().selectPaths([str(self.root / name)])
        self.assertTrue(self.h.wait_for(lambda: not self.preview.property('loading')
                                        and self.preview.property('paths') == [str(self.root / name)], 8000))
        self.h.pump(300)

    def player(self):
        from PySide6.QtCore import QObject
        found = self.window.findChild(QObject, 'mediaPlayer') or self.window.contentItem().findChild(QObject, 'mediaPlayer')
        self.assertIsNotNone(found, 'no MediaPlayer')
        return found

    def test_shown_with_a_selection_on_wide_windows_only(self):
        self.assertFalse(self.window.property('inspectorShown'))
        self.select('a.png')
        self.assertTrue(self.window.property('inspectorShown'))
        self.assertEqual(self.find('inspectorName').property('text'), 'a.png')
        self.window.resize(900, 800)
        self.h.pump(50)
        self.assertFalse(self.window.property('inspectorShown'))
        self.assertEqual(self.warnings, [])

    def test_ctrl_i_toggles_and_persists(self):
        self.select('a.png')
        self.h.key(self.window, self.Qt.Key_I, self.Qt.ControlModifier, 'i')
        self.assertFalse(self.files.property('inspector'))
        self.assertFalse(self.window.property('inspectorShown'))
        self.h.key(self.window, self.Qt.Key_I, self.Qt.ControlModifier, 'i')
        self.assertTrue(self.window.property('inspectorShown'))

    def test_markdown_view_source_and_links(self):
        self.select('notas.md')
        body = self.find('previewBody')
        self.assertIn('<h1', self.preview.property('html'))
        self.assertFalse(self.find('inspector').property('showingSource'))
        chip = self.find('sourceChip')
        from PySide6.QtCore import QPointF
        point = chip.mapToScene(QPointF(chip.width() / 2, chip.height() / 2))
        self.h.click(self.window, point.x(), point.y())
        self.assertTrue(self.find('inspector').property('showingSource'))
        self.assertIn('[el tema](docs/tema.md)', body.property('text'))
        self.h.call(self.window, 'followLink', 'docs/tema.md')
        self.assertTrue(self.h.wait_for(lambda: self.tab().property('path') == str(self.root / 'docs')
                                        and self.model().property('selectedPaths') == [str(self.root / 'docs/tema.md')], 3000))

    def test_space_expands_and_arrows_walk_the_pictures(self):
        self.select('a.png')
        self.h.call(self.window, 'focusFiles')
        self.h.key(self.window, self.Qt.Key_Space, text=' ')
        self.assertTrue(self.window.property('expanded'))
        self.assertTrue(self.h.wait_for(lambda: self.find('expandedPreview').property('opacity') == 1, 1000))
        self.h.key(self.window, self.Qt.Key_Right)
        self.assertTrue(self.h.wait_for(lambda: self.preview.property('name') == 'b.png', 3000))
        self.h.key(self.window, self.Qt.Key_Plus, text='+')
        self.assertGreater(self.find('expandedPreview').property('zoom'), 1)
        self.h.key(self.window, self.Qt.Key_Escape)
        self.assertFalse(self.window.property('expanded'))

    def click(self, item):
        from PySide6.QtCore import QPointF
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        self.h.click(self.window, point.x(), point.y())

    def test_the_preview_takes_the_height_left_by_the_information(self):
        self.select('a.png')
        pane = self.find('previewPicture')
        self.assertGreater(pane.height(), self.find('inspector').height() * 0.5)
        self.assertIsNone(self.find('expandButton'), 'no «Ampliar»: «Abrir» opens the app')

    def test_a_click_on_the_path_copies_it_whole(self):
        from PySide6.QtGui import QGuiApplication
        self.select('a.png')
        self.click(self.find('pathRow'))
        self.assertEqual(QGuiApplication.clipboard().text(), str(self.root / 'a.png'))

    def test_open_sends_a_picture_to_the_player_and_media_from_its_second(self):
        from wysun_files.quick import operations, preview as module
        self.select('a.png')
        self.assertEqual(self.find('openButton').property('text'), 'Abrir')
        self.assertEqual(self.find('openButton').property('icon'), '')
        with patch.object(operations, 'launch') as launch:
            self.click(self.find('openButton'))
        launch.assert_called_once_with([str(self.root / 'a.png')])
        self.select('clip.mp4')
        with patch.object(module, 'launch') as launch:
            self.click(self.find('openButton'))
        self.assertEqual(launch.call_args.args[0], [str(self.root / 'clip.mp4')])
        self.assertIn('start', launch.call_args.kwargs)

    def test_no_panel_for_folders(self):
        self.model().selectPaths([str(self.root / 'docs')])
        self.h.pump(50)
        self.assertFalse(self.window.property('inspectorShown'))

    def test_broken_picture(self):
        self.select('roto.png')
        self.assertEqual(self.model().property('selectedPaths'), [str(self.root / 'roto.png')])
        self.assertTrue(self.find('previewBroken').property('visible'))

    def test_one_player_that_stops_when_the_file_changes(self):
        self.select('clip.mp4')
        player = self.player()
        self.assertTrue(player.property('source').toString().endswith('clip.mp4'))
        self.assertTrue(self.h.wait_for(lambda: player.property('duration') > 0, 5000))
        player.play()
        self.assertTrue(self.h.wait_for(lambda: self.window.property('mediaState') == 1, 3000))
        from wysun_files.quick import preview as module
        with patch.object(module, 'launch') as launch:
            self.preview.continueInPlayer(str(self.root / 'clip.mp4'), 1.5)
        launch.assert_called_once_with([str(self.root / 'clip.mp4')], start=1.5)
        self.select('a.png')
        self.assertEqual(self.window.property('mediaState'), 0)
        self.assertEqual(player.property('source').toString(), '')


if __name__ == '__main__':
    unittest.main()
