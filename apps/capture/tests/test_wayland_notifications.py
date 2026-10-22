"""The shell owns notifications; tests use its Do Not Disturb command and leases only, no session daemon."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from loomrec.integration import Concentration

class NotificationLeaseTests(unittest.TestCase):
    def test_exact_previous_pause_is_restored_after_cancel_or_finish(self):
        for previous in ('true','false'):
            with self.subTest(previous=previous),tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'XDG_STATE_HOME':folder}),patch('loomrec.integration.dnd_state',return_value=previous),patch('loomrec.integration.set_dnd') as command:
                state=Concentration();state.begin(Path(folder)/'own-project');lease=state.lease
                self.assertEqual(json.loads(lease.read_text())['previous'],previous);self.assertEqual(lease.stat().st_mode&0o777,0o600)
                state.restore();self.assertEqual(command.call_args.args[0],previous);self.assertFalse(lease.exists());state.restore();self.assertEqual(command.call_count,2)
    def test_changed_lease_cannot_restore_over_another_recorder(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'XDG_STATE_HOME':folder}),patch('loomrec.integration.dnd_state',return_value='false'),patch('loomrec.integration.set_dnd') as command:
            state=Concentration();state.begin(Path(folder)/'own-project');data=json.loads(state.lease.read_text());data['token']='another-owner';state.lease.write_text(json.dumps(data));command.reset_mock()
            state.restore();command.assert_not_called();self.assertTrue(state.lease.exists())
    def test_recovery_restores_stale_lease_but_never_live_owner(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'XDG_STATE_HOME':folder}),patch('loomrec.integration.set_dnd') as command:
            path=Path(folder)/'loomrec/concentration.json';path.parent.mkdir();path.write_text(json.dumps(dict(previous='false',project_dir=folder,token='own')))
            with patch.object(Concentration,'active',return_value=True):self.assertFalse(Concentration().recover());command.assert_not_called()
            with patch.object(Concentration,'active',return_value=False):self.assertTrue(Concentration().recover())
            self.assertEqual(command.call_args.args[0],'false');self.assertFalse(path.exists())

if __name__=='__main__':unittest.main()
