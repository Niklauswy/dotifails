"""Native UI and real unprivileged installer flow, with no desktop replacement."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('ORBIT_REDUCED_MOTION', '1')
from pathlib import Path
import sys
import tempfile
import unittest
import json
import subprocess
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE/'installer'))
from PySide6.QtCore import QEvent, QEventLoop, QTimer, Qt
from PySide6.QtGui import QKeyEvent, QShortcut
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from gui import CONTENT, HOME, RUN, SYSTEM, InstallerWindow
from install_model import InstallOptions, load_json
from material_widgets import Sheet

APP = QApplication.instance() or QApplication(['dotifails-ui-test'])
APP.setStyle('Fusion')
SHOTS = Path(os.environ.get('DOTIFAILS_SCREENSHOTS', tempfile.gettempdir() + '/dotifails-installer-qa'))


def settle(milliseconds=40):
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def wait_workers(window, timeout=30):
    for _ in range(timeout * 50):
        if not window.workers and not window.review_timer.isActive():
            settle(20)
            return
        settle(20)
    raise AssertionError('Review did not finish')


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


def key(widget, value, modifiers=Qt.NoModifier):
    for kind in (QEvent.KeyPress, QEvent.KeyRelease):
        APP.sendEvent(widget, QKeyEvent(kind, value, modifiers))


def snapshot(home):
    return {p.relative_to(home).as_posix(): p.read_bytes() for p in Path(home).rglob('*') if p.is_file()}


def finish_preview(window):
    window.runner.timer.stop()
    while window.runner.running:
        window.runner.tick()


class InstallerUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dotifails-ui-test-')
        self.home = Path(self.temp.name)
        self.window = InstallerWindow(SOURCE, self.home)
        self.window.show()
        settle()

    def tearDown(self):
        window = self.window
        if window.runner.running:
            window.runner.cancel()
            wait_process(window.runner)
        wait_workers(window)
        window.close()
        window.deleteLater()
        settle()
        os.environ.pop('WYSUN_THEME', None)
        self.temp.cleanup()

    def run_configuration(self):
        """Configuration-only installs stay a CLI mode; the window's runner still drives them."""
        w = self.window
        options = InstallOptions(SOURCE, self.home, ('terminal',), config_only=True)
        plan = options.summary()
        w.start_operation('install', '/usr/bin/python3', [str(SOURCE/'installer/main.py'), *options.argv()], plan)
        wait_process(w.runner)
        return plan

    def test_selection_is_the_desktop_plus_three_pieces_and_review_gates_install(self):
        w = self.window
        w.show_page(CONTENT, animate=False)
        for tile in w.addon_tiles.values():
            tile.setChecked(False)
        self.assertEqual(w.selected_components(), ('desktop', 'wayland', 'terminal'))
        editor = w.addon_tiles['editor']
        editor.setFocus()
        key(editor, Qt.Key_Space)
        self.assertIn('editor', w.selected_components())
        w.app_bubbles['obsidian'].click()
        options = w.options()
        self.assertEqual(options.extras, ('obsidian',))
        self.assertEqual(options.boot_components, ('grub', 'plymouth'))
        self.assertTrue(options.prepare_repositories and options.upgrade_system)
        self.assertFalse(options.config_only or options.profile or options.skip_nvim_tools)
        self.assertEqual(w.bar_title.text(), 'Wysun + Neovim + Obsidian')
        wait_workers(w)
        self.assertFalse(w.next.isEnabled())  # A full system install cannot target a test home.
        self.assertTrue(w.details_button.isVisible())
        self.assertTrue(any(c['level'] == 'error' for c in w.checks))
        self.assertEqual(list(self.home.iterdir()), [])  # Reviewing is read-only.
        w.show_page(SYSTEM, animate=False)
        w.upgrade.click()
        self.assertFalse(w.options().upgrade_system)

    def test_real_configuration_install_and_restore_through_qprocess(self):
        original = self.home/'.zshrc'
        original.write_text('my original shell')
        w = self.window
        self.run_configuration()
        self.assertEqual(w.last_result['status'], 'complete', w.logs.toPlainText())
        self.assertEqual(w.page_index, RUN)
        self.assertEqual(w.run_scene.state, 'done')
        self.assertTrue((self.home/'.config/ghostty/config').exists())
        self.assertEqual(w.runner.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((w.runner.directory/'console.log').stat().st_mode & 0o777, 0o600)
        self.assertEqual(load_json(w.runner.directory/'plan.json')['components'], ['terminal'])
        self.assertEqual({stage['level'] for stage in w.run_stages}, {'done'})
        ident = w.last_result['backup']
        w.start_operation('restore', '/usr/bin/python3', [str(SOURCE/'installer/main.py'), 'restore', ident, '--target-home', str(self.home)])
        wait_process(w.runner)
        self.assertEqual(w.last_result['status'], 'complete', w.logs.toPlainText())
        self.assertEqual(original.read_text(), 'my original shell')

    def test_cancel_is_cooperative_and_presented_as_stopped(self):
        w = self.window

        def cancel_at_backup(event):
            if event.get('event') == 'backup':
                w.request_stop()
        w.runner.event.connect(cancel_at_backup)
        self.run_configuration()
        self.assertEqual(w.last_result['status'], 'cancelled', w.logs.toPlainText())
        self.assertEqual(w.run_scene.state, 'cancelled')
        self.assertTrue(w.runner.cancel_requested)
        self.assertEqual(load_json(self.home/'.local/state/dotifails/backups'/w.last_result['backup']/'journal.json')['status'], 'cancelled')

    def test_failure_is_not_reported_as_success_and_offers_recovery(self):
        w = self.window
        w.start_operation('install', '/usr/bin/python3', ['-c', 'print("diagnostic failure");raise SystemExit(7)'])
        wait_process(w.runner)
        self.assertEqual(w.last_result['status'], 'failed')
        self.assertEqual(w.run_scene.state, 'error')
        self.assertTrue(w.logs.isVisible())
        self.assertIn('diagnostic failure', w.logs.toPlainText())
        settle(60)
        texts = [b.text() for b in w.findChildren(type(w.next)) if b.isVisible()]
        self.assertIn('Recuperación', texts)

    def test_closing_during_an_operation_asks_and_stops_cooperatively(self):
        w = self.window
        w.start_operation('install', '/usr/bin/python3', ['-c', 'import time;time.sleep(30)'])
        w.close()
        settle()
        self.assertTrue(w.isVisible())
        sheets = [s for s in w.findChildren(Sheet) if s.isVisible()]
        self.assertEqual(len(sheets), 1)
        key(sheets[0], Qt.Key_Escape)
        settle(60)
        self.assertTrue(w.runner.running)
        self.assertFalse(w.runner.cancel_requested)
        w.runner.process.kill()
        wait_process(w.runner)

    def test_keyboard_navigation_help_sheet_and_stepper(self):
        w = self.window
        shortcuts = {s.key().toString(): s for s in w.findChildren(QShortcut)}
        self.assertTrue({'Alt+Right', 'Alt+Left', 'Ctrl+Return', 'F1', 'Ctrl+L'} <= set(shortcuts), shortcuts)
        shortcuts['Alt+Right'].activated.emit()
        self.assertEqual(w.page_index, SYSTEM)
        shortcuts['Alt+Left'].activated.emit()
        self.assertEqual(w.page_index, HOME)
        self.assertNotIn(CONTENT, w.reachable())  # a new installation goes in order
        w.stepper.setFocus()
        w.show_page(SYSTEM, animate=False)
        key(w.stepper, Qt.Key_Left)
        self.assertEqual(w.page_index, HOME)
        shortcuts['F1'].activated.emit()
        settle(60)
        self.assertTrue(w.sheet_open())
        w.advance()  # blocked while the sheet is open
        self.assertEqual(w.page_index, HOME)
        sheet = next(s for s in w.findChildren(Sheet) if s.isVisible())
        key(sheet, Qt.Key_Escape)
        settle(60)
        self.assertFalse(w.sheet_open())

    def test_visible_text_says_wysun_never_orbit(self):
        w = self.window
        for index in (HOME, SYSTEM, CONTENT):
            w.show_page(index, animate=False)
        wait_workers(w)
        texts = [label.text() for label in w.findChildren(QLabel)]
        for widget in w.findChildren(QWidget):
            texts += [widget.accessibleName(), widget.accessibleDescription(), widget.toolTip()]
            texts += [str(getattr(widget, name, '')) for name in ('title', 'detail', 'subtitle', 'eyebrow')]
        import journey
        texts += [item['detail'] for item in journey.COMPONENTS.values()] + [item[1] for item in journey.ADDONS.values()]
        offenders = [text for text in texts if 'orbit' in text.lower()]
        self.assertEqual(offenders, [])
        self.assertIn('Wysun Tools', [tile.title for tile in w.addon_tiles.values()])

    def test_pages_have_no_horizontal_overflow_at_laptop_sizes(self):
        w = self.window
        SHOTS.mkdir(parents=True, exist_ok=True)
        for width, height in ((1366, 740), (1180, 800), (820, 600)):
            w.resize(width, height)
            for index in (HOME, SYSTEM, CONTENT):
                w.show_page(index, animate=False)
                wait_workers(w)
                settle()
                scroll = w.stack.current()
                self.assertLessEqual(scroll.widget().width(), scroll.viewport().width(), (width, index))
                self.assertEqual(scroll.horizontalScrollBar().maximum(), 0, (width, index))
                self.assertLess(scroll.widget().height(), 2000, (width, index))
                w.grab().save(str(SHOTS/f'installer-{index}-{width}.png'))

    def test_preview_ignores_installed_receipt_and_never_executes_or_writes(self):
        receipt = self.home / '.local/state/dotifails/installed.json'
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({'components': ['desktop'], 'source': str(SOURCE)}))
        before = snapshot(self.home)
        preview = InstallerWindow(SOURCE, self.home, preview=True)
        preview.show()
        try:
            self.assertFalse(preview.updating)
            self.assertFalse(preview.recovery_button.isVisible())
            self.assertIn(CONTENT, preview.reachable())
            with patch('subprocess.run', side_effect=AssertionError('Preview must not execute commands')), \
                 patch('subprocess.Popen', side_effect=AssertionError('Preview must not execute commands')), \
                 patch('process_runner.InstallerProcess.start', side_effect=AssertionError('Preview must not use the real process')):
                preview.show_page(SYSTEM, animate=False)
                settle(1600)
                self.assertTrue(preview.host and all('simulado' in c['detail'] or c['level'] == 'info' for c in preview.host))
                self.assertEqual(preview.scan.state, 'ok')
                preview.show_page(CONTENT, animate=False)
                wait_workers(preview)
                self.assertTrue(preview.next.isEnabled(), preview.checks)
                preview.advance()
                self.assertEqual(preview.page_index, RUN)
                planned = [stage['name'] for stage in preview.run_stages]
                finish_preview(preview)
                self.assertEqual([stage['name'] for stage in preview.run_stages], planned)
                self.assertTrue(preview.last_result['preview'])
                self.assertEqual({stage['level'] for stage in preview.run_stages}, {'done'})
                self.assertEqual(preview.run_scene.state, 'done')
                preview.reboot()
                preview.request_reboot()  # guarded even when called directly
                settle(60)
            self.assertEqual(snapshot(self.home), before)
        finally:
            preview.close()
            preview.deleteLater()
            settle()

    def test_preview_cancel_stops_at_a_stage_boundary(self):
        preview = InstallerWindow(SOURCE, self.home, preview=True)
        try:
            preview.show_page(CONTENT, animate=False)
            wait_workers(preview)
            preview.start_install()
            preview.runner.timer.stop()
            preview.runner.tick()
            preview.request_stop()
            finish_preview(preview)
            self.assertEqual(preview.last_result['status'], 'cancelled')
            levels = [stage['level'] for stage in preview.run_stages]
            self.assertEqual(levels[0], 'done')  # the running stage finishes; the next ones never start
            self.assertEqual(set(levels[1:]), {'pending'})
            self.assertEqual(preview.run_scene.state, 'cancelled')
        finally:
            preview.close()
            preview.deleteLater()

    def test_existing_installation_gets_maintenance_and_keeps_appearance(self):
        receipt = self.home / '.local/state/dotifails/installed.json'
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({'components': ['desktop', 'wayland', 'terminal', 'boot'],
                                       'last_selection': ['desktop', 'wayland', 'terminal', 'boot']}))
        installed = InstallerWindow(SOURCE, self.home)
        try:
            self.assertTrue(installed.updating)
            self.assertIn('Modificar', installed.next.text())
            self.assertEqual(installed.stepper.steps[0][1], 'Resumen')
            self.assertFalse(installed.upgrade.isChecked())
            self.assertEqual(installed.addons, {'boot'})
            self.assertIn(CONTENT, installed.reachable())
            installed.advance()
            self.assertEqual(installed.page_index, SYSTEM)
        finally:
            installed.close()
            installed.deleteLater()

    def test_installed_executable_has_its_own_ui_runtime_without_the_repository(self):
        command = ['/usr/bin/python3', str(SOURCE/'installer/main.py'), 'install', '--installer-only',
                   '--source', str(SOURCE), '--target-home', str(self.home)]
        completed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        manager = self.home / '.local/share/dotifails/installer'
        self.assertTrue((manager/'ui_runtime/wysun_music/ui/widgets.py').is_file())
        self.assertTrue((manager/'ui_runtime/ui_theme.py').is_file())
        self.assertTrue((manager/'scenes.py').is_file())
        code = '''import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from PySide6.QtWidgets import QApplication
app=QApplication(['standalone-installer-test'])
from gui import InstallerWindow, CONTENT
import theme_core
assert str(Path(sys.argv[1])/'ui_runtime') in theme_core.__file__
w=InstallerWindow(Path('/missing/repository'), Path(sys.argv[2]), preview=True)
w.show();w.show_page(CONTENT,animate=False)
end=time.monotonic()+15
while (w.workers or w.review_timer.isActive()) and time.monotonic()<end:
    app.processEvents();time.sleep(.02)
app.processEvents()
assert w.next.isEnabled(), w.checks
'''
        env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home/'.config'),
                   XDG_STATE_HOME=str(self.home/'.local/state'), XDG_DATA_HOME=str(self.home/'.local/share'),
                   XDG_CACHE_HOME=str(self.home/'.cache'), QT_QPA_PLATFORM='offscreen')
        result = subprocess.run(['/usr/bin/python3', '-c', code, str(manager), str(self.home)],
                                cwd=self.home, env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        desktop = (self.home/'.local/share/applications/wysun-installer-preview.desktop').read_text()
        self.assertIn('Exec=wysun-installer --preview', desktop)

    def test_light_and_dark_render_every_page_at_laptop_size(self):
        from theme_tokens import invalidate
        SHOTS.mkdir(parents=True, exist_ok=True)
        for theme in ('light', 'dark'):
            with patch.dict(os.environ, {'WYSUN_THEME': theme}):
                invalidate()
                preview = InstallerWindow(SOURCE, self.home, preview=True)
                preview.resize(1180, 760)
                preview.show()
                try:
                    for index in (HOME, SYSTEM, CONTENT):
                        preview.show_page(index, animate=False)
                        wait_workers(preview)
                        settle(1500 if index == SYSTEM else 40)
                        scroll = preview.stack.current()
                        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0, (theme, index))
                        preview.grab().save(str(SHOTS/f'wysun-{theme.replace(":", "-")}-{index}.png'))
                    preview.start_install()
                    finish_preview(preview)
                    preview.grab().save(str(SHOTS/f'wysun-{theme.replace(":", "-")}-done.png'))
                finally:
                    preview.close()
                    preview.deleteLater()
                    settle()
        invalidate()


if __name__ == '__main__':
    unittest.main(verbosity=2)
