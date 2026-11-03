"""List items, cards, empty states and the top app bar."""
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

    def on_surface(self, body, width=320, height=200):
        return self.h.view('Rectangle { anchors.fill: parent; color: Theme.m3surface }\n' + body, width, height)


class ListItemTests(Base):
    def test_heights_by_lines(self):
        view = self.on_surface('Column { width: 300\n'
                               '  ListItem { objectName: "one"; width: 300; headline: "Música" }\n'
                               '  ListItem { objectName: "two"; width: 300; headline: "Música"; supporting: "120 canciones" }\n'
                               '  ListItem { objectName: "three"; width: 300; lines: 3; headline: "Música"; supporting: "Una descripción larga" } }', 320, 240)
        self.assertEqual(self.child(view, 'one').property('height'), 56)
        self.assertEqual(self.child(view, 'two').property('height'), 72)
        self.assertEqual(self.child(view, 'three').property('height'), 88)

    def test_selected_list_item_uses_secondary_container(self):
        self.h.use('orange-light')
        c = self.colours('orange-light')
        view = self.on_surface('ListItem { objectName: "i"; width: 300; headline: "Documentos"; leadingIcon: "folder"; selected: true }')
        item = self.child(view, 'i')
        support.close_to(self, self.h.pixel(self.h.grab(view), 290, 4), c['secondaryContainer'])
        support.close_to(self, item.property('headlineColor'), c['onSecondaryContainer'])

    def test_list_item_long_text_elides(self):
        view = self.on_surface('ListItem { objectName: "i"; width: 160; headline: "Un nombre de archivo larguísimo que no cabe.pdf"; '
                               'supporting: "Una ruta también muy larga que tampoco cabe"; trailingText: "12 MB" }')
        item = self.child(view, 'i')
        self.assertEqual(item.property('height'), 72)
        self.assertTrue(item.property('headlineTruncated'))

    def test_clicks_double_clicks_and_context(self):
        view = self.on_surface('property var log: []\n'
                               'ListItem { width: 300; headline: "a"; onClicked: root.log = root.log.concat(["click"]); '
                               'onDoubleClicked: root.log = root.log.concat(["double"]); '
                               'onContextRequested: (x, y) => root.log = root.log.concat(["context"]) }')
        self.h.click(view, 100, 20)
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QGuiApplication, QMouseEvent
        for kind, buttons in ((QEvent.MouseButtonPress, self.Qt.RightButton), (QEvent.MouseButtonRelease, self.Qt.NoButton)):
            QGuiApplication.sendEvent(view, QMouseEvent(kind, QPointF(100, 20), view.mapToGlobal(QPointF(100, 20)),
                                                        self.Qt.RightButton, buttons, self.Qt.NoModifier))
        self.h.pump(20)
        log = view.rootObject().property('log').toVariant()
        self.assertIn('click', log)
        self.assertIn('context', log)

    def test_only_visible_delegates_are_created(self):
        view = self.on_surface('ListView { id: list; objectName: "list"; anchors.fill: parent; model: 10000\n'
                               '  delegate: ListItem { required property int index; objectName: "row"; width: ListView.view.width; '
                               'headline: "Elemento " + index; supporting: "detalle"; leadingIcon: "description" } }', 320, 600)
        rows = lambda: len(self.h.items(view, 'row'))
        self.assertGreater(rows(), 5)
        self.assertLess(rows(), 60)
        list_view = self.child(view, 'list')
        list_view.setProperty('contentY', 72 * 5000)
        self.h.pump(30)
        self.assertLess(rows(), 60)


class CardTests(Base):
    def test_card_variants_surface_and_outline(self):
        self.h.use('blue-dark')
        c = self.colours('blue-dark')
        view = self.on_surface('Card { objectName: "e"; x: 10; y: 10; width: 90; height: 60 }\n'
                               'Card { objectName: "f"; x: 110; y: 10; width: 90; height: 60; variant: "filled" }\n'
                               'Card { objectName: "o"; x: 210; y: 10; width: 90; height: 60; variant: "outlined" }', 320, 100)
        image = self.h.grab(view)
        self.assertEqual(self.child(view, 'e').property('radius'), self.h.theme('rounding')['medium'])
        support.close_to(self, self.h.pixel(image, 155, 40), c['surfaceContainerHighest'], msg='filled')
        support.close_to(self, self.h.pixel(image, 255, 40), c['surface'], msg='outlined inside')
        support.close_to(self, self.h.pixel(image, 255, 10), c['outlineVariant'], msg='outlined edge')
        self.assertGreater(self.child(view, 'e').property('level'), 0)

    def test_clickable_card(self):
        view = self.on_surface('property int clicks: 0\n'
                               'Card { x: 10; y: 10; width: 90; height: 60; clickable: true; onClicked: root.clicks += 1 }')
        self.h.click(view, 50, 40)
        self.assertEqual(view.rootObject().property('clicks'), 1)


