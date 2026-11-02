"""Buttons, icon buttons, FABs and segmented buttons: M3 measures, role colours, morph, keyboard and toggles."""
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
        from PySide6.QtCore import QObject, Qt
        self.QObject = QObject
        self.Qt = Qt
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

    def on_surface(self, body, width=200, height=80):
        return self.h.view('Rectangle { anchors.fill: parent; color: Theme.m3surface }\n' + body, width, height)


class ButtonTests(Base):
    def test_a_wide_button_centres_its_text(self):
        view = self.on_surface('Button { objectName: "b"; width: 180; text: "Abrir" }')
        button = self.h.find(view, 'b')
        natural = button.property('implicitWidth')
        self.assertAlmostEqual(button.property('contentX'), (180 - (natural - 48)) / 2, delta=1)

    def test_height_and_label_role(self):
        view = self.on_surface('Button { objectName: "b"; text: "Guardar" }')
        button = self.child(view, 'b')
        self.assertEqual(button.property('implicitHeight'), 40)
        self.assertEqual(button.property('height'), 40)
        self.assertGreater(button.property('width'), 48)

    def test_container_and_content_colours_by_type(self):
        expected = {'filled': ('primary', 'onPrimary'), 'tonal': ('secondaryContainer', 'onSecondaryContainer'),
                    'outlined': (None, 'primary'), 'text': (None, 'primary'), 'elevated': ('surfaceContainerLow', 'primary')}
        for palette in ('default-light', 'orange-dark'):
            self.h.use(palette)
            c = self.colours(palette)
            for kind, (container, content) in expected.items():
                with self.subTest(palette=palette, type=kind):
                    view = self.on_surface(f'Button {{ objectName: "b"; x: 10; y: 10; type: "{kind}"; text: "Guardar" }}')
                    button = self.child(view, 'b')
                    support.close_to(self, button.property('contentColor'), c[content], msg='content')
                    pixel = self.h.pixel(self.h.grab(view), 10 + 20, 10 + 3)      # inside, above the label
                    if container is None:
                        support.close_to(self, pixel, c['surface'], msg='no container')
                    elif kind == 'elevated':
                        self.assertNotEqual(support.hex_of(pixel), '#' + c['surface'], 'elevated has its own container')
                    else:
                        support.close_to(self, pixel, c[container], msg='container')
                    self.h.close_views()

    def test_outlined_has_one_pixel_outline(self):
        self.h.use('green-light')
        c = self.colours('green-light')
        view = self.on_surface('Button { objectName: "b"; x: 10; y: 10; type: "outlined"; text: "Guardar" }')
        button = self.child(view, 'b')
        self.assertEqual(button.property('outline'), 1)
        image = self.h.grab(view)
        x = 10 + button.property('width') / 2
        support.close_to(self, self.h.pixel(image, x, 10), c['outline'], msg='top edge')
        support.close_to(self, self.h.pixel(image, x, 12), c['surface'], msg='inside')

    def test_disabled_ten_and_thirty_eight_percent(self):
        self.h.use('blue-light')
        c = self.colours('blue-light')
        view = self.on_surface('Button { objectName: "b"; x: 10; y: 10; type: "filled"; text: "Guardar"; disabled: true }')
        button = self.child(view, 'b')
        support.close_to(self, self.h.pixel(self.h.grab(view), 30, 13), support.blend(c['onSurface'], c['surface'], 0.10), msg='container 10 %')
        content = button.property('contentColor')
        self.assertAlmostEqual(content.alphaF(), 0.38, delta=0.01)

    def test_press_morphs_corner(self):
        view = self.on_surface('Button { objectName: "b"; x: 10; y: 10; text: "Guardar" }')
        button = self.child(view, 'b')
        self.assertEqual(button.property('radius'), 20)
        self.h.move(view, 40, 30)
        self.h.press(view, 40, 30)
        self.assertEqual(button.property('radius'), self.h.theme('rounding')['small'])
        self.h.release(view, 40, 30)
        self.assertEqual(button.property('radius'), 20)

    def test_keyboard_activation(self):
        view = self.on_surface('property int clicks: 0\n'
                               'Button { objectName: "b"; text: "Guardar"; onClicked: root.clicks += 1 }')
        button = self.child(view, 'b')
        button.forceActiveFocus(self.Qt.TabFocusReason)
        self.h.key(view, self.Qt.Key_Space, text=' ')
        self.h.key(view, self.Qt.Key_Return, text='\r')
        self.h.key(view, self.Qt.Key_Enter, text='\r')
        self.h.key(view, self.Qt.Key_Escape)
        self.assertEqual(view.rootObject().property('clicks'), 3)

    def test_mouse_click_does_not_take_focus(self):
        view = self.on_surface('Button { objectName: "b"; x: 10; y: 10; text: "Guardar" }')
        self.h.click(view, 40, 30)
        self.assertFalse(self.child(view, 'b').property('activeFocus'))

    def test_disabled_not_focusable_and_not_clickable(self):
        view = self.on_surface('property int clicks: 0\n'
                               'Button { objectName: "a"; text: "Uno" }\n'
                               'Button { objectName: "b"; x: 100; text: "Dos"; disabled: true; onClicked: root.clicks += 1 }')
        self.assertFalse(self.child(view, 'b').property('activeFocusOnTab'))
        self.h.click(view, 130, 20)
        self.assertEqual(view.rootObject().property('clicks'), 0)

    def test_checkable_toggles(self):
        view = self.on_surface('Button { objectName: "b"; x: 10; y: 10; text: "Fijar"; checkable: true }')
        button = self.child(view, 'b')
        self.h.click(view, 40, 30)
        self.assertTrue(button.property('checked'))
        self.h.click(view, 40, 30)
        self.assertFalse(button.property('checked'))

    def test_icon_adds_a_leading_glyph_of_18(self):
        view = self.on_surface('Button { objectName: "b"; text: "Añadir"; icon: "add" }\n'
                               'Button { objectName: "c"; y: 50; text: "Añadir" }', 240, 100)
        self.assertEqual(self.child(view, 'b').property('iconSize'), 18)
        self.assertGreater(self.child(view, 'b').property('width'), self.child(view, 'c').property('width'))


