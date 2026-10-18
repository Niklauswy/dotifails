"""Regression checks for restarts, unplug/replug and legacy duplicate desktops."""
import copy
import json
import unittest
from unittest.mock import patch

from display_workspaces import reconcile, workspace_layout
from settings_runtime import restore_workspaces


def output(name, x=0, primary=False):
    return dict(name=name, connected=True, enabled=True, x=x, primary=primary)


OUTPUTS = [output('eDP-1'), output('DP-2', 1920, True), output('DP-1', 3840)]


def leaf(number):
    return dict(id=number, client={'className': 'Test'}, firstChild=None, secondChild=None)


def window_ids(node):
    if not node:
        return set()
    return ({node['id']} if node.get('client') else set()) | window_ids(node.get('firstChild')) | window_ids(node.get('secondChild'))


class WM:
    """Stateful IPC fixture that refuses deletion of an occupied/last desktop."""
    def __init__(self, groups, focused='1'):
        self.calls = []
        self.serial = 100
        self.state = {'monitors': []}
        for name, desktops in groups:
            monitor = {'id': self.allocate(), 'name': name, 'desktops': []}
            for label, root in desktops:
                monitor['desktops'].append(self.desktop(label, root))
            monitor['focusedDesktopId'] = monitor['desktops'][0]['id']
            self.state['monitors'].append(monitor)
        self.state['focusedMonitorId'] = self.state['monitors'][0]['id']
        self.focus(self.find_desktop(focused))

    def allocate(self):
        self.serial += 1
        return self.serial

    def desktop(self, name, root=None):
        return dict(id=self.allocate(), name=name, root=copy.deepcopy(root), focusedNodeId=next(iter(window_ids(root)), 0))

    def all_desktops(self):
        return [d for m in self.state['monitors'] for d in m['desktops']]

    def find_desktop(self, selector):
        return next(d for d in self.all_desktops() if d['id'] == selector or d['name'] == selector)

    def find_monitor(self, selector):
        return next(m for m in self.state['monitors'] if m['id'] == selector or m['name'] == selector)

    def owner(self, desktop):
        return next(m for m in self.state['monitors'] if desktop in m['desktops'])

    def focus(self, desktop):
        m = self.owner(desktop)
        m['focusedDesktopId'] = desktop['id']
        self.state['focusedMonitorId'] = m['id']

    def windows(self):
        return set().union(*(window_ids(d['root']) for d in self.all_desktops()))

    def mutation_calls(self):
        return [c for c in self.calls if c != ['bspc', 'wm', '-d']]

    def __call__(self, args):
        self.calls.append(args)
        if args == ['bspc', 'wm', '-d']:
            return json.dumps(self.state)
        if args[:3] == ['bspc', 'wm', '-O']:
            monitors = [self.find_monitor(n) for n in args[3:]]
            assert len(monitors) == len(self.state['monitors'])
            self.state['monitors'] = monitors
            return ''
        kind, selector, action, *values = args[1:]
        selector = int(selector, 16) if selector.startswith('0x') else selector
        if kind == 'monitor':
            m = self.find_monitor(selector)
            if action == '-a':
                m['desktops'].append(self.desktop(values[0]))
            elif action == '-r':
                assert all(d['root'] is None for d in m['desktops'])
                self.state['monitors'].remove(m)
            elif action == '-o':
                assert sorted(values) == sorted(d['name'] for d in m['desktops'])
                m['desktops'] = [next(d for d in m['desktops'] if d['name'] == name) for name in values]
            else:
                raise AssertionError(args)
        elif kind == 'desktop':
            d = self.find_desktop(selector)
            m = self.owner(d)
            if action == '-n':
                d['name'] = values[0]
            elif action in ('-m', '-r'):
                assert len(m['desktops']) > 1
                assert action != '-r' or d['root'] is None
                m['desktops'].remove(d)
                if m['focusedDesktopId'] == d['id']:
                    m['focusedDesktopId'] = m['desktops'][0]['id']
                if action == '-m':
                    self.find_monitor(int(values[0], 16))['desktops'].append(d)
            elif action == '-f':
                self.focus(d)
            else:
                raise AssertionError(args)
        elif kind == 'node':
            if action == '-d':
                source = next(d for d in self.all_desktops() if d['root'] and d['root']['id'] == selector)
                dest = self.find_desktop(int(values[0], 16))
                tree = source['root']
                source['root'], source['focusedNodeId'] = None, 0
                dest['root'] = dict(id=self.allocate(), client=None, firstChild=dest['root'], secondChild=tree) if dest['root'] else tree
                dest['focusedNodeId'] = next(iter(window_ids(tree)), 0)
            elif action == '-f':
                dest = next(d for d in self.all_desktops() if selector in window_ids(d['root']))
                dest['focusedNodeId'] = selector
                self.focus(dest)
            else:
                raise AssertionError(args)
        else:
            raise AssertionError(args)
        return ''


def normal_wm():
    return WM([
        ('eDP-1', [('AUX', None)]),
        ('DP-2', [(str(n), leaf(1000 + n) if n in (1, 5) else None) for n in range(1, 6)]),
        ('DP-1', [(str(n), leaf(1000 + n) if n == 7 else None) for n in range(6, 11)]),
    ])


