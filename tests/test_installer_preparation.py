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
from install_model import InstallOptions
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

    def test_system_upgrade_cannot_remove_packages_or_replace_configuration(self):
        with patch.object(backend, 'run') as run:
            backend.upgrade_system()
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn('update', commands[0])
        self.assertIn('upgrade', commands[1])
        self.assertIn('--no-remove', commands[1])
        self.assertIn('Dpkg::Options::=--force-confold', commands[1])
        self.assertNotIn('dist-upgrade', commands[1])

    def test_preparation_is_explicit_and_rejected_for_configuration_only(self):
        options = InstallOptions(SOURCE, components=('terminal',), upgrade_system=True)
        self.assertIn('--upgrade-system', options.argv())
        self.assertTrue(options.summary()['upgrade_system'])
        with self.assertRaises(ValueError):
            InstallOptions(SOURCE, self.root, ('terminal',), config_only=True, upgrade_system=True).validate()
        with self.assertRaises(ValueError):
            backend.main(['install', '--source', str(SOURCE), '--target-home', str(self.root), '--installer-only', '--prepare-repositories'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_full_install_resolves_dependencies_before_upgrading_the_system(self):
        home = self.root / 'home'
        commands = []
        def record(command, env=None):
            commands.append(list(map(str, command)))
        with patch.dict(os.environ, {'HOME': str(home)}), \
             patch.object(backend, 'host_supported', return_value={'ID': 'debian', 'VERSION_ID': '13'}), \
             patch.object(backend.os, 'geteuid', return_value=1000), \
             patch.object(backend, 'run', side_effect=record), \
             patch.object(backend, 'install_tools'), patch.object(backend, 'doctor', return_value=0), \
             contextlib.redirect_stdout(io.StringIO()):
            code = backend.main(['install', '--source', str(SOURCE), '--components', 'terminal', '--upgrade-system'])
        self.assertEqual(code, 0)
        index = lambda word: next(i for i, command in enumerate(commands) if word in command)
        self.assertLess(index('update'), index('--simulate'))
        self.assertLess(index('--simulate'), index('upgrade'))
        self.assertLess(index('upgrade'), next(i for i, c in enumerate(commands) if 'install' in c and '--simulate' not in c))
        receipt = json.loads((home/'.local/state/dotifails/installed.json').read_text())
        journal = json.loads((home/'.local/state/dotifails/backups'/receipt['last_backup']/'journal.json').read_text())
        self.assertEqual(journal['status'], 'complete')

    def test_dependency_failure_stops_before_upgrade_or_configuration_changes(self):
        home = self.root / 'home'
        def fail_resolution(command, env=None):
            if '--simulate' in command:
                raise RuntimeError('Synthetic unsatisfied dependency')
        with patch.dict(os.environ, {'HOME': str(home)}), \
             patch.object(backend, 'host_supported', return_value={'ID': 'debian', 'VERSION_ID': '13'}), \
             patch.object(backend.os, 'geteuid', return_value=1000), \
             patch.object(backend, 'run', side_effect=fail_resolution), \
             patch.object(backend, 'upgrade_system') as upgrade, \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                backend.main(['install', '--source', str(SOURCE), '--components', 'terminal', '--upgrade-system'])
        upgrade.assert_not_called()
        self.assertFalse((home/'.config').exists())
        journal = next((home/'.local/state/dotifails/backups').glob('*/journal.json'))
        self.assertEqual(json.loads(journal.read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
