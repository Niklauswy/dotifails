"""Chips, badge, divider, linear/circular progress and the expressive shape emblem."""
from pathlib import Path
import sys
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402


def tearDownModule():
    support.Harness.get().close_views()


class Base(unittest.TestCase):
    def setUp(self):
        from PySide6.QtCore import QObject
        self.QObject = QObject
        self.h = support.Harness.get()
        self.h.bridge.setPreview(None)
        self.h.bridge.setReducedMotion(True)
        self.h.pump()

    def tearDown(self):
        self.h.bridge.setReducedMotion(None)
        self.h.close_views()

    def child(self, view, name):
        return view.rootObject().findChild(self.QObject, name)

    def colours(self, name):
        return support.palettes()[name]['colours']

    def on_surface(self, body, width=240, height=80):
        return self.h.view('Rectangle { anchors.fill: parent; color: Theme.m3surface }\n' + body, width, height)


class ChipTests(Base):
    def test_height_corner_and_outline(self):
        self.h.use('default-light')
        c = self.colours('default-light')
        view = self.on_surface('Chip { objectName: "c"; x: 10; y: 10; kind: "assist"; text: "Compartir"; icon: "share" }')
        chip = self.child(view, 'c')
        self.assertEqual(chip.property('height'), 32)
        self.assertEqual(chip.property('radius'), self.h.theme('rounding')['small'])
        self.assertEqual(chip.property('iconSize'), 18)
        image = self.h.grab(view)
        support.close_to(self, self.h.pixel(image, 10 + chip.property('width') / 2, 10), c['outlineVariant'], msg='outline')

    def test_filter_chip_selected_shows_check(self):
        self.h.use('orange-dark')
        c = self.colours('orange-dark')
        view = self.on_surface('Chip { objectName: "c"; x: 10; y: 10; kind: "filter"; text: "Imágenes" }')
        chip = self.child(view, 'c')
        self.assertEqual(chip.property('leadingIcon'), '')
        width = chip.property('width')
        self.h.click(view, 30, 26)
        self.h.move(view, 230, 75)
        self.assertTrue(chip.property('selected'))
        self.assertEqual(chip.property('leadingIcon'), 'check')
        self.assertGreater(chip.property('width'), width, 'the check makes room for itself')
        self.assertEqual(chip.property('outline'), 0)
        support.close_to(self, self.h.pixel(self.h.grab(view), 10 + chip.property('width') / 2, 12), c['secondaryContainer'], msg='selected')

    def test_input_chip_remove_emits(self):
        view = self.on_surface('property int removed: 0\n'
                               'Chip { objectName: "c"; x: 10; y: 10; kind: "input"; text: "foto.png"; onRemoved: root.removed += 1 }')
        chip = self.child(view, 'c')
        right = 10 + chip.property('width') - 14
        self.h.click(view, right, 26)
        self.assertEqual(view.rootObject().property('removed'), 1)

    def test_assist_chip_click(self):
        view = self.on_surface('property int clicks: 0\n'
                               'Chip { x: 10; y: 10; text: "Abrir"; onClicked: root.clicks += 1 }')
        self.h.click(view, 30, 26)
        self.assertEqual(view.rootObject().property('clicks'), 1)


class BadgeTests(Base):
    def test_dot_and_pill(self):
        self.h.use('green-light')
        c = self.colours('green-light')
        view = self.on_surface('Badge { objectName: "dot"; x: 10; y: 10 }\n'
                               'Badge { objectName: "n"; x: 40; y: 10; count: 3 }\n'
                               'Badge { objectName: "big"; x: 80; y: 10; count: 1200 }')
        dot = self.child(view, 'dot')
        self.assertEqual((dot.property('width'), dot.property('height')), (6, 6))
        self.assertEqual(self.child(view, 'n').property('height'), 16)
        self.assertEqual(self.child(view, 'n').property('label'), '3')
        support.close_to(self, self.h.pixel(self.h.grab(view), 13, 13), c['error'], msg='badge colour')

    def test_badge_99_plus(self):
        view = self.on_surface('Badge { objectName: "b"; count: 100 }')
        self.assertEqual(self.child(view, 'b').property('label'), '99+')


class DividerTests(Base):
    def test_insets_and_colour(self):
        self.h.use('blue-dark')
        c = self.colours('blue-dark')
        view = self.on_surface('Divider { objectName: "d"; y: 10; width: 200 }\n'
                               'Divider { objectName: "s"; y: 20; width: 200; inset: "start" }\n'
                               'Divider { objectName: "b"; y: 30; width: 200; inset: "both" }')
        image = self.h.grab(view)
        self.assertEqual(self.child(view, 'd').property('height'), 1)
        support.close_to(self, self.h.pixel(image, 2, 10), c['outlineVariant'])
        support.close_to(self, self.h.pixel(image, 2, 20), c['surface'], msg='start inset')
        support.close_to(self, self.h.pixel(image, 20, 20), c['outlineVariant'])
        support.close_to(self, self.h.pixel(image, 198, 20), c['outlineVariant'], msg='start inset keeps the end')
        support.close_to(self, self.h.pixel(image, 198, 30), c['surface'], msg='both insets')


