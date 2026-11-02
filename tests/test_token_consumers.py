"""Widgets that read the schema-3 tokens directly: default roles and the mono family (offscreen Qt)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'installer'))
sys.path.insert(0, str(ROOT / 'apps/python'))

from PySide6.QtWidgets import QApplication

APP = QApplication.instance() or QApplication(['wysun-token-consumers'])

from wysun_core.qt_theme import tokens


class InstallerLabelTests(unittest.TestCase):
    def test_label_without_role_uses_the_body_role(self):
        from material_widgets import label
        widget = label('x')
        self.assertEqual(widget.property('installerRole'), 'body')
        self.assertEqual(widget.font().pointSizeF(), tokens()['font.body.medium.size'])

    def test_boot_recovery_dialog_builds(self):
        from boot_recovery import BootRecoveryDialog
        with tempfile.TemporaryDirectory() as home:
            dialog = BootRecoveryDialog(home)
            dialog.deleteLater()


if __name__ == '__main__':
    unittest.main()
