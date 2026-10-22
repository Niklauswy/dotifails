"""Real isolated deployments, conflicts, recovery and safe session boundaries."""
import contextlib
import io
import json
import os
import runpy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'installer'))
import main as installer
import install_model
import session_registration
import wayland


class WaylandInstallTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {'WYSUN_SKIP_RUNTIME': '1'}))
        self.tmp = tempfile.TemporaryDirectory(prefix='wysun-install-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.source = self.root / 'source'
        self.source.mkdir()
        # Use a tiny shell fixture until/without a real compositor. All other
        # distribution code is the actual source under test.
        for relative in ('installer', 'manifests', 'bin', 'config', 'assets/backgrounds', 'apps/wysun', 'apps/tools', 'apps/capture'):
            shutil.copytree(ROOT / relative, self.source / relative,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (self.source / 'apps/shell').mkdir()
        (self.source / 'apps/shell/shell.qml').write_text('import Quickshell\nShellRoot {}\n')

    def install(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return installer.main(['install', '--source', str(self.source), '--target-home',
                                   str(self.home), '--components', 'wayland', '--config-only'])

    def test_portal_check_reads_only_existing_unique_owner_and_never_activates(self):
        module = runpy.run_path(str(ROOT / 'bin/wysun-session'))
        bus = Mock()
        bus.get_name_owner.side_effect = [':1.42', ':1.43']
        bus.call_blocking.return_value = 5
        self.assertTrue(module['portal_preflight'](bus))
        self.assertEqual(bus.get_name_owner.call_count, 2)
        for call in bus.call_blocking.call_args_list:
            self.assertEqual(call.args[0], ':1.42')
            self.assertEqual(call.args[2:4], ('org.freedesktop.DBus.Properties', 'Get'))
        bus = Mock()
        bus.get_name_owner.side_effect = RuntimeError('no existing owner')
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertFalse(module['portal_preflight'](bus))
        bus.call_blocking.assert_not_called()
        self.assertIn('no se reinició ni activó', errors.getvalue())
        bus = Mock()
        bus.get_name_owner.side_effect = [':1.42', ':1.43']
        bus.call_blocking.side_effect = RuntimeError('No such interface')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(module['portal_preflight'](bus))

    def test_optional_selection_and_native_repository_plan(self):
        self.assertIn('wayland', install_model.normalize_components())
        self.assertEqual(install_model.normalize_components(('wayland',)), ('wayland',))
        with patch.object(install_model, 'read_os_release', return_value={'ID': 'parrot'}):
            packages = install_model.package_names(ROOT, ('wayland',))
        self.assertIn('hyprland/echo-backports', packages)
        self.assertIn('hyprpicker/echo-backports', packages)
        self.assertIn('qt6-wayland', packages)
        self.assertNotIn('bspwm', packages)
        self.assertNotIn('picom', packages)

    def test_clean_update_conflicts_private_data_and_recovery(self):
        private = {'.config/other-desktop/wmrc': 'custom window manager', '.config/other-desktop/compositor.conf': 'custom compositor',
                   '.config/other-desktop/keysrc': 'my bindings', '.config/hypr/hyprland.conf': 'other session',
                   '.config/wysun/local.lua': '-- synthetic per-machine scale preference',
                   '.config/xdg-desktop-portal/portals.conf': '[preferred]\ndefault=custom;\n',
                   '.local/share/orbit/notes/private.md': 'private fixture',
                   '.config/loomrec/preferences.json': '{"custom": true}',
                   '.local/share/loomrec/recordings/fixture/project.json': 'recording fixture',
                   '.local/share/wybie-screenshot/sessions/fixture/original.png': 'image fixture'}
        for relative, value in private.items():
            path = self.home / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(value)
        with patch.object(installer, 'run') as host_run:
            self.assertEqual(self.install(), 0)
            host_run.assert_not_called()
            self.assertEqual(self.install(), 0)
        receipt = installer.read(self.home / '.local/state/dotifails/installed.json')
        journal = installer.read(self.home / '.local/state/dotifails/backups' / receipt['last_backup'] / 'journal.json')
        self.assertEqual(journal['operations'], [])
        config = self.home / '.config/wysun/hyprland.lua'
        config.write_text('personal Lua configuration')
        (self.source / 'config/.config/wysun/hyprland.lua').write_text('-- new proposed config\n')
        app = self.home / '.local/share/orbit/app/orbit.py'
        app.write_text('# local app customization\n')
        before_launcher = (self.home / '.local/bin/wysun').read_text()
        (self.source / 'bin/wysun').write_text(before_launcher + '\n# new dispatcher\n')
        self.assertEqual(self.install(), 2)
        receipt = installer.read(self.home / '.local/state/dotifails/installed.json')
        backup = self.home / '.local/state/dotifails/backups' / receipt['last_backup']
        self.assertEqual(config.read_text(), 'personal Lua configuration')
        self.assertEqual(app.read_text(), '# local app customization\n')
        self.assertTrue((backup / 'incoming/.local/share/orbit/app/orbit.py').is_file())
        for relative, value in private.items():
            self.assertEqual((self.home / relative).read_text(), value)
        # Recover the original clean install; preserve later user edits.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(installer.restore(self.home, receipt['last_backup']), 0)

    def test_registration_idempotence_modified_file_and_remove(self):
        root = self.root / 'system'
        root.mkdir()
        login = root / 'etc/lightdm/lightdm.conf'
        login.parent.mkdir(parents=True); login.write_text('user-session=wysun\n')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(session_registration.register(ROOT / 'installer', root), 0)
            self.assertEqual(session_registration.register(ROOT / 'installer', root), 0)
            desktop = root / 'usr/share/wayland-sessions/wysun-hyprland.desktop'
            desktop.write_text('local modification')
            self.assertEqual(session_registration.register(ROOT / 'installer', root, restore=True), 2)
            self.assertEqual(desktop.read_text(), 'local modification')
            shutil.copy2(ROOT / 'installer/wysun-hyprland.desktop', desktop)
            desktop.chmod(0o644)
            self.assertEqual(session_registration.register(ROOT / 'installer', root, restore=True), 0)
        self.assertFalse(desktop.exists())
        self.assertFalse((root / 'usr/local/bin/wysun-session').exists())
        self.assertEqual(login.read_text(), 'user-session=wysun\n')

    def test_wysun_only_updates_managed_shell_without_session_config(self):
        self.assertEqual(self.install(), 0)
        config = self.home / '.config/wysun/hyprland.lua'
        config.write_text('-- personal bindings\n')
        (self.source / 'apps/shell/shell.qml').write_text('// new shell code\n')
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(installer.Deployment, 'configure_files', side_effect=AssertionError('portal rewrite requested')):
            self.assertEqual(installer.main(['install', '--source', str(self.source),
                '--target-home', str(self.home), '--wysun-only']), 0)
        self.assertEqual(config.read_text(), '-- personal bindings\n')
        self.assertEqual((self.home / '.local/share/wysun/quickshell/shell.qml').read_text(), '// new shell code\n')
        self.assertFalse((self.home / '.config/sxhkd').exists())

    def test_incompatible_packages_fail_before_journal_or_deployment(self):
        with patch.object(installer, 'host_supported', return_value={'ID': 'parrot'}), \
             patch.object(Path, 'home', return_value=self.home), \
             patch.object(installer.os, 'geteuid', return_value=1000), \
             patch('wayland.simulate_packages', side_effect=RuntimeError('ABI conflict')):
            with self.assertRaisesRegex(RuntimeError, 'ABI conflict'):
                installer.main(['install', '--source', str(self.source), '--components', 'wayland'])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_runtime_is_built_into_the_private_prefix_and_legacy_config_is_copied(self):
        old = self.home / '.config/wysun/caelestia'
        old.mkdir(parents=True); (old / 'shell.json').write_text('{"a": 1}')

        class Deployment:
            home = self.home
            source = ROOT
            def stage(self, name): pass
        calls = []
        with patch.dict(os.environ, {'WYSUN_SKIP_RUNTIME': '0'}), \
             patch('main.run', side_effect=lambda argv, env=None: calls.append((list(map(str, argv)), env))):
            wayland.migrate_legacy_names(Deployment())
            wayland.ensure_runtime(Deployment())
        self.assertEqual((self.home / '.config/wysun/shell/shell.json').read_text(), '{"a": 1}')
        self.assertTrue(old.exists(), 'the legacy copy stays until an explicit clean')
        argv, env = calls[0]
        self.assertTrue(argv[1].endswith('installer/runtime_build.py'))
        self.assertEqual(argv[-1], str(self.home / '.local/share/wysun/runtime'))
        self.assertEqual(env['HOME'], str(self.home))

    def test_unverified_shell_release_fails_repository_preflight(self):
        newer = subprocess.CompletedProcess([], 0, 'Version: 0.56.0-1\n', '')
        with patch.object(wayland, 'package_specs', return_value=['hyprland/trixie-backports']), \
             patch.object(wayland.subprocess, 'run', return_value=newer):
            with self.assertRaisesRegex(RuntimeError, 'serie comprobada 0.55'):
                wayland.check_repository(ROOT, {'ID': 'debian'})

    def test_cli_dry_run_resolves_exact_packages_without_creating_journal(self):
        args=['install','--source',str(self.source),'--target-home',str(self.home),
              '--components','wayland','--dry-run']
        output=io.StringIO()
        with patch.object(installer,'host_supported',return_value={'ID':'debian'}), \
             patch.object(installer,'package_names',return_value=['hyprland/trixie-backports']), \
             patch.object(wayland,'simulate_packages',return_value='APT exact fixture plan') as simulate, \
             contextlib.redirect_stdout(output):
            self.assertEqual(installer.main(args),0)
        self.assertIn('APT exact fixture plan',output.getvalue())
        self.assertEqual(simulate.call_args.kwargs['wanted'],['hyprland/trixie-backports'])
        self.assertEqual(list(self.home.iterdir()),[])

    def test_code_launchers_resolve_managed_code_with_separate_xdg_data(self):
        code = self.home / '.local/share/orbit/app/orbit-client'
        code.parent.mkdir(parents=True); code.write_text('#!/bin/sh\nprintf managed-client\n'); code.chmod(0o755)
        shell = self.home / '.local/share/wysun/quickshell'
        (shell / 'wysun').mkdir(parents=True); (shell / 'shell.qml').write_text('// fixture\n')
        shutil.copy2(ROOT / 'apps/shell/wysun/runtime.sh', shell / 'wysun/runtime.sh')
        data = self.root / 'separate-data'
        qs = data / 'wysun/runtime/quickshell/bin/quickshell'; qs.parent.mkdir(parents=True)
        qs.write_text('#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n'); qs.chmod(0o755)
        env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(data), WYSUN_SHELL_CONFIG=str(shell),
                   PATH='/usr/bin:/bin')
        self.assertEqual(subprocess.check_output([ROOT / 'config/.local/bin/orbit'], env=env, text=True), 'managed-client')
        args = json.loads(subprocess.check_output([ROOT / 'bin/wysun-shell', 'status'], env=env, text=True))
        self.assertEqual(args, ['-p', str(shell), 'ipc', 'call', 'wysunShell', 'status'])

    def test_unowned_system_files_and_linked_parents_preserved(self):
        root = self.root / 'system'; root.mkdir()
        target = root / 'usr/local/bin/wysun-session'
        target.parent.mkdir(parents=True); target.write_text('unowned command')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(session_registration.register(ROOT / 'installer', root), 2)
        self.assertEqual(target.read_text(), 'unowned command')
        self.assertFalse((root / 'usr/share/wayland-sessions/wysun-hyprland.desktop').exists())
        other = self.root / 'other'; other.mkdir()
        (other / 'usr').symlink_to(root / 'usr')
        with self.assertRaises(ValueError):
            session_registration.register(ROOT / 'installer', other)

    def test_session_root_symlink_rejected_before_state_creation(self):
        root=self.root/'real-system';root.mkdir()
        link=self.root/'linked-system';link.symlink_to(root,target_is_directory=True)
        for destination in (link,link/'nested'):
            with self.assertRaises(ValueError):
                session_registration.register(ROOT/'installer',destination)
        self.assertEqual(list(root.iterdir()),[])

    def test_interrupted_registration_retries_from_persisted_intent(self):
        root = self.root / 'interrupted-system'; root.mkdir()
        with patch.object(session_registration.shutil, 'copy2', side_effect=OSError('synthetic interruption')):
            with self.assertRaisesRegex(OSError, 'synthetic interruption'):
                session_registration.register(ROOT / 'installer', root)
        self.assertTrue((root / 'var/lib/dotifails/wayland-session/installed.json').exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(session_registration.register(ROOT / 'installer', root), 0)
            self.assertEqual(session_registration.register(ROOT / 'installer', root, restore=True), 0)
        self.assertFalse((root / 'usr/local/bin/wysun-session').exists())

    def test_locker_never_suspends_after_failure(self):
        binary = self.root / 'bin'; binary.mkdir()
        log = self.root / 'called'
        (binary / 'swaylock').write_text('#!/bin/sh\nexit 1\n')
        (binary / 'systemctl').write_text('#!/bin/sh\nprintf called > "$WYSUN_TEST_LOG"\n')
        for path in binary.iterdir(): path.chmod(0o755)
        env = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'], HOME=str(self.home),
                   WAYLAND_DISPLAY='fixture', XDG_SESSION_TYPE='wayland', WYSUN_TEST_LOG=str(log), WYSUN_LOCK_BACKEND='swaylock')
        result = subprocess.run([str(ROOT / 'bin/wysun-lock'), '--suspend'], env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(log.exists())

    def test_session_imports_environment_before_clients_and_fails_closed(self):
        services = runpy.run_path(str(ROOT / 'bin/wysun-session-services'))
        env = {'HYPRLAND_INSTANCE_SIGNATURE': 'isolated-test', 'WAYLAND_DISPLAY': 'test-wayland',
               'XDG_SESSION_TYPE': 'wayland', 'XDG_CURRENT_DESKTOP': 'Wysun:Hyprland',
               'XDG_CONFIG_HOME': '/tmp/fixture-config', 'XDG_RUNTIME_DIR': '/tmp/fixture-runtime'}
        calls = Mock()
        child = Mock(); child.poll.return_value = 0
        calls.launch.return_value = child
        with patch.dict(os.environ, env, clear=True), \
             patch('signal.signal'), patch('shutil.which', return_value=None), \
             patch('subprocess.run', calls.import_environment), patch('subprocess.Popen', calls.launch):
            with self.assertRaisesRegex(RuntimeError, 'monitor de bloqueo'): services['main']()
        self.assertEqual(calls.mock_calls[0][0], 'import_environment')
        args = calls.import_environment.call_args_list[0].args[0]
        self.assertIn('--systemd', args)
        self.assertIn('HYPRLAND_INSTANCE_SIGNATURE', args)
        self.assertIn('XDG_CONFIG_HOME', args)
        self.assertIn('XDG_RUNTIME_DIR', args)
        with patch.dict(os.environ, env, clear=True), patch('signal.signal'), \
             patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'fixture')), \
             patch('subprocess.Popen') as launch:
            with self.assertRaises(subprocess.CalledProcessError): services['main']()
            launch.assert_not_called()

    def test_shell_failure_keeps_idle_protection_and_only_stops_owned_children(self):
        services = runpy.run_path(str(ROOT / 'bin/wysun-session-services'))
        shell, idle, daemon = Mock(), Mock(), Mock()
        shell.poll.return_value = 1
        idle.poll.return_value = daemon.poll.return_value = None
        env = {'HYPRLAND_INSTANCE_SIGNATURE': 'isolated-test', 'XDG_SESSION_TYPE': 'wayland'}
        def login_ends(_):
            idle.terminate.assert_not_called()
            daemon.terminate.assert_not_called()
            raise SystemExit(0)
        with patch.dict(os.environ, env, clear=True), patch('signal.signal'), \
             patch('shutil.which', return_value=None), patch('pathlib.Path.is_file', return_value=False), \
             patch('subprocess.run') as run, patch('subprocess.Popen', side_effect=[shell,idle,daemon]), \
             patch('time.sleep', side_effect=login_ends):
            with self.assertRaises(SystemExit): services['main']()
        self.assertEqual(run.call_count, 1)  # environment import; no spurious lock
        shell.terminate.assert_not_called()
        idle.terminate.assert_called_once()
        daemon.terminate.assert_called_once()
        for child in (shell,idle,daemon):child.wait.assert_called_once_with(timeout=2)

    def test_recovery_closes_the_shell_picker_with_exact_ipc(self):
        recovery = runpy.run_path(str(ROOT / 'bin/wysun-recover'))
        main = recovery['main']
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            return Mock(returncode=0, stdout='')
        with patch.dict(main.__globals__, {'run': run}), patch('os.kill') as kill, patch('subprocess.Popen') as launch:
            self.assertEqual(main([]), 0)
            kill.assert_not_called();launch.assert_not_called()
        self.assertEqual([command[1:] for command in calls], [
            ['status'], ['close'], ['picker', 'close']])

    def test_recovery_reports_an_unclosable_picker_without_signalling(self):
        recovery = runpy.run_path(str(ROOT / 'bin/wysun-recover'))
        main = recovery['main']
        def run(command, **kwargs):
            return Mock(returncode=1 if 'picker' in command else 0, stdout='')
        with patch.dict(main.__globals__, {'run': run}), patch('os.kill') as kill:
            self.assertEqual(main([]), 1)
            kill.assert_not_called()

    def test_dead_shell_is_relaunched_with_crash_loop_backoff(self):
        services = runpy.run_path(str(ROOT / 'bin/wysun-session-services'))
        revive, children = services['revive_shell'], services['children']
        dead, fresh = Mock(), Mock()
        dead.poll.return_value = -9
        children[:] = [dead]
        restarts, log = [], []
        with patch.dict(revive.__globals__, {'log_event': log.append}), \
             patch('subprocess.Popen', return_value=fresh) as launch:
            self.assertTrue(revive(restarts, clock=lambda: 0))
            fresh.poll.return_value = None
            self.assertFalse(revive(restarts, clock=lambda: 0))  # a live shell is left alone
            fresh.poll.return_value = 1
            restarts.clear()
            self.assertTrue(revive(restarts, clock=lambda: 0))
            launch.reset_mock()
            restarts.clear()
            children[:] = [dead]
            self.assertTrue(revive(restarts, clock=lambda: 0))
            launch.assert_called_once_with(['wysun-shell'])
            self.assertIs(children[0], fresh)
            self.assertIn('señal 9', log[0])
            for moment in range(1, services['RESTART_BURST']):
                self.assertTrue(revive(restarts, clock=lambda m=moment: m))
            self.assertFalse(revive(restarts, clock=lambda: 10))  # burst exhausted: cool down
            self.assertTrue(revive(restarts, clock=lambda: 10 + services['RESTART_COOLDOWN']))
        with patch.dict(revive.__globals__, {'log_event': log.append}), \
             patch('subprocess.Popen', side_effect=OSError('fixture')):
            children[:] = [dead]
            self.assertFalse(revive([], clock=lambda: 0))
        children.clear()

    def test_partial_client_start_failure_reaps_already_started_children(self):
        services = runpy.run_path(str(ROOT / 'bin/wysun-session-services'))
        shell = Mock(); shell.poll.return_value = None
        env = {'HYPRLAND_INSTANCE_SIGNATURE': 'isolated-test', 'XDG_SESSION_TYPE': 'wayland'}
        with patch.dict(os.environ, env, clear=True), patch('signal.signal'), \
             patch('subprocess.run') as run, patch('subprocess.Popen', side_effect=[shell,OSError('fixture spawn')]):
            with self.assertRaisesRegex(OSError,'fixture spawn'):services['main']()
        self.assertEqual(run.call_args_list[-1].args[0], ['wysun-lock'])
        self.assertTrue(run.call_args_list[-1].kwargs['check'])
        shell.terminate.assert_called_once()
        shell.wait.assert_called_once_with(timeout=2)


if __name__ == '__main__':
    unittest.main()