class ProgressTests(Base):
    def test_linear_height_and_proportional_fill(self):
        self.h.use('default-dark')
        c = self.colours('default-dark')
        for value in (0.25, 0.5, 1.0):
            with self.subTest(value=value):
                view = self.on_surface(f'LinearProgress {{ objectName: "p"; x: 10; y: 10; width: 200; value: {value} }}')
                bar = self.child(view, 'p')
                self.assertEqual(bar.property('height'), 4)
                image = self.h.grab(view)
                end = 10 + 200 * value
                support.close_to(self, self.h.pixel(image, end - 4, 12), c['primary'], msg='indicator up to the value')
                if value < 1:
                    support.close_to(self, self.h.pixel(image, min(end + 10, 205), 12), c['secondaryContainer'], msg='track after it')
                self.h.close_views()

    def test_indeterminate_animates_and_stops_when_hidden(self):
        self.h.bridge.setReducedMotion(False)
        self.h.pump()
        view = self.on_surface('LinearProgress { objectName: "p"; width: 200; indeterminate: true }\n'
                               'CircularProgress { objectName: "c"; x: 120; y: 10; indeterminate: true }')
        bar = self.child(view, 'p')
        circle = self.child(view, 'c')
        self.assertTrue(bar.property('animating'))
        self.assertTrue(circle.property('animating'))
        bar.setProperty('visible', False)
        circle.setProperty('visible', False)
        self.h.pump()
        self.assertFalse(bar.property('animating'))
        self.assertFalse(circle.property('animating'))

    def test_indeterminate_is_still_with_reduced_motion(self):
        view = self.on_surface('LinearProgress { objectName: "p"; width: 200; indeterminate: true }')
        self.assertFalse(self.child(view, 'p').property('animating'))

    def test_circular_progress_renders_with_shapes(self):
        self.h.use('green-dark')
        c = self.colours('green-dark')
        view = self.on_surface('CircularProgress { objectName: "c"; x: 10; y: 10; value: 0.25 }', 100, 100)
        circle = self.child(view, 'c')
        self.assertEqual((circle.property('width'), circle.property('height')), (48, 48))
        image = self.h.grab(view)
        # A quarter from 12 o'clock clockwise: the indicator covers the upper right, the track the lower left.
        support.close_to(self, self.h.pixel(image, 10 + 24 + 16, 10 + 24 - 16), c['primary'], tolerance=40, msg='indicator')
        support.close_to(self, self.h.pixel(image, 10 + 24 - 16, 10 + 24 + 16), c['secondaryContainer'], tolerance=40, msg='track')
        support.close_to(self, self.h.pixel(image, 10 + 24, 10 + 24), c['surface'], msg='hollow centre')


class EmblemTests(Base):
    def test_emblem_cookie_with_m3shapes(self):
        self.h.use('default-light')
        c = self.colours('default-light')
        view = self.on_surface('ShapeEmblem { objectName: "e"; x: 10; y: 10; size: 56; shape: "cookie"; '
                               'color: Theme.m3primaryContainer }', 100, 100)
        emblem = self.child(view, 'e')
        self.h.wait_for(lambda: emblem.property('usingShapes') is not None)
        if not emblem.property('usingShapes'):
            self.skipTest('M3Shapes is not in this runtime')
        from PySide6.QtQuick import QQuickWindow
        if QQuickWindow.sceneGraphBackend() == 'software':
            # MaterialShape draws with its own geometry node, which the offscreen software renderer skips: check
            # what it was told to draw (the real window check of the gallery covers the pixels).
            body = emblem.findChild(self.QObject, 'emblemShape')
            self.assertIsNotNone(body)
            support.close_to(self, body.property('color'), c['primaryContainer'], msg='shape colour')
            self.assertEqual(body.property('shapeName'), 'Cookie9Sided')
            return
        image = self.h.grab(view)
        support.close_to(self, self.h.pixel(image, 10 + 28, 10 + 28), c['primaryContainer'], msg='filled centre')
        support.close_to(self, self.h.pixel(image, 11, 11), c['surface'], msg='the cookie is not a square')

    def test_emblem_falls_back_without_m3shapes(self):
        script = textwrap.dedent('''
            import sys
            from wysun_qml import bootstrap
            bootstrap.preload_qt()
            from qml import support
            h = support.Harness.get()
            h.engine.setImportPathList([p for p in h.engine.importPathList() if '/deps/' not in p])
            h.bridge.setReducedMotion(True)
            from PySide6.QtCore import QObject
            view = h.view('ShapeEmblem { objectName: "e"; size: 56; shape: "cookie" }', 80, 80)
            e = view.rootObject().findChild(QObject, 'e')
            h.wait_for(lambda: e.property('usingShapes') is not None)
            print('USING', e.property('usingShapes'), 'RADIUS', e.property('fallbackRadius'))
            h.close_views()
        ''')
        result = support.run_in_venv(['-c', script])
        self.assertIn('USING False', result.stdout, result.stdout + result.stderr)
        self.assertIn('RADIUS 28', result.stdout)
        self.assertLessEqual(result.stderr.count('ShapeEmblem'), 1, 'the warning appears once')

    def test_content_is_centred_on_the_emblem(self):
        view = self.on_surface('ShapeEmblem { objectName: "e"; size: 56; icon: "folder" }', 100, 100)
        emblem = self.child(view, 'e')
        self.assertEqual(emblem.property('width'), 56)
        self.assertEqual(emblem.property('icon'), 'folder')


if __name__ == '__main__':
    unittest.main()
