"""Wysun Processes' QML window (venv Python, offscreen): loads clean in dark and light, keyboard navigation of the
table, the query bar and its filter chips, view switching, the confirmation dialog, the five sections, the app
sheet (container transform), services without systemd and read-only exec-once entries in Inicio."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402
from qml.check_processes_controller import FIREFOX, KITTY, FakeHypr  # noqa: E402
from test_processes_core import write_proc  # noqa: E402


class NoServices:
    available = False

    def list(self):
        return []


class FakeStartup:
    def items(self):
        return [dict(id='session:Hyprland', name='Hyprland', source='session', editable=False, enabled=True, delay=0,
                     started_s=0.0, ready_s=0.4, impact=2, app='Hyprland'),
                dict(id='once:wysun workspaces', name='wysun workspaces', source='exec-once', editable=False,
                     enabled=True, delay=0, started_s=0.8, ready_s=0.8, impact=1, app='wysun'),
                dict(id='systemd:syncthing.service', name='syncthing', source='systemd', editable=True, enabled=True,
                     delay=0, started_s=1.0, ready_s=2.2, impact=3, app='syncthing')]


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QObject, Qt
        cls.Qt, cls.QObject = Qt, QObject
        cls.h = support.Harness.get()
        cls.tmp = tempfile.TemporaryDirectory()
        proc = Path(cls.tmp.name)
        write_proc(proc, 10, 'firefox', cgroup=FIREFOX, rss_pages=50000)
        write_proc(proc, 11, 'Web Content', ppid=10, cgroup=FIREFOX)
        write_proc(proc, 20, 'kitty', cgroup=KITTY)
        write_proc(proc, 21, 'btop', ppid=20, cgroup=KITTY, state='R')
        write_proc(proc, 30, 'dbus-daemon', cgroup='0::/user.slice/user-1000.slice/user@1000.service\n', rss_pages=20000)
        from wysun_processes.core.sampler import Sampler
        from wysun_processes.quick.controller import ProcessesController
        from wysun_processes.quick.window import QmlProcessesWindow
        cls.c = ProcessesController(sampler=Sampler(proc_root=proc), hypr=FakeHypr(), services=NoServices(),
                                    startup=FakeStartup(), auto=False)
        cls.warnings = []
        cls.win = QmlProcessesWindow(controller=cls.c)
        cls.win.engine.warnings.connect(lambda errors: cls.warnings.extend(e.toString() for e in errors))
        cls.win.bridge.setReducedMotion(True)
        cls.window = cls.win.window
        cls.window.resize(1280, 820)
        cls.win.present()
        for _ in range(3):
            cls.c.tick()
        cls.c.refreshStartup()
        cls.c.refreshServices()
        cls.h.wait_for(lambda: cls.c.property('startupItems'), 2000)
        cls.h.pump(100)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.c.close()
        cls.win.close()
        cls.h.pump(30)
        cls.tmp.cleanup()

    def setUp(self):
        self.warnings.clear()
        self.key(self.Qt.Key_Escape)
        self.key(self.Qt.Key_1, '1')
        self.c.setQuery('')
        self.c.setMode('apps')
        self.h.pump(30)
        page = self.find('appsPage')
        if page:
            page.setProperty('selectedColumn', 0)
            page.setProperty('selectedRow', 0)
            page.setProperty('systemExpanded', False)
        self.h.pump(20)

    def find(self, name):
        return self.h.find_in(self.window.contentItem(), name) or self.window.findChild(self.QObject, name)

    def find_all(self, name):
        found, stack = [], [self.window.contentItem()]
        while stack:
            item = stack.pop()
            if item.objectName() == name:
                found.append(item)
            stack.extend(reversed(item.childItems()))
        return found

    def key(self, key, text=''):
        self.h.key(self.window, key, text=text)
        self.h.pump(30)

    def test_loads_clean_in_both_modes(self):
        self.key(self.Qt.Key_3, '3')
        for palette in ('default-dark', 'default-light', 'green-dark', 'orange-light'):
            self.win.bridge.setPreview(support.palettes()[palette])
            self.h.pump(60)
        self.win.bridge.setPreview(None)
        self.key(self.Qt.Key_1, '1')
        self.assertEqual([w for w in self.warnings if 'processes' in w], [])
        self.assertEqual([w for w in self.warnings if 'AppsPage' in w or 'WindowTile' in w], [])
        self.assertIsNotNone(self.find('processTable'))

    def test_apps_columns_follow_monitor_x(self):
        self.key(self.Qt.Key_3, '3')
        self.window.resize(1826, 1036)          # present() capped the window to the offscreen screen; widen for 3 columns
        self.h.pump(120)
        columns = self.c.property('monitorColumns')
        self.assertEqual([c['label'] for c in columns], ['Philips', 'LG'])
        first = next(item for item in self.find_all('monitorColumn-DP-2') if item.isVisible())
        second = next(item for item in self.find_all('monitorColumn-DP-1') if item.isVisible())
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        origin = self.window.contentItem()
        self.assertLess(first.mapToItem(origin, 0, 0).x(), second.mapToItem(origin, 0, 0).x())
        self.assertGreater(first.width(), 0)
        self.assertFalse(self.find('appsPage').property('stacked'))
        self.window.resize(1280, 820)
        self.h.pump(80)

    def test_narrow_window_stacks_columns_with_the_side_last(self):
        self.key(self.Qt.Key_3, '3')
        self.window.resize(900, 1000)
        self.h.pump(120)
        page = self.find('appsPage')
        self.assertTrue(page.property('stacked'))
        first = next(item for item in self.find_all('monitorColumn-DP-2') if item.isVisible())
        second = next(item for item in self.find_all('monitorColumn-DP-1') if item.isVisible())
        side = next(item for item in self.find_all('windowlessColumn') if item.isVisible())
        origin = self.window.contentItem()
        self.assertEqual(first.mapToItem(origin, 0, 0).x(), second.mapToItem(origin, 0, 0).x())
        self.assertLess(first.mapToItem(origin, 0, 0).y(), second.mapToItem(origin, 0, 0).y())
        self.assertLess(second.mapToItem(origin, 0, 0).y(), side.mapToItem(origin, 0, 0).y())
        self.window.resize(1280, 820)
        self.h.pump(80)

    def test_arrows_cross_monitor_columns(self):
        self.key(self.Qt.Key_3, '3')
        self.h.pump(80)
        page = self.find('appsPage')
        self.assertEqual(page.property('selectedColumn'), 0)
        self.key(self.Qt.Key_Right)
        self.assertEqual(page.property('selectedColumn'), 1)
        self.key(self.Qt.Key_Left)
        self.assertEqual(page.property('selectedColumn'), 0)

    def test_system_windowless_folds_into_one_line(self):
        self.key(self.Qt.Key_3, '3')
        self.h.pump(80)
        self.assertIsNone(self.find('windowlessRow-dbus-daemon'))
        system = self.find('systemWindowless')
        self.assertTrue(system.property('visible'))
        self.assertIn('Sistema', self.find('systemWindowlessLabel').property('text'))
        expected = len(self.c.property('windowless')) + len(self.c.property('systemWindowless').get('apps', []))
        self.assertEqual(self.find('windowlessCount').property('text'), str(expected))
        expanded = self.find('systemWindowlessApps')
        self.assertFalse(expanded.property('visible'))
        page = self.find('appsPage')
        page.setProperty('selectedColumn', len(self.c.property('monitorColumns')))
        page.setProperty('selectedRow', 0)
        self.key(self.Qt.Key_Return)
        self.assertTrue(expanded.property('visible'))
        self.key(self.Qt.Key_Return)
        self.assertFalse(expanded.property('visible'))

    def test_arrows_move_selection(self):
        self.c.setMode('list')
        self.c.select(self.c.property('rows').keys()[0])
        first = self.c.property('selectedKey')
        self.key(self.Qt.Key_Down)
        self.assertNotEqual(self.c.property('selectedKey'), first)
        self.key(self.Qt.Key_K, 'k')
        self.assertEqual(self.c.property('selectedKey'), first)

    def test_slash_focuses_search_and_filters(self):
        self.key(self.Qt.Key_Slash, '/')
        search = self.find('querySearch')
        self.assertTrue(search.property('focused'))
        self.h.type_text(self.window, 'cpu>=0 kit')
        self.h.wait_for(lambda: self.c.property('query') == 'cpu>=0 kit', 1500)
        self.assertEqual(self.c.property('tokens'), ['cpu>=0'])
        self.assertIsNotNone(self.find('token-cpu>=0'))
        self.key(self.Qt.Key_Escape)
        self.key(self.Qt.Key_Escape)
        self.assertFalse(search.property('focused'))

    def test_v_cycles_view(self):
        self.key(self.Qt.Key_V, 'v')
        self.assertEqual(self.c.property('mode'), 'tree')
        self.key(self.Qt.Key_V, 'v')
        self.assertEqual(self.c.property('mode'), 'list')

    def test_delete_asks_and_escape_cancels(self):
        self.c.setMode('list')
        self.c.select('p:21:1000')
        self.key(self.Qt.Key_Delete)
        dialog = self.find('confirmDialog')
        self.assertTrue(dialog.property('opened'))
        self.key(self.Qt.Key_Escape)
        self.assertFalse(dialog.property('opened'))

    def test_sections_by_number(self):
        for key, page in ((self.Qt.Key_2, 'perf'), (self.Qt.Key_3, 'apps'), (self.Qt.Key_4, 'services'),
                          (self.Qt.Key_5, 'startup'), (self.Qt.Key_1, 'procs')):
            self.key(key, chr(key))
            self.assertEqual(self.c.property('page'), page)
        self.assertEqual([w for w in self.warnings if 'processes' in w], [])

    def test_apps_sheet_opens_and_closes(self):
        self.key(self.Qt.Key_3, '3')
        self.h.pump(60)
        self.key(self.Qt.Key_Return)
        sheet = self.find('appSheetHost')
        self.assertTrue(sheet.property('opened'))
        self.key(self.Qt.Key_Escape)
        self.assertFalse(sheet.property('opened'))

    def test_services_without_systemd(self):
        self.key(self.Qt.Key_4, '4')
        self.assertTrue(self.find('servicesEmpty').property('visible'))

    def test_startup_exec_once_has_no_switch(self):
        self.key(self.Qt.Key_5, '5')
        self.h.pump(60)
        self.assertIsNotNone(self.find('startupRow-once:wysun workspaces'))
        self.assertIsNone(self.find('startupSwitch-once:wysun workspaces'))
        self.assertIsNotNone(self.find('startupSwitch-systemd:syncthing.service'))

    def test_palette_and_help(self):
        self.h.key(self.window, self.Qt.Key_K, self.Qt.ControlModifier)
        self.h.pump(30)
        self.assertTrue(self.find('commandPalette').property('opened'))
        self.key(self.Qt.Key_Escape)
        self.assertFalse(self.find('commandPalette').property('opened'))
        self.key(self.Qt.Key_Question, '?')
        self.assertTrue(self.find('shortcutsHelp').property('opened'))
        self.key(self.Qt.Key_Escape)


if __name__ == '__main__':
    unittest.main()
