"""Menus, dialogs, snackbars and tooltips: placement, keyboard, focus, queueing, delays and role colours."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

MODEL = ('[{id: "open", text: "Abrir", icon: "open_in_new", shortcut: "Enter"}, {id: "copy", text: "Copiar", icon: "content_copy"}, '
         '{divider: true}, {id: "off", text: "No disponible", disabled: true}, {id: "trash", text: "Mover a la papelera", icon: "delete"}]')


def tearDownModule():
    support.Harness.get().close_views()


class Base(unittest.TestCase):
    def setUp(self):
        from PySide6.QtCore import Qt
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

    def on_surface(self, body, width=600, height=400):
        return self.h.view('Rectangle { anchors.fill: parent; color: Theme.m3surface }\n' + body, width, height)


class MenuTests(Base):
    BODY = ('property var log: []\n'
            'Rectangle { id: anchor; objectName: "anchor"; x: 20; y: 20; width: 10; height: 10; focusPolicy: Qt.TabFocus }\n'
            f'Menu {{ id: menu; objectName: "menu"; model: {MODEL}; onTriggered: id => root.log = root.log.concat([id]) }}\n'
            'function popupAt(x, y) { menu.popup(root, x, y) }')

    def menu(self, view):
        return self.child(view, 'menu')

    def test_opens_at_the_point_and_flips_at_the_four_edges(self):
        view = self.on_surface(self.BODY)
        menu = self.menu(view)
        for (x, y), check in (((40, 40), lambda px, py, w, h: (px, py) == (40, 40)),
                              ((590, 40), lambda px, py, w, h: px + w <= 600 and px < 590),
                              ((40, 395), lambda px, py, w, h: py + h <= 400 and py < 395),
                              ((590, 395), lambda px, py, w, h: px + w <= 600 and py + h <= 400),
                              ((-50, -50), lambda px, py, w, h: px >= 0 and py >= 0)):
            with self.subTest(point=(x, y)):
                self.h.call(view.rootObject(), 'popupAt', x, y)
                self.h.pump()
                self.assertTrue(menu.property('opened'))
                geometry = [menu.property(p) for p in ('panelX', 'panelY', 'panelWidth', 'panelHeight')]
                self.assertTrue(check(*geometry), geometry)
                self.h.call(menu, 'close')

    def test_measures_and_colours(self):
        self.h.use('green-dark')
        c = self.colours('green-dark')
        view = self.on_surface(self.BODY)
        menu = self.menu(view)
        self.h.call(view.rootObject(), 'popupAt', 40, 40)
        self.h.pump()
        self.assertEqual(self.child(view, 'menuitem-copy').property('height'), 48)
        self.assertEqual(menu.property('panelRadius'), self.h.theme('rounding')['extraSmall'])
        self.assertGreaterEqual(menu.property('panelWidth'), 112)
        self.assertLessEqual(menu.property('panelWidth'), 280)
        image = self.h.grab(view)
        support.close_to(self, self.h.pixel(image, 40 + menu.property('panelWidth') - 6, 40 + 4), c['surfaceContainer'], tolerance=6)

    def test_width_follows_the_model_both_ways(self):
        view = self.on_surface(self.BODY)
        menu = self.menu(view)
        self.h.call(view.rootObject(), 'popupAt', 40, 40)
        self.h.pump()
        wide = menu.property('panelWidth')
        self.assertGreater(wide, 112)
        self.h.call(menu, 'close')
        menu.setProperty('model', [{'id': 'a', 'text': 'A'}])
        self.h.pump()
        self.assertEqual(menu.property('panelWidth'), 112, 'a short model shrinks the panel back to the minimum')

    def test_menu_keyboard_flow(self):
        view = self.on_surface(self.BODY)
        menu = self.menu(view)
        self.child(view, 'anchor').forceActiveFocus(self.Qt.TabFocusReason)
        self.h.call(view.rootObject(), 'popupAt', 40, 40)
        self.h.pump()
        self.assertEqual(menu.property('currentIndex'), 0)
        self.h.key(view, self.Qt.Key_Down)
        self.assertEqual(menu.property('currentIndex'), 1)
        self.h.key(view, self.Qt.Key_Down)
        self.assertEqual(menu.property('currentIndex'), 4, 'skips the divider and the disabled item')
        self.h.key(view, self.Qt.Key_Down)
        self.assertEqual(menu.property('currentIndex'), 0, 'wraps around')
        self.h.key(view, self.Qt.Key_Up)
        self.assertEqual(menu.property('currentIndex'), 4)
        self.h.key(view, self.Qt.Key_Return, text='\r')
        self.assertEqual(view.rootObject().property('log').toVariant(), ['trash'])
        self.assertFalse(menu.property('opened'))
        self.assertTrue(self.child(view, 'anchor').property('activeFocus'), 'focus goes back')

    def test_escape_closes_and_returns_focus(self):
        view = self.on_surface(self.BODY)
        menu = self.menu(view)
        self.child(view, 'anchor').forceActiveFocus(self.Qt.TabFocusReason)
        self.h.call(view.rootObject(), 'popupAt', 40, 40)
        self.h.pump()
        self.h.key(view, self.Qt.Key_Escape)
        self.assertFalse(menu.property('opened'))
        self.assertTrue(self.child(view, 'anchor').property('activeFocus'))
        self.assertEqual(view.rootObject().property('log').toVariant(), [])

    def test_click_item_and_click_outside(self):
        view = self.on_surface(self.BODY)
        menu = self.menu(view)
        self.h.call(view.rootObject(), 'popupAt', 40, 40)
        self.h.pump()
        item = self.child(view, 'menuitem-copy')
        point = item.mapToItem(view.rootObject(), 30, 24)
        self.h.click(view, point.x(), point.y())
        self.assertEqual(view.rootObject().property('log').toVariant(), ['copy'])
        self.h.call(view.rootObject(), 'popupAt', 40, 40)
        self.h.pump()
        disabled = self.child(view, 'menuitem-off')
        point = disabled.mapToItem(view.rootObject(), 30, 24)
        self.h.click(view, point.x(), point.y())
        self.assertTrue(menu.property('opened'), 'a disabled item does nothing')
        self.h.click(view, 580, 380)
        self.assertFalse(menu.property('opened'))
        self.assertEqual(view.rootObject().property('log').toVariant(), ['copy'])


class DialogTests(Base):
    BODY = ('property var log: []\n'
            'Rectangle { id: opener; objectName: "opener"; width: 10; height: 10; focusPolicy: Qt.TabFocus }\n'
            'Dialog { id: dialog; objectName: "dialog"; title: "¿Borrar 3 archivos?"; message: "No se puede deshacer."; icon: "delete"\n'
            '  actions: [{id: "cancel", text: "Cancelar"}, {id: "delete", text: "Borrar", primary: true}]\n'
            '  onAccepted: id => root.log = root.log.concat([id]); onRejected: root.log = root.log.concat(["rejected"]) }')

    def test_dialog_traps_focus_and_escape_rejects(self):
        view = self.on_surface(self.BODY)
        dialog = self.child(view, 'dialog')
        self.child(view, 'opener').forceActiveFocus(self.Qt.TabFocusReason)
        self.h.call(dialog, 'open')
        self.h.pump()
        cancel, delete = self.child(view, 'action-cancel'), self.child(view, 'action-delete')
        self.assertTrue(delete.property('activeFocus'), 'the primary action takes focus')
        self.h.key(view, self.Qt.Key_Tab)
        self.assertTrue(cancel.property('activeFocus'), 'Tab wraps inside the dialog')
        self.h.key(view, self.Qt.Key_Tab)
        self.assertTrue(delete.property('activeFocus'))
        self.h.key(view, self.Qt.Key_Backtab)
        self.assertTrue(cancel.property('activeFocus'))
        self.h.key(view, self.Qt.Key_Escape)
        self.assertFalse(dialog.property('opened'))
        self.assertEqual(view.rootObject().property('log').toVariant(), ['rejected'])
        self.assertTrue(self.child(view, 'opener').property('activeFocus'))

    def test_action_accepts_with_its_id(self):
        view = self.on_surface(self.BODY)
        dialog = self.child(view, 'dialog')
        self.h.call(dialog, 'open')
        self.h.pump()
        self.h.key(view, self.Qt.Key_Return, text='\r')
        self.assertEqual(view.rootObject().property('log').toVariant(), ['delete'])
        self.assertFalse(dialog.property('opened'))

    def test_dialog_width_clamped(self):
        view = self.on_surface('Dialog { objectName: "small"; title: "Hola"; actions: [{id: "ok", text: "OK"}] }\n'
                               'Dialog { objectName: "big"; title: "Hola"; Rectangle { implicitWidth: 2000; implicitHeight: 20 } }', 1200, 600)
        for name in ('small', 'big'):
            self.h.call(self.child(view, name), 'open')
        self.h.pump()
        self.assertEqual(self.child(view, 'small').property('panelWidth'), 280)
        self.assertEqual(self.child(view, 'big').property('panelWidth'), 560)
        self.assertEqual(self.child(view, 'big').property('panelRadius'), self.h.theme('rounding')['extraLarge'])

    def test_scrim_and_container_colours(self):
        self.h.use('orange-dark')
        c = self.colours('orange-dark')
        view = self.on_surface(self.BODY)
        dialog = self.child(view, 'dialog')
        self.h.call(dialog, 'open')
        self.h.pump()
        image = self.h.grab(view)
        support.close_to(self, self.h.pixel(image, 4, 390), support.blend(c['scrim'], c['surface'], 0.32), tolerance=3, msg='scrim')
        x, y = dialog.property('panelX'), dialog.property('panelY')
        support.close_to(self, self.h.pixel(image, x + dialog.property('panelWidth') / 2, y + 6), c['surfaceContainerHigh'], tolerance=6)


class SnackbarTests(Base):
    BODY = ('property var log: []\n'
            'SnackbarHost { id: host; objectName: "host"; anchors.fill: parent; '
            'onActionTriggered: text => root.log = root.log.concat(["action:" + text]); '
            'onDismissed: text => root.log = root.log.concat(["dismissed:" + text]) }')

    def test_snackbar_queue_order_and_dismiss(self):
        view = self.on_surface(self.BODY)
        host = self.child(view, 'host')
        self.h.call(host, 'show', {'text': 'Uno', 'duration': 60000})
        self.h.call(host, 'show', {'text': 'Dos', 'duration': 60000})
        self.h.pump()
        self.assertEqual(host.property('currentText'), 'Uno')
        self.assertEqual(host.property('queued'), 1)
        self.h.call(host, 'dismiss')
        self.h.pump()
        self.assertEqual(host.property('currentText'), 'Dos')
        self.h.call(host, 'dismiss')
        self.h.pump()
        self.assertEqual(host.property('currentText'), '')
        self.assertEqual(view.rootObject().property('log').toVariant(), ['dismissed:Uno', 'dismissed:Dos'])

    def test_times_out(self):
        view = self.on_surface(self.BODY)
        host = self.child(view, 'host')
        self.h.call(host, 'show', {'text': 'Copiado', 'duration': 100})
        self.assertTrue(self.h.wait_for(lambda: host.property('currentText') == '', 1500))

    def test_snackbar_action_signal(self):
        self.h.use('blue-light')
        c = self.colours('blue-light')
        view = self.on_surface(self.BODY)
        host = self.child(view, 'host')
        self.h.call(host, 'show', {'text': 'Archivo borrado', 'action': 'Deshacer', 'duration': 60000})
        self.h.pump()
        bar = self.child(view, 'snackbar')
        self.assertEqual(bar.property('height'), 48)
        image = self.h.grab(view)
        point = bar.mapToItem(view.rootObject(), 6, 6)
        support.close_to(self, self.h.pixel(image, point.x(), point.y()), c['inverseSurface'], tolerance=4)
        action = self.child(view, 'snackbar-action')
        support.close_to(self, action.property('contentColor'), c['inversePrimary'])
        self.h.call(action, 'activate')
        self.h.pump()
        self.assertEqual(view.rootObject().property('log').toVariant(), ['action:Deshacer'])
        self.assertEqual(host.property('currentText'), '')

    def test_two_lines_are_taller(self):
        view = self.on_surface(self.BODY, 360, 400)
        host = self.child(view, 'host')
        self.h.call(host, 'show', {'text': 'Un mensaje bastante largo que no cabe en una sola línea del snackbar', 'action': 'Ver', 'duration': 60000})
        self.h.pump()
        self.assertEqual(self.child(view, 'snackbar').property('height'), 68)


class TooltipTests(Base):
    BODY = ('Rectangle { id: target; objectName: "target"; x: 100; y: 100; width: 40; height: 40; color: Theme.m3primary\n'
            '  Tooltip { objectName: "tip"; text: "Nueva carpeta" } }')

    def test_tooltip_delay_and_hide_on_leave(self):
        view = self.on_surface(self.BODY)
        tip = self.child(view, 'tip')
        self.h.move(view, 120, 120)
        self.h.pump(100)
        self.assertFalse(tip.property('shown'), 'not before the delay')
        self.assertTrue(self.h.wait_for(lambda: tip.property('shown'), 1500))
        self.assertEqual(tip.property('delay'), self.h.theme('anim')['durations']['normal'])
        self.assertEqual(tip.property('panelHeight'), 24)
        self.h.move(view, 400, 300)
        self.h.pump()
        self.assertFalse(tip.property('shown'))

    def test_reduced_motion_overlays_appear_instantly(self):
        view = self.on_surface(self.BODY + '\nMenu { id: m; objectName: "menu"; model: [{id: "a", text: "A"}] }\n'
                               'function openMenu() { m.popup(root, 10, 10) }')
        self.h.call(view.rootObject(), 'openMenu')
        self.h.pump()
        self.assertEqual(self.child(view, 'menuPanel').property('opacity'), 1)
        self.assertEqual(self.child(view, 'menuPanel').property('scale'), 1)
        tip = self.child(view, 'tip')
        self.h.call(tip, 'show')
        self.h.pump()
        self.assertEqual(self.child(view, 'tooltipPanel').property('opacity'), 1)

    def test_rich_tooltip_has_room_for_its_text(self):
        view = self.on_surface('Rectangle { id: target; x: 100; y: 100; width: 40; height: 40\n'
                               '  Tooltip { objectName: "tip"; rich: true; title: "Título"; text: "Un texto de ayuda algo largo" } }')
        self.h.call(self.child(view, 'tip'), 'show')
        self.h.pump()
        panel = self.child(view, 'tooltipPanel')
        self.assertGreater(panel.property('width'), 100)
        self.assertGreater(panel.property('height'), 40)

    def test_plain_tooltip_colours(self):
        self.h.use('green-light')
        c = self.colours('green-light')
        view = self.on_surface(self.BODY)
        tip = self.child(view, 'tip')
        self.h.call(tip, 'show')
        self.h.pump()
        panel = self.child(view, 'tooltipPanel')
        point = panel.mapToItem(view.rootObject(), 3, 12)
        support.close_to(self, self.h.pixel(self.h.grab(view), point.x(), point.y()), c['inverseSurface'], tolerance=4)


if __name__ == '__main__':
    unittest.main()
