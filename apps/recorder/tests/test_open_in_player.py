"""A finished recording opens in Wysun Player (never in a Recorder window), and a missing player never breaks the notice."""
import os
from pathlib import Path
import tempfile
import time
import unittest
import warnings
from unittest import mock

from wysun_recorder import headless


def fake(folder, name, record):
    """An executable that writes its arguments, one per line, to ``record``."""
    path = Path(folder) / name
    path.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{record}"\n')
    path.chmod(0o755)


def wait_for(path, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists() and path.read_text().endswith('\n'):
            return path.read_text().splitlines()
        time.sleep(0.02)
    return None


class OpenInPlayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wysun-open-player-')
        self.addCleanup(self.tmp.cleanup)
        self.enterContext(warnings.catch_warnings())
        warnings.simplefilter('ignore', ResourceWarning)      # the launched helper is detached on purpose
        root = Path(self.tmp.name)
        self.bin = root / 'bin'
        self.bin.mkdir()
        self.home = root / 'home'
        self.home.mkdir()
        self.record = root / 'argv.txt'
        self.video = root / 'out.mp4'
        patcher = mock.patch.dict(os.environ, {'PATH': str(self.bin), 'HOME': str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_launches_wysun_player_with_the_video(self):
        fake(self.bin, 'wysun', self.record)
        self.assertTrue(headless.open_in_player(self.video))
        self.assertEqual(wait_for(self.record), ['player', '--', str(self.video)])

    def test_the_player_does_not_inherit_the_releases_code_or_qml(self):
        """The Recorder's launcher points PYTHONPATH and WYSUN_QML_LIB at its own release: the Player must not see them."""
        path = Path(self.bin) / 'wysun'
        path.write_text(f'#!/bin/sh\nprintf "%s\\n" "${{WYSUN_QML_LIB-unset}}|${{PYTHONPATH-unset}}" > "{self.record}"\n')
        path.chmod(0o755)
        with mock.patch.dict(os.environ, {'WYSUN_QML_LIB': '/release/qml', 'PYTHONPATH': '/release'}):
            self.assertTrue(headless.open_in_player(self.video))
        self.assertEqual(wait_for(self.record), ['unset|unset'])

    def test_falls_back_to_xdg_open_when_wysun_is_missing(self):
        fake(self.bin, 'xdg-open', self.record)
        self.assertTrue(headless.open_in_player(self.video))
        self.assertEqual(wait_for(self.record), [str(self.video)])

    def test_returns_false_when_nothing_can_open_it(self):
        self.assertFalse(headless.open_in_player(self.video))

    def test_notify_when_ready_opens_the_player_and_not_the_recorder(self):
        ready = {'state': 'ready', 'output': str(self.video)}
        with mock.patch('wysun_recorder.finalize.status', return_value=ready), \
                mock.patch('subprocess.run') as run, \
                mock.patch.object(headless, 'open_in_player', return_value=True) as opened, \
                mock.patch('subprocess.Popen') as popen:
            result = headless.notify_when_ready(self.tmp.name)
        self.assertEqual(result, str(self.video))
        notice = run.call_args.args[0]
        self.assertEqual((notice[0], 'Grabación guardada' in notice, str(self.video) in notice), ('notify-send', True, True))
        opened.assert_called_once_with(str(self.video))
        popen.assert_not_called()                  # nothing else is launched: no Recorder window

    def test_a_missing_player_does_not_break_the_notice(self):
        ready = {'state': 'ready', 'output': str(self.video)}
        with mock.patch('wysun_recorder.finalize.status', return_value=ready), mock.patch('subprocess.run'), \
                mock.patch.object(headless, 'open_in_player', return_value=False):
            self.assertEqual(headless.notify_when_ready(self.tmp.name), str(self.video))


if __name__ == '__main__':
    unittest.main()
