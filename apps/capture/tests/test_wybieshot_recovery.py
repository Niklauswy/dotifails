"""Recovery IPC uses synthetic documents and private sockets, never the desktop."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from wybieshot.document import Document
from wybieshot.recovery import RecoveryServer, session_key, runtime_directory
from wybieshot.schema import Layer
from wybieshot.storage import Storage
from wybieshot.ui.floating import FloatingSelection
from wybieshot.ui.main import Window
from wybieshot.ui.selection import SelectionGroup


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ipc_acknowledges_and_isolates_compositors(self):
        with tempfile.TemporaryDirectory(prefix='wr-') as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
            owner = Mock()
            owner.recover_capture.return_value = True
            self.app._wybieshot_window = owner
            server = RecoveryServer(self.app)
            script = 'from wybieshot.recovery import request_recovery; print(request_recovery())'
            try:
                env = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE='another-compositor')
                result = subprocess.check_output([sys.executable, '-c', script], env=env, text=True)
                self.assertEqual(result.strip(), '(0, 0)')
                owner.recover_capture.assert_not_called()
                for response, expected in ((True, '(1, 0)'), (False, '(0, 0)'), ('pending', '(0, 1)'), (RuntimeError('cannot save'), '(0, 1)')):
                    owner.recover_capture.side_effect = response if isinstance(response, Exception) else None
                    owner.recover_capture.return_value = response
                    process = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.PIPE, text=True)
                    deadline = time.monotonic() + 5
                    while process.poll() is None and time.monotonic() < deadline:
                        self.app.processEvents()
                        time.sleep(.005)
                    if process.poll() is None:process.kill()
                    output, _ = process.communicate(timeout=2)
                    self.assertEqual(process.returncode, 0)
                    self.assertEqual(output.strip(), expected)
            finally:
                server.close()
                self.app._wybieshot_window = None
            self.assertFalse(server.path.exists())

    def test_pending_portal_cancellation_does_not_claim_closed(self):
        from types import SimpleNamespace
        owner = SimpleNamespace(busy=True, overlay=None, cancel_capture=Mock())
        self.assertEqual(Window.recover_capture(owner), 'pending')
        owner.cancel_capture.assert_called_once_with()

    def test_rejects_shared_runtime_directory(self):
        with tempfile.TemporaryDirectory(prefix='wr-') as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
            path = runtime_directory()
            path.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, 'private'):runtime_directory()

    def test_recovery_saves_each_annotation_and_leaves_library_idle(self):
        with tempfile.TemporaryDirectory() as directory:
            window = Window(Storage(directory));window.thumbnail_timer.stop();window.quick.hide()
            overlays = []
            try:
                self.assertFalse(window.recover_capture())
                image = QImage(200, 100, QImage.Format_ARGB32);image.fill(QColor('black'))
                for _ in range(2):
                    overlay = FloatingSelection(image, QRect(0, 0, 200, 100))
                    overlay.document = Document(image, 'Synthetic recovery')
                    overlay.document.add_layer(Layer('rectangle', [(10, 10), (30, 30)]))
                    overlays.append(overlay)
                window.overlay = SelectionGroup(overlays);window.busy = True
                documents = [o.document for o in overlays]
                self.assertTrue(window.recover_capture())
                self.assertIsNone(window.overlay)
                for doc in documents:
                    reopened = window.storage.load(doc.session_id)
                    self.assertEqual(len(reopened.layers), 1)
                window.overlay = SelectionGroup(overlays);window.busy = True
                with patch.object(window.storage, 'save', side_effect=OSError('full disk')):
                    with self.assertRaises(OSError):window.recover_capture()
                self.assertIsNotNone(window.overlay)
                self.assertTrue(window.busy)
            finally:
                window.overlay = None;window.busy = False;window.close();window.deleteLater()
                for overlay in overlays:overlay.close();overlay.deleteLater()
                self.app.processEvents()


if __name__ == '__main__':unittest.main()
