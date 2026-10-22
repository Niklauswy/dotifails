"""The resident hosts utilities and clipboard history; it has no launcher window."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication

from data_v2 import StoreV2
import orbit


class ResidentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = StoreV2(self.tmp.name)
        self.daemon = orbit.OrbitDaemon(self.store, test=True)

    def test_constructs_headless_and_hosts_clipboard_watch(self):
        from wayland_clipboard import ClipboardWatch
        with patch.object(ClipboardWatch, 'start'):
            watch = ClipboardWatch(self.daemon)
        self.assertIs(watch.owner, self.daemon)
        self.assertFalse(hasattr(self.daemon, 'search'))

    def test_paused_follows_the_shared_store_live(self):
        self.assertFalse(self.daemon.paused)
        self.store.set('paused', '1')
        self.assertTrue(self.daemon.paused)

    def test_launcher_modes_are_not_qt_menus_any_more(self):
        with patch.object(orbit, 'run') as run:
            self.daemon.show_mode('power')
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0][1], 'session')
        with patch.object(self.daemon, 'show_utility') as utility:
            self.daemon.show_mode('clipboard')
            self.daemon.show_mode('color')
            utility.assert_called_once_with('color')


if __name__ == '__main__':
    unittest.main()