class IconButtonTests(Base):
    def test_target_is_40(self):
        view = self.on_surface('IconButton { objectName: "b"; icon: "close" }')
        button = self.child(view, 'b')
        self.assertEqual((button.property('width'), button.property('height')), (40, 40))
        self.assertEqual(button.property('iconSize'), 24)

    def test_colours_by_type(self):
        self.h.use('default-dark')
        c = self.colours('default-dark')
        cases = {'standard': (None, 'onSurfaceVariant'), 'filled': ('primary', 'onPrimary'),
                 'tonal': ('secondaryContainer', 'onSecondaryContainer'), 'outlined': (None, 'onSurfaceVariant')}
        for kind, (container, content) in cases.items():
            with self.subTest(type=kind):
                view = self.on_surface(f'IconButton {{ objectName: "b"; x: 10; y: 10; type: "{kind}"; icon: "close" }}')
                support.close_to(self, self.child(view, 'b').property('contentColor'), c[content], msg='content')
                pixel = self.h.pixel(self.h.grab(view), 10 + 20, 10 + 3)
                support.close_to(self, pixel, c[container or 'surface'], msg='container')
                self.h.close_views()

    def test_toggle_icon_button_swaps_icon(self):
        self.h.use('default-dark')
        view = self.on_surface('IconButton { objectName: "b"; x: 10; y: 10; type: "tonal"; checkable: true; '
                               'icon: "favorite_border"; iconChecked: "favorite" }')
        button = self.child(view, 'b')
        self.assertEqual(button.property('shownIcon'), 'favorite_border')
        self.h.click(view, 30, 30)
        self.assertTrue(button.property('checked'))
        self.assertEqual(button.property('shownIcon'), 'favorite')
        c = self.colours('default-dark')
        support.close_to(self, button.property('contentColor'), c['onSecondary'], msg='checked tonal content')


class FabTests(Base):
    def test_sizes(self):
        view = self.on_surface('Fab { objectName: "s"; size: "small"; icon: "add" }\n'
                               'Fab { objectName: "r"; x: 50; icon: "add" }\n'
                               'Fab { objectName: "l"; x: 120; size: "large"; icon: "add" }\n'
                               'Fab { objectName: "e"; y: 100; extended: true; text: "Nueva carpeta"; icon: "add" }', 260, 160)
        self.assertEqual(self.child(view, 's').property('height'), 40)
        self.assertEqual(self.child(view, 'r').property('width'), 56)
        self.assertEqual(self.child(view, 'l').property('height'), 96)
        self.assertEqual(self.child(view, 'l').property('iconSize'), 36)
        extended = self.child(view, 'e')
        self.assertEqual(extended.property('height'), 56)
        self.assertGreater(extended.property('width'), 56)

    def test_variant_colours(self):
        self.h.use('green-dark')
        c = self.colours('green-dark')
        for variant, (container, content) in {'primary': ('primaryContainer', 'onPrimaryContainer'),
                                              'secondary': ('secondaryContainer', 'onSecondaryContainer'),
                                              'tertiary': ('tertiaryContainer', 'onTertiaryContainer')}.items():
            with self.subTest(variant=variant):
                view = self.on_surface(f'Fab {{ objectName: "f"; x: 10; y: 10; variant: "{variant}"; icon: "add" }}', 100, 100)
                fab = self.child(view, 'f')
                support.close_to(self, fab.property('contentColor'), c[content], msg='content')
                pixel = self.h.pixel(self.h.grab(view), 10 + 28, 10 + 4)
                support.close_to(self, pixel, c[container], tolerance=12, msg='container (tonal elevation 3)')
                self.h.close_views()

    def test_extended_fab_collapses(self):
        view = self.on_surface('Fab { objectName: "e"; extended: true; text: "Nueva carpeta"; icon: "add" }', 260, 80)
        fab = self.child(view, 'e')
        fab.setProperty('expanded', False)
        self.h.pump(30)
        self.assertEqual(fab.property('width'), 56)
        fab.setProperty('expanded', True)
        self.h.pump(30)
        self.assertGreater(fab.property('width'), 56)


