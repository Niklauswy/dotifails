"""The private qml-runtime venv (PySide6 bindings on the shell Qt) and the runner of the QML suites."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'installer'))
sys.path.insert(0, str(ROOT / 'tests'))
import qml_runtime
import wayland


class FakeRunner:
    """Records the commands and makes the side effects the real ones would have."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, cmd, **kw):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        if self.fail_on and self.fail_on in cmd:
            raise subprocess.CalledProcessError(1, cmd)
        if 'venv' in cmd:
            prefix = Path(cmd[-1])
            (prefix / 'bin').mkdir(parents=True, exist_ok=True)
            (prefix / 'bin/python3').write_text('')
            (prefix / 'lib/python3.13/site-packages').mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0)


def fake_site_packages(prefix):
    site = Path(prefix) / 'lib/python3.13/site-packages/PySide6'
    (site / 'Qt/lib').mkdir(parents=True)
    (site / 'Qt/lib/libQt6Core.so.6').write_text('qt')
    for folder in ('include', 'doc', 'glue'):
        (site / folder).mkdir()
        (site / folder / 'x').write_text('x')
    for tool in ('designer', 'uic', 'qmlls', 'QtQuick.abi3.so', 'libpyside6qml.abi3.so.6.9'):
        (site / tool).write_text('x')
    (Path(prefix) / 'bin').mkdir(exist_ok=True)
    (Path(prefix) / 'bin/pyside6-uic').write_text('x')
    (Path(prefix) / 'bin/python3').write_text('')
    return site


class QmlRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wysun-qmlrt-', dir=Path.home() / '.cache')
        self.addCleanup(self.tmp.cleanup)
        self.prefix = Path(self.tmp.name) / 'qml-runtime'

    def test_wanted_version_matches_runtime_manifest(self):
        manifest = json.loads((ROOT / 'manifests/runtime.json').read_text())
        self.assertEqual(qml_runtime.wanted_version(), manifest['qt']['version'])

    def test_default_prefix_follows_xdg_and_override(self):
        with patch.dict(os.environ, {'XDG_DATA_HOME': '/xdg'}, clear=False):
            os.environ.pop('WYSUN_QML_RUNTIME', None)
            self.assertEqual(qml_runtime.default_prefix(), Path('/xdg/wysun/qml-runtime'))
        with patch.dict(os.environ, {'WYSUN_QML_RUNTIME': '/elsewhere'}):
            self.assertEqual(qml_runtime.default_prefix(), Path('/elsewhere'))

    def test_ensure_creates_venv_with_system_site_packages_and_pinned_wheels(self):
        runner = FakeRunner()
        self.assertTrue(qml_runtime.ensure(self.prefix, '6.9.3', runner=runner))
        venv, pip = runner.calls
        self.assertEqual(venv[1:], ['-m', 'venv', '--system-site-packages', str(self.prefix)])
        self.assertEqual(pip[0], str(self.prefix / 'bin/python3'))
        self.assertIn('--no-deps', pip)
        self.assertIn('--only-binary=:all:', pip)          # never a source build on this machine
        self.assertIn('--no-cache-dir', pip)
        self.assertEqual(pip[-2:], ['PySide6_Essentials==6.9.3', 'shiboken6==6.9.3'])
        self.assertEqual(qml_runtime.stamp(self.prefix), {'pyside6': '6.9.3', 'qt': '6.9.3'})

    def test_ensure_is_idempotent_when_stamp_matches(self):
        qml_runtime.ensure(self.prefix, '6.9.3', runner=FakeRunner())
        runner = FakeRunner()
        self.assertFalse(qml_runtime.ensure(self.prefix, '6.9.3', runner=runner))
        self.assertEqual(runner.calls, [])

    def test_version_bump_reinstalls_without_recreating_the_venv(self):
        qml_runtime.ensure(self.prefix, '6.9.2', runner=FakeRunner())
        self.assertTrue(qml_runtime.needs_update(self.prefix, '6.9.3'))
        runner = FakeRunner()
        self.assertTrue(qml_runtime.ensure(self.prefix, '6.9.3', runner=runner))
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0][-2:], ['PySide6_Essentials==6.9.3', 'shiboken6==6.9.3'])
        self.assertEqual(qml_runtime.stamp(self.prefix)['pyside6'], '6.9.3')

    def test_failed_install_leaves_no_stamp_so_the_next_run_retries(self):
        with self.assertRaises(subprocess.CalledProcessError):
            qml_runtime.ensure(self.prefix, '6.9.3', runner=FakeRunner(fail_on='--no-deps'))
        self.assertIsNone(qml_runtime.stamp(self.prefix))
        self.assertTrue(qml_runtime.needs_update(self.prefix, '6.9.3'))

    def test_broken_stamp_means_update(self):
        self.prefix.mkdir(parents=True)
        (self.prefix / qml_runtime.STAMP).write_text('{not json')
        self.assertIsNone(qml_runtime.stamp(self.prefix))
        self.assertTrue(qml_runtime.needs_update(self.prefix, '6.9.3'))

    def test_prune_removes_qt_tree_and_tools_only(self):
        site = fake_site_packages(self.prefix)
        freed = qml_runtime.prune(self.prefix)
        self.assertGreater(freed, 0)
        self.assertFalse((site / 'Qt').exists())
        for tool in ('designer', 'uic', 'qmlls'):
            self.assertFalse((site / tool).exists(), tool)
        self.assertFalse((self.prefix / 'bin/pyside6-uic').exists())
        for folder in ('include', 'doc', 'glue'):
            self.assertFalse((site / folder).exists(), folder)
        self.assertTrue((site / 'QtQuick.abi3.so').exists())
        self.assertTrue((site / 'libpyside6qml.abi3.so.6.9').exists())
        self.assertEqual(qml_runtime.prune(self.prefix), 0)

    def test_check_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(qml_runtime.main(['--prefix', str(self.prefix), '--version', '6.9.3', '--check']), 3)
        qml_runtime.ensure(self.prefix, '6.9.3', runner=FakeRunner())
        with contextlib.redirect_stdout(out):
            self.assertEqual(qml_runtime.main(['--prefix', str(self.prefix), '--version', '6.9.3', '--check']), 0)


