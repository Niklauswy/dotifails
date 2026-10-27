"""Adaptive navigation (modal drawer < 600, rail 600-839, standard drawer >= 840), its items and tabs."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

DESTINATIONS = ('[{header: "Lugares"}, {id: "home", icon: "home", label: "Inicio"}, '
                '{id: "docs", icon: "description", label: "Documentos", badge: 3}, '
                '{id: "music", icon: "music_note", label: "Música"}, {divider: true}, '
                '{header: "Favoritos"}, {id: "trash", icon: "delete", label: "Papelera", rail: false}]')


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
        return self.h.find(view, name)

    def colours(self, name):
        return support.palettes()[name]['colours']

    def on_surface(self, body, width=320, height=480):
        return self.h.view('Rectangle { anchors.fill: parent; color: Theme.m3surface }\n' + body, width, height)

    def adaptive(self, width, extra=''):
        return self.on_surface(
            'AdaptiveNavigation { id: nav; objectName: "nav"; anchors.fill: parent; windowWidth: width; '
            f'destinations: {DESTINATIONS}; currentId: "home"; onDestinationSelected: id => currentId = id\n'
            f'{extra}\n'
            '  Rectangle { objectName: "page"; anchors.fill: parent; color: Theme.m3surface } }', width, 480)


class WindowClassTests(Base):
    def test_window_class_boundaries(self):
        view = self.on_surface('function cls(w) { return Metrics.windowClass(w) }', 10, 10)
        for width, expected in ((0, 'modal'), (599, 'modal'), (600, 'rail'), (839, 'rail'), (840, 'standard'), (3000, 'standard')):
            with self.subTest(width=width):
                self.assertEqual(self.h.call(view.rootObject(), 'cls', width), expected)

    def test_mode_does_not_flap_while_resizing(self):
        view = self.adaptive(1000)
        nav = self.child(view, 'nav')
        modes = []
        nav.modeChanged.connect(lambda: modes.append(nav.property('mode')))
        for width in list(range(1000, 400, -7)) + list(range(400, 1000, 7)):
            nav.setProperty('windowWidth', width)
        self.h.pump()
        self.assertEqual(modes, ['rail', 'modal', 'rail', 'standard'])


class DrawerTests(Base):
    def test_drawer_dimensions(self):
        view = self.adaptive(1000)
        nav = self.child(view, 'nav')
        self.assertEqual(nav.property('mode'), 'standard')
        drawer = self.child(view, 'drawer')
        self.assertEqual(drawer.property('width'), 280)
        self.assertEqual(drawer.property('topRightRadius'), self.h.theme('rounding')['large'])
        self.assertEqual(drawer.property('topLeftRadius'), 0)
        item = self.child(view, 'nav-docs')
        self.assertEqual(item.property('height'), 56)
        self.assertEqual(self.child(view, 'page').property('x'), 0)
        self.assertEqual(self.child(view, 'content').property('x'), 280)

    def test_selected_uses_secondary_container(self):
        self.h.use('green-dark')
        c = self.colours('green-dark')
        view = self.adaptive(1000)
        item = self.child(view, 'nav-home')
        point = item.mapToItem(view.rootObject(), item.property('width') - 20, 4)
        support.close_to(self, self.h.pixel(self.h.grab(view), point.x(), point.y()), c['secondaryContainer'])
        support.close_to(self, item.property('contentColor'), c['onSecondaryContainer'])
        other = self.child(view, 'nav-music')
        support.close_to(self, other.property('contentColor'), c['onSurfaceVariant'])
        self.assertTrue(item.property('iconFilled'))
        self.assertFalse(other.property('iconFilled'))

    def test_section_headers_title_small_on_surface_variant(self):
        self.h.use('orange-light')
        c = self.colours('orange-light')
        view = self.adaptive(1000)
        header = self.child(view, 'header-Favoritos')
        self.assertEqual(header.property('role'), 'title.small')
        support.close_to(self, header.property('color'), c['onSurfaceVariant'])
        self.assertIsNotNone(self.child(view, 'divider-4'))

    def test_click_selects(self):
        view = self.adaptive(1000)
        item = self.child(view, 'nav-music')
        point = item.mapToItem(view.rootObject(), 60, 28)
        self.h.click(view, point.x(), point.y())
        self.assertEqual(self.child(view, 'nav').property('currentId'), 'music')

    def test_keyboard_navigation_in_drawer(self):
        view = self.adaptive(1000)
        self.child(view, 'nav-home').forceActiveFocus(self.Qt.TabFocusReason)
        self.h.key(view, self.Qt.Key_Down)
        self.assertTrue(self.child(view, 'nav-docs').property('activeFocus'))
        self.h.key(view, self.Qt.Key_Down)
        self.h.key(view, self.Qt.Key_Down)
        self.assertTrue(self.child(view, 'nav-trash').property('activeFocus'), 'headers and dividers are skipped')
        self.h.key(view, self.Qt.Key_Up)
        self.assertTrue(self.child(view, 'nav-music').property('activeFocus'))
        self.h.key(view, self.Qt.Key_Return, text='\r')
        self.assertEqual(self.child(view, 'nav').property('currentId'), 'music')

    def test_badge_in_destination(self):
        view = self.adaptive(1000)
        self.assertEqual(self.child(view, 'nav-docs').property('trailingText'), '3')
        self.h.close_views()
        view = self.adaptive(700)
        badge = self.child(view, 'badge-docs')
        self.assertIsNotNone(badge)
        self.assertEqual(badge.property('count'), 3)


class RailTests(Base):
    def test_rail_dimensions(self):
        view = self.adaptive(700)
        self.assertEqual(self.child(view, 'nav').property('mode'), 'rail')
        rail = self.child(view, 'rail')
        self.assertEqual(rail.property('width'), 80)
        self.assertEqual(self.child(view, 'content').property('x'), 80)
        active = self.child(view, 'indicator-home')
        idle = self.child(view, 'indicator-music')
        self.assertEqual((active.property('width'), active.property('height')), (56, 32))
        self.assertEqual(idle.property('width'), 32)
        self.assertIsNone(self.child(view, 'nav-trash'), 'rail: false keeps a destination in the drawers only')
        item = self.child(view, 'nav-music')
        point = item.mapToItem(view.rootObject(), 40, 16)
        self.h.click(view, point.x(), point.y())
        self.assertEqual(idle.property('width'), 56)

    def test_rail_labels_are_label_medium(self):
        view = self.adaptive(700)
        self.assertEqual(self.child(view, 'label-home').property('role'), 'label.medium')


class ModalTests(Base):
    def test_modal_opens_closes_with_escape_and_scrim(self):
        view = self.adaptive(500, '  Rectangle { objectName: "opener"; width: 10; height: 10; focusPolicy: Qt.TabFocus }')
        nav = self.child(view, 'nav')
        self.assertEqual(nav.property('mode'), 'modal')
        self.assertTrue(nav.property('menuButtonVisible'))
        self.assertEqual(self.child(view, 'content').property('x'), 0)
        opener = self.child(view, 'opener')
        opener.forceActiveFocus(self.Qt.TabFocusReason)
        self.h.call(nav, 'openModal')
        self.assertTrue(nav.property('modalOpen'))
        self.assertTrue(self.child(view, 'nav-home').property('activeFocus'), 'focus moves into the drawer')
        self.h.key(view, self.Qt.Key_Escape)
        self.assertFalse(nav.property('modalOpen'))
        self.assertTrue(opener.property('activeFocus'), 'focus goes back')
        self.h.call(nav, 'openModal')
        self.h.click(view, 490, 240)            # the scrim, right of the 280 px drawer
        self.assertFalse(nav.property('modalOpen'))

    def test_scrim_colour(self):
        self.h.use('blue-light')
        c = self.colours('blue-light')
        view = self.adaptive(500)
        self.h.call(self.child(view, 'nav'), 'openModal')
        expected = support.blend(c['scrim'], c['surface'], 0.32)
        support.close_to(self, self.h.pixel(self.h.grab(view), 490, 240), expected, tolerance=3)

    def test_selecting_closes_the_modal(self):
        view = self.adaptive(500)
        nav = self.child(view, 'nav')
        self.h.call(nav, 'openModal')
        item = self.child(view, 'nav-music')
        point = item.mapToItem(view.rootObject(), 60, 28)
        self.h.click(view, point.x(), point.y())
        self.assertEqual(nav.property('currentId'), 'music')
        self.assertFalse(nav.property('modalOpen'))

    def test_modal_closed_when_growing_to_rail(self):
        view = self.adaptive(500)
        nav = self.child(view, 'nav')
        self.h.call(nav, 'openModal')
        nav.setProperty('windowWidth', 700)
        self.h.pump()
        self.assertEqual(nav.property('mode'), 'rail')
        self.assertFalse(nav.property('modalOpen'))


class AdaptiveCaptureTests(Base):
    def test_adaptive_matches_mockup_widths(self):
        self.h.use('default-dark')
        c = self.colours('default-dark')
        for width, nav_width in ((500, 0), (700, 80), (1000, 280)):
            with self.subTest(width=width):
                view = self.adaptive(width)
                image = self.h.grab(view)
                if nav_width == 280:
                    support.close_to(self, self.h.pixel(image, 140, 470), c['surfaceContainerLow'], msg='standard drawer container')
                elif nav_width == 80:
                    support.close_to(self, self.h.pixel(image, 40, 470), c['surface'], msg='the rail sits on the surface')
                support.close_to(self, self.h.pixel(image, nav_width + 40, 470), c['surface'], msg='content')
                self.h.close_views()


class TabTests(Base):
    TABS = '[{id: "a", text: "Canciones"}, {id: "b", text: "Álbumes"}, {id: "c", text: "Artistas"}]'

    def test_tabs_indicator_sizes_and_keys(self):
        self.h.use('green-light')
        c = self.colours('green-light')
        view = self.on_surface(f'TabBar {{ objectName: "p"; width: 300; tabs: {self.TABS}; currentId: "a" }}\n'
                               f'TabBar {{ objectName: "s"; y: 60; width: 300; variant: "secondary"; tabs: {self.TABS}; currentId: "a" }}', 320, 120)
        primary, secondary = self.child(view, 'p'), self.child(view, 's')
        self.assertEqual(primary.property('height'), 48)
        self.assertEqual(self.child(view, 'p').property('indicatorHeight'), 3)
        self.assertEqual(self.child(view, 's').property('indicatorHeight'), 2)
        self.assertLess(primary.property('indicatorWidth'), 100, 'primary: as wide as the label')
        self.assertEqual(secondary.property('indicatorWidth'), 100, 'secondary: the whole tab')
        support.close_to(self, self.h.pixel(self.h.grab(view), primary.property('indicatorX') + 4, 46), c['primary'])
        primary.forceActiveFocus(self.Qt.TabFocusReason)
        self.h.key(view, self.Qt.Key_Right)
        self.assertEqual(primary.property('currentId'), 'b')
        self.h.key(view, self.Qt.Key_Right)
        self.h.key(view, self.Qt.Key_Right)
        self.assertEqual(primary.property('currentId'), 'c', 'stops at the last tab')
        self.h.key(view, self.Qt.Key_Left)
        self.assertEqual(primary.property('currentId'), 'b')
        self.h.click(view, 50, 84)
        self.assertEqual(secondary.property('currentId'), 'a')
        self.h.click(view, 250, 84)
        self.assertEqual(secondary.property('currentId'), 'c')


if __name__ == '__main__':
    unittest.main()


class ExtendedDestinationTests(Base):
    """Artwork, trailing icons, rail-only/drawer-only destinations, rail order and labels, header actions and
    context menus (what Wysun Music's playlists and sections need)."""

    def setUp(self):
        super().setUp()
        from PySide6.QtGui import QColor, QImage
        image = QImage(24, 24, QImage.Format_RGB32)
        image.fill(QColor(200, 30, 30))       # theme-exception: synthetic artwork pixel for the test
        self.cover = Path(self.h.dir.name) / 'cover.png'
        image.save(str(self.cover))
        self.destinations = (
            '[{header: "Escuchar"}, {id: "home", icon: "home", label: "Inicio", railOrder: 0},'
            ' {id: "add", icon: "download", label: "Añadir música", railLabel: "Añadir", railOrder: 2},'
            ' {id: "albums", icon: "album", label: "Álbumes", railIcon: "library_music", railLabel: "Biblioteca", railOrder: 1},'
            ' {id: "lists", icon: "queue_music", label: "Listas", drawer: false, railOrder: 3},'
            ' {header: "Playlists", action: "add", actionId: "new"},'
            f' {{id: "pl", icon: "queue_music", label: "Mi lista", rail: false, image: "{self.cover.as_uri()}", trailingIcon: "graphic_eq"}}]')

    def adaptive_with(self, width):
        return self.on_surface(
            'property var log: []\n'
            'AdaptiveNavigation { id: nav; objectName: "nav"; anchors.fill: parent; windowWidth: width; '
            f'destinations: {self.destinations}; currentId: "home"\n'
            '  onHeaderAction: id => root.log = root.log.concat(["action:" + id])\n'
            '  onContextRequested: (id, x, y) => root.log = root.log.concat(["context:" + id + "@" + Math.round(x) + "," + Math.round(y)]) }',
            width, 480)

    def test_image_replaces_the_icon_and_trailing_icon_shows(self):
        view = self.adaptive_with(1000)
        item = self.child(view, 'nav-pl')
        images = [i for i in self.h.items(view, 'navImage') if i.property('visible')]
        self.assertEqual(len(images), 1)
        self.assertTrue(self.h.wait_for(lambda: images[0].property('progress') == 1.0))      # loaded
        self.assertTrue([i for i in self.h.items(view, 'navTrailingIcon') if i.property('visible')])
        self.assertIsNotNone(item)

    def test_drawer_false_stays_out_of_the_drawer(self):
        view = self.adaptive_with(1000)
        self.assertIsNone(self.child(view, 'nav-lists'))
        self.assertIsNotNone(self.child(view, 'nav-albums'))

    def test_rail_order_label_and_icon(self):
        view = self.adaptive_with(700)
        order = [i.property('destinationId') for i in self.h.items(view)
                 if str(i.objectName()).startswith('nav-')]
        self.assertEqual(order, ['home', 'albums', 'add', 'lists'])
        self.assertEqual(self.child(view, 'label-albums').property('text'), 'Biblioteca')
        self.assertEqual(self.child(view, 'nav-albums').property('iconName'), 'library_music')
        self.assertIsNone(self.child(view, 'nav-pl'))

    def test_header_action(self):
        view = self.adaptive_with(1000)
        button = self.child(view, 'headerAction-new')
        point = button.mapToItem(view.rootObject(), 20, 20)
        self.h.click(view, point.x(), point.y())
        self.assertEqual(view.rootObject().property('log').toVariant(), ['action:new'])

    def test_right_click_requests_a_context_menu_in_window_coordinates(self):
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QGuiApplication, QMouseEvent
        view = self.adaptive_with(1000)
        item = self.child(view, 'nav-pl')
        point = item.mapToItem(view.rootObject(), 60, 20)
        for kind, buttons in ((QEvent.MouseButtonPress, self.Qt.RightButton), (QEvent.MouseButtonRelease, self.Qt.NoButton)):
            QGuiApplication.sendEvent(view, QMouseEvent(kind, point, view.mapToGlobal(point), self.Qt.RightButton, buttons,
                                                        self.Qt.NoModifier))
        self.h.pump(20)
        self.assertEqual(view.rootObject().property('log').toVariant(),
                         [f'context:pl@{round(point.x())},{round(point.y())}'])
        self.assertEqual(self.child(view, 'nav').property('currentId'), 'home', 'a right click does not navigate')
