"""Native repository setup and explicit system preparation, using synthetic roots."""
import json
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / 'installer'))
import main as backend
from repositories import enabled, ensure, repository_spec


class RepositoryPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='wysun-repositories-')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_native_sources_never_mix_distributions(self):
        debian = repository_spec({'ID': 'debian', 'VERSION_ID': '13'})
        parrot = repository_spec({'ID': 'parrot', 'VERSION_ID': '7.4'})
        self.assertIn('debian-archive-keyring', debian[2])
        self.assertNotIn('parrot', debian[2])
        self.assertIn('echo-backports', parrot[2])
        self.assertNotIn('debian.org', parrot[2])
        for fields in ({'ID': 'ubuntu', 'ID_LIKE': 'debian', 'VERSION_ID': '24.04'},
                       {'ID': 'debian', 'VERSION_ID': '12'}, {'ID': 'parrot', 'VERSION_ID': '6'}):
            with self.assertRaises(ValueError):
                repository_spec(fields)

    def test_disabled_sources_and_comments_do_not_count_as_enabled(self):
        folder = self.root / 'etc/apt/sources.list.d'
        folder.mkdir(parents=True)
        (folder / 'old.list').write_text('# deb https://example.invalid trixie-backports main\n')
        path = folder / 'test.sources'
        path.write_text('Types: deb\nSuites: trixie-backports\nEnabled: no\n')
        self.assertFalse(enabled(self.root, 'trixie-backports'))
        path.write_text('Types: deb\nSuites: trixie trixie-backports\nEnabled: yes\n')
        self.assertTrue(enabled(self.root, 'trixie-backports'))

    def test_ensure_is_idempotent_and_journals_before_adding_a_source(self):
        key = self.root / 'usr/share/keyrings/debian-archive-keyring.gpg'
        key.parent.mkdir(parents=True)
        key.write_text('synthetic archive key')
        fields = {'ID': 'debian', 'VERSION_ID': '13'}
        backup = Path(ensure(fields, self.root))
        journal = json.loads((backup / 'journal.json').read_text())
        source = self.root / journal['path']
        self.assertIsNone(journal['before'])
        self.assertEqual(source.read_text(), journal['after'])
        self.assertIsNone(ensure(fields, self.root))
        self.assertEqual(len(list(backup.parent.iterdir())), 1)
        self.assertEqual((backup / 'journal.json').stat().st_mode & 0o777, 0o600)

    def test_existing_user_source_is_never_replaced(self):
        target = self.root / 'etc/apt/sources.list.d/wysun-backports.list'
        target.parent.mkdir(parents=True)
        target.write_text('personal source\n')
        with self.assertRaises(RuntimeError):
            ensure({'ID': 'parrot', 'VERSION_ID': '7'}, self.root)
        self.assertEqual(target.read_text(), 'personal source\n')
        self.assertFalse((self.root / 'var').exists())

    def test_full_install_prepares_repositories_and_resolves_before_installing(self):
        home = self.root / 'home'
        commands = []
        def record(command, env=None):
            commands.append(list(map(str, command)))
        with patch.dict(os.environ, {'HOME': str(home), 'WYSUN_SKIP_RUNTIME': '1'}), \
             patch.object(backend, 'host_supported', return_value={'ID': 'debian', 'VERSION_ID': '13'}), \
             patch.object(backend.os, 'geteuid', return_value=1000), \
             patch.object(backend, 'run', side_effect=record), \
             patch.object(backend, 'install_tools'), patch.object(backend, 'doctor', return_value=0), \
             patch.object(backend, 'nvim_setup'), patch.object(backend, 'install_extras') as extras, \
             patch('wayland.simulate_packages', return_value='plan'), \
             contextlib.redirect_stdout(io.StringIO()):
            code = backend.main(['install', '--source', str(SOURCE)])
        self.assertIn(code, (0, 2))
        index = lambda word: next(i for i, command in enumerate(commands) if any(word in part for part in command))
        self.assertLess(index('repositories.py'), index('update'))
        self.assertLess(index('update'), next(i for i, c in enumerate(commands) if 'install' in c and '--yes' in c))
        self.assertTrue(any('boot.py' in ' '.join(c) and 'grub,plymouth,greeter' in c for c in commands), 'boot screens with greetd')
        self.assertEqual(extras.call_args.args[0], ('brave', 'discord', 'obsidian'))
        receipt = json.loads((home/'.local/state/wysun/install/installed.json').read_text())
        self.assertEqual(set(receipt['inputs']), {'packages', 'session', 'boot', 'editor', 'extras'})
        self.assertNotIn('upgrade', [part for c in commands for part in c])

    def test_dependency_failure_stops_before_configuration_changes(self):
        home = self.root / 'home'
        def fail_resolution(command, env=None):
            if 'repositories.py' in ' '.join(map(str, command)):
                raise RuntimeError('Synthetic unsatisfied dependency')
        with patch.dict(os.environ, {'HOME': str(home)}), \
             patch.object(backend, 'host_supported', return_value={'ID': 'debian', 'VERSION_ID': '13'}), \
             patch.object(backend.os, 'geteuid', return_value=1000), \
             patch.object(backend, 'run', side_effect=fail_resolution), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                backend.main(['install', '--source', str(SOURCE)])
        self.assertFalse((home/'.config').exists())
        journal = next((home/'.local/state/wysun/install/backups').glob('*/journal.json'))
        self.assertEqual(json.loads(journal.read_text())['status'], 'failed')

if __name__ == '__main__':
    unittest.main()
