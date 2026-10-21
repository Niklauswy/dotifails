"""Process module ordering, aggregation and safe actions, independent of a desktop."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('process_widget', ROOT/'apps/shell/modules/processes/backend.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


def row(pid, ppid=0, name='app', cpu=1, memory=100):
    return dict(pid=pid, ppid=ppid, name=name, app=name, uid=os.getuid(), cpu=cpu, memory=memory,
                read_rate=None, write_rate=None, gpu=None, threads=1, nice=0, start='1', user='test', state='S')


class ProcessWidgetTests(unittest.TestCase):
    def test_app_totals_and_collapse(self):
        rows = [row(2, name='browser', cpu=3), row(3, name='browser', cpu=4), row(4, name='editor')]
        result, count = backend.view(rows, dict(mode='apps', sort='cpu', collapsed=['browser']))
        self.assertEqual(count, 3)
        self.assertEqual(result[0]['name'], 'browser')
        self.assertEqual(result[0]['cpu'], 7)
        self.assertEqual(result[0]['memory'], 200)
        self.assertIsNone(result[0]['gpu'])
        self.assertEqual([r['pid'] for r in result], [0, 0, 4])

    def test_tree_search_keeps_ancestors_and_collapse(self):
        rows = [row(1, name='parent'), row(2, 1, name='child'), row(3, 2, name='match')]
        result, count = backend.view(rows, dict(mode='tree', query='match'))
        self.assertEqual(count, 1)
        self.assertEqual([r['depth'] for r in result], [0, 1, 2])
        result, _ = backend.view(rows, dict(mode='tree', collapsed=[1]))
        self.assertEqual([r['pid'] for r in result], [1])

    def test_sort_directions_and_unavailable_io(self):
        rows = [row(2, cpu=1), row(3, cpu=5)]
        self.assertEqual(backend.view(rows, dict(sort='cpu', descending=False))[0][0]['pid'], 2)
        self.assertEqual(backend.view(rows, dict(sort='cpu', descending=True))[0][0]['pid'], 3)
        self.assertEqual(len(backend.view(rows, dict(sort='read_rate'))[0]), 2)

    def test_tree_cycle_is_bounded(self):
        result, _ = backend.view([row(1, 2), row(2, 1)], dict(mode='tree'))
        self.assertEqual(len(result), 2)

    def test_priority_rejects_reused_identity_without_syscall(self):
        with patch.object(backend.Processes, 'checked', side_effect=RuntimeError('stale')), patch.object(os, 'setpriority') as change:
            with self.assertRaises(RuntimeError):
                backend.action(dict(row=row(42), action='priority', nice=5))
            change.assert_not_called()

    def test_protected_session_cannot_change_priority(self):
        protected = row(1, name='Hyprland')
        with patch.object(backend.Processes, 'checked', return_value=protected), patch.object(os, 'setpriority') as change:
            with self.assertRaises(PermissionError):
                backend.action(dict(row=protected, action='priority', nice=5))
            change.assert_not_called()

    def test_own_synthetic_child_priority_and_terminate(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
        try:
            from process_data import process_record
            identity = process_record(child.pid)
            backend.action(dict(row=identity, action='priority', nice=7))
            self.assertEqual(os.getpriority(os.PRIO_PROCESS, child.pid), 7)
            backend.action(dict(row=identity, action='terminate'))
            child.wait(timeout=3)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
