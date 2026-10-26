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


class FilesMonoTests(unittest.TestCase):
    def test_code_font_is_the_mono_family_in_points(self):
        from wysun_files.textview import mono_font
        font = mono_font(scale=1)
        self.assertEqual(font.family(), tokens()['font.family.mono'])
        self.assertEqual(font.pointSizeF(), tokens()['font.body.medium.size'])

    def test_markdown_code_css_names_the_mono_family(self):
        from wysun_files.textview import ink
        self.assertEqual(ink()['mono'], '"%s"' % tokens()['font.family.mono'])


if __name__ == '__main__':
    unittest.main()
