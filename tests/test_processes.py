import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'apps/orbit'))
from process_data import Processes,process_record,safe_command,matched

class ProcessTests(unittest.TestCase):
    def test_pause_resume_and_identity_guard(self):
        p=subprocess.Popen(['sleep','30']);model=Processes()
        try:
            row=process_record(p.pid);model.act(row,'pause')
            for _ in range(100):
                if process_record(p.pid)['state']=='T':break
                time.sleep(.01)
            self.assertEqual(process_record(p.pid)['state'],'T');model.act(row,'resume')
            for _ in range(100):
                if process_record(p.pid)['state']!='T':break
                time.sleep(.01)
            self.assertNotEqual(process_record(p.pid)['state'],'T')
            with self.assertRaises(RuntimeError):model.act(dict(row,start='0'),'kill')
            self.assertIsNone(p.poll());model.act(row,'terminate');self.assertEqual(p.wait(timeout=2),-15)
        finally:
            if p.poll() is None:p.send_signal(signal.SIGCONT);p.kill();p.wait()
    def test_snapshot_details_and_permissions(self):
        model=Processes();rows=model.scan();self.assertTrue(rows);self.assertGreater(model.summary['total_memory'],0)
        row=process_record(os.getpid());details=model.details(row)
        self.assertEqual(details['key'],(row['pid'],row['start']));self.assertTrue(details['exe']);self.assertGreater(details['file_count'],0)
        with self.assertRaises(PermissionError):model.act(row,'pause')
        self.assertTrue(model.action_reason(dict(row,pid=999999,uid=os.getuid()+1)))
    def test_credentials_redacted_before_display(self):
        output=safe_command(['app','--token','private-value','--password=other-value','https://user:password@example.test','--header','Authorization: Bearer private-value'])
        self.assertNotIn('private-value',output);self.assertNotIn('other-value',output);self.assertNotIn('user:password',output);self.assertIn('••••',output)
    def test_filters_are_literal_and_composable(self):
        row=dict(name='python3',pid=42,ppid=7,user='tester')
        self.assertTrue(matched(row,'python user:test'));self.assertTrue(matched(row,'pid:42'));self.assertFalse(matched(row,'pid:4'));self.assertTrue(matched(row,'ppid:7'));self.assertFalse(matched(row,'[.*'))
