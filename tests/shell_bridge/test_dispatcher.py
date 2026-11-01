"""`bin/wysun`, the single entry point: shell surfaces and actions over IPC, apps as `python3 -P -m`, no aliases."""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader('wysun_dispatcher', str(ROOT / 'bin/wysun'))
spec = importlib.util.spec_from_loader(loader.name, loader)
wysun = importlib.util.module_from_spec(spec)
loader.exec_module(wysun)
SHELL = str(ROOT / 'bin/wysun-shell')
APP = str(ROOT / 'apps/python')


def bridge_surfaces():
    qml = (ROOT / 'apps/shell/wysun/WysunBridge.qml').read_text()
    return re.findall(r'(\w+):', re.search(r'property var surfaces: \((\{.*?\})\)', qml, re.S)[1])


class DispatcherTests(unittest.TestCase):
    def invoke(self, args=(), response='true\n', code=0, error=None, env=None):
        run = Mock(return_value=subprocess.CompletedProcess([], code, response, ''), side_effect=error)
        with patch.dict(os.environ, env if env is not None else {'WAYLAND_DISPLAY': 'synthetic'}, clear=True), \
                patch.object(sys, 'argv', ['wysun', *args]), patch.object(wysun.subprocess, 'run', run), \
                patch.object(wysun.subprocess, 'Popen') as popen, \
                patch.object(wysun.os, 'execv') as execute, patch.object(wysun.os, 'execve') as module, \
                contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()) as out:
            status = wysun.main()
        self.module, self.popen, self.err, self.out = module, popen, err.getvalue(), out.getvalue()
        return status, run, execute

    def assert_module(self, module, args, root=APP):
        python, argv, env = self.module.call_args.args
        self.assertEqual((python, argv), ('/usr/bin/python3', [python, '-P', '-m', module, *args]))
        self.assertEqual(env['PYTHONPATH'].split(os.pathsep)[0], root)

    def test_no_arguments_toggles_the_launcher_once(self):
        status, run, execute = self.invoke()
        self.assertEqual(status, 0)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], [SHELL, 'toggle', 'launcher'])
        execute.assert_not_called()

    def test_every_shell_surface_toggles_through_the_shell(self):
        names = bridge_surfaces()
        self.assertIn('colors', names)
        self.assertIn('processes', names)
        for name in names:
            status, run, execute = self.invoke((name,))
            self.assertEqual(status, 0, name)
            self.assertEqual(run.call_args.args[0], [SHELL, 'toggle', name], name)
            execute.assert_not_called()
            self.module.assert_not_called()

    def test_shell_actions(self):
        for args, route in ((('clipboard',), ['category', 'clip']), (('calculator',), ['category', 'calc']),
                            (('color-pick',), ['color-pick']), (('settings',), ['nexus', 'home']),
                            (('settings', 'displays'), ['nexus', 'displays'])):
            status, run, _ = self.invoke(args)
            self.assertEqual(status, 0, args)
            self.assertEqual(run.call_args.args[0], [SHELL, *route], args)

    def test_a_silent_rejecting_or_missing_shell_fails_visibly(self):
        for kwargs in ({'response': 'false\n'}, {'code': 1}, {'code': 2}, {'error': FileNotFoundError()},
                       {'error': subprocess.TimeoutExpired('ipc', 3)}):
            for args in ((), ('processes',), ('settings', 'displays')):
                status, run, execute = self.invoke(args, **kwargs)
                self.assertEqual(status, 1, (args, kwargs))
                self.assertTrue(self.err, (args, kwargs))
                execute.assert_not_called()

    def test_apps_run_as_modules_from_the_package_root(self):
        for args, module, forwarded in ((('files', '/tmp/a b'), 'wysun_files', ['/tmp/a b']),
                                        (('music',), 'wysun_music', []),
                                        (('player', '--paused', '--', 'x.mp4'), 'wysun_player', ['--paused', '--', 'x.mp4']),
                                        (('scheme', 'refresh'), 'wysun_services.scheme', ['refresh']),
                                        (('wallpaper', 'list'), 'wysun_services.wallpaper', ['list']),
                                        (('workspaces',), 'wysun_settings.runtime', ['workspaces']),
                                        (('daemon',), 'wysun_services.daemon', []),
                                        (('reload',), 'wysun_services.daemon', ['reload'])):
            _, run, execute = self.invoke(args)
            run.assert_not_called()
            execute.assert_not_called()
            self.assert_module(module, forwarded)

    def test_tools_run_from_their_own_root(self):
        self.invoke(('tools', 'dev', 'doctor'))
        self.assert_module('wysun_tools', ['dev', 'doctor'], root=str(ROOT / 'apps/tools'))

    def test_music_mini_starts_music_hidden_and_opens_the_media_widget(self):
        _, run, execute = self.invoke(('music-mini',))
        argv = self.popen.call_args.args[0]
        self.assertEqual(argv, ['/usr/bin/python3', '-P', '-m', 'wysun_music', '--background'])
        self.assertTrue(self.popen.call_args.kwargs['start_new_session'])
        execute.assert_called_once_with(SHELL, [SHELL, 'media', 'Wysun Music'])

    def test_programs_keep_their_arguments(self):
        for args, program, forwarded in ((('recover', '--help'), 'wysun-recover', ['--help']),
                                         (('recorder', '--quick-record'), 'wysun-recorder', ['--quick-record']),
                                         (('shell', 'record', 'pause'), 'wysun-shell', ['record', 'pause']),
                                         (('lock',), 'wysun-lock', []),
                                         (('session-check',), 'wysun-session', ['--check']),
                                         (('install', '--wysun-only'), 'wysun-install', ['install', '--wysun-only']),
                                         (('doctor',), 'wysun-install', ['doctor']),
                                         (('activate', '0x1'), 'wysun-wm', ['activate', '0x1'])):
            _, run, execute = self.invoke(args)
            run.assert_not_called()
            target = str(ROOT / 'bin' / program)
            execute.assert_called_once_with(target, [target, *forwarded])

    def test_removed_aliases_are_not_commands(self):
        # Each falls through to the shell as a surface name, which the shell does not know.
        commands = {*wysun.MODULES, *wysun.PROGRAMS, *wysun.SHELL_ACTIONS, 'settings', 'music-mini'}
        for alias in ('image', 'color', 'screenshot', 'toggle', 'power', 'audio', 'calendar', 'system', 'tools-cli',
                      'network', 'settings-workspaces'):
            self.assertNotIn(alias, commands)
            self.assertNotIn(alias, bridge_surfaces())
            status, run, execute = self.invoke((alias,), response='false\n', code=2)
            self.assertEqual(status, 1, alias)
            self.assertEqual(run.call_args.args[0], [SHELL, 'toggle', alias])
            self.module.assert_not_called()
            execute.assert_not_called()
        self.assertFalse((ROOT / 'apps/python/wysun_services/client.py').exists())

    def test_only_surfaces_reach_the_shell_as_bare_words(self):
        # Quickshell's own commands (kill, log…) and wysun-shell's actions are never reached by a bare word.
        for word in ('kill', 'log', 'status', 'screenshot', 'record'):
            self.invoke((word,), response='false\n', code=2)
        status, run, _ = self.invoke(('kill',), response='false\n', code=2)
        self.assertEqual(run.call_args.args[0], [SHELL, 'toggle', 'kill'])
        for option in ('--quick', '-x'):
            status, run, _ = self.invoke((option,))
            self.assertEqual(status, 2, option)
            run.assert_not_called()

    def test_a_program_missing_from_the_checkout_is_reported(self):
        with patch.object(wysun.os, 'execv', side_effect=FileNotFoundError(2, 'No such file')):
            with patch.object(sys, 'argv', ['wysun', 'install']), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(wysun.main(), 127)
        self.assertIn('wysun-install', err.getvalue())

    def test_study_surface_service_and_actions(self):
        self.assertIn('study', bridge_surfaces())
        self.assertIn("if (kind === \"study\") return Study.toggle();", (ROOT / 'apps/shell/wysun/WysunBridge.qml').read_text())
        self.assertIn('pomodoro) shift; exec "$runtime" ipc call pomodoro "${1:-status}" ;;', Path(SHELL).read_text())
        service = (ROOT / 'apps/shell/services/Study.qml').read_text()
        self.assertRegex(service, r"target: ['\"]pomodoro['\"]")
        for name in ('toggle', 'stop', 'status'):
            self.assertRegex(service, rf'function {name}\(\)', name)

    def test_study_module_is_wired(self):
        shell = (ROOT / 'apps/shell/shell.qml').read_text()
        self.assertIn('import qs.modules.study', shell)
        self.assertRegex(shell, r'\n\s*StudyModule \{\}')

    def test_study_copy(self):
        text = '\n'.join(p.read_text() for p in (ROOT / 'apps/shell/modules/study').glob('*.qml'))
        for copy in ('esperará al final de la sesión', 'Mantén para salir', '¿Terminar la sesión?',
                     'Levántate, estira, bebe agua.', 'Sesión terminada', 'Sesión de estudio', 'Modo estudio',
                     'Ocultar el tiempo', 'distracciones frenadas', '¿Seguimos?'):
            self.assertIn(copy, text, copy)

    def test_a_surface_takes_no_arguments(self):
        status, run, _ = self.invoke(('processes', 'extra'))
        self.assertEqual(status, 2)
        run.assert_not_called()

    def test_help_names_commands_without_aliases(self):
        status, run, _ = self.invoke(('--help',))
        self.assertEqual(status, 0)
        run.assert_not_called()
        self.assertIn('wysun-shell surfaces', self.out)
        self.assertNotIn('alias', self.out.lower())


if __name__ == '__main__':
    unittest.main()
