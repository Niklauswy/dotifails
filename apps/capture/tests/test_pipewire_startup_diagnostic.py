"""Own-pipeline readback fixtures: no GStreamer runtime or media."""
import json
import unittest
from types import SimpleNamespace
from loomrec.pipewire_bridge import startup_diagnostic


class Properties:
    def __init__(self,values):self.values=values
    def get_property(self,key):
        if key not in self.values:raise TypeError(key)
        return self.values[key]
    def get_factory(self):return SimpleNamespace(get_plugin=lambda:SimpleNamespace(get_version=lambda:'1.4.2'))


class StartupDiagnosticTests(unittest.TestCase):
    def test_failure_readback_preserves_counters_without_fd_value(self):
        source=Properties({'fd':13887,'path':None,'target-object':'44','autoconnect':True})
        rate=Properties({'in':0,'out':0,'drop':0,'duplicate':0})
        sink=Properties({'stats':SimpleNamespace(get_value=lambda key:{'rendered':0,'dropped':0}[key])})
        raw=startup_diagnostic(source,rate,sink);result=json.loads(raw)
        self.assertTrue(result['fd_valid']);self.assertNotIn('13887',raw)
        self.assertEqual(result['target-object'],'44');self.assertIsNone(result['path']);self.assertTrue(result['autoconnect'])
        self.assertEqual(result['plugin_version'],'1.4.2');self.assertEqual(result['videorate'],dict.fromkeys(['in','out','drop','duplicate'],0))
        self.assertEqual(result['appsink'],dict(rendered=0,dropped=0))
    def test_missing_properties_do_not_mask_startup_failure(self):
        empty=Properties({});result=json.loads(startup_diagnostic(empty,empty,empty))
        self.assertFalse(result['fd_valid']);self.assertIsNone(result['autoconnect']);self.assertIsNone(result['videorate']['in'])
        self.assertIsNone(result['appsink']['rendered'])
    def test_retained_input_and_no_input_remain_distinguishable(self):
        source=Properties({'fd':-1});sink=Properties({})
        before=json.loads(startup_diagnostic(source,Properties(dict({'in':0,'out':0})),sink))
        retained=json.loads(startup_diagnostic(source,Properties(dict({'in':1,'out':0})),sink))
        self.assertEqual(before['videorate']['in'],0);self.assertEqual(retained['videorate']['in'],1)
        self.assertFalse(retained['fd_valid'])

if __name__=='__main__':unittest.main()
