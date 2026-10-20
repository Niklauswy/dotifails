"""Isolated phase-5 contracts; never acquires a real lock or uses private media."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SHELL = Path(__file__).resolve().parents[1]
MODULE = SHELL / 'modules/background'
ROOT = SHELL.parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
PYTHON = shutil.which('python3') or '/usr/bin/python3'


def qml_url(path):
    """QML import/FontLoader URL for an absolute path (``import "/x"`` is rejected)."""
    return 'file:' + str(path).replace('%', '%25').replace(' ', '%20').replace('#', '%23')


class BackgroundPolicyTests(unittest.TestCase):
    def evaluate(self, expression):
        source = (MODULE / 'BackgroundPolicy.js').read_text().replace('.pragma library', '')
        return json.loads(subprocess.check_output(['node', '-e', source + '\nconsole.log(JSON.stringify(' + expression + '))'], text=True))

    def test_clock_is_opt_in_and_rejects_truthy_strings(self):
        for data in ({}, {'wallpaper': None}, {'wallpaper': {'clock': {'enabled': 'true'}}}):
            self.assertFalse(self.evaluate('clockSettings(%s,"DP-1",false).enabled' % json.dumps(data)))

    def test_local_fullscreen_and_hotplug_do_not_disable_other_outputs(self):
        data = {'wallpaper': {'clock': {'enabled': True, 'position': 'bottom-right'},
                             'monitors': {'DP-1': {'clock': {'position': 'middle-center'}},
                                          'DP-2': {'clock': {'enabled': False}}}}}
        encoded = json.dumps(data)
        self.assertFalse(self.evaluate('clockSettings(%s,"DP-1",true).enabled' % encoded))
        self.assertTrue(self.evaluate('clockSettings(%s,"eDP-1",false).enabled' % encoded))
        self.assertFalse(self.evaluate('clockSettings(%s,"DP-2",false).enabled' % encoded))
        self.assertEqual(self.evaluate('clockSettings(%s,"DP-1",false).position' % encoded), 'middle-center')
        # Unplug/replug is stateless and recomputes that output's preferences.
        self.assertEqual(self.evaluate('clockSettings(%s,"DP-1",false)' % encoded),
                         {'enabled': True, 'position': 'middle-center'})

    def test_local_disable_and_invalid_position(self):
        data = {'wallpaper': {'clock': {'enabled': True}, 'monitors': {'DP': {'clock': {'enabled': False, 'position': 'bad'}}}}}
        self.assertEqual(self.evaluate('clockSettings(%s,"DP",false)' % json.dumps(data)), {'enabled': False, 'position': 'top-left'})

    def test_only_local_images_and_correct_url_escaping(self):
        self.assertEqual(self.evaluate('localUrl("/tmp/photo #1?%.png")'), 'file:///tmp/photo%20%231%3F%25.png')
        for value in ('https://example.test/a', 'file:///tmp/a', '~/a', 'data:image/png,a', '', '/tmp/a\n.png'):
            self.assertEqual(self.evaluate('localUrl(%s)' % json.dumps(value)), '')

    def test_all_clock_positions_fit_tiny_and_normal_outputs(self):
        for width, height, clock_w, clock_h in ((1920, 1080, 420, 160), (100, 60, 100, 60)):
            for vertical in ('top', 'middle', 'bottom'):
                for horizontal in ('left', 'center', 'right'):
                    point = self.evaluate('position(%d,%d,%d,%d,96,"%s-%s")' % (width, height, clock_w, clock_h, vertical, horizontal))
                    self.assertGreaterEqual(point['x'], 0)
                    self.assertGreaterEqual(point['y'], 0)
                    self.assertLessEqual(point['x'] + clock_w, width)
                    self.assertLessEqual(point['y'] + clock_h, height)


class LockCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.log = self.folder / 'calls.jsonl'
        for executable in ('swaylock', 'systemctl'):
            path = self.folder / executable
            path.write_text('#!' + PYTHON + '\nimport json, os, sys\n'
                            'with open(os.environ["FIXTURE_LOG"], "a") as f: f.write(json.dumps(sys.argv)+"\\n")\n'
                            'sys.exit(int(os.environ.get("FIXTURE_FAIL", "0")) if "swaylock" in sys.argv[0] else 0)\n')
            path.chmod(0o755)
        self.env = {'PATH': str(self.folder) + ':/usr/bin:/bin', 'HOME': str(self.folder),
                    'XDG_CONFIG_HOME': str(self.folder / 'config'), 'XDG_STATE_HOME': str(self.folder / 'state'),
                    'XDG_RUNTIME_DIR': str(self.folder / 'runtime'), 'XDG_SESSION_TYPE': 'wayland',
                    'WAYLAND_DISPLAY': 'fixture-not-a-socket', 'FIXTURE_LOG': str(self.log)}

    def invoke(self, *args, **environment):
        result = subprocess.run([str(ROOT / 'bin/wysun-lock'), *args], env={**self.env, **environment}, capture_output=True, text=True)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def test_lock_is_private_and_never_suspends_by_default(self):
        result, calls = self.invoke(WYSUN_LOCK_COLOR='abcdef')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)
        args = calls[0]
        self.assertEqual(args[args.index('--config') + 1], '/dev/null')
        self.assertEqual(args[args.index('--color') + 1], 'abcdef')
        self.assertIn('--daemonize', args)
        self.assertNotIn('--image', args)
        self.assertNotIn('--indicator-idle-visible', args)

    def test_suspend_requires_successful_acquisition(self):
        result, calls = self.invoke('--suspend', FIXTURE_FAIL='9')
        self.assertEqual(result.returncode, 9)
        self.assertEqual(len(calls), 1)
        self.log.unlink()
        result, calls = self.invoke('--suspend')
        self.assertEqual(result.returncode, 0)
        self.assertEqual([Path(call[0]).name for call in calls], ['swaylock', 'systemctl'])
        self.assertEqual(calls[1][1:], ['suspend'])

    def test_invalid_argv_and_non_wayland_never_acquire_or_suspend(self):
        for args, environment in ((('--bad',), {}), (('--suspend', 'extra'), {}), ((), {'XDG_SESSION_TYPE': 'x11'}), ((), {'WAYLAND_DISPLAY': ''})):
            result, calls = self.invoke(*args, **environment)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(calls)

    def test_valid_palette_and_invalid_tokens_are_not_shell_code(self):
        result, calls = self.invoke(WYSUN_LOCK_ACCENT='aabbcc', WYSUN_LOCK_DANGER='ff0011',
                                  WYSUN_LOCK_TEXT='$(touch nope)', WYSUN_LOCK_RADIUS='999999',
                                  WYSUN_LOCK_THICKNESS='2', WYSUN_LOCK_FONT_SIZE='0')
        self.assertEqual(result.returncode, 0)
        self.assertIn('--ring-ver-color', calls[0])
        self.assertIn('--ring-wrong-color', calls[0])
        self.assertIn('--indicator-thickness', calls[0])
        self.assertNotIn('--indicator-radius', calls[0])
        self.assertNotIn('--font-size', calls[0])
        self.assertNotIn('$(touch nope)', calls[0])


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell 0.3 is required for isolated QML loading')
class BackgroundQmlTests(unittest.TestCase):
    def test_real_qml_synthetic_images_clock_idle_fullscreen_hotplug_and_wake(self):
        # Run only an offscreen FloatingWindow, with no compositor/session bus.
        # The synthetic PNG and every QML/cache/config file live under this HOME.
        with tempfile.TemporaryDirectory(prefix='wysun-background-qml-') as temporary:
            folder = Path(temporary)
            from PySide6.QtGui import QImage, QColor
            image = QImage(64, 64, QImage.Format_RGB32)
            image.fill(QColor('cyan'))  # synthetic fixture, not a UI colour
            self.assertTrue(image.save(str(folder / 'synthetic #1.png')))
            qml = '''import QtQuick
import Quickshell
import "%s" as BackgroundModule
import "%s" as Wysun
ShellRoot {
    id: root
    property int phase: 0
    property var spec: (%s)
    property var variants: [["space-black","space-black"],["space-black","tokyo"],["space-black","severance"],["fluent","light"],["fluent","dark"]]
    property int variantIndex: 0
    QtObject {
        id: prefs
        property string home: %s
        property var environment: ({wallpaper:{default:home + "/synthetic #1.png",clock:{enabled:true,position:"bottom-right"}}})
    }
    FontLoader { source: "%s"; onStatusChanged: if (status === FontLoader.Ready) Wysun.Appearance.refreshFonts() }
    FloatingWindow {
        implicitWidth: 720; implicitHeight: 480; visible: true
        BackgroundModule.Background { id: first; anchors.fill: parent; preferences: prefs; outputName: "DP-1" }
        BackgroundModule.Background { id: second; width: 160; height: 90; preferences: prefs; outputName: "eDP-1" }
    }
    function check(condition, message) { if (!condition) { console.error("FIXTURE_FAIL",message); Qt.quit(); } }
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (root.phase === 0) {
                var selection = root.variants[root.variantIndex];
                Wysun.Appearance.apply(root.spec, {style:selection[0],variant:selection[1]});
                root.variantIndex++;
                if (root.variantIndex < root.variants.length) return;
                check(first.children[0].status === Image.Ready, "synthetic wallpaper decoded");
                check(first.children[1].item !== null, "clock QML loaded");
                check(second.children[1].item !== null, "small output clock loaded");
                first.fullscreen = true;
            } else if (root.phase === 1) {
                check(first.children[1].item === null, "fullscreen unloads local clock/time service");
                check(second.children[1].item !== null, "other output still active");
                first.fullscreen = false;
                second.outputName = "DP-replugged";
            } else if (root.phase === 2) {
                check(first.children[1].item !== null, "wake exits fullscreen and reloads clock");
                check(second.clockSettings.enabled, "hotplug recomputes local settings");
                prefs.environment = {wallpaper:{default:prefs.home + "/missing.png"}};
            } else if (root.phase === 3) {
                check(first.children[1].item === null, "opt-out destroys clock");
                check(first.children[0].status === Image.Error, "missing image uses canvas");
                prefs.environment = {wallpaper:{default:"https://invalid.test/private.png"}};
            } else {
                check(first.children[0].status === Image.Null, "remote image rejected");
                console.info("FIXTURE_PASS backgrounds, five presets, fullscreen, hotplug, idle/wake, privacy");
                Qt.quit();
            }
            root.phase++;
        }
    }
}''' % (qml_url(MODULE), qml_url(SHELL),
        (SHELL / 'wysun_theme.json').read_text(), json.dumps(str(folder)),
        qml_url(SHELL / 'assets/fonts/Rubik-Variable.ttf'))
            path = folder / 'fixture.qml'
            path.write_text(qml)
            env = {**os.environ, 'HOME': temporary, 'XDG_CONFIG_HOME': temporary,
                   'XDG_DATA_HOME': temporary, 'XDG_STATE_HOME': temporary,
                   'XDG_CACHE_HOME': temporary, 'XDG_RUNTIME_DIR': temporary,
                   'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
                   'DISPLAY': '', 'WAYLAND_DISPLAY': '',
                   'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + temporary + '/no-session-bus'}
            result = subprocess.run(['quickshell', '-p', str(path)], env=env, capture_output=True, text=True, timeout=30)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn('FIXTURE_PASS', output, output)
            self.assertNotIn('FIXTURE_FAIL', output)
            self.assertNotIn('ReferenceError', output)
            self.assertNotIn('TypeError', output)


if __name__ == '__main__':
    unittest.main()
