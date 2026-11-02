"""Wysun Files' QML controller (venv Python): tabs, per-tab history with reselection, files that open their
folder, settings that persist (view mode, hidden files, inspector) and the window title."""
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


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()

    def setUp(self):
        from PySide6.QtCore import QSettings
        from wysun_files.quick.controller import FilesController
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        self.tmp = tempfile.TemporaryDirectory(prefix='files-ctl-', dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for folder in ('a/b/c', 'd'):
            (self.root / folder).mkdir(parents=True)
        (self.root / 'a/nota.txt').write_text('x')
        self.settings = QSettings(str(self.root / 'files.ini'), QSettings.IniFormat)
        self.files = FilesController([str(self.root / 'a')], settings=self.settings, thumbnails=False)
        self.addCleanup(self.files.close)

    def tab(self):
        return self.files.property('current')

    def wait(self, tab=None):
        tab = tab or self.tab()
        self.assertTrue(self.h.wait_for(lambda: not tab.property('model').property('loading'), 3000))

    def selected(self, tab=None):
        return [Path(p).name for p in (tab or self.tab()).property('model').property('selectedPaths')]

    def test_starts_on_the_given_folder(self):
        self.wait()
        self.assertEqual(self.tab().property('path'), str(self.root / 'a'))
        self.assertEqual(self.tab().property('title'), 'a')
        self.assertEqual(self.files.property('title'), 'a · Wysun Archivos')

    def test_history_back_forward_and_up_reselects_the_folder_we_left(self):
        tab = self.tab()
        self.assertTrue(tab.navigate(str(self.root / 'a/b')))
        self.assertTrue(tab.navigate(str(self.root / 'a/b/c')))
        self.assertTrue(tab.property('canBack'))
        tab.back()
        self.wait()
        self.assertEqual(tab.property('path'), str(self.root / 'a/b'))
        self.assertEqual(self.selected(), ['c'], 'going back to a parent reselects the child')
        self.assertTrue(tab.property('canForward'))
        tab.forward()
        self.assertEqual(tab.property('path'), str(self.root / 'a/b/c'))
        tab.up()
        tab.up()
        self.wait()
        self.assertEqual(tab.property('path'), str(self.root / 'a'))
        self.assertEqual(self.selected(), ['b'])
        self.assertFalse(tab.property('canForward'), 'a new step clears the forward list')

    def test_up_from_root_does_nothing(self):
        tab = self.tab()
        tab.navigate('/')
        tab.up()
        self.assertEqual(tab.property('path'), '/')

    def test_a_file_opens_its_folder_and_selects_it(self):
        self.tab().navigate(str(self.root / 'd'))
        self.assertTrue(self.tab().navigate(str(self.root / 'a/nota.txt')))
        self.wait()
        self.assertEqual(self.tab().property('path'), str(self.root / 'a'))
        self.assertEqual(self.selected(), ['nota.txt'])

    def test_missing_and_unreadable_folders_are_refused(self):
        locked = self.root / 'cerrada'
        locked.mkdir()
        locked.chmod(0)
        self.addCleanup(locked.chmod, 0o755)
        self.assertFalse(self.tab().navigate(str(self.root / 'no')))
        if not os.access(locked, os.R_OK):
            self.assertFalse(self.tab().navigate(str(locked)))
        self.assertEqual(self.tab().property('path'), str(self.root / 'a'))

    def test_navigating_clears_the_filters(self):
        model = self.tab().property('model')
        model.setFilterText('zz')
        model.setGroup('images')
        self.tab().navigate(str(self.root / 'd'))
        self.assertEqual((model.property('filterText'), model.property('group')), ('', 'all'))

    def test_crumbs(self):
        self.tab().navigate(str(self.root / 'a/b'))
        crumbs = self.tab().property('crumbs')
        self.assertEqual([c['path'] for c in crumbs][-2:], [str(self.root / 'a'), str(self.root / 'a/b')])
        self.assertEqual(crumbs[-1]['label'], 'b')
        self.tab().navigate(str(Path.home()))
        crumbs = self.tab().property('crumbs')
        self.assertEqual((crumbs[0]['label'], crumbs[0]['icon'], len(crumbs)), ('Inicio', 'home', 1))
        self.tab().navigate('/')
        self.assertEqual(self.tab().property('crumbs')[0]['label'], 'Sistema')

    def test_tabs(self):
        self.assertEqual(self.files.newTab(str(self.root / 'd')), 1)
        self.assertEqual(self.files.property('currentIndex'), 1)
        self.assertEqual(self.tab().property('path'), str(self.root / 'd'))
        self.files.newTab('')
        self.assertEqual(self.tab().property('path'), str(self.root / 'd'), 'a new tab opens where the current one is')
        self.files.cycleTab(1)
        self.assertEqual(self.files.property('currentIndex'), 0)
        self.files.cycleTab(-1)
        self.assertEqual(self.files.property('currentIndex'), 2)
        self.files.closeTab(2)
        self.assertEqual(len(self.files.property('tabs')), 2)
        self.assertEqual(self.files.property('currentIndex'), 1)
        closed = []
        self.files.closeRequested.connect(lambda: closed.append(1))
        self.files.closeTab(0)
        self.files.closeTab(0)
        self.assertEqual(closed, [1], 'closing the last tab closes the window')
        self.assertEqual(len(self.files.property('tabs')), 1)

    def test_several_paths_open_one_tab_each(self):
        from wysun_files.quick.controller import FilesController
        files = FilesController([str(self.root / 'a'), str(self.root / 'd')], settings=self.settings, thumbnails=False)
        self.addCleanup(files.close)
        self.assertEqual([t.property('path') for t in files.property('tabs')], [str(self.root / 'a'), str(self.root / 'd')])

    def test_hidden_and_view_mode_persist_and_reach_every_tab(self):
        self.files.newTab(str(self.root / 'd'))
        self.files.setShowHidden(True)
        self.assertTrue(all(t.property('model').property('showHidden') for t in self.files.property('tabs')))
        self.files.setViewMode('list')
        self.files.setInspector(False)
        self.settings.sync()
        self.assertEqual(self.settings.value('viewMode'), 'list')
        self.assertIn(self.settings.value('hidden'), (True, 'true'))
        from wysun_files.quick.controller import FilesController
        again = FilesController([str(self.root)], settings=self.settings, thumbnails=False)
        self.addCleanup(again.close)
        self.assertEqual(again.property('viewMode'), 'list')
        self.assertTrue(again.property('showHidden'))
        self.assertFalse(again.property('inspector'))
        self.assertTrue(again.property('current').property('model').property('showHidden'))

    def test_free_space_of_the_current_folder(self):
        self.assertRegex(self.tab().property('freeText'), r'libres$')

    def test_newest_first_by_default_and_each_folder_remembers_its_order(self):
        tab, model = self.tab(), self.tab().property('model')
        self.assertEqual((model.property('sortKey'), model.property('descending')), ('modified', True))
        model.sortBy('name', False)
        tab.navigate(str(self.root / 'd'))
        self.assertEqual((model.property('sortKey'), model.property('descending')), ('modified', True))
        tab.navigate(str(self.root / 'a'))
        self.assertEqual((model.property('sortKey'), model.property('descending')), ('name', False))

    def test_special_folders_have_glyphs(self):
        from wysun_files.quick.controller import FilesController
        self.assertIsInstance(FilesController.special_glyphs(), dict)


if __name__ == '__main__':
    unittest.main()
