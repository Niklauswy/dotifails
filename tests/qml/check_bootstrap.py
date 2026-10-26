"""wysun_qml.bootstrap / engine: PySide6 bindings running on the shell's own Qt, with no LD_LIBRARY_PATH."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
from wysun_qml import bootstrap  # noqa: E402  (does not import PySide6)


def setUpModule():
    if not bootstrap.qt_prefix().is_dir():
        sys.stderr.write('\nAVISO: falta el runtime del shell (%s); se omiten las pruebas de arranque QML.\n' % bootstrap.runtime_dir())
        raise unittest.SkipTest('no shell runtime')
    bootstrap.preload_qt()          # must happen before PySide6 is imported anywhere


def mapped(name):
    with open('/proc/self/maps') as maps:
        return sorted({line.split()[-1] for line in maps if name in line and line.split()[-1].startswith('/')})


class PreloadTests(unittest.TestCase):
    def test_preload_maps_runtime_qt_only(self):
        import PySide6.QtCore  # noqa: F401
        prefix = str(bootstrap.qt_prefix())
        for library in ('libQt6Core.so', 'libQt6Gui.so', 'libQt6Qml.so', 'libQt6Quick.so'):
            paths = mapped(library)
            self.assertTrue(paths, library)
            for path in paths:
                self.assertTrue(path.startswith(prefix), path + ' is not the runtime Qt')
        self.assertEqual([p for p in mapped('libQt6') if 'PySide6/Qt' in p], [])

    def test_preload_returns_the_loaded_libraries(self):
        loaded = bootstrap.preload_qt()
        self.assertIn('Core', loaded)
        self.assertIn('Quick', loaded)

    def test_preload_tolerates_a_missing_runtime(self):
        self.assertEqual(bootstrap.preload_qt(Path('/no/existe')), [])

    def test_no_ld_library_path_is_exported(self):
        before = os.environ.get('LD_LIBRARY_PATH')
        bootstrap.preload_qt()
        bootstrap.configure_qt()
        self.assertEqual(os.environ.get('LD_LIBRARY_PATH'), before)
        self.assertNotIn('QT_PLUGIN_PATH', os.environ)


class ConfigureTests(unittest.TestCase):
    def test_import_paths_include_runtime_deps_and_library(self):
        paths = bootstrap.configure_qt()
        self.assertIn(bootstrap.qt_prefix() / 'qml', paths)
        self.assertIn(bootstrap.runtime_dir() / 'deps/lib/qt6/qml', paths)     # M3Shapes
        self.assertIn(bootstrap.library_path(), paths)
        self.assertTrue((bootstrap.library_path() / 'WysunM3').is_dir())

    def test_plugins_come_from_the_runtime(self):
        from PySide6.QtCore import QCoreApplication
        bootstrap.configure_qt()
        self.assertEqual(QCoreApplication.libraryPaths(), [str(bootstrap.qt_prefix() / 'plugins')])

    def test_library_path_prefers_the_override(self):
        with patch.dict(os.environ, {'WYSUN_QML_LIB': '/somewhere/qml'}):
            self.assertEqual(bootstrap.library_path(), Path('/somewhere/qml'))

    def test_qt_prefix_follows_the_runtime_stamp(self):
        self.assertTrue((bootstrap.qt_prefix() / 'lib/libQt6Core.so.6').exists())


class VersionTests(unittest.TestCase):
    def test_versions_match_the_runtime(self):
        self.assertIsNone(bootstrap.check_versions())

    def test_mismatch_warns_without_raising(self):
        with patch.object(bootstrap, '_qt_version', return_value='6.8.2'):
            text = bootstrap.check_versions()
        self.assertIn('6.8.2', text)
        self.assertIn(bootstrap.pyside_version(), text)
        self.assertIn('qml_runtime.py', text)


class ReexecTests(unittest.TestCase):
    def test_reexec_selects_the_venv_python(self):
        venv = Path('/fake/venv')
        with patch.object(bootstrap, 'qml_runtime_python', return_value=venv / 'bin/python3'), \
                patch.object(sys, 'prefix', '/usr'), patch('os.execve') as execve:
            bootstrap.ensure_runtime_python('wysun_qml', ['--page', 'buttons'])
        python, argv, env = execve.call_args.args
        self.assertEqual(python, str(venv / 'bin/python3'))
        self.assertEqual(argv, [str(venv / 'bin/python3'), '-P', '-m', 'wysun_qml', '--page', 'buttons'])
        self.assertEqual(env['PYTHONPATH'], str(ROOT / 'apps/python'))

    def test_no_reexec_when_already_in_the_venv(self):
        venv = Path('/fake/venv')
        with patch.object(bootstrap, 'qml_runtime_python', return_value=venv / 'bin/python3'), \
                patch.object(sys, 'prefix', str(venv)), patch('os.execve') as execve:
            bootstrap.ensure_runtime_python('wysun_qml', [])
        execve.assert_not_called()

    def test_missing_venv_prints_the_install_hint_and_exits_2(self):
        with patch.object(bootstrap, 'qml_runtime_python', return_value=None), \
                patch('sys.stderr') as err, self.assertRaises(SystemExit) as raised:
            bootstrap.ensure_runtime_python('wysun_qml', [])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn('qml_runtime.py', ''.join(call.args[0] for call in err.write.call_args_list))

    def test_runtime_python_needs_a_complete_stamp(self):
        with patch.dict(os.environ, {'WYSUN_QML_RUNTIME': '/no/existe'}):
            self.assertIsNone(bootstrap.qml_runtime_python())


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wysun_qml import engine
        cls.app, cls.engine = engine.create_engine('Wysun QML test')

    def load(self, source):
        from PySide6.QtQml import QQmlComponent
        component = QQmlComponent(self.engine)
        component.setData(source.encode(), 'inline.qml')
        item = component.create()
        self.assertIsNotNone(item, component.errorString())
        return item

    def test_creating_an_engine_twice_reuses_the_application(self):
        from wysun_qml import engine
        app, _ = engine.create_engine('again')
        self.assertIs(app, self.app)

    def test_quick_shapes_import(self):
        self.load('import QtQuick\nimport QtQuick.Shapes\nItem {}')

    def test_base_library_import(self):
        self.load('import QtQuick\nimport WysunM3\nItem { property color c: Theme.m3primary }')

    def test_m3shapes_import(self):
        self.load('import QtQuick\nimport M3Shapes\nItem {}')

    def test_fonts_are_registered(self):
        from PySide6.QtGui import QFontDatabase
        families = QFontDatabase.families()
        self.assertIn('Google Sans Flex', families)
        self.assertIn('Material Symbols Rounded', families)

    def test_qt_comes_from_the_runtime(self):
        from PySide6.QtCore import qVersion
        self.assertEqual(qVersion(), bootstrap.pyside_version())


if __name__ == '__main__':
    unittest.main()
