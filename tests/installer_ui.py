"""Native UI and real unprivileged installer flow, with no desktop replacement."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('ORBIT_REDUCED_MOTION', '1')
from pathlib import Path
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE/'installer'))
from PySide6.QtCore import QEvent, QEventLoop, QTimer, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from gui import InstallerWindow
from install_model import load_json

APP = QApplication.instance() or QApplication(['dotifails-ui-test'])
APP.setStyle('Fusion')


def settle(milliseconds=40):
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def wait_process(runner, timeout=20000):
    if not runner.running:
        return
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    runner.finished.connect(loop.quit)
    timer.start(timeout)
    loop.exec()
    runner.finished.disconnect(loop.quit)
    if runner.running:
        runner.cancel()
        raise AssertionError('Installer did not finish within the test deadline')


class InstallerUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dotifails-ui-test-')
        self.home = Path(self.temp.name)
        self.window = InstallerWindow(SOURCE, self.home)
        self.window.show()
        settle()

    def tearDown(self):
        if self.window.runner.running:
            self.window.runner.cancel()
            wait_process(self.window.runner)
        self.window.close()
        self.window.deleteLater()
        settle()
        self.temp.cleanup()

    def configure_terminal(self):
        self.window.selected = {'terminal'}
        self.window.config_only.setChecked(True)
        self.window.sync_components()

    def test_keyboard_selection_dependency_and_preflight_gate(self):
        w = self.window
        w.preset('essential')
        w.show_page(2, animate=False)
        editor = w.component_cards['editor']
        editor.setFocus()
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            APP.sendEvent(editor, QKeyEvent(kind, Qt.Key_Space, Qt.NoModifier))
        self.assertIn('editor', w.selected)
        self.assertIn('terminal', w.selected)
        self.assertFalse(w.component_cards['terminal'].isEnabled())
        w.show_page(4, animate=False)
        self.assertFalse(w.next.isEnabled())  # Full system install cannot target a test home.
        self.configure_terminal()
        w.refresh_review()
        self.assertTrue(w.next.isEnabled())
        self.assertEqual(list(self.home.iterdir()), [])  # Reviewing is read-only.

    def test_real_configuration_install_and_restore_through_qprocess(self):
        original = self.home/'.zshrc'
        original.write_text('my original shell')
        w = self.window
        self.configure_terminal()
        w.select_theme('tokyo')
        w.show_page(4, animate=False)
        w.start_install()
        wait_process(w.runner)
        self.assertEqual(w.last_result['status'], 'complete', w.logs.toPlainText())
        self.assertEqual(w.page_index, 6)
        self.assertTrue((self.home/'.config/ghostty/config').exists())
        self.assertFalse((self.home/'.config/bspwm').exists())
        self.assertEqual(w.runner.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((w.runner.directory/'console.log').stat().st_mode & 0o777, 0o600)
        self.assertEqual(load_json(w.runner.directory/'plan.json')['components'], ['terminal'])
        ident = w.last_result['backup']
        w.start_operation('restore', '/usr/bin/python3', [str(SOURCE/'installer/main.py'),'restore',ident,'--target-home',str(self.home)])
        wait_process(w.runner)
        self.assertEqual(w.last_result['status'], 'complete', w.logs.toPlainText())
        self.assertEqual(original.read_text(), 'my original shell')

    def test_cancel_is_cooperative_and_presented_as_stopped(self):
        w = self.window
        self.configure_terminal()
        def cancel_at_backup(event):
            if event.get('event') == 'backup':
                w.request_stop()
        w.runner.event.connect(cancel_at_backup)
        w.start_install()
        wait_process(w.runner)
        self.assertEqual(w.last_result['status'], 'cancelled', w.logs.toPlainText())
        self.assertEqual(w.page_index, 6)
        self.assertTrue(w.runner.cancel_requested)
        self.assertEqual(load_json(self.home/'.local/state/dotifails/backups'/w.last_result['backup']/'journal.json')['status'], 'cancelled')

    def test_failure_is_not_reported_as_success(self):
        w = self.window
        w.start_operation('install', '/usr/bin/python3', ['-c', 'print("diagnostic failure");raise SystemExit(7)'])
        wait_process(w.runner)
        self.assertEqual(w.last_result['status'], 'failed')
        self.assertIn('diagnostic failure', w.logs.toPlainText())

    def test_small_and_large_pages_have_no_horizontal_overflow(self):
        w = self.window
        self.configure_terminal()
        output = Path(os.environ.get('DOTIFAILS_SCREENSHOTS', '/tmp/dotifails-installer-qa'))
        output.mkdir(parents=True, exist_ok=True)
        for width, height in ((1100,780), (800,600)):
            w.resize(width,height)
            for index in range(5):
                w.show_page(index, animate=False)
                settle()
                scroll = w.stack.currentWidget()
                self.assertLessEqual(scroll.widget().width(), scroll.viewport().width(), (width,index))
                self.assertEqual(scroll.horizontalScrollBar().maximum(), 0, (width,index))
                w.grab().save(str(output/f'installer-{index}-{width}.png'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
