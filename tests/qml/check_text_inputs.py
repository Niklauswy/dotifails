"""Outlined/filled text fields and the search bar: measures, floating label, focus/error/disabled, keys."""
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

    def on_surface(self, body, width=300, height=120):
        return self.h.view('Rectangle { anchors.fill: parent; color: Theme.m3surface }\n' + body, width, height)


class TextFieldTests(Base):
    def test_height_and_corners(self):
        view = self.on_surface('TextField { objectName: "o"; width: 200; label: "Nombre" }\n'
                               'TextField { objectName: "f"; y: 60; width: 200; variant: "filled"; label: "Nombre" }', 240, 130)
        outlined, filled = self.child(view, 'o'), self.child(view, 'f')
        self.assertEqual(outlined.property('fieldHeight'), 56)
        self.assertEqual(filled.property('fieldHeight'), 56)
        self.assertEqual(outlined.property('cornerRadius'), self.h.theme('rounding')['extraSmall'])

    def test_outline_grows_to_two_primary_pixels_on_focus(self):
        self.h.use('blue-light')
        c = self.colours('blue-light')
        view = self.on_surface('TextField { objectName: "t"; x: 10; y: 20; width: 200; label: "Nombre" }')
        field = self.child(view, 't')
        self.assertEqual(field.property('outlineWidth'), 1)
        support.close_to(self, self.h.pixel(self.h.grab(view), 10, 50), c['outline'], msg='rest outline')
        self.h.click(view, 100, 48)
        self.assertTrue(field.property('focused'))
        self.assertEqual(field.property('outlineWidth'), 2)
        image = self.h.grab(view)
        support.close_to(self, self.h.pixel(image, 11, 50), c['primary'], msg='focused outline, 2 px')

    def test_label_floats_with_focus_or_text(self):
        view = self.on_surface('TextField { objectName: "t"; x: 10; y: 20; width: 200; label: "Nombre" }')
        field = self.child(view, 't')
        self.assertFalse(field.property('labelFloating'))
        rest_y = field.property('labelY')
        self.h.click(view, 100, 48)
        self.assertTrue(field.property('labelFloating'))
        self.assertLess(field.property('labelY'), rest_y)
        view.rootObject().forceActiveFocus()
        self.h.pump()
        self.assertFalse(field.property('labelFloating'))
        field.setProperty('text', 'Ana')
        self.h.pump()
        self.assertTrue(field.property('labelFloating'), 'text keeps the label up without focus')

    def test_error_colours(self):
        self.h.use('green-dark')
        c = self.colours('green-dark')
        view = self.on_surface('TextField { objectName: "t"; x: 10; y: 20; width: 200; label: "Nombre"; '
                               'error: true; errorText: "Obligatorio" }')
        field = self.child(view, 't')
        support.close_to(self, field.property('indicatorColor'), c['error'], msg='outline')
        self.assertEqual(field.property('supportingShown'), 'Obligatorio')
        support.close_to(self, field.property('supportingColor'), c['error'], msg='supporting text')

    def test_disabled(self):
        view = self.on_surface('TextField { objectName: "t"; x: 10; y: 20; width: 200; label: "Nombre"; text: "Ana"; disabled: true }')
        field = self.child(view, 't')
        self.assertAlmostEqual(field.property('indicatorColor').alphaF(), 0.12, delta=0.01)
        self.assertAlmostEqual(field.property('textColor').alphaF(), 0.38, delta=0.01)
        self.h.click(view, 100, 48)
        self.assertFalse(field.property('focused'))

    def test_typing_accepted_and_insert(self):
        view = self.on_surface('property int accepted: 0\n'
                               'TextField { objectName: "t"; x: 10; y: 20; width: 200; label: "Nombre"; onAccepted: root.accepted += 1 }')
        field = self.child(view, 't')
        self.h.click(view, 100, 48)
        self.h.type_text(view, 'Ana')
        self.assertEqual(field.property('text'), 'Ana')
        self.h.call(field, 'insert', 0, 'Sra. ')
        self.assertEqual(field.property('text'), 'Sra. Ana')
        self.h.call(field, 'selectAll')
        self.assertEqual(field.property('selectedText'), 'Sra. Ana')
        self.h.key(view, self.Qt.Key_Return, text='\r')
        self.assertEqual(view.rootObject().property('accepted'), 1)

    def test_long_text_is_clipped(self):
        view = self.on_surface('TextField { objectName: "t"; x: 10; y: 20; width: 120; label: "Ruta"; '
                               'text: "/una/ruta/muy/larga/que/no/cabe/en/el/campo/de/texto.txt" }')
        field = self.child(view, 't')
        self.assertEqual(field.property('width'), 120)
        self.assertTrue(field.property('clipsInput'))

    def test_filled_indicator(self):
        self.h.use('orange-light')
        c = self.colours('orange-light')
        view = self.on_surface('TextField { objectName: "t"; x: 10; y: 20; width: 200; variant: "filled"; label: "Nombre" }')
        image = self.h.grab(view)
        support.close_to(self, self.h.pixel(image, 100, 25), c['surfaceContainerHighest'], msg='filled container')
        support.close_to(self, self.h.pixel(image, 100, 20 + 55), c['onSurfaceVariant'], msg='active indicator')


