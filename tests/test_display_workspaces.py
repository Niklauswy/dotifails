import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/orbit'))
from display_workspaces import reconcile,workspace_layout


def output(name,primary=False,x=0):
    return dict(name=name,connected=True,enabled=True,primary=primary,x=x)


class WorkspaceLayoutTests(unittest.TestCase):
    def test_no_active_destination_never_mutates_bspwm(self):
        runner=Mock()
        with self.assertRaises(RuntimeError):reconcile([],runner=runner)
        runner.assert_not_called()

    def test_laptop_keeps_all_ten_desktops(self):
        self.assertEqual(workspace_layout([output('eDP-1')]),{'eDP-1':[str(i) for i in range(1,11)]})

    def test_three_screens_preserve_numbered_externals_and_aux(self):
        layout=workspace_layout([output('eDP-1'),output('DP-1',x=3840),output('DP-2',True,1920)])
        self.assertEqual(layout,{'DP-2':['1','2','3','4','5'],'eDP-1':['AUX'],'DP-1':['6','7','8','9','10']})

    def test_saved_custom_names_are_not_reset(self):
        self.assertEqual(workspace_layout([output('eDP-1')],{'eDP-1':['Trabajo','Código'],'DP-1':['Otros']}),{'eDP-1':['Trabajo','Código']})

    def test_missing_bspwm_destination_never_mutates(self):
        runner=Mock(return_value='{"monitors": []}')
        with self.assertRaises(RuntimeError):reconcile([output('eDP-1')],runner=runner)
        runner.assert_called_once_with(['bspc','wm','-d'])

if __name__=='__main__':unittest.main()
