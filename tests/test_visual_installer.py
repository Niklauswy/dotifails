"""Selection isolation, recovery, preflight and native process protocol regressions."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE/'installer'))
import main as backend
from install_events import InstallationCancelled
from install_model import InstallOptions, backups, normalize_components, package_names, preflight


class VisualInstallerBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dotifails-installer-test-')
        self.home = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def install(self, components, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return backend.main(['install', '--source', str(SOURCE), '--target-home', str(self.home),
                                 '--config-only', '--components', components, *args])

    def test_dependencies_and_rejected_incompatible_selections(self):
        self.assertEqual(normalize_components(['editor']), ('terminal', 'editor'))
        with self.assertRaises(ValueError):
            normalize_components([])
        with self.assertRaises(ValueError):
            normalize_components(['typo'])
        with self.assertRaises(ValueError):
            InstallOptions(SOURCE, self.home, ('boot',), config_only=True).validate()
        with self.assertRaises(ValueError):
            InstallOptions(SOURCE, self.home, ('terminal',), extras=('brave',), config_only=True).validate()
        with self.assertRaises(ValueError):
            InstallOptions(SOURCE, Path.home(), ('boot',), boot_components=()).validate()

    def test_plan_never_executes_legacy_boot_install(self):
        with patch.object(backend, 'boot_appearance') as apply:
            with self.assertRaises(ValueError):
                backend.main(['install','--boot-only','--plan'])
            apply.assert_not_called()

    def test_backups_use_creation_time_not_random_id_suffix(self):
        for ident, created in (('20261012T120000Z-zzzzzz','2026-10-12T12:00:00.100000+00:00'),('20261012T120000Z-aaaaaa','2026-10-12T12:00:00.900000+00:00')):
            backend.write(self.home/'.local/state/dotifails/backups'/ident/'journal.json',dict(id=ident,created_at=created,status='complete',operations=[]))
        self.assertTrue(backups(self.home)[0]['id'].endswith('aaaaaa'))

    def test_plan_matches_backend_arguments_and_selected_packages(self):
        options = InstallOptions(SOURCE, components=('terminal',), theme='tokyo', extras=('obsidian',))
        plan = options.summary()
        self.assertEqual(plan['command'], options.argv())
        self.assertIn('flatpak', plan['packages'])
        self.assertIn('zsh', plan['packages'])
        self.assertNotIn('bspwm', plan['packages'])
        self.assertNotIn('plymouth', plan['packages'])
        self.assertNotIn('nvim', plan['artifacts'])
        self.assertEqual(plan['packages'], package_names(SOURCE, ('terminal',), ('obsidian',)))
        boot = InstallOptions(SOURCE, components=('boot',), boot_components=('grub',)).summary()
        self.assertIn('grub-common', boot['packages'])
        self.assertNotIn('plymouth', boot['packages'])
        self.assertNotIn('slick-greeter', boot['packages'])

    def test_installer_only_preserves_application_and_selected_components(self):
        app = self.home/'.local/share/orbit/app/orbit.py'
        app.parent.mkdir(parents=True)
        app.write_text('unchanged app')
        state = self.home/'.local/state/dotifails/installed.json'
        backend.write(state, {'files':{}, 'components':['desktop','terminal'], 'last_selection':['desktop','terminal']})
        with contextlib.redirect_stdout(io.StringIO()):
            code = backend.main(['install','--source',str(SOURCE),'--target-home',str(self.home),'--installer-only'])
        self.assertEqual(code, 0)
        self.assertEqual(app.read_text(), 'unchanged app')
        self.assertEqual(backend.read(state)['last_selection'], ['desktop','terminal'])
        self.assertTrue((self.home/'.local/share/dotifails/installer/gui.py').exists())
        self.assertFalse((self.home/'.config').exists())

    def test_terminal_only_keeps_desktop_editor_private_data_and_profile(self):
        originals = {'.config/nvim/init.lua':'my editor', '.config/other-desktop/wmrc':'my desktop',
                     '.config/dotifails/theme.json':'{"name":"personal"}',
                     '.local/share/orbit/notes/private.md':'private note'}
        for relative, content in originals.items():
            path = self.home/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.assertEqual(self.install('terminal', '--theme', 'tokyo'), 0)
        for relative, content in originals.items():
            self.assertEqual((self.home/relative).read_text(), content)
        self.assertFalse((self.home/'.local/share/orbit/app').exists())
        self.assertFalse((self.home/'.local/share/backgrounds').exists())
        self.assertTrue((self.home/'.config/ghostty/config').is_file())
        self.assertTrue((self.home/'.local/share/applications/dotifails-installer.desktop').is_file())

    def test_repeat_is_idempotent_then_conflict_and_restore_keep_edits(self):
        zsh = self.home/'.zshrc'
        zsh.write_text('original shell')
        self.assertEqual(self.install('terminal'), 0)
        receipt = backend.read(self.home/'.local/state/dotifails/installed.json')
        first = receipt['last_backup']
        self.assertEqual(self.install('terminal'), 0)
        receipt = backend.read(self.home/'.local/state/dotifails/installed.json')
        journal = backend.read(self.home/'.local/state/dotifails/backups'/receipt['last_backup']/'journal.json')
        self.assertEqual(journal['operations'], [])
        zsh.write_text('my edited shell')
        self.assertEqual(self.install('terminal'), 2)
        self.assertEqual(zsh.read_text(), 'my edited shell')
        with contextlib.redirect_stdout(io.StringIO()):
            backend.restore(self.home, first)
        self.assertEqual(zsh.read_text(), 'original shell')
        rescued = self.home/'.local/state/dotifails/backups'/first/'changes-before-restore/.zshrc'
        self.assertEqual(rescued.read_text(), 'my edited shell')

    def test_preflight_detects_incomplete_source_and_symlink_parent(self):
        options = InstallOptions(self.home, self.home, ('terminal',), config_only=True)
        self.assertTrue(any(item['key']=='source' and item['level']=='error' for item in preflight(options)))
        options.source = SOURCE
        (self.home/'.config').symlink_to(SOURCE)
        self.assertTrue(any(item['key']=='paths' and item['level']=='error' for item in preflight(options)))

    def test_cancel_before_start_changes_no_files(self):
        cancel = self.home/'cancel'
        cancel.touch()
        with patch.dict(os.environ, DOTIFAILS_CANCEL_FILE=str(cancel)):
            with self.assertRaises(InstallationCancelled):
                self.install('terminal')
        self.assertFalse((self.home/'.local/state/dotifails').exists())

    def test_cancelled_authorization_is_reported_as_cancelled(self):
        import subprocess
        cancel = self.home/'cancel'
        def cancelled_command(*args, **kwargs):
            cancel.touch()
            raise subprocess.CalledProcessError(1, args[0])
        with patch.dict(os.environ, DOTIFAILS_CANCEL_FILE=str(cancel)), patch.object(backend.subprocess, 'run', cancelled_command):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(InstallationCancelled):
                backend.run(['sudo', 'true'])

    def test_cancel_after_a_durable_operation_keeps_recoverable_journal(self):
        cancel = self.home/'cancel'
        original = backend.Deployment.deploy
        def stop_after_one(deployment, source, relative):
            original(deployment, source, relative)
            if deployment.journal['operations']:
                cancel.touch()
        with patch.dict(os.environ, DOTIFAILS_CANCEL_FILE=str(cancel)), patch.object(backend.Deployment, 'deploy', stop_after_one):
            with self.assertRaises(InstallationCancelled):
                self.install('terminal')
        journal_path = next((self.home/'.local/state/dotifails/backups').glob('*/journal.json'))
        journal = backend.read(journal_path)
        self.assertEqual(journal['status'], 'cancelled')
        self.assertGreater(len(journal['operations']), 0)
        with contextlib.redirect_stdout(io.StringIO()):
            backend.restore(self.home, journal['id'])
        self.assertEqual(backend.read(journal_path)['status'], 'restored')


if __name__ == '__main__':
    unittest.main()
