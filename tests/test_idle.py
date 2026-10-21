import json
import os
from pathlib import Path
import runpy
import stat
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
IDLE = ROOT / 'bin/wysun-idle'


class IdlePreferencesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ, XDG_CONFIG_HOME=self.tmp.name + '/config', XDG_RUNTIME_DIR=self.tmp.name, WYSUN_IDLE_LEGACY='0')
        self.module = runpy.run_path(str(IDLE))

    def test_defaults_never_lock_but_lock_before_sleep(self):
        with patch.dict(os.environ, self.env):
            prefs = self.module['load']()
            self.assertEqual(prefs, {'lock_minutes': 0, 'display_off_minutes': 0, 'lock_before_sleep': True})
            self.assertEqual(self.module['swayidle_arguments'](prefs), ['swayidle', '-w', 'before-sleep', 'wysun-lock'])

    def test_timers_and_invalid_values(self):
        with patch.dict(os.environ, self.env):
            self.module['save']({'lock_minutes': 5, 'display_off_minutes': 7, 'lock_before_sleep': False})
            prefs = self.module['load']()
            self.assertEqual((prefs['lock_minutes'], prefs['display_off_minutes'], prefs['lock_before_sleep']), (5, 0, False))
            argv = self.module['swayidle_arguments'](prefs)
            self.assertEqual(argv, ['swayidle', '-w', 'timeout', '300', 'wysun-lock'])
            self.assertIsNone(self.module['swayidle_arguments']({'lock_minutes': 0, 'display_off_minutes': 0, 'lock_before_sleep': False}))
            display = self.module['swayidle_arguments']({'lock_minutes': 0, 'display_off_minutes': 10, 'lock_before_sleep': False})
            self.assertEqual(display[2:4], ['timeout', '600'])
            self.assertIn('resume', display)

    def test_set_validates(self):
        for args, code in ((['set', 'lock_minutes', '7'], 1), (['set', 'lock_before_sleep', 'maybe'], 1), (['set', 'nope', '5'], 2)):
            result = subprocess.run([str(IDLE), *args], env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, code, result.stderr)
        self.assertFalse((Path(self.tmp.name) / 'config/orbit/idle.json').exists())

    def test_run_rebuilds_swayidle_when_preferences_change(self):
        bin_dir = Path(self.tmp.name) / 'bin'
        bin_dir.mkdir()
        log = Path(self.tmp.name) / 'calls'
        fake = bin_dir / 'swayidle'
        fake.write_text('#!/bin/sh\necho "$@" >> "$FAKE_LOG"\nexec sleep 30\n')
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        env = dict(self.env, PATH=f'{bin_dir}:{os.environ["PATH"]}', FAKE_LOG=str(log))
        daemon = subprocess.Popen([str(IDLE), 'run'], env=env)
        try:
            self.wait_for(lambda: log.exists() and len(log.read_text().splitlines()) == 1)
            subprocess.run([str(IDLE), 'set', 'lock_minutes', '15'], env=dict(env, PATH=env['PATH']), check=True, capture_output=True)
            self.wait_for(lambda: len(log.read_text().splitlines()) == 2)
            self.assertEqual(log.read_text().splitlines()[1], '-w timeout 900 wysun-lock before-sleep wysun-lock')
        finally:
            daemon.terminate()
            daemon.wait(timeout=5)
            subprocess.run(['pkill', '-f', 'sleep 30'], check=False)

    def wait_for(self, check, timeout=8):
        end = time.time() + timeout
        while time.time() < end:
            if check():
                return
            time.sleep(0.2)
        self.fail('timed out')


if __name__ == '__main__':
    unittest.main()
