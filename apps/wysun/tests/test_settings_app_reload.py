"""The Settings process restarts onto new code only while hidden and idle."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import settings_app


class StaleCodeTests(unittest.TestCase):
    def test_restart_only_when_code_changed_and_window_idle(self):
        with tempfile.TemporaryDirectory(prefix='wysun-settings-code-') as folder:
            root = Path(folder); source = root / 'settings_hub.py'; source.write_text('# v1\n')
            started = settings_app.code_stamp(root)
            window = Mock(); window.isVisible.return_value = False; window.jobs = []; window.trial = None
            self.assertFalse(settings_app.stale(started, window, root))
            later = time.time() + 5; os.utime(source, (later, later))
            self.assertTrue(settings_app.stale(started, window, root))
            window.isVisible.return_value = True
            self.assertFalse(settings_app.stale(started, window, root))
            window.isVisible.return_value = False; window.trial = object()
            self.assertFalse(settings_app.stale(started, window, root))
            window.trial = None; window.jobs = [object()]
            self.assertFalse(settings_app.stale(started, window, root))


if __name__ == '__main__':
    unittest.main()
