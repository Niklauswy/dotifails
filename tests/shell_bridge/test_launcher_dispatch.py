"""Native launcher selection and fallback without launching real applications."""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader('wysun_wave2_dispatch', str(ROOT / 'bin/wysun'))
spec = importlib.util.spec_from_loader(loader.name, loader)
wysun = importlib.util.module_from_spec(spec)
loader.exec_module(wysun)


class LauncherDispatchTests(unittest.TestCase):
    def invoke(self, args=(), response='true\n', code=0, error=None, env=None):
        run = Mock(return_value=subprocess.CompletedProcess([], code, response, ''), side_effect=error)
        with patch.dict(os.environ, env if env is not None else {'WAYLAND_DISPLAY': 'synthetic'}, clear=True), \
                patch.object(sys, 'argv', ['wysun', *args]), patch.object(wysun.subprocess, 'run', run), \
                patch.object(wysun.os, 'execv') as execute, patch.object(Path, 'is_file', return_value=True), \
                contextlib.redirect_stderr(io.StringIO()):
            status = wysun.main()
        return status, run, execute

    def test_launcher_commands_reach_the_shell_once_without_qt(self):
        for args in ((), ('launcher',), ('toggle',)):
            status, run, execute = self.invoke(args)
            self.assertEqual(status, 0)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], [str(ROOT / 'bin/wysun-shell'), 'launcher'])
            execute.assert_not_called()

    def test_former_qt_menus_are_served_by_the_shell(self):
        expected = {
            'clipboard': ['search', '>clip '], 'snippets': ['search', '>snip '], 'emoji': ['search', '>emoji '],
            'calculator': ['search', '>calc '], 'windows': ['windows'], 'power': ['session'],
            'audio': ['open', 'quicksettings'], 'notifications': ['open', 'notifications'],
            'calendar': ['open', 'dashboard'], 'system': ['open', 'dashboard']}
        for command, route in expected.items():
            status, run, execute = self.invoke((command,))
            self.assertEqual(status, 0, command)
            self.assertEqual(run.call_args.args[0], [str(ROOT / 'bin/wysun-shell'), *route])
            execute.assert_not_called()

    def test_unavailable_rejected_or_silent_shell_fails_visibly_without_qt(self):
        for kwargs in ({'response': 'false\n'}, {'code': 1}, {'error': FileNotFoundError()},
                       {'error': subprocess.TimeoutExpired('ipc', 3)}):
            status, run, execute = self.invoke(**kwargs)
            self.assertEqual(status, 1)
            self.assertEqual(run.call_count, 1)
            execute.assert_not_called()

    def test_no_qt_launcher_override_remains(self):
        text = (ROOT / 'bin/wysun').read_text()
        self.assertNotIn('WYSUN_LAUNCHER', text)
        for env in ({'WAYLAND_DISPLAY': 'synthetic', 'WYSUN_LAUNCHER': 'qt'}, {'DISPLAY': ':synthetic'}):
            status, run, execute = self.invoke(env=env)
            self.assertEqual(status, 0)
            run.assert_called_once()
            execute.assert_not_called()

    def test_other_modes_never_toggle_launcher(self):
        for args, executable, forwarded in (
                (('notes',), 'orbit', ['notes']),
                (('settings', 'displays'), 'orbit', ['settings', 'displays']),
                (('recover', '--help'), 'wysun-recover', ['--help']),
                (('files', '/tmp/example'), 'orbit-files', ['/tmp/example']),
                (('recorder', '--quick-record'), 'wysun-recorder', ['--quick-record'])):
            _, run, execute = self.invoke(args)
            run.assert_not_called()
            target = str(ROOT / 'bin' / executable)
            execute.assert_called_once_with(target, [target, *forwarded])


if __name__ == '__main__':
    unittest.main()
