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
        for mode, title in (('recorder', 'Wysun Recorder'), ('screenshot', 'Wysun Screenshot')):
            output = subprocess.check_output([str(launch), mode, '--version'], cwd='/', text=True)
            self.assertIn(title, output)
        for old in ('loomrec', 'wybie-screenshot'):
            self.assertIn('Wysun', subprocess.check_output([str(launch.parent / old), '--version'], cwd='/', text=True))
        entries = self.home / '.local/share/applications'
        self.assertEqual(len(list(entries.glob('*.desktop'))), 5)
        self.assertIn('Name=Wysun Recorder', (entries / 'loomrec.desktop').read_text())
        self.assertIn('Name=Wysun Ajustes', (entries / 'orbit-settings.desktop').read_text())
        self.assertIn('Name=Wysun Conexiones', (entries / 'orbit-connections.desktop').read_text())
        self.assertNotIn('Órbita', (entries / 'orbit-settings.desktop').read_text())
        self.assertFalse((entries / 'wysun-recorder.desktop').exists())
        update = self.deploy()
        update.configure_wysun()
        self.assertFalse(update.conflicts)
        self.assertEqual(update.journal['operations'], [])

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
        for command in ('loomrec', 'wybie-screenshot'):
            self.assertIn('Wysun', subprocess.check_output([str(self.home / '.local/bin' / command), '--version'], text=True))

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

    def test_public_dispatch_preserves_arguments_and_legacy_fallback(self):
        import shutil
        directory = self.home / 'bin'
        directory.mkdir()
        shutil.copy2(ROOT / 'bin/wysun', directory / 'wysun')
        for name in ('orbit', 'wysun-recorder', 'wysun-screenshot', 'orbit-files'):
            path = directory / name
            path.write_text('#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv))\n')
            path.chmod(0o755)
        for args, executable, forwarded in (
            ([], 'orbit', ['toggle']),
            (['music'], 'orbit', ['music']),
            (['files', '/tmp/a file'], 'orbit-files', ['/tmp/a file']),
            (['recorder', '--quick-record'], 'wysun-recorder', ['--quick-record']),
            (['screenshot', '--region', '--delay', '0'], 'wysun-screenshot', ['--region', '--delay', '0']),
        ):
            output = json.loads(subprocess.check_output([str(directory / 'wysun'), *args], cwd='/', text=True))
            self.assertEqual(output, [str(directory / executable), *forwarded])

    def test_full_configuration_repeat_preserves_private_preferences(self):
        import contextlib
        import io
        for iteration in range(2):
            deployment = self.deploy()
            with contextlib.redirect_stdout(io.StringIO()):
                deployment.configure(theme='space-black', components=('desktop',))
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
