"""Appearance preference and process regressions using isolated data."""
import os
import tempfile,unittest
from pathlib import Path
from wysun_core.appearance import read_appearance,save_appearance
from process_data import matched,pressure,thread_snapshot


def row(pid=20,start='10',ppid=1,**values):
    result=dict(pid=pid,start=start,ppid=ppid,uid=os.getuid(),user='demo',name='editor',cpu=26.,memory=400*1024**2,state='S',threads=3,nice=0,age=65,read_rate=32,write_rate=4)
    result.update(values);return result


class DataTests(unittest.TestCase):
    def test_preferences_preserve_unknown_fields_and_clamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'.config/orbit/appearance.json';path.parent.mkdir(parents=True);path.write_text('{"custom":"keep"}')
            save_appearance(dict(opacity=2,reduced_motion=True),tmp)
            self.assertEqual(read_appearance(tmp)['opacity'],65);self.assertTrue(read_appearance(tmp)['reduced_motion']);self.assertIn('keep',path.read_text())
    def test_advanced_queries(self):
        r=row();self.assertTrue(matched(r,'cpu>20 mem>=256m state:s user:demo'))
        self.assertFalse(matched(r,'cpu>30'));self.assertFalse(matched(r,'mem<200m'));self.assertFalse(matched(r,'cpu>oops'))
        self.assertTrue(matched(r,'pid:20 ppid:1'))
    def test_pressure_missing_and_real_threads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'cpu').write_text('some avg10=12.34 avg60=1.0 avg300=0.1 total=40\n')
            data=pressure(root);self.assertEqual(data['cpu'],12.34);self.assertIsNone(data['io'])
        threads,total=thread_snapshot(os.getpid());self.assertGreater(total,0);self.assertTrue(any(t['tid']==os.getpid() for t in threads))


if __name__=='__main__':unittest.main(verbosity=2)