class WorkspaceTests(unittest.TestCase):
    def test_restart_orders_aux_last_without_replacing_any_desktop(self):
        wm = normal_wm()
        before = copy.deepcopy({d['id']: d for d in wm.all_desktops()})
        reconcile(OUTPUTS, runner=wm)
        self.assertEqual([d['name'] for d in wm.all_desktops()], [str(n) for n in range(1, 11)] + ['AUX'])
        self.assertEqual({d['id']: d for d in wm.all_desktops()}, before)
        wm.calls.clear()
        reconcile(OUTPUTS, runner=wm)
        self.assertEqual(wm.mutation_calls(), [])

    def test_occupied_duplicates_and_recovered_trees_are_merged(self):
        tree = dict(id=2000, client=None, firstChild=leaf(2001), secondChild=leaf(2002), splitRatio=.3)
        wm = WM([('eDP-1', [('1', leaf(1001)), ('1', tree), ('1 · recuperado', leaf(3001)), ('1 · recuperado 2', None)])])
        before = wm.windows()
        focus = wm.find_desktop('1')['focusedNodeId']
        reconcile([output('eDP-1', primary=True)], runner=wm)
        self.assertEqual([d['name'] for d in wm.all_desktops()], [str(n) for n in range(1, 11)])
        self.assertEqual(wm.windows(), before)
        self.assertEqual(window_ids(wm.find_desktop('1')['root']), before)
        self.assertEqual(wm.find_desktop('1')['focusedNodeId'], focus)
        def find(node):
            if not node or node['id'] == tree['id']:
                return node
            return find(node.get('firstChild')) or find(node.get('secondChild'))
        self.assertEqual(find(wm.find_desktop('1')['root']), tree)

    def test_focused_recovered_desktop_keeps_its_identity(self):
        wm = WM([('eDP-1', [('1', leaf(1001)), ('1 · recuperado', leaf(2001))])], focused='1 · recuperado')
        focused = wm.find_desktop('1 · recuperado')['id']
        reconcile([output('eDP-1', primary=True)], runner=wm)
        self.assertEqual(wm.find_desktop('1')['id'], focused)
        self.assertEqual(wm.find_monitor('eDP-1')['focusedDesktopId'], focused)
        self.assertEqual(wm.windows(), {1001, 2001})

    def test_unplug_and_replug_keep_all_window_and_numbered_desktop_ids(self):
        wm = normal_wm()
        before = {d['name']: d['id'] for d in wm.all_desktops()}
        windows = wm.windows()
        reconcile([output('eDP-1', primary=True)], runner=wm)
        self.assertEqual([m['name'] for m in wm.state['monitors']], ['eDP-1'])
        self.assertEqual(wm.windows(), windows)
        for name in ('DP-2', 'DP-1'):
            d = wm.desktop('Desktop')
            wm.state['monitors'].append(dict(id=wm.allocate(), name=name, focusedDesktopId=d['id'], desktops=[d]))
        reconcile(OUTPUTS, runner=wm)
        self.assertEqual({d['name']: d['id'] for d in wm.all_desktops()}, before)
        self.assertEqual(wm.windows(), windows)
        self.assertEqual([d['name'] for d in wm.find_monitor('DP-2')['desktops']], ['1', '2', '3', '4', '5'])
        self.assertEqual([d['name'] for d in wm.find_monitor('DP-1')['desktops']], ['6', '7', '8', '9', '10'])

    def test_failed_merge_does_not_delete_an_occupied_desktop(self):
        wm = WM([('eDP-1', [('1', leaf(1001)), ('1', leaf(2001))])])
        def runner(args):
            if args[:2] == ['bspc', 'node'] and '-d' in args:
                return ''  # Even a falsely successful IPC result must be checked.
            return wm(args)
        with self.assertRaises(RuntimeError):
            reconcile([output('eDP-1', primary=True)], runner=runner)
        self.assertEqual(wm.windows(), {1001, 2001})
        self.assertEqual(sum(d['name'] == '1' for d in wm.all_desktops()), 2)

    def test_custom_names_and_saved_order_are_preserved(self):
        wm = WM([('eDP-1', [('Trabajo', leaf(1001)), ('Personal', leaf(2001)), ('Notas · recuperado', leaf(3001))])], focused='Trabajo')
        before = {d['name']: d['id'] for d in wm.all_desktops()}
        reconcile([output('eDP-1', primary=True)], {'eDP-1': ['Personal', 'Trabajo']}, wm)
        self.assertEqual([d['name'] for d in wm.all_desktops()], ['Personal', 'Trabajo', 'Notas · recuperado'])
        self.assertEqual({d['name']: d['id'] for d in wm.all_desktops()}, before)

    def test_missing_active_monitor_or_no_outputs_causes_no_mutation(self):
        wm = WM([('eDP-1', [('1', leaf(1001))])])
        for outputs in ([], OUTPUTS):
            with self.assertRaises(RuntimeError):
                reconcile(outputs, runner=wm)
        self.assertEqual(wm.mutation_calls(), [])

    def test_saved_legacy_labels_do_not_recreate_extra_desktops(self):
        saved = {'eDP-1': ['1', '1 · recuperado', '2', '1 · recuperado 2']}
        self.assertEqual(workspace_layout([output('eDP-1')], saved), {'eDP-1': ['1', '2']})

    def test_settings_restore_does_not_rename_by_position(self):
        wm = normal_wm()
        before = {d['id']: d['name'] for d in wm.all_desktops()}
        class Backend:
            runner = staticmethod(wm)
            def section(self, name):
                return {'DP-2': ['5', '1', '2', '3', '4'], 'DP-1': [str(n) for n in range(6, 11)], 'eDP-1': ['AUX']}
        with patch('settings_runtime.display_inventory', return_value=OUTPUTS):
            restore_workspaces(Backend())
        self.assertEqual({d['id']: d['name'] for d in wm.all_desktops()}, before)
        self.assertEqual([d['name'] for d in wm.find_monitor('DP-2')['desktops']], ['5', '1', '2', '3', '4'])


if __name__ == '__main__':
    unittest.main()
