"""Phase-5 lock contracts: presentation policy, PAM packaging and mocked QML.

Nothing here acquires a session lock, reads a real credential or touches
/etc/pam.d: PAM runs against a throw-away service directory with a synthetic
secret, and QML loads under an offscreen platform with temporary HOME/XDG.
"""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

SHELL = Path(__file__).resolve().parents[1]
LOCK = SHELL / 'modules/lock'
ROOT = SHELL.parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
PYTHON = shutil.which('python3') or '/usr/bin/python3'
SECRET = 'wysun-synthetic-secret'
VARIANTS = '[["space-black","space-black"],["space-black","tokyo"],["space-black","severance"],["fluent","light"],["fluent","dark"]]'


def qml_url(path):
    return 'file:' + str(path).replace('%', '%25').replace(' ', '%20').replace('#', '%23')


def run_quickshell(folder, qml, timeout=40, extra=None):
    path = folder / 'fixture.qml'
    path.write_text(qml)
    env = {**os.environ, 'HOME': str(folder), 'XDG_CONFIG_HOME': str(folder),
           'XDG_DATA_HOME': str(folder), 'XDG_STATE_HOME': str(folder),
           'XDG_CACHE_HOME': str(folder), 'XDG_RUNTIME_DIR': str(folder),
           'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
           'DISPLAY': '', 'WAYLAND_DISPLAY': '',
           'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(folder) + '/no-session-bus', **(extra or {})}
    result = subprocess.run(['quickshell', '-p', str(path)], env=env, capture_output=True, text=True, timeout=timeout)
    return result, result.stdout + result.stderr


def policy(expression):
    source = (LOCK / 'LockPolicy.js').read_text().replace('.pragma library', '')
    return json.loads(subprocess.check_output(
        ['node', '-e', source + '\nconsole.log(JSON.stringify(' + expression + '))'], text=True))


class LockPolicyTests(unittest.TestCase):
    def test_state_texts_never_reveal_the_secret_or_account(self):
        self.assertEqual(policy('text("locked","")'), 'Introduce tu contraseña')
        self.assertEqual(policy('text("authenticating","")'), 'Comprobando…')
        self.assertIn('incorrecta', policy('text("failed","")'))
        self.assertIn('Demasiados', policy('text("maxtries","")'))
        self.assertIn('PAM', policy('text("error","")'))
        self.assertIn('x', policy('text("error","x")'))
        self.assertEqual([policy('isError("%s")' % s) for s in ('locked', 'authenticating', 'failed', 'maxtries', 'error', 'success')],
                         [False, False, True, True, True, False])

    def test_key_buffer_rules(self):
        self.assertEqual(policy('key("ab",65,"c",false)'), {'buffer': 'abc', 'submit': False})
        self.assertEqual(policy('key("ab",13,"\\r",false)'), {'buffer': 'ab', 'submit': True})
        self.assertEqual(policy('key("ab",8,"",false)')['buffer'], 'a')
        self.assertEqual(policy('key("ab",8,"",true)')['buffer'], '')
        self.assertEqual(policy('key("ab",27,"",false)')['buffer'], '')
        # Control sequences, ctrl shortcuts and non-printable text never enter the buffer.
        self.assertEqual(policy('key("ab",65,"\\u0001",true)')['buffer'], 'ab')
        self.assertEqual(policy('key("ab",0,"\\u007f",false)')['buffer'], 'ab')
        self.assertEqual(policy('key("ab",0,"",false)')['buffer'], 'ab')
        self.assertEqual(policy('key("ab",0,12,false)')['buffer'], 'ab')

    def test_buffer_is_bounded_and_mask_has_no_content(self):
        long = 'x' * 256
        self.assertEqual(policy('key("%s",65,"y",false)' % long)['buffer'], long)
        self.assertEqual(policy('mask(3)'), '•••')
        self.assertEqual(policy('mask(0)'), '')
        self.assertEqual(len(policy('mask(100000)')), 256)

    def test_layout_fits_tiny_and_large_outputs(self):
        for width, height in ((100, 60), (1280, 720), (3840, 2160), (0, 0)):
            layout = policy('layout(%d,%d)' % (width, height))
            self.assertLessEqual(layout['width'], max(0, width - 48) or 0.0001 + layout['width'])
            self.assertGreaterEqual(layout['scale'], 0.7)
            self.assertLessEqual(layout['scale'], 1.25)
        self.assertEqual(policy('layout("x",null)')['scale'], 1)

    def test_media_is_opt_in_only(self):
        for value, expected in ((True, True), ('1', True), (False, False), ('true', False), (1, False), (None, False), ('0', False)):
            self.assertEqual(policy('mediaEnabled(%s)' % json.dumps(value)), expected)


class LockSourceContractTests(unittest.TestCase):
    def test_pam_service_only_delegates_to_the_system_login_service(self):
        lines = [line for line in (SHELL / 'config/pam.d/wysun-lock').read_text().splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        self.assertEqual(lines, ['auth include /etc/pam.d/login'])

    def test_no_forbidden_upstream_backend_or_unlock_ipc(self):
        # Comments may name excluded upstream pieces; code may not use them.
        sources = '\n'.join(re.sub(r'//.*', '', path.read_text()) for path in list(LOCK.glob('*.qml')) + [SHELL / 'lock.qml'])
        for forbidden in ('IpcHandler', 'Screencopy', 'ScreencopyView', 'Cava', 'cava', 'Visualiser',
                          'Quickshell.Io.Process', 'onHovered: unlock'):
            self.assertNotIn(forbidden, sources)
        # The only process launched is the readiness marker writer in LockRoot.
        for path in LOCK.glob('*.qml'):
            if path.name != 'LockRoot.qml':
                self.assertNotRegex(path.read_text(), r'\bProcess\s*\{', path.name)
        self.assertNotIn('console.log', sources)
        self.assertNotRegex(sources, r'console\.\w+\([^)]*(password|buffer|pending)')

    def test_unlock_only_through_pam_success(self):
        root = (LOCK / 'LockRoot.qml').read_text()
        self.assertEqual(len(re.findall(r'locked\s*=\s*false', root)), 1)
        self.assertEqual(len(re.findall(r'\.unlock\(', root)), 0)
        self.assertIn('onAuthenticated: root.unlockNow()', root)
        self.assertIn('if (!lock.secure || !lock.locked) return;', root)

    def test_derived_sources_keep_gpl_notice_and_origin_commit(self):
        # LockTheme.qml is original Wysun code (token loader) and carries no upstream notice.
        for path in list(LOCK.glob('*.qml')) + [LOCK / 'LockPolicy.js', SHELL / 'lock.qml']:
            if path.name == 'LockTheme.qml':
                continue
            text = path.read_text()[:1500]
            self.assertIn('GPL-3.0', text, path.name)
            self.assertIn('LICENSES/GPL-3.0.txt', text, path.name)

    def test_no_literal_colours_in_lock_ui(self):
        for path in LOCK.glob('*.qml'):
            self.assertNotRegex(path.read_text(), r'#[0-9a-fA-F]{3,8}\b|Qt\.rgba|"(white|black|red|green|blue)"', path.name)


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell 0.3 is required for isolated QML loading')
class LockQmlTests(unittest.TestCase):
    def pam_directory(self, folder):
        service = folder / 'pam.d'
        service.mkdir()
        checker = folder / 'check.py'
        checker.write_text('import sys\nsys.exit(0 if sys.stdin.buffer.read().rstrip(b"\\0") == %r else 1)\n' % SECRET.encode())
        # pam_exec reports a failing command as a system error; map it to the
        # ordinary authentication failure real stacks produce (pam_deny).
        (service / 'inner').write_text('auth [success=1 default=ignore] pam_exec.so expose_authtok quiet %s %s\n'
                                       'auth requisite pam_deny.so\nauth required pam_permit.so\n' % (PYTHON, checker))
        packaged = (SHELL / 'config/pam.d/wysun-lock').read_text()
        self.assertIn('/etc/pam.d/login', packaged)
        (service / 'wysun-lock').write_text(packaged.replace('/etc/pam.d/login', str(service / 'inner')))
        return service

    def test_pam_client_rejects_wrong_secret_then_accepts_the_right_one(self):
        with tempfile.TemporaryDirectory(prefix='wysun-lock-pam-') as temporary:
            folder = Path(temporary)
            service = self.pam_directory(folder)
            qml = '''import QtQuick
import Quickshell
import "%s" as LockModule
ShellRoot {
    id: root
    property int step: 0
    property bool done: false
    LockModule.LockAuth {
        id: auth
        secure: root.step > 0
        configDirectory: "%s"
        onAuthenticated: {
            if (root.step !== 3) console.error("FIXTURE_FAIL authenticated too early");
            else { console.info("FIXTURE_PASS pam"); }
            Qt.quit();
        }
    }
    function fail(message) { console.error("FIXTURE_FAIL " + message); Qt.quit(); }
    Timer {
        interval: 300; running: true; repeat: true
        onTriggered: {
            if (root.step === 0) { if (auth.submit(%s)) root.fail("insecure session accepted a secret"); root.step = 1; }
            else if (root.step === 1) { if (auth.state !== "locked") root.fail("state after secure " + auth.state); if (!auth.submit("wrong")) root.fail("submit refused"); root.step = 2; }
            else if (root.step === 2 && auth.state === "failed") { if (auth.attempts !== 1) root.fail("attempts"); root.step = 3; if (!auth.submit(%s)) root.fail("second submit refused"); }
            else if (root.step === 2 && auth.state === "authenticating") return;
            else if (root.step === 2) root.fail("unexpected state " + auth.state);
            else if (root.step === 3 && auth.state === "error") root.fail("pam error " + auth.detail);
        }
    }
}''' % (qml_url(LOCK), service, json.dumps(SECRET), json.dumps(SECRET))
            result, output = run_quickshell(folder, qml)
            self.assertEqual(result.returncode, 0, output)
            self.assertIn('FIXTURE_PASS pam', output, output)
            self.assertNotIn('FIXTURE_FAIL', output)
            self.assertNotIn(SECRET, output)
            self.assertNotIn('wrong', output.replace('FIXTURE_FAIL', ''))

    def test_panel_and_media_in_five_presets_without_media_by_default(self):
        with tempfile.TemporaryDirectory(prefix='wysun-lock-ui-') as temporary:
            folder = Path(temporary)
            qml = '''import QtQuick
import Quickshell
import "%s" as LockModule
import "%s" as Wysun
ShellRoot {
    id: root
    property int index: 0
    property var spec: (%s)
    property var variants: %s
    property var submitted: []
    FontLoader { source: "%s"; onStatusChanged: if (status === FontLoader.Ready) Wysun.Appearance.refreshFonts() }
    FloatingWindow {
        implicitWidth: 900; implicitHeight: 600; visible: true
        LockModule.LockPanel { id: big; anchors.fill: parent; secure: true; onSubmitted: function(p) { root.submitted.push(p); } }
    }
    FloatingWindow {
        implicitWidth: 100; implicitHeight: 60; visible: true
        LockModule.LockPanel { id: tiny; anchors.fill: parent; secure: false; state: "failed"; attempts: 3 }
    }
    function check(condition, message) { if (!condition) { console.error("FIXTURE_FAIL " + message); Qt.quit(); } }
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (root.index < root.variants.length) {
                var selection = root.variants[root.index];
                Wysun.Appearance.apply(root.spec, {style: selection[0], variant: selection[1]});
                root.index++;
                return;
            }
            check(big.layout.width <= 520 * 1.25, "column bounded");
            check(tiny.layout.width <= 52, "tiny column fits");
            big.buffer = %s;
            big.submit();
            check(big.buffer === "", "buffer cleared after submit");
            check(root.submitted.length === 1 && root.submitted[0] === %s, "secret delivered once");
            big.buffer = "x";
            tiny.buffer = "y"; tiny.submit();
            check(root.submitted.length === 1, "insecure panel does not submit");
            big.authenticating = true; big.buffer = "z"; big.submit();
            check(root.submitted.length === 1, "no submit while authenticating");
            console.info("FIXTURE_PASS lock ui");
            Qt.quit();
        }
    }
}''' % (qml_url(LOCK), qml_url(SHELL), (SHELL / 'wysun_theme.json').read_text(), VARIANTS,
        qml_url(SHELL / 'assets/fonts/Rubik-Variable.ttf'), json.dumps(SECRET), json.dumps(SECRET))
            result, output = run_quickshell(folder, qml)
            self.assertEqual(result.returncode, 0, output)
            self.assertIn('FIXTURE_PASS lock ui', output, output)
            for marker in ('FIXTURE_FAIL', 'ReferenceError', 'TypeError', 'Mpris'):
                self.assertNotIn(marker, output)

    def test_unsupported_compositor_never_publishes_readiness(self):
        # No Wayland socket: ext-session-lock is unavailable, so the process
        # must not claim a lock. It exits by itself with a non-zero status
        # (wysun-lock then falls back to swaylock).
        with tempfile.TemporaryDirectory(prefix='wysun-lock-root-') as temporary:
            folder = Path(temporary)
            ready = folder / 'ready'
            ready.touch()
            env = {**os.environ, 'HOME': temporary, 'XDG_CONFIG_HOME': temporary, 'XDG_DATA_HOME': temporary,
                   'XDG_STATE_HOME': temporary, 'XDG_CACHE_HOME': temporary, 'XDG_RUNTIME_DIR': temporary,
                   'QT_QPA_PLATFORM': 'offscreen', 'DISPLAY': '', 'WAYLAND_DISPLAY': '',
                   'WYSUN_SHELL_ROOT': str(SHELL), 'WYSUN_LOCK_READY': str(ready),
                   'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + temporary + '/no-session-bus'}
            result = subprocess.run(['quickshell', '-p', str(SHELL / 'lock.qml')], env=env,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertEqual(ready.read_text(), '')


class QmlBackendSelectionTests(unittest.TestCase):
    """bin/wysun-lock with fixture swaylock/quickshell/systemctl executables."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.log = self.folder / 'calls.jsonl'
        (self.folder / 'runtime').mkdir()
        for executable in ('swaylock', 'systemctl', 'quickshell'):
            path = self.folder / executable
            path.write_text('#!' + PYTHON + '\nimport json, os, sys, time\n'
                            'name = os.path.basename(sys.argv[0])\n'
                            'with open(os.environ["FIXTURE_LOG"], "a") as f: f.write(json.dumps([name] + sys.argv[1:]) + "\\n")\n'
                            'if name == "quickshell":\n'
                            '    mode = os.environ.get("FIXTURE_QS", "ready")\n'
                            '    if mode == "ready": open(os.environ["WYSUN_LOCK_READY"], "w").write("locked")\n'
                            '    if mode == "hang": time.sleep(8)\n'
                            '    sys.exit(int(os.environ.get("FIXTURE_QS_CODE", "0")))\n'
                            'sys.exit(0)\n')
            path.chmod(0o755)
        self.env = {'PATH': str(self.folder) + ':/usr/bin:/bin', 'HOME': str(self.folder),
                    'XDG_CONFIG_HOME': str(self.folder / 'config'), 'XDG_RUNTIME_DIR': str(self.folder / 'runtime'),
                    'XDG_SESSION_TYPE': 'wayland', 'WAYLAND_DISPLAY': 'fixture-not-a-socket',
                    'FIXTURE_LOG': str(self.log), 'WYSUN_SHELL_ROOT': str(SHELL)}

    def invoke(self, *args, **environment):
        result = subprocess.run([str(ROOT / 'bin/wysun-lock'), *args], env={**self.env, **environment},
                                capture_output=True, text=True, timeout=30)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def names(self, calls):
        return [call[0] for call in calls]

    def test_default_and_unknown_backends_use_swaylock_only(self):
        for environment in ({}, {'WYSUN_LOCK_BACKEND': 'bogus'}, {'WYSUN_LOCK_BACKEND': 'QML;rm'}):
            if self.log.exists():
                self.log.unlink()
            result, calls = self.invoke(**environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.names(calls), ['swaylock'])

    def test_config_file_selects_qml_and_environment_wins(self):
        (self.folder / 'config/orbit').mkdir(parents=True)
        (self.folder / 'config/orbit/lock.json').write_text('{"backend": "qml", "media": true}')
        result, calls = self.invoke()
        self.assertEqual(self.names(calls), ['quickshell'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.log.unlink()
        result, calls = self.invoke(WYSUN_LOCK_BACKEND='swaylock')
        self.assertEqual(self.names(calls), ['swaylock'])

    def test_qml_ready_marker_means_locked_and_suspend_follows_it(self):
        result, calls = self.invoke('--suspend', WYSUN_LOCK_BACKEND='qml')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.names(calls), ['quickshell', 'systemctl'])
        self.assertEqual(calls[0][:2], ['quickshell', '-p'])
        self.assertTrue(calls[0][2].endswith('/lock.qml'))
        self.assertEqual(os.listdir(self.folder / 'runtime'), [], 'readiness marker is removed')

    def test_qml_failure_before_ready_falls_back_to_swaylock_without_suspending_early(self):
        result, calls = self.invoke('--suspend', WYSUN_LOCK_BACKEND='qml', FIXTURE_QS='fail', FIXTURE_QS_CODE='3')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.names(calls), ['quickshell', 'swaylock', 'systemctl'])
        self.assertEqual(os.listdir(self.folder / 'runtime'), [])
        self.log.unlink()
        result, calls = self.invoke(WYSUN_LOCK_BACKEND='qml', FIXTURE_QS='fail', FIXTURE_QS_CODE='3')
        self.assertEqual(self.names(calls), ['quickshell', 'swaylock'])

    def test_unconfirmed_but_alive_qml_never_gets_a_second_locker_or_suspend(self):
        result, calls = self.invoke('--suspend', WYSUN_LOCK_BACKEND='qml', FIXTURE_QS='hang', WYSUN_LOCK_WAIT='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.names(calls), ['quickshell'])

    def test_missing_quickshell_or_shell_files_fall_back(self):
        (self.folder / 'quickshell').unlink()
        # /usr/bin is kept out of the lookup of quickshell by deleting the fixture;
        # a distribution-installed one is hidden with a restricted PATH.
        result, calls = self.invoke(WYSUN_LOCK_BACKEND='qml', PATH=str(self.folder))
        self.assertEqual(self.names(calls), ['swaylock'])
        self.log.unlink()
        (self.folder / 'quickshell').write_text('#!/bin/sh\nexit 0\n')
        (self.folder / 'quickshell').chmod(0o755)
        result, calls = self.invoke(WYSUN_LOCK_BACKEND='qml', WYSUN_SHELL_ROOT=str(self.folder / 'missing'), PATH=str(self.folder))
        self.assertEqual(self.names(calls), ['swaylock'])


if __name__ == '__main__':
    unittest.main()
