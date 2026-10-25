"""Migration checks: preserve media, commands, customization and running releases."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
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
        self.assertIn('Wysun', subprocess.check_output([str(launch.parent / 'loomrec'), '--version'], cwd='/', text=True))
        # Screenshots are taken by the shell; the former commands only redirect there.
        for old in ('wysun-screenshot', 'wybie-screenshot'):
            self.assertIn('/wysun" screenshot "$@"', (launch.parent / old).read_text())
        entries = self.home / '.local/share/applications'
        self.assertFalse((entries / 'wybie-screenshot.desktop').exists())
        self.assertEqual(sorted(path.name for path in entries.glob('*.desktop')),
                         ['loomrec.desktop', 'orbit-settings.desktop', 'orbit.desktop', 'wysun-player.desktop'])
        self.assertTrue(os.access(launch.parent / 'wysun-player', os.X_OK))
        self.assertIn('Name=Wysun Recorder', (entries / 'loomrec.desktop').read_text())
        self.assertIn('Name=Wysun Settings', (entries / 'orbit-settings.desktop').read_text())
        self.assertFalse((entries / 'orbit-connections.desktop').exists())
        self.assertNotIn('Órbita', (entries / 'orbit-settings.desktop').read_text())
        self.assertFalse((entries / 'wysun-recorder.desktop').exists())
        update = self.deploy()
        update.configure_wysun()
        self.assertFalse(update.conflicts)
        self.assertEqual(update.journal['operations'], [])

    def test_each_release_carries_its_own_player_and_runs_without_the_repository(self):
        deployment = self.deploy()
        deployment.configure_wysun()
        deployment.finish()
        deployment.lock.close()
        releases = self.home / '.local/share/wysun/capture/releases'
        release = next(releases.iterdir())
        self.assertTrue((release / 'wysun_media/__init__.py').is_file())
        self.assertFalse((release / 'wysun_media').is_symlink(), 'a release holds a copy, not a link back to the repository')
        env = dict(os.environ, PYTHONPATH=str(release), HOME=str(self.home), QT_QPA_PLATFORM='offscreen')
        for variable in ('WAYLAND_DISPLAY', 'DISPLAY'):
            env.pop(variable, None)
        code = ('import wysun_media, loomrec.ui.media_host as host; from wysun_media.player import MediaPlayer; '
                'print(wysun_media.__file__); print(host.__file__)')
        done = subprocess.run([sys.executable, '-P', '-c', code], cwd='/', env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        for line in done.stdout.split():
            self.assertTrue(line.startswith(str(release)), line)

    def test_a_player_change_makes_a_new_release_and_keeps_the_old_one(self):
        import shutil
        first = self.deploy()
        first.configure_wysun()
        first.finish()
        first.lock.close()
        releases = self.home / '.local/share/wysun/capture/releases'
        old = next(releases.iterdir())
        source = self.home / 'source'
        shutil.copytree(ROOT / 'apps/capture', source / 'apps/capture', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (source / 'bin').mkdir()
        shutil.copy2(ROOT / 'bin/wysun', source / 'bin/wysun')
        player = source / 'apps/capture/wysun_media/player.py'
        player.write_text(player.read_text() + '\n# synthetic player change\n')
        update = installer.Deployment(self.home, source)
        update.begin()
        self.addCleanup(update.lock.close)
        update.configure_wysun()
        update.finish()
        self.assertEqual(len(list(releases.iterdir())), 2, 'the shared package is part of the release hash')
        self.assertNotIn('synthetic player change', (old / 'wysun_media/player.py').read_text())

    def test_adopt_verified_legacy_files_and_preserve_all_private_roots(self):
        private = ('.local/share/loomrec/recordings/old/project.json',
                   '.local/share/wybie-screenshot/sessions/old/original.png',
                   '.config/loomrec/preferences.json', '.local/share/orbit/orbit.sqlite3',
                   '.config/orbit/theme.json')
        for name in private:
            path = self.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'private fixture untouched')
        for command, base, absolute in (('loomrec', 'loomrec', False), ('wybie-screenshot', 'wybie-screenshot', True)):
            owned = {}
            for key, relative in (('launcher', '.local/bin/' + command),
                                  ('desktop', '.local/share/applications/' + command + '.desktop'),
                                  ('icon', '.local/share/icons/hicolor/scalable/apps/' + command + '.svg')):
                path = self.home / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('old managed ' + key)
                owned[str(path) if absolute else key] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest = self.home / ('.local/share/' + base + '/install-manifest.json')
            manifest.write_text(json.dumps({'version': 1, 'files': owned}))
        deployment = self.deploy()
        deployment.configure_wysun()
        self.assertFalse(deployment.conflicts)
        for name in private:
            self.assertEqual((self.home / name).read_bytes(), b'private fixture untouched')
        self.assertIn('Wysun', subprocess.check_output([str(self.home / '.local/bin/loomrec'), '--version'], text=True))
        # The verified standalone Screenshot install is adopted: redirect, no menu entry or icon.
        self.assertIn('/wysun" screenshot', (self.home / '.local/bin/wybie-screenshot').read_text())
        self.assertFalse((self.home / '.local/share/applications/wybie-screenshot.desktop').exists())
        self.assertFalse((self.home / '.local/share/icons/hicolor/scalable/apps/wybie-screenshot.svg').exists())

    def test_unowned_commands_and_modified_legacy_are_kept(self):
        legacy = self.home / '.local/bin/loomrec'
        legacy.parent.mkdir(parents=True)
        legacy.write_text('my custom recorder launcher')
        deployment = self.deploy()
        deployment.configure_wysun()
        self.assertEqual(legacy.read_text(), 'my custom recorder launcher')
        self.assertIn('.local/bin/loomrec', deployment.conflicts)
        self.assertTrue((deployment.backup / 'incoming/.local/bin/loomrec').is_file())
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
        original = (first / 'loomrec/__main__.py').read_bytes()
        # Alter only an isolated source copy; never touch a running installation.
        import shutil
        source = self.home / 'source'
        shutil.copytree(ROOT / 'apps/capture', source / 'apps/capture', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (source / 'bin').mkdir()
        shutil.copy2(ROOT / 'bin/wysun', source / 'bin/wysun')
        main = source / 'apps/capture/loomrec/__main__.py'
        main.write_bytes(original + b'\n# synthetic source upgrade\n')
        update = installer.Deployment(self.home, source)
        update.begin()
        self.addCleanup(update.lock.close)
        update.configure_wysun()
        update.finish()
        update.lock.close()
        self.assertEqual(len(list(releases.iterdir())), 2)
        self.assertEqual((first / 'loomrec/__main__.py').read_bytes(), original)
        old_launcher = (self.home / '.local/bin/loomrec').read_text()
        installer.restore(self.home, update.journal['id'])
        self.assertNotEqual((self.home / '.local/bin/loomrec').read_text(), old_launcher)
        self.assertIn(str(first), (self.home / '.local/bin/loomrec').read_text())

    def test_public_dispatch_preserves_arguments(self):
        import shutil
        directory = self.home / 'bin'
        directory.mkdir()
        shutil.copy2(ROOT / 'bin/wysun', directory / 'wysun')
        for name in ('orbit', 'wysun-recorder', 'wysun-shell', 'orbit-files'):
            path = directory / name
            path.write_text('#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv))\n')
            path.chmod(0o755)
        for args, executable, forwarded in (
            (['music'], 'orbit', ['music']),
            (['files', '/tmp/a file'], 'orbit-files', ['/tmp/a file']),
            (['recorder', '--quick-record'], 'wysun-recorder', ['--quick-record']),
            (['screenshot', '--region', '--delay', '0'], 'wysun-shell', ['screenshot', '--options', '--no-save']),
            (['screenshot', '--region', '--accept-on-select', '--clipboard', '--path', '/tmp/s'], 'wysun-shell',
             ['screenshot', '--path', '/tmp/s']),
        ):
            output = json.loads(subprocess.check_output([str(directory / 'wysun'), *args], cwd='/', text=True))
            self.assertEqual(output, [str(directory / executable), *forwarded])

    def test_full_configuration_repeat_preserves_private_preferences(self):
        import contextlib
        import io
        for iteration in range(2):
            deployment = self.deploy()
            with contextlib.redirect_stdout(io.StringIO()):
                deployment.configure(components=('desktop',))
                deployment.finish()
            self.assertFalse(deployment.conflicts)
            self.assertEqual((self.home / '.local/share/applications/orbit.desktop').read_text(), installer.WYSUN_DESKTOP)
            private = self.home / '.config/orbit/personal-layout.json'
            if iteration:
                self.assertFalse(deployment.journal['operations'])
                self.assertEqual(private.read_text(), 'private fixture')
            else:
                private.write_text('private fixture')
            deployment.lock.close()


if __name__ == '__main__':
    unittest.main()