class SegmentedTests(Base):
    MODEL = '[{value: "list", text: "Lista", icon: "list"}, {value: "grid", text: "Cuadrícula", icon: "grid_view"}, ' \
            '{value: "cols", text: "Columnas"}]'

    def test_height_and_equal_segments(self):
        view = self.on_surface(f'SegmentedButtons {{ objectName: "s"; model: {self.MODEL}; current: "list" }}', 420, 60)
        group = self.child(view, 's')
        self.assertEqual(group.property('height'), 40)
        widths = self.h.call(group, 'segmentWidths')
        self.assertEqual(len(set(widths)), 1, widths)

    def test_segmented_single_select(self):
        self.h.use('blue-dark')
        c = self.colours('blue-dark')
        view = self.on_surface(f'SegmentedButtons {{ objectName: "s"; model: {self.MODEL}; current: "list" }}', 420, 60)
        group = self.child(view, 's')
        widths = self.h.call(group, 'segmentWidths')
        self.h.click(view, widths[0] * 1.5, 20)
        self.assertEqual(group.property('current'), 'grid')
        self.assertEqual(self.h.call(group, 'isSelected', 'list'), False)
        self.h.move(view, 410, 55)                     # off the segments: no hover layer
        pixel = self.h.pixel(self.h.grab(view), widths[0] + 6, 6)
        support.close_to(self, pixel, c['secondaryContainer'], tolerance=3, msg='selected segment')
        support.close_to(self, self.h.pixel(self.h.grab(view), 10, 20), c['surface'], tolerance=3, msg='unselected')

    def test_segmented_multi_select(self):
        view = self.on_surface(f'SegmentedButtons {{ objectName: "s"; model: {self.MODEL}; multiSelect: true; selection: ["list"] }}', 420, 60)
        group = self.child(view, 's')
        widths = self.h.call(group, 'segmentWidths')
        self.h.click(view, widths[0] * 2.5, 20)
        self.assertEqual(sorted(group.property('selection').toVariant()), ['cols', 'list'])
        self.h.click(view, widths[0] * 0.5, 20)
        self.assertEqual(list(group.property('selection').toVariant()), ['cols'])

    def test_selected_segment_shows_check(self):
        view = self.on_surface(f'SegmentedButtons {{ objectName: "s"; model: {self.MODEL}; current: "cols" }}', 420, 60)
        group = self.child(view, 's')
        self.assertEqual(self.h.call(group, 'iconOf', 'cols'), 'check')
        self.assertEqual(self.h.call(group, 'iconOf', 'grid'), 'grid_view')


class CaptureTests(Base):
    BODY = ('Column { x: 8; y: 8; spacing: 8\n'
            '  Row { spacing: 8; Button { text: "Filled" } Button { type: "tonal"; text: "Tonal" } '
            'Button { type: "outlined"; text: "Outlined" } Button { type: "text"; text: "Text" } '
            'Button { type: "elevated"; text: "Elevated" } }\n'
            '  Row { spacing: 8; IconButton { icon: "close" } IconButton { type: "filled"; icon: "add" } '
            'IconButton { type: "tonal"; icon: "edit" } IconButton { type: "outlined"; icon: "share" } '
            'Fab { icon: "add" } Fab { extended: true; icon: "edit"; text: "Compose" } }\n'
            '}')

    def test_every_type_paints_in_light_and_dark(self):
        for palette in ('default-light', 'default-dark'):
            with self.subTest(palette=palette):
                self.h.use(palette)
                view = self.on_surface(self.BODY, 560, 140)
                image = self.h.grab(view)
                distinct = {image.pixel(x, y) for x in range(0, 560, 7) for y in range(0, 140, 7)}
                self.assertGreater(len(distinct), 8)
                self.h.close_views()


if __name__ == '__main__':
    unittest.main()
