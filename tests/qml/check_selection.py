"""Switch and Dropdown: M3 measures, role colours (light and dark), click and keyboard, the menu of the dropdown."""
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
        from PySide6.QtCore import QObject, QPointF, Qt
        self.QObject, self.QPointF, self.Qt = QObject, QPointF, Qt
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

    def on_surface(self, body, width=220, height=100):
        return self.h.view('Rectangle { anchors.fill: parent; color: Theme.m3surface }\nproperty int count: 0\n'
                           'property var log: []\n' + body, width, height)

    def click_item(self, view, item):
        point = item.mapToScene(self.QPointF(item.width() / 2, item.height() / 2))
        self.h.click(view, point.x(), point.y())

    def focus(self, item):
        item.forceActiveFocus(self.Qt.TabFocusReason)
        self.h.pump(20)


class SwitchTests(Base):
    BODY = ('Switch { objectName: "on"; x: 10; y: 10; checked: true; onToggled: root.count += 1 }\n'
            'Switch { objectName: "off"; x: 100; y: 10; onToggled: root.count += 1 }')

    def test_size_and_role_colours(self):
        for palette in ('default-light', 'orange-dark'):
            with self.subTest(palette=palette):
                self.h.use(palette)
                c = self.colours(palette)
                view = self.on_surface(self.BODY)
                on, off = self.child(view, 'on'), self.child(view, 'off')
                self.assertEqual((on.property('width'), on.property('height')), (52, 32))
                image = self.h.grab(view)
                support.close_to(self, self.h.pixel(image, 10 + 8, 10 + 16), c['primary'], msg='on track')
                support.close_to(self, self.h.pixel(image, 10 + 36, 10 + 16), c['onPrimary'], msg='on handle')
                support.close_to(self, self.h.pixel(image, 100 + 44, 10 + 16), c['surfaceContainerHighest'], msg='off track')
                support.close_to(self, self.h.pixel(image, 100 + 26, 10 + 1), c['outline'], msg='off outline')
                support.close_to(self, self.h.pixel(image, 100 + 16, 10 + 16), c['outline'], msg='off handle')
                self.h.close_views()

    def test_toggles_by_click_and_space_and_emits_once_each(self):
        view = self.on_surface(self.BODY)
        off = self.child(view, 'off')
        self.h.click(view, 100 + 26, 10 + 16)
        self.assertEqual((off.property('checked'), view.rootObject().property('count')), (True, 1))
        self.focus(off)
        self.h.key(view, self.Qt.Key_Space)
        self.assertEqual((off.property('checked'), view.rootObject().property('count')), (False, 2))

    def test_disabled_switch_ignores_input(self):
        view = self.on_surface('Switch { objectName: "s"; x: 10; y: 10; disabled: true; onToggled: root.count += 1 }')
        switch = self.child(view, 's')
        self.h.click(view, 36, 26)
        self.focus(switch)
        self.h.key(view, self.Qt.Key_Space)
        self.assertEqual((switch.property('checked'), view.rootObject().property('count')), (False, 0))


class DropdownTests(Base):
    MODEL = '[{value: "15", text: "15 fps"}, {value: "30", text: "30 fps"}, {value: "60", text: "60 fps"}]'

    def dropdown(self, extra='', current='30'):
        return self.on_surface(f'Dropdown {{ objectName: "d"; x: 10; y: 10; width: 200; model: {self.MODEL}; '
                               f'current: "{current}"; {extra + ";" if extra else ""} '
                               'onActivated: value => root.log = root.log.concat([value]) }',
                               260, 320)

    def test_shows_the_current_text_or_the_placeholder(self):
        view = self.dropdown('placeholder: "Elige"')
        field = self.child(view, 'd')
        self.assertEqual((field.property('height'), field.property('displayText')), (56, '30 fps'))
        field.setProperty('current', '')
        self.assertEqual(field.property('displayText'), 'Elige')

    def test_outline_uses_the_outline_role(self):
        for palette in ('green-light', 'blue-dark'):
            self.h.use(palette)
            view = self.dropdown()
            support.close_to(self, self.h.pixel(self.h.grab(view), 10 + 100, 10), self.colours(palette)['outline'], msg=palette)
            self.h.close_views()

    def test_opens_a_menu_and_emits_the_chosen_value(self):
        view = self.dropdown()
        field = self.child(view, 'd')
        self.h.click(view, 10 + 100, 10 + 28)
        self.assertTrue(field.property('opened'))
        self.assertIsNotNone(self.h.find_in(view.contentItem(), 'menuPanel'))
        self.click_item(view, self.h.find_in(view.contentItem(), 'menuitem-60'))
        self.assertEqual(list(view.rootObject().property('log').toVariant()), ['60'])
        self.assertEqual((field.property('current'), field.property('opened')), ('60', False))

    def test_keyboard_opens_on_the_current_row_and_enter_chooses(self):
        view = self.dropdown()
        field = self.child(view, 'd')
        self.focus(field)
        self.h.key(view, self.Qt.Key_Down)
        menu = self.child(view, 'dropdownMenu')
        self.assertTrue(field.property('opened'))
        self.assertEqual(menu.property('currentIndex'), 1)
        self.h.key(view, self.Qt.Key_Down)
        self.h.key(view, self.Qt.Key_Return)
        self.assertEqual(list(view.rootObject().property('log').toVariant()), ['60'])
        self.assertFalse(field.property('opened'))

    def test_escape_closes_without_changing_the_value(self):
        view = self.dropdown()
        field = self.child(view, 'd')
        self.focus(field)
        self.h.key(view, self.Qt.Key_Space)
        self.assertTrue(field.property('opened'))
        self.h.key(view, self.Qt.Key_Escape)
        self.assertEqual((field.property('opened'), field.property('current'), len(view.rootObject().property('log').toVariant())),
                         (False, '30', 0))

    def test_disabled_dropdown_does_not_open(self):
        view = self.dropdown('disabled: true')
        field = self.child(view, 'd')
        self.h.click(view, 10 + 100, 10 + 28)
        self.focus(field)
        self.h.key(view, self.Qt.Key_Down)
        self.assertFalse(field.property('opened'))


if __name__ == '__main__':
    unittest.main()
