"""`wysun recorder` without arguments ends with the settings window's own exit code."""
import sys
import unittest
from unittest import mock

from wysun_recorder import __main__ as entry


class WindowExitCodeTests(unittest.TestCase):
    def run_main(self, result):
        with mock.patch.object(sys, 'argv', ['wysun recorder']), mock.patch('wysun_recorder.ui.main', return_value=result):
            with self.assertRaises(SystemExit) as ended:
                entry.main()
        return ended.exception.code

    def test_a_failure_of_the_window_is_the_exit_code(self):
        self.assertEqual(self.run_main(3), 3)

    def test_a_clean_end_is_zero(self):
        self.assertIn(self.run_main(0), (0, None))


if __name__ == '__main__':
    unittest.main()