class FakeDeployment:
    def __init__(self, home, source=ROOT):
        self.home = Path(home)
        self.source = Path(source)
        self.stages = []

    def stage(self, name):
        self.stages.append(name)


class InstallerStepTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wysun-qmlrt-', dir=Path.home() / '.cache')
        self.addCleanup(self.tmp.cleanup)
        self.deployment = FakeDeployment(self.tmp.name)

    def test_skip_env_leaves_the_installer_alone(self):
        with patch.dict(os.environ, {'WYSUN_SKIP_RUNTIME': '1'}), patch.object(qml_runtime, 'ensure') as ensure:
            wayland.ensure_qml_runtime(self.deployment)
        ensure.assert_not_called()

    def test_step_targets_the_live_prefix_with_the_manifest_version(self):
        env = {k: v for k, v in os.environ.items() if k not in ('WYSUN_SKIP_RUNTIME', 'WYSUN_QML_RUNTIME')}
        with patch.dict(os.environ, env, clear=True), patch.object(qml_runtime, 'ensure', return_value=True) as ensure:
            wayland.ensure_qml_runtime(self.deployment)
        prefix, version = ensure.call_args.args[:2]
        self.assertEqual(prefix, Path(self.tmp.name) / '.local/share/wysun/qml-runtime')
        self.assertEqual(version, qml_runtime.wanted_version(ROOT / 'manifests/runtime.json'))

    def test_network_failure_is_a_warning_not_an_abort(self):
        env = {k: v for k, v in os.environ.items() if k != 'WYSUN_SKIP_RUNTIME'}
        error = subprocess.CalledProcessError(1, ['pip'])
        err = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(qml_runtime, 'ensure', side_effect=error), \
                contextlib.redirect_stderr(err):
            wayland.ensure_qml_runtime(self.deployment)      # must not raise
        self.assertIn('qml-runtime', err.getvalue())

    def test_up_to_date_runtime_is_not_announced_as_a_stage(self):
        env = {k: v for k, v in os.environ.items() if k != 'WYSUN_SKIP_RUNTIME'}
        with patch.dict(os.environ, env, clear=True), patch.object(qml_runtime, 'needs_update', return_value=False):
            wayland.ensure_qml_runtime(self.deployment)
        self.assertEqual(self.deployment.stages, [])


class QmlSuiteRunner(unittest.TestCase):
    """Runs tests/qml with the venv Python (the system PySide6 has no QtQuick). Skipped, with a warning, without the venv."""

    def test_qml_suites_with_venv_python(self):
        import qml.support as support
        python = support.venv_python()
        if python is None:
            sys.stderr.write('\nAVISO: sin qml-runtime (venv de PySide6 6.9.x); se omiten las pruebas QML. '
                             'Créalo con: python3 installer/qml_runtime.py\n')
            self.skipTest('no qml-runtime venv')
        done = support.run_in_venv(['-m', 'unittest', 'discover', '-s', 'tests/qml', '-t', 'tests', '-p', 'check_*.py'])
        self.assertEqual(done.returncode, 0, done.stdout[-4000:] + done.stderr[-4000:])

    def test_missing_venv_is_reported_as_none(self):
        import qml.support as support
        with patch.dict(os.environ, {'WYSUN_QML_RUNTIME': '/no/existe', 'HOME': '/no/existe'}):
            self.assertIsNone(support.venv_python())


if __name__ == '__main__':
    unittest.main()
