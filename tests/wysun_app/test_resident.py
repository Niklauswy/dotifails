"""The resident records the clipboard history; it has no windows."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QGuiApplication

from wysun_services.data_v2 import StoreV2
from wysun_services import daemon


class ResidentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

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

    def test_a_resident_of_an_earlier_version_can_re_exec_into_this_one(self):
        # Earlier residents restart themselves as `wysun_services.daemon daemon --daemon`.
        with patch.object(daemon, 'send', return_value=True):
            self.assertEqual(daemon.main(['daemon', '--daemon']), 0)

    def test_re_exec_stops_the_clipboard_watcher_first(self):
        # An orphaned `wl-paste --watch` survives execve and records every copy twice.
        calls = []
        watch = type('Watch', (), {'stop': lambda _self: calls.append('stop')})()
        closer = type('Closer', (), {'close': lambda _self: calls.append('close')})()
        self.daemon.wayland_clipboard = watch
        with patch.object(daemon.os, 'execve', side_effect=lambda *_: calls.append('execve')):
            daemon.re_exec(closer, closer, self.daemon)
        self.assertEqual(calls, ['stop', 'close', 'close', 'execve'])

    def test_reload_with_a_resident_only_asks_it(self):
        with patch.object(daemon, 'send', return_value=True) as send, patch.object(daemon.subprocess, 'Popen') as popen:
            self.assertEqual(daemon.main(['reload']), 0)
        self.assertEqual(send.call_args.args[1], b'reload')
        popen.assert_not_called()

    def test_the_resident_never_loads_qt_widgets(self):
        """It has no windows: a Widgets application (style, palette, icon theme) would only cost memory."""
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2] / 'apps/python'
        code = ('import sys; sys.path.insert(0, %r)\n'
                'from wysun_services import daemon, wayland_clipboard\n'
                'import inspect\n'
                "print('PySide6.QtWidgets' in sys.modules, 'QApplication(' in inspect.getsource(daemon.main))" % str(root))
        done = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, QT_QPA_PLATFORM='offscreen'))
        self.assertEqual((done.returncode, done.stdout.strip()), (0, 'False False'), done.stderr[-500:])


if __name__ == '__main__':
    unittest.main()
