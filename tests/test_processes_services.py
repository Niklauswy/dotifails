"""Wysun Processes: systemd --user services (core/services.py),
with fake runners and temporary homes — nothing touches the real user session."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_processes.core import services  # noqa: E402

UNITS = [
    {'unit': 'pipewire.service', 'load': 'loaded', 'active': 'active', 'sub': 'running', 'description': 'PipeWire'},
    {'unit': 'hypridle.service', 'load': 'loaded', 'active': 'failed', 'sub': 'failed', 'description': 'Idle'},
    {'unit': 'syncthing.service', 'load': 'loaded', 'active': 'inactive', 'sub': 'dead', 'description': 'Sync'},
    {'unit': 'backup.timer', 'load': 'loaded', 'active': 'active', 'sub': 'waiting', 'description': 'Backup'},
    {'unit': 'dev-sda.device', 'load': 'loaded', 'active': 'active', 'sub': 'plugged', 'description': 'disk'},
]
SHOW = """Id=pipewire.service
MemoryCurrent=33554432
CPUUsageNSec=1200000000
TasksCurrent=6
MainPID=1301
UnitFileState=enabled
Result=success
ExecMainStatus=0
ActiveEnterTimestampMonotonic=5000000
InactiveExitTimestampMonotonic=4500000

Id=hypridle.service
MemoryCurrent=[not set]
CPUUsageNSec=[not set]
TasksCurrent=[not set]
MainPID=0
UnitFileState=enabled
Result=exit-code
ExecMainStatus=1
ActiveEnterTimestampMonotonic=0
InactiveExitTimestampMonotonic=0

Id=syncthing.service
MainPID=0
UnitFileState=disabled
Result=success
ExecMainStatus=0

Id=backup.timer
UnitFileState=enabled
Result=success
"""
TIMERS = [{'next': 1793700000000000, 'left': 100, 'last': 1793600000000000, 'passed': 5, 'unit': 'backup.timer',
           'activates': 'backup.service'}]


class Runner:
    def __init__(self, missing=False, timeout=False):
        self.calls, self.missing, self.timeout = [], missing, timeout

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if self.missing:
            raise FileNotFoundError(cmd[0])
        if self.timeout:
            raise subprocess.TimeoutExpired(cmd, kw.get('timeout', 1))
        out = ''
        if 'list-units' in cmd:
            out = json.dumps(UNITS)
        elif 'list-timers' in cmd:
            out = json.dumps(TIMERS)
        elif 'show' in cmd:
            out = SHOW
        elif cmd[0] == 'journalctl':
            out = '\n'.join(json.dumps(e) for e in (
                {'PRIORITY': '6', '__REALTIME_TIMESTAMP': '1793600000000000', 'MESSAGE': 'Started'},
                {'PRIORITY': '3', '__REALTIME_TIMESTAMP': '1793600001000000', 'MESSAGE': 'boom'},
                {'PRIORITY': '4', '__REALTIME_TIMESTAMP': '1793600002000000', 'MESSAGE': [104, 105]}))
        return subprocess.CompletedProcess(cmd, 0, out, '')


class ServicesTests(unittest.TestCase):
    def test_list_parses_json(self):
        units = {u['unit']: u for u in services.Services(run=Runner()).list()}
        self.assertEqual(sorted(units), ['backup.timer', 'hypridle.service', 'pipewire.service', 'syncthing.service'])
        pw = units['pipewire.service']
        self.assertEqual((pw['state'], pw['kind'], pw['enabled'], pw['memory'], pw['tasks'], pw['main_pid']),
                         ('active', 'service', True, 33554432, 6, 1301))
        self.assertEqual(units['hypridle.service']['state'], 'failed')
        self.assertIn('1', units['hypridle.service']['error'])
        self.assertFalse(units['syncthing.service']['enabled'])
        self.assertEqual(units['backup.timer']['kind'], 'timer')
        self.assertEqual(units['backup.timer']['next_us'], 1793700000000000)

    def test_missing_systemctl(self):
        s = services.Services(run=Runner(missing=True))
        self.assertEqual(s.list(), [])
        self.assertFalse(s.available)

    def test_timeout_does_not_raise(self):
        s = services.Services(run=Runner(timeout=True))
        self.assertEqual(s.list(), [])
        self.assertEqual(s.journal('pipewire.service'), [])

    def test_journal_levels(self):
        lines = services.Services(run=Runner()).journal('pipewire.service')
        self.assertEqual([l[0] for l in lines], ['info', 'err', 'warn'])
        self.assertEqual(lines[2][2], 'hi')

    def test_actions_use_user_manager(self):
        runner = Runner()
        services.Services(run=runner).action('pipewire.service', 'restart')
        self.assertEqual(runner.calls[-1][:3], ['systemctl', '--user', 'restart'])
        with self.assertRaises(ValueError):
            services.Services(run=runner).action('pipewire.service', 'mask')


def write_stat(proc, pid, comm, start):
    folder = Path(proc) / str(pid)
    folder.mkdir(parents=True, exist_ok=True)
    fields = ['S', '1'] + ['0'] * 17 + [str(start)] + ['0', '0']
    (folder / 'stat').write_text(f'{pid} ({comm}) ' + ' '.join(fields) + '\n')
    (folder / 'cmdline').write_bytes(comm.encode() + b'\0')


if __name__ == '__main__':
    unittest.main()
