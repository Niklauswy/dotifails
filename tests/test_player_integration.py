"""Desktop integration of Wysun Player: launchers, desktop entry, default associations, update and restore."""
import configparser
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import media_support as support

support.app()
from PySide6.QtCore import QMimeDatabase  # noqa: E402
from wysun_media.source import kind_of  # noqa: E402

ROOT = support.ROOT
sys.path.insert(0, str(ROOT / 'installer'))
spec = importlib.util.spec_from_file_location('player_integration_installer', ROOT / 'installer/main.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

DESKTOP = ROOT / 'config/.local/share/applications/wysun-player.desktop'


def mimeapps(home):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(Path(home) / '.config/mimeapps.list')
    return parser


class DesktopEntryTests(unittest.TestCase):
    def entry(self):
        parser = configparser.ConfigParser(interpolation=None, delimiters=('=',))
        parser.optionxform = str
        parser.read(DESKTOP)
        return parser['Desktop Entry']

    def test_entry_is_valid_and_visible_name_is_wysun_player(self):
        entry = self.entry()
        self.assertEqual(entry['Name'], 'Wysun Player')
        self.assertEqual(entry['StartupWMClass'], 'wysun-player')
        self.assertEqual(entry['Type'], 'Application')
        if shutil.which('desktop-file-validate'):
            done = subprocess.run(['desktop-file-validate', str(DESKTOP)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_exec_protects_file_names_that_look_like_options(self):
        words = self.entry()['Exec'].split()
        self.assertEqual(words[:2], ['wysun-player', '--'])
        self.assertEqual(words[-1], '%F')

    def test_every_declared_type_is_one_the_player_can_open(self):
        database = QMimeDatabase()
        types = [t for t in self.entry()['MimeType'].split(';') if t]
        self.assertGreater(len(types), 20)
        for name in types:
            mime = database.mimeTypeForName(name)
            self.assertTrue(mime.isValid(), name)
            self.assertTrue(any(kind_of('sample.' + suffix) for suffix in mime.suffixes()), f'{name}: no known extension opens in the player')
        self.assertNotIn('image/svg+xml', types)
        self.assertEqual(len(types), len(set(types)))

    def test_music_does_not_claim_audio_types_so_the_player_can_own_them(self):
        music = (ROOT / 'config/.local/share/applications/orbit-music.desktop').read_text()
        self.assertNotIn('MimeType', music)


class LaunchRouteTests(unittest.TestCase):
    def test_wysun_player_and_image_commands_reach_the_player_launcher(self):
        with tempfile.TemporaryDirectory() as root:
            bin_dir = Path(root)
            shutil.copy(ROOT / 'bin/wysun', bin_dir / 'wysun')
            stub = bin_dir / 'wysun-player'
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            stub.chmod(0o755)
            for command in ('player', 'image'):
                done = subprocess.run([sys.executable, str(bin_dir / 'wysun'), command, '--paused', '--', '-odd.png', 'b.mp4'],
                                      capture_output=True, text=True, timeout=20)
                self.assertEqual(done.stdout.split(), ['--paused', '--', '-odd.png', 'b.mp4'], command)

    def test_launcher_runs_the_installed_application(self):
        text = (ROOT / 'bin/wysun-player').read_text()
        self.assertIn('exec /usr/bin/python3 "$HOME/.local/share/orbit/app/player_app.py" "$@"', text)
        self.assertTrue(os.access(ROOT / 'bin/wysun-player', os.X_OK))


class InstallerTests(unittest.TestCase):
    def deployment(self, home):
        deployment = installer.Deployment(home, ROOT)
        deployment.begin()
        self.addCleanup(deployment.lock.close)
        return deployment

    def home(self, mime=None):
        directory = tempfile.TemporaryDirectory(prefix='wysun-player-home-')
        self.addCleanup(directory.cleanup)
        home = Path(directory.name)
        if mime:
            (home / '.config').mkdir(parents=True)
            (home / '.config/mimeapps.list').write_text(mime)
        return home

    def test_full_installation_makes_the_player_the_default(self):
        home = self.home()
        deployment = self.deployment(home)
        deployment.configure_files(player=True)
        deployment.configure_wysun()                                  # the desktop entry xdg-mime looks the default up in
        deployment.finish()
        parser = mimeapps(home)
        for name in deployment.player_mime_types():
            self.assertEqual(parser['Default Applications'][name], 'wysun-player.desktop;', name)
            self.assertIn('wysun-player.desktop', parser['Added Associations'][name])
        self.assertEqual(parser['Default Applications']['inode/directory'], 'orbit-files.desktop;', 'Files keeps folders')
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_DATA_HOME=str(home / '.local/share'),
                   XDG_CURRENT_DESKTOP='Wysun:Hyprland', PATH=str(home / '.local/bin') + ':/usr/bin:/bin')
        for name in ('image/png', 'video/mp4', 'audio/flac'):
            self.assertEqual(subprocess.check_output(['xdg-mime', 'query', 'default', name], env=env, text=True).strip(), 'wysun-player.desktop')

    def test_previous_choices_stay_as_alternatives_and_unrelated_ones_are_untouched(self):
        home = self.home('[Default Applications]\nimage/png=viewnior.desktop;\napplication/pdf=reader.desktop;\n'
                         '[Added Associations]\nimage/png=gimp.desktop;\n[Removed Associations]\nvideo/mp4=wysun-player.desktop;other.desktop;\n')
        deployment = self.deployment(home)
        deployment.configure_files(player=True)
        deployment.finish()
        parser = mimeapps(home)
        self.assertEqual(parser['Default Applications']['image/png'], 'wysun-player.desktop;')
        self.assertEqual(parser['Added Associations']['image/png'], 'wysun-player.desktop;viewnior.desktop;gimp.desktop;')
        self.assertEqual(parser['Default Applications']['application/pdf'], 'reader.desktop;')
        self.assertEqual(parser['Removed Associations']['video/mp4'], 'other.desktop;')

    def test_updating_wysun_alone_never_changes_what_files_open_with(self):
        home = self.home('[Default Applications]\nimage/png=viewnior.desktop;\n')
        deployment = self.deployment(home)
        deployment.configure_files()                                  # what an --orbit-only update runs on its own
        deployment.configure_wysun()
        deployment.finish()
        parser = mimeapps(home)
        self.assertEqual(parser['Default Applications']['image/png'], 'viewnior.desktop;')
        self.assertNotIn('video/mp4', parser['Default Applications'])
        self.assertTrue((home / '.local/bin/wysun-player').is_file())
        self.assertTrue(os.access(home / '.local/bin/wysun-player', os.X_OK))
        self.assertTrue((home / '.local/share/applications/wysun-player.desktop').is_file())

    def test_associating_twice_changes_nothing(self):
        home = self.home()
        first = self.deployment(home)
        first.configure_files(player=True)
        first.finish()
        first.lock.close()
        second = self.deployment(home)
        second.configure_files(player=True)
        self.assertEqual([op for op in second.journal['operations'] if op['path'] == '.config/mimeapps.list'], [])

    def test_restore_brings_back_the_previous_defaults_and_keeps_later_edits(self):
        original = '[Default Applications]\nimage/png=viewnior.desktop;\n'
        home = self.home(original)
        deployment = self.deployment(home)
        deployment.configure_files(player=True)
        deployment.finish()
        identifier = deployment.journal['id']
        deployment.lock.close()
        edited = (home / '.config/mimeapps.list').read_text() + '[Added Associations]\ntext/plain=mine.desktop;\n'
        (home / '.config/mimeapps.list').write_text(edited)
        installer.restore(home, identifier)
        self.assertEqual((home / '.config/mimeapps.list').read_text(), original)
        rescued = next((home / '.local/state/dotifails/backups' / identifier / 'changes-before-restore').rglob('mimeapps.list'))
        self.assertEqual(rescued.read_text(), edited, 'a change made after installing is rescued, not lost')

    def test_packages_for_opengl_are_declared_for_every_desktop_component(self):
        import json
        packages = json.loads((ROOT / 'manifests/packages.json').read_text())['components']
        for component in ('desktop', 'wayland'):
            for name in ('python3-pyside6.qtopengl', 'python3-pyside6.qtopenglwidgets'):
                self.assertIn(name, packages[component], (component, name))


if __name__ == '__main__':
    unittest.main()
