"""Wysun QML apps name their OS process (`wysun_qml/naming.py`) so `ps` and the process monitor do not read
`python3`. The real `prctl` runs in a child process: the test suites keep their own `comm`."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_qml import naming  # noqa: E402


class NamingTests(unittest.TestCase):
    def test_the_kernel_name_fits_fifteen_bytes(self):
        self.assertEqual(naming.process_name('wysun-processes'), 'wysun-processes')
        self.assertEqual(naming.process_name('wysun-music'), 'wysun-music')
        self.assertEqual(naming.process_name('wysun-processes-extra'), 'wysun-processes')
        self.assertEqual(naming.process_name('a' * 20), 'a' * 15)
        self.assertEqual(len(naming.process_name('ñ' * 20).encode()), 14)     # cut on a character boundary
        self.assertEqual(naming.process_name(''), '')

    def test_prctl_changes_the_child_process_name(self):
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'apps/python')}
        code = ('from wysun_qml import naming; print(naming.set_process_name("wysun-processes")); '
                'print(open("/proc/self/comm").read().strip())')
        done = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.splitlines(), ['wysun-processes', 'wysun-processes'])


if __name__ == '__main__':
    unittest.main()
