"""LANShare: activity, idle shutdown, the status file the bar reads, and --detener."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))

from wysun_lanshare import status  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'


class ActivityTests(unittest.TestCase):
    def test_idle_deadline(self):
        clock = Clock()
        act = status.Activity(600, clock)
        self.assertEqual(act.deadline(), 1600)
        clock.now = 1599
        self.assertFalse(act.expired())
        clock.now = 1601
        self.assertTrue(act.expired())

    def test_touch_moves_the_deadline(self):
        clock = Clock()
        act = status.Activity(600, clock)
        clock.now = 1500
        before = act.version
        act.touch('10.0.0.5', IPHONE)
        self.assertGreater(act.version, before)
        self.assertEqual(act.deadline(), 2100)
        self.assertEqual(act.clients(), [{'ip': '10.0.0.5', 'device': 'iPhone', 'seen': 1500}])
        clock.now = 1500 + 301
        self.assertEqual(act.clients(), [])

    def test_transfer_keeps_it_alive(self):
        clock = Clock()
        act = status.Activity(600, clock)
        tid = act.begin('10.0.0.5', IPHONE, 'Expo final.mp4', 1000, 'down')
        act.advance(tid, 400)
        clock.now = 5000
        self.assertFalse(act.expired())
        self.assertEqual(act.transfers(), [{'ip': '10.0.0.5', 'device': 'iPhone', 'name': 'Expo final.mp4',
                                            'done': 400, 'total': 1000, 'direction': 'down'}])
        act.end(tid)
        self.assertEqual(act.deadline(), 5600)
        self.assertFalse(act.expired())
        clock.now = 5601
        self.assertTrue(act.expired())

    def test_no_limit(self):
        act = status.Activity(None, Clock())
        self.assertIsNone(act.deadline())
        self.assertFalse(act.expired())

    def test_devices(self):
        self.assertEqual(status.device_of(IPHONE), 'iPhone')
        self.assertEqual(status.device_of('Mozilla/5.0 (Linux; Android 14; Pixel 8)'), 'Android')
        self.assertEqual(status.device_of('Mozilla/5.0 (Windows NT 10.0; Win64; x64)'), 'Windows')
        self.assertEqual(status.device_of('Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)'), 'Mac')
        self.assertEqual(status.device_of('Mozilla/5.0 (X11; Linux x86_64)'), 'Linux')
        self.assertEqual(status.device_of(''), 'Navegador')


class StatusFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_and_remove(self):
        clock = Clock()
        act = status.Activity(600, clock)
        info = {'paths': ['/x/Videos'], 'title': 'Videos', 'addresses': ['http://10.0.0.2:8000'],
                'port': 8000, 'password': 'k3m9rt', 'uploads': False}
        sf = status.StatusFile(4242, info, base=self.env, clock=clock)
        sf.write(act, force=True)
        path = Path(self.tmp.name) / 'wysun-lanshare' / '4242.json'
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        data = json.loads(path.read_text())
        for key in ('pid', 'paths', 'title', 'addresses', 'port', 'password', 'uploads', 'clients', 'transfers',
                    'shutdownAt', 'updated'):
            self.assertIn(key, data)
        self.assertEqual((data['pid'], data['shutdownAt'], data['updated']), (4242, 1600, 1000))
        sf.remove()
        self.assertFalse(path.exists())

    def test_writes_are_throttled(self):
        clock = Clock()
        act = status.Activity(600, clock)
        sf = status.StatusFile(1, {}, base=self.env, clock=clock)
        self.assertTrue(sf.write(act))
        act.touch('10.0.0.5', '')
        self.assertFalse(sf.write(act))
        clock.now += 1.1
        self.assertTrue(sf.write(act))
        self.assertFalse(sf.write(act))           # nothing changed …
        clock.now += status.HEARTBEAT + 0.1
        self.assertTrue(sf.write(act))            # … until the heartbeat

    def test_prune_removes_dead_servers(self):
        directory = status.status_dir(self.env)
        directory.mkdir(parents=True)
        dead = subprocess.Popen([sys.executable, '-c', 'pass'])
        dead.wait()
        (directory / f'{dead.pid}.json').write_text('{}')
        (directory / f'{os.getpid()}.json').write_text('{}')
        status.prune(self.env)
        self.assertEqual(sorted(p.name for p in directory.iterdir()), [f'{os.getpid()}.json'])


class StopTests(unittest.TestCase):
    def test_refuses_other_processes(self):
        self.assertFalse(status.stop(os.getpid()))
        self.assertFalse(status.stop(999_999_999))

    def test_stops_a_lanshare(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)', '-m', 'wysun_lanshare'])
        try:
            time.sleep(0.2)
            self.assertTrue(status.stop(child.pid))
            self.assertEqual(child.wait(5), -15)
        finally:
            child.kill()


if __name__ == '__main__':
    unittest.main()
