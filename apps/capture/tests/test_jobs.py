"""Renders started by older Wysun Recorder versions are interrupted only by identity."""
import unittest
from unittest.mock import patch

class LegacyJobTests(unittest.TestCase):
 def test_legacy_interrupt_rechecks_identity_and_never_guesses(self):
  from loomrec.ui.legacy_jobs import interrupt_render
  target={'pid':123,'identity':'old','kind':'Vista previa'}
  with patch('loomrec.ui.legacy_jobs.owned_render',return_value={**target,'identity':'new'}),patch('loomrec.ui.legacy_jobs.os.kill') as kill:
   with self.assertRaises(RuntimeError):interrupt_render(1,target)
   kill.assert_not_called()
  with patch('loomrec.ui.legacy_jobs.owned_render',return_value=target),patch('loomrec.ui.legacy_jobs.os.kill') as kill:
   interrupt_render(1,target);self.assertEqual(kill.call_args.args[0],123)


if __name__=='__main__':unittest.main()