class EmptyStateTests(Base):
    def test_empty_state_action_and_reduced_motion(self):
        view = self.on_surface('property int actions: 0\n'
                               'EmptyState { objectName: "e"; anchors.fill: parent; icon: "folder_open"; title: "Carpeta vacía"; '
                               'message: "Arrastra archivos aquí"; actionText: "Nueva carpeta"; onAction: root.actions += 1 }', 360, 360)
        emblem = self.child(view, 'emptyEmblem')
        self.assertEqual(emblem.property('scale'), 1, 'reduced motion: the emblem is already in place')
        button = self.child(view, 'emptyAction')
        self.h.call(button, 'activate')
        self.assertEqual(view.rootObject().property('actions'), 1)

    def test_emblem_springs_in(self):
        self.h.bridge.setReducedMotion(False)
        self.h.pump()
        view = self.on_surface('EmptyState { anchors.fill: parent; icon: "music_note"; title: "Sin música" }', 360, 360)
        emblem = self.child(view, 'emptyEmblem')
        self.assertLess(emblem.property('scale'), 1)
        self.assertTrue(self.h.wait_for(lambda: emblem.property('scale') == 1, 2000))

    def test_no_action_button_without_text(self):
        view = self.on_surface('EmptyState { anchors.fill: parent; title: "Nada" }', 360, 360)
        self.assertFalse(self.child(view, 'emptyAction').property('visible'))

    def test_centred_empty_state_keeps_its_title_on_one_line(self):
        # Only `anchors.centerIn`: the item takes its implicit width, so that width must come from the text and
        # never from its own width (a binding loop used to shrink it to the emblem and wrap the title word by word).
        from PySide6.QtGui import QFontMetricsF
        view = self.on_surface('EmptyState { objectName: "e"; anchors.centerIn: parent; icon: "web_asset_off"; '
                               'title: "No hay ventanas abiertas"; '
                               'message: "Aquí aparecerán las ventanas de Hyprland con lo que gasta cada una" }',
                               1000, 400)
        state = self.child(view, 'e')
        title = self.child(view, 'emptyTitle')
        self.assertGreater(state.property('width'), 200, 'the empty state took the width of its emblem')
        self.assertEqual(title.property('lineCount'), 1, 'the title wrapped one word per line')
        self.assertLessEqual(title.property('height'), QFontMetricsF(title.property('font')).height() * 1.5,
                             'the painted title is more than one line tall')


class TopAppBarTests(Base):
    def test_heights(self):
        view = self.on_surface('Column { width: 300\n'
                               '  TopAppBar { objectName: "s"; width: 300; title: "Archivos" }\n'
                               '  TopAppBar { objectName: "m"; width: 300; variant: "medium"; title: "Archivos" }\n'
                               '  TopAppBar { objectName: "l"; width: 300; variant: "large"; title: "Archivos" } }', 320, 340)
        self.assertEqual(self.child(view, 's').property('height'), 64)
        self.assertEqual(self.child(view, 'm').property('height'), 112)
        self.assertEqual(self.child(view, 'l').property('height'), 152)

    def test_top_app_bar_collapses_with_scroll_offset(self):
        self.h.use('green-light')
        c = self.colours('green-light')
        view = self.on_surface('TopAppBar { objectName: "l"; width: 300; variant: "large"; title: "Archivos" }', 320, 200)
        bar = self.child(view, 'l')
        support.close_to(self, self.h.pixel(self.h.grab(view), 290, 4), c['surface'], msg='flat at rest')
        bar.setProperty('scrollOffset', 40)
        self.h.pump()
        self.assertEqual(bar.property('height'), 112)
        bar.setProperty('scrollOffset', 500)
        self.h.pump()
        self.assertEqual(bar.property('height'), 64)
        self.assertTrue(bar.property('scrolled'))
        support.close_to(self, self.h.pixel(self.h.grab(view), 290, 4), c['surfaceContainer'], msg='container on scroll')


if __name__ == '__main__':
    unittest.main()
