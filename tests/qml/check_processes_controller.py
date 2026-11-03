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
        self.located, self.focused, self.thumb_calls = [], [], []

    def windows(self):
        return [dict(address='0xaa', pid=10, app_id='firefox', title='GitHub', workspace=1, active=False, monitor=0,
                     size=[1600, 900]),
                dict(address='0xbb', pid=20, app_id='kitty', title='btop', workspace=2, active=True, monitor=0,
                     size=[700, 1200]),
                dict(address='0xcc', pid=999, app_id='brave-browser', title='Claude Code Docs', workspace=7,
                     active=False, monitor=1, size=[1920, 1080])]

    def monitors(self):
        # Not in x order: the Philips panel is first in physical space, but is id 0.
        return [dict(id=1, name='DP-1', make='LG Electronics', model='LG ULTRAGEAR', x=1920, y=0, activeWorkspace=7),
                dict(id=0, name='DP-2', make='Philips Consumer Electronics Company', model='PHL 271E1', x=0, y=0,
                     activeWorkspace=2)]

    def active_workspace(self):
        return 2

    def focus(self, address):
        self.focused.append(address)
        return True

    def close(self, address):
        return True

    def thumbnails(self, addresses, width=None):
        self.thumb_calls.append((list(addresses), width))
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
        cls.c = ProcessesController(sampler=Sampler(proc_root=proc), hypr=cls.hypr, services=None, auto=False)
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

    def test_apps_by_monitor_and_workspace(self):
        self.c.setPage('apps')
        columns = self.c.property('monitorColumns')
        self.assertEqual([c['connector'] for c in columns], ['DP-2', 'DP-1'])
        self.assertEqual([c['label'] for c in columns], ['Philips', 'LG'])
        self.assertEqual([c['side'] for c in columns], ['izquierda', 'derecha'])
        left, right = columns
        self.assertEqual([s['id'] for s in left['workspaces']], [1, 2])
        self.assertTrue(left['workspaces'][1]['current'])
        self.assertEqual(left['workspaces'][0]['windows'][0]['app'], 'firefox')
        self.assertEqual([s['id'] for s in right['workspaces']], [7])
        self.assertEqual(right['workspaces'][0]['windows'][0]['app'], 'brave-browser')
        self.assertIn('firefox', self.c.property('stats'))

    def test_a_windowless_scope_of_a_windowed_program_gets_segundo_plano(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_proc(tmp, 999, 'brave', cgroup='0::/user.slice/user-1000.slice/user@1000.service/'
                                         'app-org.chromium.Chromium-999.scope\n', rss_pages=1000)
            write_proc(tmp, 998, 'brave', cgroup='0::/user.slice/user-1000.slice/user@1000.service/'
                                         'app-brave-998.scope\n', rss_pages=2000)
            from wysun_processes.core.sampler import Sampler
            from wysun_processes.quick.controller import ProcessesController
            c = ProcessesController(sampler=Sampler(proc_root=tmp), hypr=FakeHypr(), auto=False)
            c.tick()
            c.tick()
            c.setPage('apps')
            groups = {app['app']: app for app in c.property('windowless')}
            self.assertIn('brave', groups)
            self.assertEqual(groups['brave']['name'], 'Brave · segundo plano')
            self.assertNotIn('org.chromium.Chromium', groups)      # the window owner is not windowless
            c.close()

    def test_rows_and_the_sheet_capture_at_their_own_width(self):
        class PathsHypr(FakeHypr):
            def __init__(self, folder):
                super().__init__()
                self.folder = Path(folder)

            def thumbnails(self, addresses, width=None):
                self.thumb_calls.append((list(addresses), width))
                out = {}
                for address in addresses:
                    path = self.folder / f'{address}@{width}.png'
                    path.write_bytes(b'png')
                    out[address] = str(path)
                return out

        with tempfile.TemporaryDirectory() as tmp:
            from wysun_processes.core.sampler import Sampler
            from wysun_processes.quick.controller import ProcessesController
            hypr = PathsHypr(tmp)
            c = ProcessesController(sampler=Sampler(proc_root=self.tmp.name), hypr=hypr, auto=False)
            c.tick()
            c.tick()
            c.setPage('apps')
            c.setListThumbWidth(320)
            c._refresh_windows()
            self.assertEqual(hypr.thumb_calls[-1], (['0xaa', '0xbb', '0xcc'], 320))
            row = c.property('monitorColumns')[0]['workspaces'][0]['windows'][0]
            self.assertIn('@320.png', row['thumb'])

            c.requestPreview('0xaa', 823)                 # bucketed to 832 device px, fetched on its own lane
            self.assertEqual(hypr.thumb_calls[-1], (['0xaa'], 832))
            self.assertEqual(c.property('previewAddress'), '0xaa')
            self.assertEqual(c.property('previewWidth'), 832)
            self.assertIn('@832.png', c.property('previewThumb'))
            # Until the sheet's own capture exists it shows its placeholder: never the row's small image stretched.
            saved = c._thumb_paths.pop(('0xaa', 832))
            self.assertEqual(c.property('previewThumb'), '')
            c._thumb_paths[('0xaa', 832)] = saved
            # The row keeps its small capture: the large one never replaced it (nor the other way around).
            self.assertIn('@320.png', c.property('monitorColumns')[0]['workspaces'][0]['windows'][0]['thumb'])

            c.releasePreview('0xaa', 823)
            self.assertEqual(c.property('previewAddress'), '')
            self.assertEqual(c.property('previewThumb'), '')
            c.close()

    def test_locate_without_shell_says_so(self):
        messages = []
        self.c.message.connect(lambda text, undo: messages.append(text))
        self.c.select('g:firefox')
        self.c.locate()
        self.assertEqual(self.hypr.located, ['0xaa'])
        self.assertIn('shell', messages[-1])

    def test_open_context_prefers_the_app_named_like_the_query(self):
        import time
        from wysun_processes.core.sampler import Sampler
        from wysun_processes.quick.controller import ProcessesController
        with tempfile.TemporaryDirectory() as tmp:
            write_proc(tmp, 30, 'brave', cgroup=KITTY.replace('kitty', 'brave'))
            write_proc(tmp, 31, 'brave', ppid=30, cgroup=KITTY.replace('kitty', 'brave'))
            write_proc(tmp, 40, 'brave', cgroup=FIREFOX.replace('firefox', 'chromium'), utime=0)
            write_proc(tmp, 41, 'brave', ppid=40, cgroup=FIREFOX.replace('firefox', 'chromium'), utime=0)
            c = ProcessesController(sampler=Sampler(proc_root=tmp), hypr=FakeHypr(), auto=False)
            c.tick()
            time.sleep(0.05)
            write_proc(tmp, 40, 'brave', cgroup=FIREFOX.replace('firefox', 'chromium'), utime=50)
            c.tick()
            c.openContext('brave')                # chromium is busier, but brave is the app named so
            self.assertEqual(c.property('selectedKey'), 'g:brave')
            c.close()

    def test_keyed_model_notifies_only_the_roles_that_changed(self):
        model = self.c.property('rows')
        signals = []
        model.dataChanged.connect(lambda top, bottom, roles: signals.append((top.row(), bottom.row(), roles)))
        items = [dict(item) for item in model.items()]
        model.replace(items)                          # same content: no notification at all
        self.assertEqual(signals, [])
        changed = [dict(item) for item in items]
        changed[0]['cpu'] = 12345.5
        model.replace(changed)
        self.assertEqual(len(signals), 1)
        top, bottom, roles = signals[0]
        self.assertEqual((top, bottom), (0, 0))
        self.assertEqual(roles, [model.roleFor('cpu')])

    def test_selection_changed_only_when_the_key_changes(self):
        from wysun_processes.core.sampler import Sampler
        from wysun_processes.quick.controller import ProcessesController
        c = ProcessesController(sampler=Sampler(proc_root=self.tmp.name), hypr=FakeHypr(), auto=False)
        c.tick()
        c.tick()
        signals = []
        c.selectionChanged.connect(lambda: signals.append(c.property('selectedKey')))
        c._rebuild()
        self.assertEqual(signals, [])
        other = next(key for key in c.property('rows').keys() if key != c.property('selectedKey'))
        c.select(other)
        self.assertEqual(signals, [other])
        c.close()

    def test_summary_and_stats_emit_only_when_their_content_changes(self):
        from wysun_processes.core.sampler import Sampler, Snapshot
        from wysun_processes.quick.controller import ProcessesController
        c = ProcessesController(sampler=Sampler(proc_root=self.tmp.name), hypr=FakeHypr(), auto=False)
        snap = Snapshot([], dict(cpu=1.0, memory=2, uptime=3))
        counts = {'summary': 0, 'stats': 0}
        c.summaryChanged.connect(lambda: counts.__setitem__('summary', counts['summary'] + 1))
        c.statsChanged.connect(lambda: counts.__setitem__('stats', counts['stats'] + 1))
        c._on_snapshot(snap)
        c._on_snapshot(snap)
        self.assertEqual(counts, {'summary': 1, 'stats': 0})
        c.close()

    def test_a_hidden_window_pauses_the_controller(self):
        from wysun_processes.core.sampler import Sampler
        from wysun_processes.quick.controller import ProcessesController
        c = ProcessesController(sampler=Sampler(proc_root=self.tmp.name), hypr=FakeHypr(), auto=False)
        c.tick()
        c.setWindowVisible(False)
        self.assertTrue(c.property('suspended'))
        c.tick()                                      # a sample while hidden must not rebuild nor notify
        self.assertEqual(len(c.property('rows').keys()), 2)
        c.setWindowVisible(True)
        self.assertFalse(c.property('suspended'))
        c.tick()
        c.close()

    def test_a_wysun_module_process_reads_its_desktop_name(self):
        from wysun_processes.core.sampler import Sampler
        from wysun_processes.quick.controller import ProcessesController

        class FakeCatalog:
            def name(self, app):
                return {'wysun-processes': 'Wysun Processes'}.get(app, app)

            def icon(self, app):
                return ''

            def tint(self, app):
                return ''

            def entry(self, app):
                return None

        with tempfile.TemporaryDirectory() as tmp:
            for pid in (50, 51):
                write_proc(tmp, pid, 'python3', ppid=50 if pid == 51 else 1,
                           cgroup='0::/user.slice/user-1000.slice/session-4.scope\n',
                           cmdline=b'/venv/bin/python3\0-P\0-m\0wysun_processes\0')
            c = ProcessesController(sampler=Sampler(proc_root=tmp), hypr=FakeHypr(), catalog=FakeCatalog(), auto=False)
            c.tick()
            c.tick()
            rows = {row['key']: row for row in c.property('rows').items()}
            self.assertEqual(rows['g:wysun-processes']['title'], 'Wysun Processes')
            c.close()

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
