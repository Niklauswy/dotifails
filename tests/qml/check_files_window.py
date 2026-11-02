"""Wysun Files' QML window (venv Python, offscreen): loads clean in light and dark, grid and list, selection with
the mouse, the keyboard and a rubber band, the floating selection bar, typing to filter, the path field, history
keys with reselection, tabs, empty and error states (F-12…F-30)."""
import os
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


class FilesWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QSettings, Qt
        from wysun_files.quick.window import QmlFilesWindow
        cls.Qt = Qt
        cls.h = support.Harness.get()
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        cls.tmp = tempfile.TemporaryDirectory(prefix='files-win-', dir=scratch)
        cls.root = Path(cls.tmp.name) / 'casa'
        for folder in ('clases', 'Latex', 'repos', 'vacía'):
            (cls.root / folder).mkdir(parents=True)
        (cls.root / 'clases/tema1.md').write_text('# Tema 1\nhola')
        for name in ('tesis.pdf', 'notas.md', 'main.py', 'playa.jpg', 'ensayo.ogg', 'respaldo.zip'):
            (cls.root / name).write_bytes(b'x' * 100)
        cls.settings = QSettings(str(Path(cls.tmp.name) / 'files.ini'), QSettings.IniFormat)
        cls.warnings = []
        cls.win = QmlFilesWindow([str(cls.root)], settings=cls.settings, thumbnails=False)
        cls.win.engine.warnings.connect(lambda errors: cls.warnings.extend(e.toString() for e in errors))
        cls.win.bridge.setReducedMotion(True)
        cls.window = cls.win.window
        cls.win.present()
        cls.window.resize(1180, 800)
        cls.files = cls.win.files
        cls.files.setInspector(False)          # the inspector has its own checks (check_files_inspector)
        cls.h.pump(100)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.win.close()
        cls.h.pump(30)
        cls.tmp.cleanup()

    def setUp(self):
        self.warnings.clear()
        while len(self.files.property('tabs')) > 1:
            self.files.closeTab(len(self.files.property('tabs')) - 1)
        self.files.setViewMode('grid')
        self.tab().navigate(str(self.root))
        self.wait()
        self.model().clearSelection()
        self.model().setFilterText('')
        self.model().setGroup('all')
        self.h.call(self.window, 'focusFiles')
        self.h.pump(30)

    def tab(self):
        return self.files.property('current')

    def model(self):
        return self.tab().property('model')

    def wait(self):
        self.assertTrue(self.h.wait_for(lambda: not self.model().property('loading'), 3000))
        self.h.pump(50)

    def named(self, name):
        from PySide6.QtQuick import QQuickItem
        found, stack = [], [self.window.contentItem()]
        while stack:
            item = stack.pop()
            if item.objectName() == name:
                found.append(item)
            stack.extend(item.childItems() if isinstance(item, QQuickItem) else [])
        return found

    def find(self, name):
        return self.h.find_in(self.window.contentItem(), name)

    def visible(self, name):
        item = self.find(name)
        while item is not None:
            if not item.property('visible') or item.property('opacity') == 0:
                return False
            item = item.parentItem()
        return True

    def view(self):
        return self.find('fileGrid') if self.files.property('viewMode') == 'grid' else self.find('fileList')

    def item_of(self, name):
        folder = [v for v in self.named('folderView') if v.property('visible')][0]
        item = self.h.call(folder, 'itemFor', self.model().rowOf(str(self.root / name)))
        self.h.pump(30)
        return item

    def click_item(self, name, modifiers=None, double=False):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QGuiApplication, QMouseEvent
        item = self.item_of(name)
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 3))
        mods = modifiers if modifiers is not None else Qt.NoModifier
        kinds = [QEvent.MouseButtonPress, QEvent.MouseButtonRelease]
        if double:      # Qt 6 order: press, release, press, double click, release
            kinds += [QEvent.MouseButtonPress, QEvent.MouseButtonDblClick, QEvent.MouseButtonRelease]
        for kind in kinds:
            buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.LeftButton
            event = QMouseEvent(kind, point, self.window.mapToGlobal(point), Qt.LeftButton, buttons, mods)
            QGuiApplication.sendEvent(self.window, event)
            self.h.pump(10)
        self.h.pump(30)

    def selected(self):
        return [Path(p).name for p in self.model().property('selectedPaths')]

    def key(self, key, modifiers=None, text=''):
        self.h.key(self.window, key, modifiers, text)

    # ---------------------------------------------------------------- loading
    def test_loads_without_warnings(self):
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.window.property('title'), 'casa · Wysun Archivos')
        self.assertEqual(self.find('heroTitle').property('text'), 'casa')
        self.assertEqual(self.find('heroSummary').property('text'), '4 carpetas · 6 archivos · 600 B')
        self.assertEqual(self.find('statusText').property('text'), '10 elementos')
        self.assertTrue(self.find('freeText').property('text').endswith('libres'))
        self.assertEqual(self.warnings, [])

    def test_every_palette_and_both_views_render_clean(self):
        for palette in ('default-light', 'green-dark', 'orange-light', 'blue-dark'):
            for mode in ('grid', 'list'):
                with self.subTest(palette=palette, mode=mode):
                    self.h.use(palette)
                    self.files.setViewMode(mode)
                    self.h.pump(50)
                    self.assertFalse(self.window.grabWindow().isNull())
        self.win.bridge.setPreview({})
        self.assertEqual(self.warnings, [])

    def test_widths_follow_the_window_class(self):
        nav = self.find('filesNav')
        for width, mode in ((400, 'modal'), (720, 'rail'), (1180, 'standard')):
            self.window.resize(width, 800)
            self.h.pump(50)
            self.assertEqual(nav.property('mode'), mode)
        self.assertEqual(self.warnings, [])

    # ---------------------------------------------------------------- views
    def test_ctrl_1_and_2_switch_grid_and_list(self):
        self.key(self.Qt.Key_2, self.Qt.ControlModifier, '2')
        self.assertEqual(self.files.property('viewMode'), 'list')
        self.assertIsNotNone(self.find('fileList'))
        self.click_item('notas.md')
        self.assertEqual(self.selected(), ['notas.md'])
        self.key(self.Qt.Key_1, self.Qt.ControlModifier, '1')
        self.assertEqual(self.files.property('viewMode'), 'grid')
        self.assertEqual(self.selected(), ['notas.md'], 'the selection survives the switch')

    def test_list_column_sorts(self):
        self.files.setViewMode('list')
        self.h.pump(50)
        column = self.find('column-size')
        self.h.click(self.window, *self._centre(column))
        self.assertEqual(self.model().property('sortKey'), 'size')
        self.h.click(self.window, *self._centre(column))
        self.assertTrue(self.model().property('descending'))
        self.model().sortBy('name', False)

    def _centre(self, item):
        from PySide6.QtCore import QPointF
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        return point.x(), point.y()

    # ---------------------------------------------------------------- selection
    def test_click_ctrl_and_shift_select_and_the_bar_floats(self):
        self.click_item('main.py')
        self.assertEqual(self.selected(), ['main.py'])
        self.assertFalse(self.visible('selectionBar'), 'one file: no floating bar')
        self.click_item('tesis.pdf', self.Qt.ControlModifier)
        self.assertEqual(self.selected(), ['main.py', 'tesis.pdf'])
        self.assertTrue(self.h.wait_for(lambda: self.visible('selectionBar'), 1000))
        self.assertEqual(self.find('selectionCount').property('text'), '2 seleccionados')
        self.assertIn('2 seleccionados', self.find('statusText').property('text'))
        self.click_item('notas.md', self.Qt.ShiftModifier)      # from the anchor Ctrl+click set (tesis.pdf)
        self.assertEqual(self.selected(), ['notas.md', 'playa.jpg', 'respaldo.zip', 'tesis.pdf'])
        self.key(self.Qt.Key_Escape)
        self.assertEqual(self.selected(), [])

    def test_arrows_move_the_selection(self):
        self.click_item('clases')
        self.key(self.Qt.Key_Right)
        self.assertEqual(self.selected(), ['Latex'])
        self.key(self.Qt.Key_Right, self.Qt.ShiftModifier)
        self.assertEqual(self.selected(), ['Latex', 'repos'])
        self.key(self.Qt.Key_End)
        self.assertEqual(self.selected(), ['tesis.pdf'])
        self.key(self.Qt.Key_A, self.Qt.ControlModifier, 'a')
        self.assertEqual(len(self.selected()), 10)

    def test_rubber_band_selects_what_it_crosses(self):
        # From the empty end of the last row up to the middle of the two last files.
        a, b = self.item_of('respaldo.zip'), self.item_of('tesis.pdf')
        from PySide6.QtCore import QPointF
        start = b.mapToScene(QPointF(b.width() * 2.5, b.height() - 4))
        end = a.mapToScene(QPointF(a.width() / 2, a.height() / 2))
        self.model().clearSelection()
        self.h.move(self.window, start.x(), start.y())
        self.h.press(self.window, start.x(), start.y())
        from PySide6.QtCore import QEvent, Qt
        for step in range(1, 6):          # moves with the left button held
            self.h._mouse(self.window, QEvent.MouseMove, start.x() + (end.x() - start.x()) * step / 5,
                          start.y() + (end.y() - start.y()) * step / 5, Qt.NoButton, Qt.LeftButton)
        self.h.release(self.window, end.x(), end.y())
        self.assertEqual(self.selected(), ['respaldo.zip', 'tesis.pdf'])

    def test_background_click_clears_the_selection(self):
        self.click_item('main.py')
        from PySide6.QtCore import QPointF
        last = self.item_of('tesis.pdf')
        point = last.mapToScene(QPointF(last.width() * 2.5, last.height() / 2))
        self.h.click(self.window, point.x(), point.y())
        self.assertEqual(self.selected(), [])

    # ---------------------------------------------------------------- filter
    def test_typing_starts_the_filter_and_escape_cascades(self):
        self.click_item('main.py')
        self.h.type_text(self.window, 'no')
        self.assertEqual(self.model().property('filterText'), 'no')
        self.assertEqual([Path(self.model().pathAt(r)).name for r in range(self.model().rowCount())], ['notas.md'])
        self.assertEqual(self.find('statusText').property('text'), '1 de 10 elementos')
        self.key(self.Qt.Key_Escape)          # in the field: empties it
        self.assertEqual(self.model().property('filterText'), '')
        self.key(self.Qt.Key_Escape)          # hands focus back to the files
        self.assertTrue(self.view().property('activeFocus'))

    def test_kind_chips_keep_folders(self):
        chip = self.find('chip-code')
        self.h.click(self.window, *self._centre(chip))
        self.assertEqual(self.model().property('group'), 'code')
        names = [Path(self.model().pathAt(r)).name for r in range(self.model().rowCount())]
        self.assertEqual(names, ['clases', 'Latex', 'repos', 'vacía', 'main.py'])
        self.assertTrue(chip.property('selected'))
        self.h.click(self.window, *self._centre(chip))
        self.assertEqual(self.model().property('group'), 'all')
        self.assertFalse(chip.property('selected'))

    def test_no_match_state(self):
        self.model().setFilterText('zzz')
        self.h.pump(50)
        state = self.find('emptyState')
        self.assertIsNotNone(state)
        self.assertEqual(state.property('title'), 'Nada coincide con el filtro')

    # ---------------------------------------------------------------- navigation
    def test_enter_and_double_click_open_folders_and_alt_up_reselects(self):
        self.click_item('clases')
        self.key(self.Qt.Key_Return, text='\r')
        self.wait()
        self.assertEqual(self.tab().property('path'), str(self.root / 'clases'))
        self.key(self.Qt.Key_Up, self.Qt.AltModifier)
        self.wait()
        self.assertEqual(self.tab().property('path'), str(self.root))
        self.assertEqual(self.selected(), ['clases'])
        self.click_item('repos', double=True)
        self.wait()
        self.assertEqual(self.tab().property('path'), str(self.root / 'repos'))
        self.key(self.Qt.Key_Left, self.Qt.AltModifier)
        self.wait()
        self.assertEqual(self.tab().property('path'), str(self.root))
        self.key(self.Qt.Key_Right, self.Qt.AltModifier)
        self.wait()
        self.assertEqual(self.tab().property('path'), str(self.root / 'repos'))
        self.key(self.Qt.Key_Backspace)
        self.wait()
        self.assertEqual(self.tab().property('path'), str(self.root))

    def test_opening_a_file_is_requested(self):
        seen = []
        self.files.openRequested.connect(seen.append)
        self.click_item('notas.md', double=True)
        self.assertEqual(seen, [[str(self.root / 'notas.md')]])
        self.files.openRequested.disconnect()

    def test_ctrl_l_edits_the_path(self):
        self.key(self.Qt.Key_L, self.Qt.ControlModifier, 'l')
        field = self.find('pathField')
        self.assertTrue(field.property('activeFocus'))
        self.assertEqual(field.property('text'), str(self.root))
        field.setProperty('text', str(self.root / 'Latex'))
        self.key(self.Qt.Key_Return, text='\r')
        self.wait()
        self.assertEqual(self.tab().property('path'), str(self.root / 'Latex'))
        self.assertFalse(self.find('pathBar').property('editing'))
        self.key(self.Qt.Key_L, self.Qt.ControlModifier, 'l')
        self.key(self.Qt.Key_Escape)
        self.assertFalse(self.find('pathBar').property('editing'))
        self.assertEqual(self.tab().property('path'), str(self.root / 'Latex'))

    def test_a_missing_path_is_refused_with_a_message(self):
        self.key(self.Qt.Key_L, self.Qt.ControlModifier, 'l')
        self.find('pathField').setProperty('text', str(self.root / 'no-existe'))
        self.key(self.Qt.Key_Return, text='\r')
        self.assertEqual(self.tab().property('path'), str(self.root))
        self.assertIn('no-existe', self.find('snackbars').property('currentText') or '')
        self.key(self.Qt.Key_Escape)

    def test_empty_folder(self):
        self.tab().navigate(str(self.root / 'vacía'))
        self.wait()
        self.assertEqual(self.find('emptyState').property('title'), 'Esta carpeta está vacía')

    def test_tabs_by_keyboard(self):
        self.key(self.Qt.Key_T, self.Qt.ControlModifier, 't')
        self.assertEqual(len(self.files.property('tabs')), 2)
        self.assertTrue(self.h.wait_for(lambda: self.visible('tabStrip'), 1000))
        self.tab().navigate(str(self.root / 'Latex'))
        self.wait()
        self.assertEqual(self.window.property('title'), 'Latex · Wysun Archivos')
        self.key(self.Qt.Key_Tab, self.Qt.ControlModifier)
        self.assertEqual(self.files.property('currentIndex'), 0)
        self.key(self.Qt.Key_W, self.Qt.ControlModifier, 'w')
        self.assertEqual(len(self.files.property('tabs')), 1)
        self.assertEqual(self.tab().property('path'), str(self.root / 'Latex'))
        self.assertEqual(self.warnings, [])

    def test_the_wheel_scrolls_within_bounds(self):
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QGuiApplication, QWheelEvent
        big = self.root / 'muchos'
        big.mkdir(exist_ok=True)
        import shutil
        self.addCleanup(shutil.rmtree, big, True)
        for i in range(300):
            (big / f'f{i:03d}.txt').touch()
        self.tab().navigate(str(big))
        self.wait()
        grid = self.find('fileGrid')
        top = grid.property('contentY')
        point = grid.mapToScene(QPointF(grid.width() / 2, grid.height() / 2))

        def wheel(dy):
            QGuiApplication.sendEvent(self.window, QWheelEvent(point, self.window.mapToGlobal(point), QPoint(), QPoint(0, dy),
                                                               Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
            self.h.pump(20)
        wheel(-120)
        self.assertGreater(grid.property('contentY'), top)
        for _ in range(200):
            wheel(-120)
        bottom = grid.property('contentY')
        self.assertAlmostEqual(bottom, grid.property('originY') + grid.property('contentHeight') - grid.height(), delta=1)
        for _ in range(200):
            wheel(120)
        self.assertEqual(grid.property('contentY'), top)

    def test_bookmarks_show_in_the_drawer_and_their_menu_removes_them(self):
        target = str(self.root / 'Latex')
        places = self.win.places
        places.toggleBookmark(target)
        self.h.pump(50)
        item = self.find('nav-' + target)
        self.assertIsNotNone(item)
        self.tab().navigate(str(self.root / 'Latex'))
        self.wait()
        self.assertEqual(self.find('filesNav').property('currentId'), target, 'the most specific place lights up')
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QGuiApplication, QMouseEvent
        point = item.mapToScene(QPointF(60, 20))
        for kind, buttons in ((QEvent.MouseButtonPress, self.Qt.RightButton), (QEvent.MouseButtonRelease, self.Qt.NoButton)):
            QGuiApplication.sendEvent(self.window, QMouseEvent(kind, point, self.window.mapToGlobal(point), self.Qt.RightButton,
                                                               buttons, self.Qt.NoModifier))
        self.h.pump(50)
        menu = self.find('placeMenu')
        self.h.call(menu, 'trigger', 3)
        self.h.pump(50)
        self.assertFalse(places.isBookmark(target))
        self.assertIsNone(self.find('nav-' + target))
        self.assertEqual(self.warnings, [])

    def _wheel_folder(self):
        import shutil
        big = self.root / 'muchos'
        big.mkdir(exist_ok=True)
        self.addCleanup(shutil.rmtree, big, True)
        for i in range(300):
            (big / f'f{i:03d}.txt').touch()
        self.tab().navigate(str(big))
        self.wait()
        return self.find('fileGrid')

    def _send_wheel(self, point, pixel, angle, device):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QGuiApplication, QWheelEvent
        QGuiApplication.sendEvent(self.window, QWheelEvent(point, self.window.mapToGlobal(point), QPoint(0, pixel), QPoint(0, angle),
                                                           Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False,
                                                           Qt.MouseEventNotSynthesized, device))
        self.h.pump(20)

    def test_a_touchpad_scrolls(self):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QInputDevice, QPointingDevice
        grid = self._wheel_folder()
        device = QPointingDevice('touchpad', 77, QInputDevice.DeviceType.TouchPad, QPointingDevice.PointerType.Finger,
                                 QInputDevice.Capability.Position | QInputDevice.Capability.Scroll, 1, 0)
        top = grid.property('contentY')
        self._send_wheel(grid.mapToScene(QPointF(grid.width() / 2, grid.height() / 2)), -60, -120, device)
        self.assertGreater(grid.property('contentY'), top)

    def test_the_wheel_scrolls_from_anywhere_in_the_folder(self):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPointingDevice
        grid = self._wheel_folder()
        device = QPointingDevice.primaryPointingDevice()
        for name, point in (('header', QPointF(grid.width() - 20, 30)), ('bottom', QPointF(grid.width() - 20, grid.height() - 10))):
            with self.subTest(over=name):
                before = grid.property('contentY')
                self._send_wheel(grid.mapToScene(point), 0, -120, device)
                self.assertGreater(grid.property('contentY'), before)

    def test_f1_lists_the_shortcuts(self):
        self.key(self.Qt.Key_F1)
        sheet = self.find('shortcutSheet')
        self.assertTrue(sheet.property('opened'))
        self.h.call(sheet, 'close')
        self.assertEqual(self.warnings, [])

    def test_hidden_files_toggle(self):
        (self.root / '.secreto').write_text('s')
        self.tab().navigate(str(self.root / 'clases'))
        self.tab().navigate(str(self.root))
        self.wait()
        self.key(self.Qt.Key_H, self.Qt.ControlModifier, 'h')
        self.assertTrue(self.h.wait_for(lambda: self.model().rowOf(str(self.root / '.secreto')) >= 0, 2000))
        self.key(self.Qt.Key_H, self.Qt.ControlModifier, 'h')
        self.assertEqual(self.model().rowOf(str(self.root / '.secreto')), -1)
        (self.root / '.secreto').unlink()


if __name__ == '__main__':
    unittest.main()
