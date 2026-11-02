"""Migration checks: preserve media, commands, customization and running releases."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qml import support as qml_support  # noqa: E402  (venv_python only; no Qt here)
spec = importlib.util.spec_from_file_location('wysun_installer', ROOT / 'installer/main.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class WysunDistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def deploy(self):
        deployment = installer.Deployment(self.home, ROOT)
        deployment.begin()
        self.addCleanup(deployment.lock.close)
        return deployment

    def test_fresh_install_dispatch_and_idempotent_update(self):
        deployment = self.deploy()
        deployment.configure_wysun()
        deployment.finish()
        deployment.lock.close()
        launch = self.home / '.local/bin/wysun'
        self.assertIn('Wysun Recorder', subprocess.check_output([str(launch), 'recorder', '--version'], cwd='/', text=True))
        self.assertIn('Wysun', subprocess.check_output([str(launch.parent / 'wysun-recorder'), '--version'], cwd='/', text=True))
        # `wysun` is the only launcher of the family.
        for old in ('wysun-screenshot', 'wybie-screenshot', 'wysun-player', 'wysun-pdf', 'wysun-music', 'wysun-files'):
            self.assertFalse((launch.parent / old).exists(), old)
        entries = self.home / '.local/share/applications'
        self.assertFalse((entries / 'wybie-screenshot.desktop').exists())
        self.assertEqual(sorted(path.name for path in entries.glob('*.desktop')),
                         ['wysun-player.desktop', 'wysun-recorder.desktop', 'wysun-settings.desktop', 'wysun.desktop'])
        self.assertIn('Exec=wysun player -- %F', (entries / 'wysun-player.desktop').read_text())
        self.assertIn('Name=Wysun Recorder', (entries / 'wysun-recorder.desktop').read_text())
        self.assertIn('Name=Wysun Settings', (entries / 'wysun-settings.desktop').read_text())
        self.assertNotIn('Órbita', (entries / 'wysun-settings.desktop').read_text())
        update = self.deploy()
        update.configure_wysun()
        self.assertFalse(update.conflicts)
        self.assertEqual(update.journal['operations'], [])

    def test_app_update_keeps_file_integration_and_tools_with_the_wayland_component(self):
        deployment = self.deploy()
        deployment.receipt['components'] = ['desktop', 'wayland']
        with patch.dict(os.environ, WYSUN_SKIP_RUNTIME='1'):
            deployment.configure_app()
        self.assertFalse(deployment.conflicts)
        for relative in ('.local/bin/wysun', '.local/share/wysun/app/wysun_lanshare/__main__.py', '.local/share/applications/wysun-files.desktop',
                         '.config/systemd/user/wysun-files-integration.service',
                         '.local/share/dbus-1/services/org.freedesktop.impl.portal.desktop.wysun.service',
                         '.local/share/xdg-desktop-portal/portals/wysun.portal'):
            self.assertTrue((self.home / relative).exists(), relative)

    def test_a_full_installation_publishes_the_recorder_twice_in_one_run(self):
        # The wayland component and the desktop profile both publish the Wysun family in a full installation.
        deployment = self.deploy()
        deployment.configure_wysun()
        deployment.configure_wysun()
        self.assertFalse(deployment.conflicts)
        self.assertEqual(len(list((self.home / '.local/share/wysun/capture/releases').iterdir())), 1)

    def release(self):
        deployment = self.deploy()
        deployment.configure_wysun()
        deployment.finish()
        deployment.lock.close()
        return next((self.home / '.local/share/wysun/capture/releases').iterdir())

    def clean_env(self, release=None, **extra):
        env = dict(os.environ, HOME=str(self.home), QT_QPA_PLATFORM='offscreen', XDG_DATA_HOME=str(self.home / '.local/share'),
                   XDG_CONFIG_HOME=str(self.home / '.config'), XDG_STATE_HOME=str(self.home / '.local/state'))
        if release:
            env['PYTHONPATH'] = str(release)
        for variable in ('WAYLAND_DISPLAY', 'DISPLAY', 'WYSUN_QML_LIB'):
            env.pop(variable, None)
        env.update(extra)
        return env

    def test_release_carries_the_qml_window_and_not_the_media_engine(self):
        release = self.release()
        for name in ('wysun_qml/bootstrap.py', 'qml/WysunM3/qmldir', 'wysun_recorder/ui/qml/Main.qml', 'wysun_core/tokens.json'):
            self.assertTrue((release / name).is_file(), name)
        self.assertFalse((release / 'wysun_media').exists(), 'the Recorder no longer plays: the engine is not part of it')
        for name in ('wysun_qml', 'qml/WysunM3', 'wysun_core'):
            self.assertFalse((release / name).is_symlink(), f'{name}: a release holds a copy, not a link back to the repository')
        launcher = (self.home / '.local/bin/wysun-recorder').read_text()
        self.assertIn('export WYSUN_QML_LIB=' + shlex.quote(str(release / 'qml')), launcher)
        desktop = (self.home / '.local/share/applications/wysun-recorder.desktop').read_text()
        self.assertIn('Comment=Ajustes de grabación de Wysun', desktop)

    @staticmethod
    def shell_runtime():
        """The installed shell runtime (private Qt) of the person running the tests, if any."""
        data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
        runtime = Path(os.environ.get('WYSUN_RUNTIME') or data / 'wysun/runtime')
        return runtime if (runtime / 'RUNTIME.json').exists() else None

    @unittest.skipUnless(qml_support.venv_python() and shell_runtime.__func__(), 'needs the qml-runtime venv and the shell runtime')
    def test_the_release_window_loads_its_own_code_only(self):
        release = self.release()
        code = ('import sys\nfrom wysun_qml import bootstrap\nbootstrap.require_qt()\nbootstrap.configure_qt()\n'
                'from wysun_recorder.ui.window import RecorderSettingsWindow\n'
                'window = RecorderSettingsWindow()\nprint(window.window.objectName())\n'
                'own = ("wysun_core", "wysun_qml", "wysun_recorder", "wysun_media", "wysun_files", "wysun_player")\n'
                'print("\\n".join(sorted({m.__file__ for n, m in list(sys.modules.items()) '
                'if n.split(".")[0] in own and getattr(m, "__file__", None)})))')
        env = self.clean_env(release, WYSUN_QML_LIB=str(release / 'qml'), WYSUN_RUNTIME=str(self.shell_runtime()),
                             WYSUN_QML_RUNTIME=str(qml_support.venv_python().parent.parent))
        done = subprocess.run([str(qml_support.venv_python()), '-P', '-c', code], cwd='/', env=env, capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        lines = done.stdout.split()
        self.assertEqual(lines[0], 'recorderWindow')
        self.assertGreater(len(lines), 3)
        for line in lines[1:]:
            self.assertTrue(line.startswith(str(release)), line)

    def test_without_the_qml_runtime_only_the_window_fails(self):
        self.release()
        launcher = str(self.home / '.local/bin/wysun-recorder')
        env = self.clean_env(WYSUN_QML_RUNTIME='/nonexistent')
        prefs = subprocess.run([launcher, '--prefs'], cwd='/', env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(prefs.returncode, 0, prefs.stderr)
        self.assertIn('record_mic', json.loads(prefs.stdout))
        window = subprocess.run([launcher], cwd='/', env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(window.returncode, 2, window.stderr)
        self.assertIn('runtime QML', window.stderr)

    def test_a_player_change_makes_a_new_release_and_keeps_the_old_one(self):
        import shutil
        first = self.deploy()
        first.configure_wysun()
        first.finish()
        first.lock.close()
        releases = self.home / '.local/share/wysun/capture/releases'
        old = next(releases.iterdir())
        source = self.home / 'source'
        shutil.copytree(ROOT / 'apps/recorder', source / 'apps/recorder', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (source / 'bin').mkdir()
        shutil.copy2(ROOT / 'bin/wysun', source / 'bin/wysun')
        engine = source / 'apps/recorder/wysun_qml/bootstrap.py'
        engine.write_text(engine.read_text() + '\n# synthetic engine change\n')
        update = installer.Deployment(self.home, source)
        update.begin()
        self.addCleanup(update.lock.close)
        update.configure_wysun()
        update.finish()
        self.assertEqual(len(list(releases.iterdir())), 2, 'the shared package is part of the release hash')
        self.assertNotIn('synthetic engine change', (old / 'wysun_qml/bootstrap.py').read_text())

    def test_update_retires_old_launchers_it_wrote_and_keeps_private_roots(self):
        private = ('.local/share/wysun/recorder/recordings/old/project.json',
                   '.local/share/wybie-screenshot/sessions/old/original.png',
                   '.config/wysun/recorder/preferences.json', '.local/share/wysun/wysun.sqlite3',
                   '.config/wysun/theme.json')
        for name in private:
            path = self.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'private fixture untouched')
        owned, edited, foreign = ('.local/bin/wysun-player', '.local/bin/wybie-screenshot',
                                  '.local/share/applications/wybie-screenshot.desktop'), '.local/bin/gvm', '.local/bin/web-dev'
        receipt = {}
        for relative in (*owned, edited, foreign):
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('old ' + relative)
            if relative != foreign:
                receipt[relative] = installer.fingerprint(path)
        (self.home / edited).write_text('changed by the user')
        deployment = self.deploy()
        deployment.receipt['files'].update(receipt)
        deployment.configure_wysun()
        for relative in owned:
            self.assertFalse((self.home / relative).exists(), relative)
            self.assertNotIn(relative, deployment.receipt['files'])
        # A launcher the user changed is theirs now: kept, dropped from the receipt, never a recurring conflict.
        self.assertEqual((self.home / edited).read_text(), 'changed by the user')
        self.assertEqual(deployment.conflicts, [])
        self.assertNotIn(edited, deployment.receipt['files'])
        self.assertEqual((self.home / foreign).read_text(), 'old ' + foreign)
        for name in private:
            self.assertEqual((self.home / name).read_bytes(), b'private fixture untouched')

    def test_a_launcher_the_active_hyprland_config_still_calls_is_kept(self):
        launcher = self.home / '.local/bin/wysun-workspaces'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('old launcher')
        config = self.home / '.config/wysun/hyprland.lua'
        config.parent.mkdir(parents=True)
        config.write_text('hl.on("hyprland.start", function () hl.exec_cmd("wysun-workspaces") end)\n')
        deployment = self.deploy()
        deployment.receipt['files']['.local/bin/wysun-workspaces'] = installer.fingerprint(launcher)
        deployment.configure_wysun()
        self.assertTrue(launcher.exists(), 'retiring it would break the active binds')
        self.assertIn('.local/bin/wysun-workspaces', deployment.receipt['files'])
        self.assertFalse(deployment.conflicts)
        deployment.finish()
        deployment.lock.close()
        config.write_text('hl.on("hyprland.start", function () hl.exec_cmd("wysun workspaces") end)\n'
                          'hl.window_rule({ match = { class = "^wysun-workspaces$" } })\n')   # a class is not a call
        update = self.deploy()
        update.receipt['files']['.local/bin/wysun-workspaces'] = installer.fingerprint(launcher)
        update.configure_wysun()
        self.assertFalse(launcher.exists())

    def test_unowned_commands_and_modified_legacy_are_kept(self):
        legacy = self.home / '.local/bin/wysun-recorder'
        legacy.parent.mkdir(parents=True)
        legacy.write_text('my custom recorder launcher')
        deployment = self.deploy()
        deployment.configure_wysun()
        self.assertEqual(legacy.read_text(), 'my custom recorder launcher')
        self.assertIn('.local/bin/wysun-recorder', deployment.conflicts)
        self.assertTrue((deployment.backup / 'incoming/.local/bin/wysun-recorder').is_file())
        deployment.lock.close()
        public = legacy.with_name('wysun')
        public.write_text('unrelated personal tool')
        update = self.deploy()
        update.receipt['files'].pop('.local/bin/wysun', None)
        update.configure_wysun()
        self.assertEqual(public.read_text(), 'unrelated personal tool')
        self.assertEqual(update.journal['operations'], [])

    def test_upgrade_retains_old_bundle_and_restore_restores_dispatcher(self):
        deployment = self.deploy()
        deployment.configure_wysun()
        deployment.finish()
        ident = deployment.journal['id']
        deployment.lock.close()
        releases = self.home / '.local/share/wysun/capture/releases'
        first = next(releases.iterdir())
        original = (first / 'wysun_recorder/__main__.py').read_bytes()
        # Alter only an isolated source copy; never touch a running installation.
        import shutil
        source = self.home / 'source'
        shutil.copytree(ROOT / 'apps/recorder', source / 'apps/recorder', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (source / 'bin').mkdir()
        shutil.copy2(ROOT / 'bin/wysun', source / 'bin/wysun')
        main = source / 'apps/recorder/wysun_recorder/__main__.py'
        main.write_bytes(original + b'\n# synthetic source upgrade\n')
        update = installer.Deployment(self.home, source)
        update.begin()
        self.addCleanup(update.lock.close)
        update.configure_wysun()
        update.finish()
        update.lock.close()
        self.assertEqual(len(list(releases.iterdir())), 2)
        self.assertEqual((first / 'wysun_recorder/__main__.py').read_bytes(), original)
        old_launcher = (self.home / '.local/bin/wysun-recorder').read_text()
        installer.restore(self.home, update.journal['id'])
        self.assertNotEqual((self.home / '.local/bin/wysun-recorder').read_text(), old_launcher)
        self.assertIn(str(first), (self.home / '.local/bin/wysun-recorder').read_text())

    def test_public_dispatch_preserves_arguments(self):
        import shutil
        directory = self.home / 'bin'
        directory.mkdir()
        shutil.copy2(ROOT / 'bin/wysun', directory / 'wysun')
        for name in ('wysun-recorder', 'wysun-shell'):
            path = directory / name
            path.write_text('#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv))\n')
            path.chmod(0o755)
        app = self.home / 'share/wysun/app'
        for module in ('wysun_music/__main__.py', 'wysun_files/__main__.py', 'wysun_player/__main__.py'):
            path = app / module
            path.parent.mkdir(parents=True, exist_ok=True)
            (path.parent / '__init__.py').write_text('')
            path.write_text('import json,sys\nprint(json.dumps(["-m " + __spec__.name, *sys.argv[1:]]))\n')
        for args, executable, forwarded in (
            (['music'], '-m wysun_music.__main__', []),
            (['files', '/tmp/a file'], '-m wysun_files.__main__', ['/tmp/a file']),
            (['player', '--start', '3', '--', '/tmp/a b.mp4'], '-m wysun_player.__main__', ['--start', '3', '--', '/tmp/a b.mp4']),
            (['recorder', '--quick-record'], 'wysun-recorder', ['--quick-record']),
            (['shell', 'screenshot', '--options'], 'wysun-shell', ['screenshot', '--options']),
        ):
            output = json.loads(subprocess.check_output([str(directory / 'wysun'), *args], cwd='/', text=True))
            self.assertEqual(output, [executable if executable.startswith('-m ') else str(directory / executable), *forwarded])

    def test_full_configuration_repeat_preserves_private_preferences(self):
        import contextlib
        import io
        for iteration in range(2):
            deployment = self.deploy()
            with contextlib.redirect_stdout(io.StringIO()):
                deployment.configure(components=('desktop',))
                deployment.finish()
            self.assertFalse(deployment.conflicts)
            self.assertEqual((self.home / '.local/share/applications/wysun.desktop').read_text(), installer.WYSUN_DESKTOP)
            private = self.home / '.config/wysun/personal-layout.json'
            if iteration:
                self.assertFalse(deployment.journal['operations'])
                self.assertEqual(private.read_text(), 'private fixture')
            else:
                private.write_text('private fixture')
            deployment.lock.close()


if __name__ == '__main__':
    unittest.main()
