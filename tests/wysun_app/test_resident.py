"""The resident records the clipboard history; it has no windows."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication

from wysun_services.data_v2 import StoreV2
from wysun_services import daemon


class ResidentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = StoreV2(self.tmp.name)
        self.daemon = daemon.ClipboardDaemon(self.store, test=True)

    def test_constructs_headless_and_hosts_clipboard_watch(self):
        from wysun_services.wayland_clipboard import ClipboardWatch
        with patch.object(ClipboardWatch, 'start'):
            watch = ClipboardWatch(self.daemon)
        self.assertIs(watch.owner, self.daemon)
        self.assertFalse(hasattr(self.daemon, 'search'))

    def test_paused_follows_the_shared_store_live(self):
        self.assertFalse(self.daemon.paused)
        self.store.set('paused', '1')
        self.assertTrue(self.daemon.paused)

    def test_the_resident_only_records_the_clipboard(self):
        self.assertFalse(hasattr(self.daemon, 'show_mode'))
        self.assertFalse(hasattr(self.daemon, 'utilities'))

    def test_reload_without_a_resident_starts_one_in_the_background(self):
        with tempfile.TemporaryDirectory() as state, patch.dict(os.environ, XDG_STATE_HOME=state), \
                patch.object(daemon, 'send', return_value=False), patch.object(daemon.subprocess, 'Popen') as popen:
            self.assertEqual(daemon.main(['reload']), 0)
        argv = popen.call_args.args[0]
        self.assertEqual(argv[1:], ['-P', '-m', 'wysun_services.daemon'])
        self.assertIn('wysun_services.daemon', argv)
        self.assertTrue(popen.call_args.kwargs['start_new_session'])

    def test_reload_with_a_resident_only_asks_it(self):
        with patch.object(daemon, 'send', return_value=True) as send, patch.object(daemon.subprocess, 'Popen') as popen:
            self.assertEqual(daemon.main(['reload']), 0)
        self.assertEqual(send.call_args.args[1], b'reload')
        popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
