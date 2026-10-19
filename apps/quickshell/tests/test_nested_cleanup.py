"""Watchdog cleanup failure paths, without launching processes or a compositor."""
import importlib.util
from pathlib import Path
import signal
import subprocess
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location("wysun_nested_runner", Path(__file__).with_name("nested_runtime.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class NestedCleanupTests(unittest.TestCase):
    def process(self):
        return Mock(pid=4312, poll=Mock(return_value=None))

    def test_watchdog_and_child_receive_group_termination(self):
        process = self.process()
        with patch.object(runner.os, "killpg") as kill:
            runner.stop_owned_group(process)
        kill.assert_called_once_with(process.pid, signal.SIGTERM)
        process.wait.assert_called_once_with(timeout=3)

    def test_stuck_group_is_killed_with_a_bounded_reap(self):
        process = self.process()
        process.wait.side_effect = [subprocess.TimeoutExpired("watchdog", 3), 0]
        with patch.object(runner.os, "killpg") as kill:
            runner.stop_owned_group(process)
        self.assertEqual(kill.call_args_list, [((process.pid, signal.SIGTERM),), ((process.pid, signal.SIGKILL),)])
        self.assertEqual(process.wait.call_count, 2)
        self.assertTrue(all(call.kwargs == {"timeout": 3} for call in process.wait.call_args_list))

    def test_exit_between_poll_and_signal_does_not_abort_cleanup(self):
        process = self.process()
        with patch.object(runner.os, "killpg", side_effect=ProcessLookupError):
            runner.stop_owned_group(process)
        process.wait.assert_called_once_with(timeout=3)

    def test_exit_between_timeout_and_kill_is_reaped(self):
        process = self.process()
        process.wait.side_effect = [subprocess.TimeoutExpired("watchdog", 3), 0]
        with patch.object(runner.os, "killpg", side_effect=[None, ProcessLookupError]):
            runner.stop_owned_group(process)
        self.assertEqual(process.wait.call_count, 2)

    def test_completed_leader_does_not_signal_a_reused_pid(self):
        process = self.process()
        process.poll.return_value = 0
        with patch.object(runner.os, "killpg") as kill:
            runner.stop_owned_group(process)
        kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
