"""The runnable gallery: every page loads without QML warnings, --shot works for every palette, every exported
component appears on some page, and page/axis transitions run clean."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

GALLERY = ROOT / 'apps/qml/gallery'
LIBRARY = ROOT / 'apps/qml/WysunM3'


class GalleryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from types import SimpleNamespace
        from wysun_qml import gallery
        cls.h = support.Harness.get()          # shares the application; the gallery gets its own engine
        cls.warnings = []
        from PySide6 import QtQuick  # noqa: F401  (QQuickItem* properties convert once QtQuick is loaded)
        from PySide6.QtQml import QQmlApplicationEngine
        engine = QQmlApplicationEngine()
        engine.warnings.connect(lambda errors: cls.warnings.extend(e.toString() for e in errors))
        for path in bootstrap.configure_qt():
            engine.addImportPath(str(path))
        options = SimpleNamespace(page='theme', palette='default', mode='dark', width=1000, height=760,
                                  bench=False, reduced_motion=True)
        cls.app, cls.engine, cls.window, cls.controller = gallery.build(options, (cls.h.app, engine))
        cls.h.pump(100)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.window.deleteLater()
        cls.engine.deleteLater()
        cls.h.pump()
        support.Harness.get().close_views()

    def setUp(self):
        self.warnings.clear()

    def test_every_page_loads_without_warnings(self):
        from wysun_qml import gallery
        for page in gallery.PAGES:
            with self.subTest(page=page):
                self.h.call(self.window, 'showPage', page)
                self.h.pump(60)
                self.assertEqual(self.window.property('page'), page)
                self.assertIsNotNone(self.window.property('currentPage'))
                self.assertEqual(self.warnings, [])

    def test_palette_and_mode_switch_live(self):
        for name in ('green', 'orange', 'blue', 'default', 'live'):
            for mode in ('light', 'dark'):
                self.controller.setPalette(name)
                self.controller.setMode(mode)
                self.h.pump(20)
                self.assertEqual(self.controller.property('mode'), mode)
        self.assertEqual(self.warnings, [])

    def test_shared_axis_steps_without_errors(self):
        self.h.call(self.window, 'showPage', 'motion')
        self.h.pump(60)
        bridge = self.controller._bridge             # the gallery's own ThemeBridge
        bridge.setReducedMotion(False)
        page = self.window.property('currentPage')
        for forward in (True, False, True):
            self.assertIsNotNone(self.h.call(page, 'axisStep', forward))
            self.h.pump(50)
        self.h.pump(1500)
        bridge.setReducedMotion(True)
        self.assertEqual(self.warnings, [])

    def test_gallery_covers_every_exported_component(self):
        qmldir = (LIBRARY / 'qmldir').read_text()
        exported = re.findall(r'^(?!internal|singleton|module)(\w+)\s+[\d.]+\s+\S+\.qml\s*$', qmldir, re.M)
        self.assertGreater(len(exported), 30)
        text = '\n'.join(p.read_text() for p in GALLERY.rglob('*.qml'))
        missing = [name for name in exported if not re.search(r'\b' + name + r'(\s+on\s+[\w.]+)?\s*\{', text)]
        self.assertEqual(missing, [], 'components without a gallery sample')


class ShotTests(unittest.TestCase):
    def test_shot_for_every_palette(self):
        out = Path.home() / '.cache/wysun-fase1/tmp/gallery-shots'
        out.mkdir(parents=True, exist_ok=True)
        from PySide6.QtGui import QImage
        for palette in ('default', 'green', 'orange', 'blue'):
            for mode in ('light', 'dark'):
                with self.subTest(palette=palette, mode=mode):
                    target = out / f'{palette}-{mode}.png'
                    target.unlink(missing_ok=True)
                    result = support.run_in_venv(['-P', '-m', 'wysun_qml', '--page', 'buttons', '--palette', palette,
                                                  '--mode', mode, '--width', '700', '--height', '500', '--shot', str(target)])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn('qml:', result.stderr)
                    image = QImage(str(target))
                    self.assertEqual((image.width(), image.height()), (700, 500))
                    colours = {image.pixel(x, y) for x in range(0, 700, 10) for y in range(0, 500, 10)}
                    self.assertGreater(len(colours), 10)


if __name__ == '__main__':
    unittest.main()
