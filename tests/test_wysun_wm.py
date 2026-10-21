from pathlib import Path
import runpy,unittest
m=runpy.run_path(str(Path(__file__).resolve().parents[1]/'bin/wysun-wm'))
plan=m['action_plan']
def window(a,pid,size=(300,200),rank=0,workspace=1,floating=False):return dict(address=a,pid=pid,size=size,focusHistoryID=rank,workspace={'id':workspace},floating=floating,mapped=True)
class NativeActionsTests(unittest.TestCase):
 def test_biggest_is_same_workspace_visible_tiled_and_valid_identity(self):
  a=window('0x1',1);b=window('0x2',2,(700,600),1);c=window('0x3',3,(900,900),2,2)
  self.assertIn('address:0x2',plan('biggest-swap',a,[a,b,c])[0])
  b['hidden']=True;self.assertIsNone(plan('biggest-swap',a,[a,b,c])[0])
 def test_history_walk_does_not_toggle_and_detects_pid_reuse(self):
  a=window('0x1',1,rank=0);b=window('0x2',2,rank=1);c=window('0x3',3,rank=2)
  cmd,state=plan('history-older',a,[a,b,c]);self.assertIn('0x2',cmd)
  cmd,state=plan('history-older',b,[b,a,c],state);self.assertIn('0x3',cmd)
  cmd,state=plan('history-newer',c,[c,b,a],state);self.assertIn('0x2',cmd)
  b['pid']=22;cmd,state=plan('history-older',a,[a,b,c],state);self.assertEqual(state['order'][1]['pid'],22)
 def test_move_requires_float_and_resize_uses_baseline_steps(self):
  a=window('0x1',1)
  with self.assertRaises(ValueError):plan('move-left',a,[a])
  self.assertIn('x=-100',plan('resize-left',a,[a])[0]);a['floating']=True
  self.assertIn('y=20',plan('move-down',a,[a])[0]);self.assertIn('x=20',plan('resize-right',a,[a])[0])
 def test_pin_explains_constraint_and_never_toggles_float_silently(self):
  a=window('0x1',1)
  with self.assertRaises(ValueError):plan('pin',a,[a])
  a['floating']=True;self.assertIn('.pin(',plan('pin',a,[a])[0])
 def test_rejects_selector_injection(self):
  with self.assertRaises(ValueError):plan('resize-left',window('0x1";os.execute()',1),[])
class ActivationTests(unittest.TestCase):
 def test_focus_only_when_nothing_covers_the_target(self):
  clients=[dict(window('0x1',1,workspace=7),**{'class':'foot'}),window('0x2',2,workspace=3)]
  dispatchers,target=m['activation_plan'](clients,'foot')
  self.assertEqual(target['address'],'0x1');self.assertEqual(dispatchers,['hl.dsp.focus({window="address:0x1"})'])
 def test_covering_fullscreen_on_same_workspace_is_left_before_focus(self):
  cover=dict(window('0x2',2,workspace=7),fullscreen=2)
  dispatchers,_=m['activation_plan']([dict(window('0x1',1,workspace=7),**{'class':'foot'}),cover],'foot')
  self.assertIn('address:0x2',dispatchers[0]);self.assertIn('action="set"',dispatchers[0]);self.assertIn('focus',dispatchers[1])
 def test_fullscreen_elsewhere_is_ignored_and_unknown_class_is_none(self):
  other=dict(window('0x2',2,workspace=3),fullscreen=2)
  dispatchers,_=m['activation_plan']([dict(window('0x1',1,workspace=7),**{'class':'foot'}),other],'foot')
  self.assertEqual(len(dispatchers),1);self.assertEqual(m['activation_plan']([other],'nada'),([],None))
if __name__=='__main__':unittest.main()
