"""Opt-in Qt event routing fixture; offscreen proof is not Wayland proof.

Run WYSUN_QML_INPUT_TEST=1 python3 -m unittest discover -s apps/quickshell/tests
-p test_shell_button_input.py -v, only in the coordinated graphics slot.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get("WYSUN_QML_INPUT_TEST") == "1", "Qt input fixture needs an explicitly coordinated opt-in")
class ShellButtonInputTests(unittest.TestCase):
    def test_secondary_click_does_not_dispatch_primary_or_break_keyboard(self):
        with tempfile.TemporaryDirectory(prefix="wysun-button-") as temporary:
            env = {"HOME": temporary, "XDG_CONFIG_HOME": temporary,
                   "XDG_CACHE_HOME": temporary, "XDG_DATA_HOME": temporary,
                   "XDG_RUNTIME_DIR": temporary, "QT_QPA_PLATFORM": "offscreen",
                   "QT_QUICK_BACKEND": "software", "QT_QUICK_CONTROLS_STYLE": "Basic"}
            with patch.dict(os.environ, env):
                from PySide6.QtCore import QPoint, Qt, QUrl
                from PySide6.QtGui import QGuiApplication
                from PySide6.QtQml import QQmlApplicationEngine
                from PySide6.QtQuick import QQuickItem
                from PySide6.QtTest import QTest
                app = QGuiApplication.instance() or QGuiApplication(["wysun-button-test"])
                engine = QQmlApplicationEngine()
                engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("tst_shell_button.qml"))))
                self.assertTrue(engine.rootObjects(), "The real ShellButton fixture must load")
                window = engine.rootObjects()[0]
                button = window.findChild(QQuickItem, "primaryButton")
                self.assertIsNotNone(button)
                QTest.qWait(50)

                def click(which, point=QPoint(60, 36)):
                    QTest.mouseClick(window, which, Qt.NoModifier, point)
                    app.processEvents()

                try:
                    click(Qt.LeftButton)
                    self.assertEqual((window.property("primaryCalls"), window.property("secondaryCalls")), (1, 0))
                    click(Qt.RightButton)
                    self.assertEqual((window.property("primaryCalls"), window.property("secondaryCalls")), (1, 1))
                    button.forceActiveFocus()
                    QTest.keyClick(window, Qt.Key_Space)
                    app.processEvents()
                    self.assertEqual((window.property("primaryCalls"), window.property("secondaryCalls")), (2, 1))
                    click(Qt.MiddleButton)
                    click(Qt.RightButton, QPoint(160, 80))
                    button.setProperty("secondaryActionEnabled", False)
                    click(Qt.RightButton)
                    click(Qt.LeftButton)
                    self.assertEqual((window.property("primaryCalls"), window.property("secondaryCalls")), (3, 1))
                    button.setProperty("secondaryActionEnabled", True)
                    button.setEnabled(False)
                    click(Qt.RightButton)
                    self.assertEqual((window.property("primaryCalls"), window.property("secondaryCalls")), (3, 1))
                finally:
                    window.close()
                    engine.deleteLater()
                    app.processEvents()


if __name__ == "__main__":
    unittest.main()
