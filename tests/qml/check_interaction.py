"""StateLayer (8/12/12/16 %), FocusRing (keyboard only) and Surface (tonal elevation, outline, disabled)."""
from pathlib import Path
import sys
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
        self.h.bridge.setReducedMotion(True)         # states settle at once; the animation has its own tests
        self.h.pump()

    def tearDown(self):
        self.h.bridge.setReducedMotion(None)
        self.h.close_views()

    def child(self, view, name):
        return view.rootObject().findChild(self.QObject, name)

    def colours(self, name):
        return support.palettes()[name]['colours']


class StateLayerTests(Base):
    BODY = ('Rectangle { anchors.fill: parent; color: Theme.m3surface\n'
            '  StateLayer { id: sl; objectName: "sl"; ripple: false } }')

    def expect(self, image, palette, alpha, msg):
        c = self.colours(palette)
        support.close_to(self, self.h.pixel(image, 50, 30), support.blend(c['onSurface'], c['surface'], alpha), msg=msg)

    def test_the_four_state_opacities_on_every_palette(self):
        for palette in ('default-dark', 'green-light', 'orange-dark', 'blue-light'):
            with self.subTest(palette=palette):
                self.h.use(palette)
                view = self.h.view(self.BODY, 100, 60)
                layer = self.child(view, 'sl')
                self.expect(self.h.grab(view), palette, 0, 'idle')
                self.h.move(view, 50, 30)
                self.assertTrue(layer.property('hovered'))
                self.expect(self.h.grab(view), palette, 0.08, 'hover')
                self.h.press(view, 50, 30)
                self.assertTrue(layer.property('pressed'))
                self.expect(self.h.grab(view), palette, 0.12, 'pressed')
                self.h.release(view, 50, 30)
                self.h.move(view, 500, 500)
                layer.setProperty('focused', True)
                self.h.pump()
                self.expect(self.h.grab(view), palette, 0.12, 'focus')
                layer.setProperty('dragged', True)
                self.h.pump()
                self.expect(self.h.grab(view), palette, 0.16, 'dragged')
                self.h.close_views()

    def test_states_do_not_stack(self):
        self.h.use('default-dark')
        view = self.h.view(self.BODY, 100, 60)
        layer = self.child(view, 'sl')
        layer.setProperty('focused', True)
        self.h.move(view, 50, 30)
        self.h.press(view, 50, 30)
        self.expect(self.h.grab(view), 'default-dark', 0.12, 'hover+focus+pressed is just 12 %')

    def test_disabled_has_no_layer_and_does_not_react(self):
        self.h.use('green-light')
        view = self.h.view(self.BODY, 100, 60)
        layer = self.child(view, 'sl')
        layer.setProperty('disabled', True)
        self.h.move(view, 50, 30)
        self.h.press(view, 50, 30)
        self.assertFalse(layer.property('pressed'))
        self.expect(self.h.grab(view), 'green-light', 0, 'disabled')

    def test_clicked_is_emitted_with_the_mouse(self):
        view = self.h.view('property int clicks: 0\nStateLayer { objectName: "sl"; ripple: false; onClicked: root.clicks += 1 }', 100, 60)
        self.h.click(view, 50, 30)
        self.assertEqual(view.rootObject().property('clicks'), 1)

    def test_ripple_grows_from_the_press_point_and_stays_inside_the_rounded_corners(self):
        self.h.use('default-dark')
        body = ('Rectangle { anchors.fill: parent; color: Theme.m3surface\n'
                '  Item { width: 100; height: 40; StateLayer { id: sl; objectName: "sl"; radius: 20; ripple: true } } }')
        view = self.h.view(body, 140, 40)
        self.h.bridge.setReducedMotion(False)
        self.h.pump()
        c = self.colours('default-dark')
        self.h.press(view, 20, 20)
        self.h.pump(900)                       # long enough for the ripple to cover the whole layer
        image = self.h.grab(view)
        support.close_to(self, self.h.pixel(image, 50, 20), support.blend(c['onSurface'], c['surface'], 0.12), tolerance=3,
                         msg='hover 8 % + ripple add up to the 12 % pressed state, not more')
        support.close_to(self, self.h.pixel(image, 0, 0), c['surface'], msg='outside the rounded corner stays untouched')
        support.close_to(self, self.h.pixel(image, 99, 39), c['surface'], msg='outside the rounded corner stays untouched')
        self.h.release(view, 20, 20)
        self.h.move(view, 130, 20)            # leave the layer (a move outside the window sends no hover leave)
        self.h.pump(900)
        support.close_to(self, self.h.pixel(self.h.grab(view), 50, 20), c['surface'], tolerance=3, msg='the ripple fades after release')


