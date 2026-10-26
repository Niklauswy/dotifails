"""The qml-runtime venv itself: bindings in lockstep with the shell Qt, pruned, system packages visible."""
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'installer'))
import qml_runtime


class RuntimeVenvTests(unittest.TestCase):
    def test_runs_in_the_private_venv_with_a_complete_stamp(self):
        stamp = qml_runtime.stamp(sys.prefix)
        self.assertIsNotNone(stamp, 'these suites must run with the qml-runtime python')
        self.assertEqual(stamp, {'pyside6': qml_runtime.wanted_version(), 'qt': qml_runtime.wanted_version()})

    def test_pyside6_is_in_lockstep_with_the_runtime_qt(self):
        # Metadata only: importing PySide6 needs the runtime Qt preloaded first (wysun_qml.bootstrap).
        from importlib import metadata
        wanted = json.loads((ROOT / 'manifests/runtime.json').read_text())['qt']['version']
        self.assertEqual(metadata.version('PySide6_Essentials'), wanted)
        self.assertEqual(metadata.version('shiboken6'), wanted)

    def test_the_wheels_qt_copy_and_tools_are_gone(self):
        spec = importlib.util.find_spec('PySide6')
        folder = Path(spec.origin).parent
        self.assertTrue((folder / 'QtQuick.abi3.so').exists(), 'bindings must stay')
        for name in ('Qt', 'include', 'doc', 'glue', 'designer', 'uic', 'qmlls'):
            self.assertFalse((folder / name).exists(), name)

    def test_system_site_packages_stay_reachable(self):
        importlib.import_module('dbus')


if __name__ == '__main__':
    unittest.main()
