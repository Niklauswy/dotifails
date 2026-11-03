"""Wysun Processes' Qt bridge (venv Python, offscreen): filtering and selection, confirmation before terminating,
pause with undo, bounded histories and the single instance that hands a query to the open window."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402
from test_processes_core import write_proc  # noqa: E402

FIREFOX = '0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-firefox-1.scope\n'
KITTY = '0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-kitty-2.scope\n'


class FakeHypr:
    def __init__(self):
        self.located, self.focused = [], []

    def windows(self):
        return [dict(address='0xaa', pid=10, app_id='firefox', title='GitHub', workspace=1, active=False, monitor=0),
                dict(address='0xbb', pid=20, app_id='kitty', title='btop', workspace=2, active=True, monitor=0)]

    def active_workspace(self):
        return 2

    def focus(self, address):
        self.focused.append(address)
        return True

    def close(self, address):
        return True

    def thumbnails(self, addresses):
        return {}

    def locate(self, address):
        self.located.append(address)
        return False


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()
        cls.tmp = tempfile.TemporaryDirectory()
        proc = Path(cls.tmp.name)
        write_proc(proc, 10, 'firefox', cgroup=FIREFOX)
        write_proc(proc, 11, 'Web Content', ppid=10, cgroup=FIREFOX)
        write_proc(proc, 20, 'kitty', cgroup=KITTY)
        from wysun_processes.core.sampler import Sampler
        from wysun_processes.quick.controller import ProcessesController
        cls.hypr = FakeHypr()
        cls.c = ProcessesController(sampler=Sampler(proc_root=proc), hypr=cls.hypr, services=None, startup=None,
                                    auto=False)
        cls.c.tick()
        cls.c.tick()

    @classmethod
    def tearDownClass(cls):
        cls.c.close()
        cls.tmp.cleanup()

    def keys(self):
        model = self.c.property('rows')
        return [model.data(model.index(i, 0), model.roleFor('key')) for i in range(model.rowCount())]

    def test_groups_and_query(self):
        self.c.setMode('apps')
        self.c.setQuery('')
        self.assertEqual(sorted(self.keys()), ['g:firefox', 'p:20:1000'])
        self.c.setQuery('web')
        self.assertEqual(self.keys(), ['g:firefox', 'p:11:1000'])
        self.c.setQuery('cpu>=0 kit')
        self.assertEqual(self.c.property('tokens'), ['cpu>=0'])
        self.assertEqual(self.keys(), ['p:20:1000'])
        self.c.removeToken('cpu>=0')
        self.assertEqual(self.c.property('query'), 'kit')
        self.c.setQuery('')

    def test_selection_moves_and_follows_key(self):
        self.c.setMode('list')
        self.c.select(self.keys()[0])
        first = self.c.property('selectedKey')
        self.c.move(1)
        self.assertNotEqual(self.c.property('selectedKey'), first)
        self.c.move(-10)
        self.assertEqual(self.c.property('selectedKey'), self.keys()[0])
        self.assertEqual(self.c.property('selected')['key'], self.keys()[0])

    def test_terminate_asks_first(self):
        self.c.setMode('list')
        self.c.select('p:20:1000')
        asked = []
        self.c.confirmNeeded.connect(lambda action, label, count, nice: asked.append((action, count)))
        self.c.act('terminate')
        self.assertEqual(asked, [('terminate', 1)])

    def test_pause_offers_undo_and_reports_errors(self):
        self.c.select('p:20:1000')
        messages = []
        self.c.message.connect(lambda text, undo: messages.append((text, undo)))
        self.c.act('pause')          # synthetic PID: the identity check refuses it and says so
        self.assertTrue(messages)
        self.assertFalse(messages[-1][1])

    def test_history_is_bounded(self):
        for _ in range(70):
            self.c.tick()
        self.assertEqual(len(self.c.property('systemHistory')['cpu']), 60)
        self.c.select('g:firefox')
        self.assertLessEqual(len(self.c.property('history')['cpu']), 60)

    def test_apps_by_workspace(self):
        apps = self.c.property('workspaces')
        self.assertEqual([w['id'] for w in apps], [1, 2])
        self.assertTrue(apps[1]['current'])
        self.assertEqual(apps[0]['windows'][0]['app'], 'firefox')
        self.assertIn('firefox', self.c.property('stats'))

    def test_locate_without_shell_says_so(self):
        messages = []
        self.c.message.connect(lambda text, undo: messages.append(text))
        self.c.select('g:firefox')
        self.c.locate()
        self.assertEqual(self.hypr.located, ['0xaa'])
        self.assertIn('shell', messages[-1])

    def test_single_instance_forwards_query(self):
        from wysun_processes.quick.instance import Instance
        received = []
        name = os.path.join(self.tmp.name, 'sock')
        first = Instance(name)
        self.assertTrue(first.listen(received.append))
        self.assertTrue(Instance(name).forward('firefox'))
        self.h.wait_for(lambda: received == ['firefox'])
        self.assertEqual(received, ['firefox'])
        first.close()


if __name__ == '__main__':
    unittest.main()