class SearchBarTests(Base):
    def test_measures_and_colours(self):
        self.h.use('default-dark')
        c = self.colours('default-dark')
        view = self.on_surface('SearchBar { objectName: "s"; x: 10; y: 10; width: 260; placeholder: "Buscar" }')
        bar = self.child(view, 's')
        self.assertEqual(bar.property('height'), 56)
        self.assertEqual(bar.property('radius'), 28)
        support.close_to(self, self.h.pixel(self.h.grab(view), 140, 14), c['surfaceContainerHigh'])

    def test_search_clear_button(self):
        view = self.on_surface('property int cleared: 0\n'
                               'SearchBar { objectName: "s"; x: 10; y: 10; width: 260; onCleared: root.cleared += 1 }')
        bar = self.child(view, 's')
        self.assertFalse(bar.property('clearVisible'))
        bar.setProperty('text', 'foto')
        self.h.pump()
        self.assertTrue(bar.property('clearVisible'))
        self.h.click(view, 10 + 260 - 28, 10 + 28)
        self.assertEqual(bar.property('text'), '')
        self.assertEqual(view.rootObject().property('cleared'), 1)

    def test_escape_clears_only_when_there_is_text(self):
        view = self.on_surface('property int escapes: 0\n'
                               'Keys.onEscapePressed: escapes += 1\n'
                               'SearchBar { objectName: "s"; x: 10; y: 10; width: 260 }')
        bar = self.child(view, 's')
        self.h.call(bar, 'forceFocus')
        self.h.type_text(view, 'foto')
        self.assertEqual(bar.property('text'), 'foto')
        self.h.key(view, self.Qt.Key_Escape)
        self.assertEqual(bar.property('text'), '')
        self.assertEqual(view.rootObject().property('escapes'), 0, 'the first Escape is the search bar\'s')
        self.h.key(view, self.Qt.Key_Escape)
        self.assertEqual(view.rootObject().property('escapes'), 1, 'an empty search bar lets Escape through')

    def test_enter_accepts(self):
        view = self.on_surface('property string query\n'
                               'SearchBar { id: s; objectName: "s"; x: 10; y: 10; width: 260; onAccepted: root.query = s.text }')
        bar = self.child(view, 's')
        self.h.call(bar, 'forceFocus')
        self.h.type_text(view, 'mar')
        self.h.key(view, self.Qt.Key_Return, text='\r')
        self.assertEqual(view.rootObject().property('query'), 'mar')


if __name__ == '__main__':
    unittest.main()
