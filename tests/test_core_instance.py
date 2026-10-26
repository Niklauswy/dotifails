"""wysun_core.instance: one process per name, line requests with optional replies."""
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_core.instance import SingleInstance, send


class InstanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / 'run'
        self.instances = []

    def instance(self, name='t'):
        created = SingleInstance(name, self.dir)
        self.instances.append(created)
        self.addCleanup(created.close)
        return created

    def serve(self, instance, handler, seconds=2.0):
        stop = time.monotonic() + seconds
        def loop():
            while time.monotonic() < stop:
                instance.poll(handler)
                time.sleep(0.005)
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        return thread

    def test_second_claim_fails_while_first_holds_lock(self):
        first, second = self.instance(), self.instance()
        self.assertTrue(first.claim())
        self.assertFalse(second.claim())
        first.close()
        self.assertTrue(second.claim())

    def test_stale_socket_is_replaced(self):
        self.dir.mkdir(mode=0o700)
        stale = socket.socket(socket.AF_UNIX)
        stale.bind(str(self.dir / 't.sock'))
        stale.close()
        self.assertTrue(self.instance().claim())

    def test_non_socket_endpoint_is_refused(self):
        self.dir.mkdir(mode=0o700)
        (self.dir / 't.sock').write_text('x')
        with self.assertRaises(RuntimeError):
            self.instance().claim()

    def test_send_delivers_line_and_reads_reply(self):
        server = self.instance()
        self.assertTrue(server.claim())
        self.serve(server, lambda line: b'ok:' + line)
        self.assertEqual(send(server.endpoint, b'hola', reply=True), b'ok:hola')

    def test_send_without_reply_reports_delivery(self):
        server = self.instance()
        server.claim()
        seen = []
        self.serve(server, lambda line: seen.append(line))
        self.assertIs(send(server.endpoint, b'present'), True)
        deadline = time.monotonic() + 1
        while not seen and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(seen, [b'present'])

    def test_send_without_server_is_false(self):
        self.assertIs(send(self.dir / 'none.sock', b'x'), False)
        self.assertIsNone(send(self.dir / 'none.sock', b'x', reply=True))

    def test_send_retries_until_server_appears(self):
        server = self.instance()
        def late():
            time.sleep(0.2)
            server.claim()
            self.serve(server, lambda line: b'up')
        threading.Thread(target=late, daemon=True).start()
        self.assertEqual(send(server.endpoint, b'?', reply=True, retry=2.0), b'up')

    def test_oversized_request_is_dropped_without_reply(self):
        server = self.instance()
        server.claim()
        calls = []
        self.serve(server, lambda line: calls.append(line) or b'x')
        self.assertIn(send(server.endpoint, b'a' * 5000, reply=True), (b'', None))
        self.assertEqual(calls, [])

    def test_a_failing_handler_does_not_wedge_later_requests(self):
        server = self.instance()
        server.claim()
        calls = []
        def handler(line):
            calls.append(line)
            if line == b'boom':
                raise OSError('recording deleted mid-scan')
            return b'ok'
        self.serve(server, handler)
        self.assertIn(send(server.endpoint, b'boom', reply=True), (b'', None))
        self.assertEqual(send(server.endpoint, b'next', reply=True), b'ok')
        self.assertEqual(calls, [b'boom', b'next'])

    def test_endpoint_and_lock_are_private(self):
        server = self.instance()
        server.claim()
        self.assertEqual(server.endpoint.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.dir.stat().st_mode & 0o777, 0o700)

    def test_close_removes_endpoint(self):
        server = self.instance()
        server.claim()
        server.close()
        self.assertFalse(server.endpoint.exists())

    def test_termination_right_after_claim_removes_the_socket(self):
        import signal
        import subprocess
        child = subprocess.Popen([sys.executable, '-c', (
            'import sys, time; sys.path.insert(0, sys.argv[1])\n'
            'from wysun_core.instance import SingleInstance, release_on_termination\n'
            'owner = SingleInstance("t", sys.argv[2]); owner.claim(); release_on_termination(owner)\n'
            'print("ready", flush=True); time.sleep(30)\n'),
            str(Path(__file__).resolve().parents[1] / 'apps/python'), str(self.dir)], stdout=subprocess.PIPE, text=True)
        self.addCleanup(child.kill)
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        self.assertTrue((self.dir / 't.sock').exists())
        child.send_signal(signal.SIGTERM)
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertFalse((self.dir / 't.sock').exists())

    def test_qt_notifier_dispatches_requests(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtCore import QCoreApplication
        from wysun_core.qt_instance import InstanceNotifier
        app = QCoreApplication.instance() or QCoreApplication([])
        server = self.instance()
        server.claim()
        seen = []
        notifier = InstanceNotifier(server, lambda line: seen.append(line))
        self.addCleanup(notifier.close)
        threading.Thread(target=lambda: send(server.endpoint, b'present'), daemon=True).start()
        deadline = time.monotonic() + 2
        while not seen and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
        self.assertEqual(seen, [b'present'])


class RecorderInstanceTests(unittest.TestCase):
    def test_recorder_instance_keeps_private_directory_and_display_tag(self):
        from unittest.mock import patch
        capture = Path(__file__).resolve().parents[1] / 'apps/recorder'
        sys.path.insert(0, str(capture))
        from wysun_recorder.ui import instance as recorder
        self.assertIn('from wysun_core.instance import SingleInstance', (capture / 'wysun_recorder/ui/instance.py').read_text())
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_RUNTIME_DIR': tmp, 'WAYLAND_DISPLAY': 'wayland-9'}):
            first, second = recorder.Instance(name='gui'), recorder.Instance(name='gui')
            try:
                self.assertEqual(first.path.parent, Path(tmp) / f'wysun-recorder-{os.getuid()}')
                self.assertEqual(first.path.parent.stat().st_mode & 0o777, 0o700)
                self.assertTrue(first.path.name.startswith('gui-'))
                self.assertTrue(first.claim())
                self.assertFalse(second.claim())
            finally:
                first.close()
                second.close()

if __name__ == '__main__':
    unittest.main()
