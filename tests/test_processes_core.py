"""Qt-free core of Wysun Processes: /proc sampling, query filters, apps/tree/list views and identity-checked
actions (apps/python/wysun_processes/core)."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_processes.core import actions, sampler, views  # noqa: E402


def write_proc(root, pid, name='app', ppid=1, state='S', utime=0, rss_pages=100, threads=1, nice=0, start=1000,
               uid=None, cgroup='0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-firefox-123.scope\n',
               cmdline=None):
    folder = Path(root) / str(pid)
    folder.mkdir(parents=True, exist_ok=True)
    fields = [state, str(ppid)] + ['0'] * 9 + [str(utime), '0'] + ['0'] * 3 + [str(nice), str(threads), '0',
                                                                             str(start), '0', str(rss_pages)]
    (folder / 'stat').write_text(f'{pid} ({name}) ' + ' '.join(fields) + '\n')
    (folder / 'cgroup').write_text(cgroup)
    (folder / 'io').write_text('read_bytes: 0\nwrite_bytes: 0\n')
    if cmdline is not None:
        (folder / 'cmdline').write_bytes(cmdline)
    return folder


def row(pid, name, app, cpu=0.0, mem=0, ppid=1, user='nicolas', uid=1000, state='S', gpu=None, ema=None):
    return dict(pid=pid, name=name, app=app, cpu=cpu, mem=mem, ppid=ppid, user=user, uid=uid, state=state,
                gpu=gpu, io=0, threads=1, start=str(pid), key=(pid, str(pid)), ema=ema or {})


class QueryTests(unittest.TestCase):
    def test_query_filters(self):
        q = views.parse_query('cpu>5 mem>1g user:root fire')
        self.assertEqual(q.tokens, ['cpu>5', 'mem>1g', 'user:root'])
        hit = row(1, 'firefox', 'Firefox', cpu=6, mem=2 * 1024 ** 3, user='root')
        self.assertTrue(q.match(hit))
        self.assertFalse(q.match(dict(hit, cpu=4)))
        self.assertFalse(q.match(dict(hit, mem=512 * 1024 ** 2)))
        self.assertFalse(q.match(dict(hit, user='nicolas')))
        self.assertFalse(q.match(dict(hit, name='kitty', app='Kitty')))

    def test_state_aliases(self):
        running = row(1, 'btop', 'Kitty', state='R')
        for text in ('state:running', 'state:ejecutando', 'state:r'):
            self.assertTrue(views.parse_query(text).match(running), text)
        self.assertFalse(views.parse_query('state:sleeping').match(running))

    def test_gpu_and_app_filters(self):
        r = row(1, 'firefox (GPU Process)', 'Firefox', gpu=12)
        self.assertTrue(views.parse_query('gpu>10 app:fire').match(r))
        self.assertFalse(views.parse_query('gpu>20').match(r))
        self.assertFalse(views.parse_query('gpu>1').match(dict(r, gpu=None)))


class ViewTests(unittest.TestCase):
    def rows(self):
        return [row(10, 'firefox', 'Firefox', cpu=5), row(11, 'Web Content', 'Firefox', cpu=3, ppid=10),
                row(20, 'kitty', 'Kitty', cpu=1)]

    def test_build_apps_groups(self):
        out, matched = views.build(self.rows(), 'apps', views.parse_query(''), 'cpu', True, set(), False, 1000)
        self.assertEqual(matched, 3)
        self.assertEqual([r['key'] for r in out], ['g:Firefox', 'p:20:20'])
        self.assertEqual(out[0]['kids'], 2)
        self.assertAlmostEqual(out[0]['cpu'], 8)
        out, _ = views.build(self.rows(), 'apps', views.parse_query(''), 'cpu', True, {'g:Firefox'}, False, 1000)
        self.assertEqual([r['key'] for r in out], ['g:Firefox', 'p:10:10', 'p:11:11', 'p:20:20'])
        self.assertEqual(out[1]['depth'], 1)

    def test_search_opens_groups(self):
        out, _ = views.build(self.rows(), 'apps', views.parse_query('web'), 'cpu', True, set(), False, 1000)
        self.assertEqual([r['key'] for r in out], ['g:Firefox', 'p:11:11'])

    def test_build_tree_keeps_ancestors(self):
        rows = [row(1, 'systemd', 'Sistema'), row(5, 'Hyprland', 'Hyprland', ppid=1),
                row(9, 'kitty', 'Kitty', ppid=5), row(12, 'btop', 'Kitty', ppid=9)]
        out, matched = views.build(rows, 'tree', views.parse_query('btop'), 'cpu', True, set(), False, 1000)
        self.assertEqual(matched, 1)
        self.assertEqual([r['pid'] for r in out], [1, 5, 9, 12])
        self.assertEqual([r['depth'] for r in out], [0, 1, 2, 3])

    def test_tree_collapses_unless_expanded(self):
        rows = [row(1, 'systemd', 'Sistema'), row(5, 'Hyprland', 'Hyprland', ppid=1)]
        out, _ = views.build(rows, 'tree', views.parse_query(''), 'cpu', True, set(), False, 1000)
        self.assertEqual([r['pid'] for r in out], [1])
        self.assertEqual(out[0]['kids'], 1)
        out, _ = views.build(rows, 'tree', views.parse_query(''), 'cpu', True, {'p:1:1'}, False, 1000)
        self.assertEqual([r['pid'] for r in out], [1, 5])

    def test_sort_uses_ema(self):
        rows = [row(1, 'a', 'A', cpu=50, ema={'cpu': 1}), row(2, 'b', 'B', cpu=2, ema={'cpu': 9})]
        out, _ = views.build(rows, 'list', views.parse_query(''), 'cpu', True, set(), False, 1000)
        self.assertEqual([r['pid'] for r in out], [2, 1])

    def test_mine_filters_other_users(self):
        rows = [row(1, 'a', 'A', uid=0, user='root'), row(2, 'b', 'B')]
        out, matched = views.build(rows, 'list', views.parse_query(''), 'cpu', True, set(), True, 1000)
        self.assertEqual(([r['pid'] for r in out], matched), ([2], 1))


class SamplerTests(unittest.TestCase):
    def test_application_group(self):
        cg = '0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-firefox-1234.scope\n'
        self.assertEqual(sampler.application_group(cg, 'x'), 'firefox')
        cg = '0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-gnome-org.gnome.Nautilus-99.scope\n'
        self.assertEqual(sampler.application_group(cg, 'x'), 'org.gnome.Nautilus')
        self.assertEqual(sampler.application_group('0::/init.scope\n', 'systemd'), 'systemd')

    def test_command_app_names_a_wysun_module(self):
        self.assertEqual(sampler.command_app(b'python3\0-P\0-m\0wysun_processes\0'), 'wysun-processes')
        self.assertEqual(sampler.command_app(b'/venv/bin/python3\0-m\0wysun_music\0'), 'wysun-music')
        self.assertEqual(sampler.command_app(b'python3\0-m\0http.server\0'), '')
        self.assertEqual(sampler.command_app(b'python3\0script.py\0'), '')
        self.assertEqual(sampler.command_app(b''), '')

    def test_a_wysun_module_without_app_scope_gets_its_desktop_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_proc(tmp, 10, 'python3', cgroup='0::/user.slice/user-1000.slice/session-4.scope\n',
                       cmdline=b'/venv/bin/python3\0-P\0-m\0wysun_processes\0')
            write_proc(tmp, 11, 'python3', cgroup='0::/user.slice/user-1000.slice/session-4.scope\n',
                       cmdline=b'python3\0-m\0http.server\0')
            rows = {r['pid']: r for r in sampler.Sampler(proc_root=tmp).sample().rows}
            self.assertEqual(rows[10]['app'], 'wysun-processes')
            self.assertEqual(rows[11]['app'], 'python3')

    def test_sampler_reads_self(self):
        snap = sampler.Sampler().sample()
        mine = [r for r in snap.rows if r['pid'] == os.getpid()]
        self.assertEqual(len(mine), 1)
        self.assertIn('app', mine[0])
        self.assertEqual(mine[0]['key'][0], os.getpid())
        self.assertGreater(snap.system['total_memory'], 0)
        self.assertEqual(len(snap.system['cores']), os.cpu_count())

    def test_sampler_survives_vanishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_proc(tmp, 10, 'ok')
            broken = Path(tmp) / '11'
            broken.mkdir()
            (Path(tmp) / 'self').mkdir()
            snap = sampler.Sampler(proc_root=tmp).sample()
            self.assertEqual([r['pid'] for r in snap.rows], [10])
            self.assertEqual(snap.rows[0]['app'], 'firefox')

    def test_cpu_and_ema_between_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_proc(tmp, 10, 'busy', utime=0)
            s = sampler.Sampler(proc_root=tmp)
            first = s.sample().rows[0]
            self.assertEqual(first['cpu'], 0)
            time.sleep(0.05)
            write_proc(tmp, 10, 'busy', utime=5)
            second = s.sample().rows[0]
            self.assertGreater(second['cpu'], 0)
            self.assertLess(second['ema']['cpu'], second['cpu'])

    def test_sampler_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            for pid in range(100, 2100):
                write_proc(tmp, pid, f'p{pid}', utime=pid % 7)
            s = sampler.Sampler(proc_root=tmp)
            s.sample()
            began = time.perf_counter()
            s.sample()
            self.assertLess(time.perf_counter() - began, 0.06)


class PortedTests(unittest.TestCase):
    """Cases carried over from the retired shell panel's backend tests."""

    def test_tree_cycle_is_bounded(self):
        rows = [row(1, 'a', 'A', ppid=2), row(2, 'b', 'B', ppid=1)]
        out, _ = views.build(rows, 'tree', views.parse_query('a'), 'cpu', True, set(), False, 1000)
        self.assertLessEqual(len(out), 2)

    def test_drm_shared_clients_are_counted_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            fdinfo = Path(tmp) / '2/fdinfo'
            fdinfo.mkdir(parents=True)
            for fd in ('4', '5'):
                (fdinfo / fd).write_text('drm-pdev: 0000:00:02.0\ndrm-client-id: 7\ndrm-engine-render: 200000000 ns\n')
            s = sampler.Sampler(proc_root=tmp)
            self.assertEqual(s._drm(2, (2, '1')), 200000000)

    def test_protected_session_cannot_change_priority(self):
        from unittest.mock import patch
        protected = dict(pid=1, name='Hyprland', uid=os.getuid(), state='S', start='1')
        with patch.object(actions.guard(), 'checked', return_value=protected), patch.object(os, 'setpriority') as change:
            with self.assertRaises(PermissionError):
                actions.set_priority(sampler.Sampler(proc_root=tempfile.gettempdir()), 'p:1:1', 5)
            change.assert_not_called()

    def test_own_child_priority_and_terminate(self):
        import subprocess
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
        try:
            from wysun_services.process_data import process_record
            key = f"p:{child.pid}:{process_record(child.pid)['start']}"
            s = sampler.Sampler()
            actions.set_priority(s, key, 7)
            self.assertEqual(os.getpriority(os.PRIO_PROCESS, child.pid), 7)
            self.assertEqual(actions.act(s, key, 'terminate'), 1)
            child.wait(timeout=3)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()


class ActionTests(unittest.TestCase):
    def test_act_rejects_reused_pid(self):
        with self.assertRaisesRegex(RuntimeError, 'El PID cambió de proceso'):
            actions.act(sampler.Sampler(), f'p:{os.getpid()}:not-the-start', 'pause')

    def test_priority_range(self):
        with self.assertRaises(ValueError):
            actions.set_priority(sampler.Sampler(), f'p:{os.getpid()}:0', 25)


if __name__ == '__main__':
    unittest.main()
