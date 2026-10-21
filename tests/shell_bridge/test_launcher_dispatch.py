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

    def test_wayland_default_accepts_native_once_without_qt(self):
        for args in ((), ('launcher',), ('toggle',)):
            status, run, execute = self.invoke(args)
            self.assertEqual(status, 0)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], [str(ROOT / 'bin/wysun-shell'), 'launcher'])
            execute.assert_not_called()

    def test_unavailable_or_rejected_shell_falls_back_once(self):
        for kwargs in ({'response': 'false\n'}, {'code': 1}, {'error': FileNotFoundError()}):
            _, run, execute = self.invoke(**kwargs)
            self.assertEqual(run.call_count, 1)
            execute.assert_called_once_with(str(ROOT / 'bin/orbit'), [str(ROOT / 'bin/orbit'), 'toggle'])

    def test_ambiguous_delivery_never_opens_a_second_launcher(self):
        for kwargs in ({'error': subprocess.TimeoutExpired('ipc', 2)}, {'response': ''}, {'response': 'unknown'}):
            status, run, execute = self.invoke(**kwargs)
            self.assertEqual(status, 1)
            self.assertEqual(run.call_count, 1)
            execute.assert_not_called()

    def test_explicit_qt_and_non_wayland_do_not_contact_shell(self):
        for env in ({'WAYLAND_DISPLAY': 'synthetic', 'WYSUN_LAUNCHER': 'qt'},
                    {'DISPLAY': ':synthetic'}, {'WAYLAND_DISPLAY': 'synthetic', 'WYSUN_LAUNCHER': 'false'}):
            _, run, execute = self.invoke(env=env)
            run.assert_not_called()
            execute.assert_called_once()

    def test_explicit_qml_can_opt_in_without_wayland_environment(self):
        status, run, execute = self.invoke(env={'WYSUN_LAUNCHER': 'qml'})
        self.assertEqual(status, 0)
        run.assert_called_once()
        execute.assert_not_called()

    def test_other_modes_and_arguments_never_toggle_launcher(self):
        for args, executable, forwarded in (
                (('notes',), 'orbit', ['notes']),
                (('settings', 'displays'), 'orbit', ['settings', 'displays']),
                (('clipboard',), 'orbit', ['clipboard']),
                (('recover', '--dry-run'), 'wysun-recover', ['--dry-run']),
                (('files', '/tmp/example'), 'orbit-files', ['/tmp/example']),
                (('launcher', 'query'), 'orbit', ['toggle', 'query']),
                (('recorder', '--quick-record'), 'wysun-recorder', ['--quick-record'])):
            _, run, execute = self.invoke(args)
            run.assert_not_called()
            target = str(ROOT / 'bin' / executable)
            execute.assert_called_once_with(target, [target, *forwarded])


if __name__ == '__main__':
    unittest.main()
