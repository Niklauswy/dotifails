import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
from desktop_backend import Desktop,wayland

class DesktopTests(unittest.TestCase):
    def test_wayland_wins_over_xwayland_display(self):
        with patch.dict(os.environ,{'DISPLAY':':2','WAYLAND_DISPLAY':'wayland-2','HYPRLAND_INSTANCE_SIGNATURE':'test'},clear=True):
            self.assertTrue(wayland());self.assertEqual(Desktop().backend,'hyprland')
    def test_hyprland_native_windows_and_lua_activation(self):
        data={'clients':[dict(address='0xabc',title='Prueba',**{'class':'synthetic'},workspace={'id':2},mapped=True,xwayland=False)],'activewindow':{'address':'0xabc'}}
        run=Mock(side_effect=lambda a:json.dumps(data[a[-1]]) if a[1]=='-j' else 'ok')
        desktop=Desktop(run,'hyprland');windows=desktop.windows()
        self.assertEqual(windows[0]['app'],'synthetic');self.assertFalse(windows[0]['xwayland']);self.assertEqual(desktop.focused(),'0xabc')
        desktop.activate('0xabc')
        self.assertEqual(run.call_args.args[0],['hyprctl','dispatch','hl.dsp.focus({ window = "address:0xabc" })'])
        with self.assertRaises(ValueError):desktop.activate('0xabc; exit')
    def test_workspace_remove_never_deletes_occupied_workspace(self):
        desktop=Desktop(Mock(),'hyprland');desktop.workspaces=Mock(return_value=[dict(id='2',name='2',monitor='DP-1',windows=1,active=True)])
        with self.assertRaisesRegex(ValueError,'vacíos'):desktop.workspace_action('remove','2')
        desktop.run.assert_not_called()
    def test_hyprland_workspace_actions_resolve_exact_name_not_selector(self):
        # v0.55.2 MiscFunctions.cpp interprets bare numbers/empty/special/+N
        # before its ordinary-name fallback. name: resolves literal names first.
        for name in ('2','empty','special','+2','name:literal','Trabajo'):
            for action in ('activate','rename','move'):
                with self.subTest(name=name,action=action):
                    rows=[dict(id='1',name=name,monitor='DP-1',windows=0,active=False),
                          dict(id='2',name='Other',monitor='DP-1',windows=0,active=True)]
                    selected=[]
                    def dispatch(method,**values):
                        selector=values['workspace']
                        if selector.startswith('name:'):
                            target=next((w for w in rows if w['name']==selector[5:]),None)
                        elif selector.isdecimal():
                            target=next((w for w in rows if w['id']==selector),None)
                        elif selector.startswith(('empty','special','+','-')):
                            target=None  # A different selector, not a literal name.
                        else:target=next((w for w in rows if w['name']==selector),None)
                        selected.append(target['id'] if target else None)
                    desktop=Desktop(Mock(),'hyprland')
                    desktop.workspaces=Mock(return_value=rows);desktop.dispatch=dispatch
                    desktop.workspace_action(action,'1','DP-2' if action=='move' else 'Renamed')
                    self.assertEqual(selected,['1'])
    def test_hyprland_named_negative_workspace_is_not_relative_id(self):
        desktop=Desktop(Mock(),'hyprland')
        desktop.workspaces=Mock(return_value=[dict(id='-1337',name='-2',monitor='DP-1',windows=0,active=False)])
        desktop.workspace_action('activate','-1337')
        self.assertEqual(desktop.run.call_args.args[0][-1],'hl.dsp.focus({ workspace = "name:-2" })')
    def test_hyprland_paste_targets_only_verified_previous_window(self):
        from wayland_clipboard import paste_to
        desktop=Desktop(Mock(return_value='ok'),'hyprland');desktop.focused=Mock(return_value='0x123')
        ok,_=paste_to('0x123',desktop)
        self.assertTrue(ok);self.assertIn('send_shortcut',desktop.run.call_args.args[0][-1])
        desktop.focused=Mock(return_value='0x456');desktop.run.reset_mock()
        ok,_=paste_to('0x123',desktop)
        self.assertFalse(ok);self.assertEqual(desktop.run.call_count,1)
    def test_unsupported_desktop_is_rejected_without_running_commands(self):
        runner=Mock()
        for backend in ('sway','bspwm','x11'):
            with self.subTest(backend=backend),self.assertRaisesRegex(ValueError,'Hyprland'):
                Desktop(runner,backend)
        runner.assert_not_called()

if __name__=='__main__':unittest.main()
