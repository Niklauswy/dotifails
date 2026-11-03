"""Opt-in resource alerts of the Wysun resident (wysun_services/process_watch.py): per-app CPU from the cgroups of
app.slice, a notice after N minutes over the threshold, one notice per episode, muting for an hour, memory, the
actions, and no reading at all while disabled. Synthetic cgroup trees and an injected clock only."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_services import process_watch  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Tree:
    def __init__(self, root):
        self.root = Path(root)
        self.usage = {}

    def scope(self, name, usage_usec, memory=100 * 1024 ** 2):
        folder = self.root / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'cpu.stat').write_text(f'usage_usec {usage_usec}\nuser_usec 0\nsystem_usec 0\n')
        (folder / 'memory.current').write_text(str(memory))


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tree = Tree(Path(self.tmp.name) / 'app.slice')
        self.config = Path(self.tmp.name) / 'processes.json'
        self.config.write_text(json.dumps({'alerts': True, 'cpu': 90, 'minutes': 3, 'memory_gb': 0}))
        self.clock = Clock()
        self.sent = []
        self.ran = []
        self.watch = process_watch.ProcessWatch(self.tree.root, self.config, notify=self.notify, clock=self.clock,
                                                run=self.ran.append)
        self.usage = 0

    def tearDown(self):
        self.tmp.cleanup()

    def notify(self, title, body, actions, image=None):
        self.sent.append((title, body, actions))
        return len(self.sent)

    def busy_for(self, seconds, percent=95, name='app-firefox-12.scope'):
        for _ in range(int(seconds // 5)):
            self.clock.now += 5
            self.usage += int(5 * 1e6 * percent / 100)
            self.tree.scope(name, self.usage)
            self.watch.tick()

    def test_disabled_reads_nothing(self):
        self.config.write_text(json.dumps({'alerts': False}))
        self.tree.root.mkdir(parents=True)
        (self.tree.root / 'cpu.stat').mkdir()     # reading it would raise: it must not be read
        self.watch.tick()
        self.assertEqual(self.sent, [])

    def test_notice_after_the_minutes_and_only_once(self):
        self.tree.scope('app-firefox-12.scope', 0)
        self.watch.tick()
        self.busy_for(170)
        self.assertEqual(self.sent, [])
        self.busy_for(20)
        self.assertEqual(len(self.sent), 1)
        title, body, actions = self.sent[0]
        self.assertIn('firefox', title.lower())
        self.assertIn('3 min', title)
        self.assertEqual([a[0] for a in actions], ['ver', 'terminar', 'silenciar'])
        self.busy_for(120)
        self.assertEqual(len(self.sent), 1)

    def test_a_dip_restarts_the_count(self):
        self.tree.scope('app-firefox-12.scope', 0)
        self.watch.tick()
        self.busy_for(150)
        self.busy_for(10, percent=5)
        self.busy_for(150)
        self.assertEqual(self.sent, [])

    def test_mute_for_an_hour(self):
        self.tree.scope('app-firefox-12.scope', 0)
        self.watch.tick()
        self.busy_for(190)
        self.watch.action(1, 'silenciar')
        self.busy_for(10, percent=5)
        self.busy_for(600)
        self.assertEqual(len(self.sent), 1)
        self.clock.now += 3600
        self.busy_for(10, percent=5)
        self.busy_for(190)
        self.assertEqual(len(self.sent), 2)

    def test_actions(self):
        self.tree.scope('app-firefox-12.scope', 0)
        self.watch.tick()
        self.busy_for(190)
        self.watch.action(1, 'ver')
        self.assertEqual(self.ran[-1], ['wysun', 'processes', 'firefox'])
        self.watch.action(1, 'terminar')          # asks once more before stopping the app
        self.assertEqual(self.sent[-1][2][0][0], 'terminar-ya')
        self.watch.action(len(self.sent), 'terminar-ya')
        self.assertEqual(self.ran[-1], ['systemctl', '--user', 'stop', 'app-firefox-12.scope'])

    def test_memory_threshold(self):
        self.config.write_text(json.dumps({'alerts': True, 'cpu': 100, 'minutes': 3, 'memory_gb': 1}))
        self.tree.scope('app-brave-3.scope', 0, memory=2 * 1024 ** 3)
        self.watch.tick()
        self.clock.now += 5
        self.watch.tick()
        self.assertEqual(len(self.sent), 1)
        self.assertIn('2.0 GB', self.sent[0][0])

    def test_unknown_action_and_id_are_ignored(self):
        self.watch.action(99, 'ver')
        self.watch.action(1, 'rm')
        self.assertEqual(self.ran, [])


class NotifierTests(unittest.TestCase):
    def test_gdbus_call_and_id(self):
        import subprocess
        from unittest.mock import patch
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '(uint32 42,)\n', '')) as run:
            notifier = process_watch.DbusNotifier.__new__(process_watch.DbusNotifier)
            ident = notifier('Firefox lleva 3 min', 'cuerpo', [('ver', 'Ver')])
        self.assertEqual(ident, 42)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:2], ['gdbus', 'call'])
        self.assertIn('["ver", "Ver"]', argv)
        self.assertIn('Firefox lleva 3 min', argv)


if __name__ == '__main__':
    unittest.main()