class FocusRingTests(Base):
    BODY = ('Rectangle { id: btn; objectName: "btn"; x: 20; y: 15; width: 60; height: 30; radius: 8; color: Theme.m3primary\n'
            '  focusPolicy: Qt.TabFocus\n'
            '  FocusRing { id: ring; objectName: "ring"; target: btn } }')

    def ring_pixel(self, view):
        # mid-way through the ring, left of the control: 2 px gap + half of the 3 px ring
        return self.h.pixel(self.h.grab(view), 20 - 2 - 2, 30)

    def test_ring_shows_for_keyboard_focus_only(self):
        self.h.use('green-light')
        view = self.h.view(self.BODY, 100, 60)
        c = self.colours('green-light')
        self.h.click(view, 50, 30)
        self.assertFalse(self.child(view, 'btn').property('activeFocus'), 'a mouse click does not focus a tab-focus item')
        support.close_to(self, self.ring_pixel(view), support.hex_of(self.h.pixel(self.h.grab(view), 2, 2)), msg='no ring after a click')
        self.h.key(view, 0x01000001)           # Qt.Key_Tab
        self.assertTrue(self.child(view, 'btn').property('activeFocus'))
        support.close_to(self, self.ring_pixel(view), c['secondary'], msg='ring after Tab')

    def test_ring_follows_the_corner_radius_and_hides_with_focus(self):
        self.h.use('orange-dark')
        view = self.h.view(self.BODY, 100, 60)
        self.h.key(view, 0x01000001)
        ring = self.child(view, 'ring')
        self.assertEqual(ring.property('visible'), True)
        view.rootObject().forceActiveFocus()
        self.h.pump()
        self.assertFalse(ring.property('visible'))


class SurfaceTests(Base):
    def test_tonal_elevation_is_monotonic_and_level_zero_is_the_container(self):
        self.h.use('green-light')
        body = ('Row { spacing: 0\n' + ''.join(
            f'  Surface {{ width: 20; height: 20; level: {level}; container: Theme.m3surfaceContainerLow }}\n' for level in range(6)) + '}')
        view, image = self.h.render(body, 120, 20)
        c = self.colours('green-light')
        support.close_to(self, self.h.pixel(image, 10, 10), c['surfaceContainerLow'], msg='level 0')
        distances = []
        base = self.h.pixel(image, 10, 10)
        for level in range(6):
            p = self.h.pixel(image, level * 20 + 10, 10)
            distances.append(abs(p.red() - base.red()) + abs(p.green() - base.green()) + abs(p.blue() - base.blue()))
        self.assertEqual(distances, sorted(distances))
        self.assertGreater(distances[5], distances[1])

    def test_outline_draws_a_border_in_the_outline_colour(self):
        self.h.use('blue-dark')
        view, image = self.h.render('Surface { x: 10; y: 10; width: 40; height: 30; outline: 1; outlineColor: Theme.m3outline; container: Theme.m3surface }', 60, 50)
        c = self.colours('blue-dark')
        support.close_to(self, self.h.pixel(image, 10, 25), c['outline'], msg='left border')
        support.close_to(self, self.h.pixel(image, 30, 25), c['surface'], msg='inside')

    def test_disabled_container_is_ten_percent_of_on_surface_and_content_is_38(self):
        self.h.use('orange-light')
        body = ('Rectangle { anchors.fill: parent; color: Theme.m3surface\n'
                '  Surface { id: s; objectName: "s"; anchors.fill: parent; disabled: true } }')
        view, image = self.h.render(body, 60, 40)
        c = self.colours('orange-light')
        support.close_to(self, self.h.pixel(image, 30, 20), support.blend(c['onSurface'], c['surface'], 0.10), msg='disabled container')
        self.assertAlmostEqual(self.child(view, 's').property('contentOpacity'), 0.38, places=2)

    def test_an_enabled_surface_keeps_its_content_opaque(self):
        view = self.h.view('Surface { id: s; objectName: "s"; width: 10; height: 10 }', 20, 20)
        self.assertEqual(self.child(view, 's').property('contentOpacity'), 1)

    def test_shadow_is_drawn_below_raised_surfaces_only(self):
        self.h.use('default-light')
        raised = ('Rectangle { anchors.fill: parent; color: Theme.m3surface\n'
                  '  Surface { x: 20; y: 10; width: 40; height: 20; level: 3; container: Theme.m3surfaceContainerHigh } }')
        flat = raised.replace('level: 3', 'level: 0')
        c = self.colours('default-light')
        below = lambda image: self.h.pixel(image, 40, 10 + 20 + 3)       # just under the surface
        _, with_shadow = self.h.render(raised, 80, 50)
        self.h.close_views()
        _, without = self.h.render(flat, 80, 50)
        self.assertNotEqual(support.hex_of(below(with_shadow)), support.hex_of(below(without)))
        support.close_to(self, below(without), c['surface'], msg='no shadow at level 0')


if __name__ == '__main__':
    unittest.main()
