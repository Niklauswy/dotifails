"""The camera in the recording flow: remembered for the recording in progress, previewed before it starts, marked by a solid
shape while it runs. The geometry is kept equal to the renderer's by tests/qml/check_shell_camera_math.py. Static checks
of the QML plus ``ProbeTests`` (offscreen Quickshell, needs ``WYSUN_TEST_RUNTIME``) for placement and drag-to-corner."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / 'apps/shell'


def source(relative):
    return (SHELL / relative).read_text()


def function_body(text, name):
    start = text.index(f'function {name}(')
    brace = text.index('{', start)
    depth = 0
    for index in range(brace, len(text)):
        depth += {'{': 1, '}': -1}.get(text[index], 0)
        if depth == 0:
            return text[brace:index + 1]
    raise AssertionError(name)


class FlowTests(unittest.TestCase):
    def test_the_recorder_remembers_the_camera_of_the_recording_in_progress(self):
        text = source('services/Recorder.qml')
        self.assertIn('property bool cameraActive', text)
        self.assertIn('property var cameraActiveStyle', text)
        launch = function_body(text, 'launch')
        self.assertIn('cameraActive = pending.camera;', launch)
        self.assertIn('cameraActiveStyle = Object.assign({}, cameraStyle);', launch)
        self.assertLess(launch.index('pending = {'), launch.index('JSON.stringify({ screen: output'),
                        'the state file is written once the request (and its camera) is known')
        self.assertIn('camera: pending.camera', launch)
        self.assertIn('cameraStyle: cameraActiveStyle', launch)
        restore = text[text.index('id: restore'):text.index('id: prefs')]
        self.assertIn('root.cameraActive = saved.camera === true;', restore)
        self.assertIn('root.cameraActiveStyle = saved.cameraStyle', restore)
        status = text[text.index('id: status'):text.index('id: control')]
        self.assertIn('root.cameraActive = false;', status)

    def test_the_picker_previews_the_camera_only_while_choosing_options(self):
        picker = source('modules/areapicker/Picker.qml')
        self.assertIn('import qs.components.camera', picker)
        block = picker[picker.index('CameraPreview {'):]
        block = block[:block.index('\n    }\n') + 7]
        self.assertIn('root.active && root.phase === "record" && Recorder.camera && Recorder.cameras.length > 0', block)
        self.assertIn('area: root.session.selection', block)
        self.assertIn('live: visible', block)

    def test_the_camera_is_released_before_the_recorder_starts(self):
        body = function_body(source('modules/areapicker/Session.qml'), 'startRecording')
        self.assertLess(body.index('phase = "done"'), body.index('Recorder.launch('),
                        'the preview ends with the phase, so the camera is free when the worker opens it')

    def test_the_marker_is_part_of_the_shell_and_covers_whole_output_recordings_too(self):
        self.assertIn('CameraMarker {}', source('shell.qml'))
        marker = source('components/camera/CameraMarker.qml')
        self.assertIn('Recorder.wholeOutput ? Qt.rect(0, 0, modelData.width, modelData.height) : Recorder.region', marker)
        self.assertIn('Recorder.active && Recorder.cameraActive', marker)
        self.assertIn('mask: Region {}', marker)
        self.assertNotIn('!Recorder.wholeOutput', marker)

    def test_a_camera_that_cannot_start_says_so(self):
        text = source('components/camera/CameraPreview.qml')
        self.assertIn('onErrorOccurred', text)
        self.assertIn('videocam_off', text)


@unittest.skipUnless(os.environ.get('WYSUN_TEST_RUNTIME'), 'needs WYSUN_TEST_RUNTIME (a built shell runtime)')
class ProbeTests(unittest.TestCase):
    def probe(self):
        runtime = Path(os.environ['WYSUN_TEST_RUNTIME']).expanduser()
        with tempfile.TemporaryDirectory(prefix='wysun-camera-') as tmp:
            home = Path(tmp)
            shell = home / 'shell'
            (shell / 'services').mkdir(parents=True)
            (shell / 'services/Colours.qml').symlink_to(SHELL / 'services/Colours.qml')
            (shell / 'services/Wallpapers.qml').write_text(
                'pragma Singleton\nimport Quickshell\nSingleton { property string current: "" }\n')
            (shell / 'services/Recorder.qml').write_text(
                'pragma Singleton\nimport Quickshell\nSingleton {\n'
                '    property bool camera: true\n    property string cameraDevice: ""\n    property var cameras: []\n'
                '    property var cameraStyle: ({ shape: "circle", size: "medium", corner: "bottom-right" })\n'
                '    function setPref(key, value) { console.info("SETPREF " + key + " " + value); }\n}\n')
            for sub in ('utils', 'components'):
                (shell / sub).symlink_to(SHELL / sub)
            (shell / 'shell.qml').write_text((ROOT / 'tests/shell_camera_probe.qml').read_text())
            env = dict(os.environ, HOME=tmp, QT_QPA_PLATFORM='offscreen', WAYLAND_DISPLAY='',
                       HYPRLAND_INSTANCE_SIGNATURE='', WYSUN_LIB_DIR=str(runtime / 'shell/lib/wysun'),
                       QML_IMPORT_PATH=os.pathsep.join([str(runtime / 'shell/lib/qt6/qml'),
                                                        str(runtime / 'deps/lib/qt6/qml')]))
            for key, sub in (('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'), ('XDG_STATE_HOME', 'state'),
                             ('XDG_CACHE_HOME', 'cache'), ('XDG_RUNTIME_DIR', 'run')):
                (home / sub).mkdir(mode=0o700)
                env[key] = str(home / sub)
            env['XDG_DATA_DIRS'] = str(home / 'none')
            (home / 'data/wysun/theme').mkdir(parents=True)
            (home / 'data/wysun/theme/tokens.json').write_text((ROOT / 'apps/python/wysun_core/tokens.json').read_text())
            (home / 'config/wysun').mkdir(parents=True)
            (home / 'config/wysun/theme.json').write_text(json.dumps({'mode': 'dark'}))
            try:
                result = subprocess.run([str(runtime / 'quickshell/bin/quickshell'), '-p', str(shell)], env=env, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, cwd=tmp)
            except subprocess.TimeoutExpired as late:
                raise AssertionError('the probe did not finish:\n' + (late.stdout or b'').decode(errors='replace')[-3000:])
        return result.stdout

    def test_the_preview_and_the_marker_sit_where_the_renderer_puts_the_camera(self):
        sys.path[:0] = [str(ROOT / 'apps/recorder'), str(ROOT / 'apps/python')]
        from wysun_recorder.render import camera_overlay
        out = self.probe()
        line = next((l for l in out.splitlines() if 'CAMERA ' in l), None)
        self.assertIsNotNone(line, out)
        got = json.loads(line.split('CAMERA ', 1)[1])
        _, bx, by = camera_overlay(SimpleNamespace(size='medium', shape='circle', corner='bottom-right'), 800, 450)
        tall = max(2, int(450 * .28) // 2 * 2)
        self.assertEqual(got['preview'], {'x': 100 + bx, 'y': 50 + by, 'width': tall, 'height': tall},
                         'the preview is the bubble, inside the selected area')
        _, mx, my = camera_overlay(SimpleNamespace(size='large', shape='rounded', corner='top-left'), 800, 450)
        high = max(2, int(450 * .38) // 2 * 2)
        wide = max(2, int(high * 4 / 3) // 2 * 2)
        inset = 2
        self.assertEqual(got['marker'], {'x': 100 + mx + inset, 'y': 50 + my + inset, 'width': wide - 2 * inset, 'height': high - 2 * inset},
                         'the marker is a little smaller than the bubble so no edge peeks out')
        self.assertEqual(got['radius'], max(4, high // 8) - inset)
        self.assertTrue(got['dragging'])
        self.assertNotEqual(got['during'], got['preview'], 'the bubble follows the pointer while dragged')
        self.assertEqual(got['afterMove'], got['preview'] | {}, 'it settles back on its (new) corner geometry')

    def test_dragging_into_another_corner_saves_it_and_staying_saves_nothing(self):
        out = self.probe()
        saved = [l.split('SETPREF ', 1)[1] for l in out.splitlines() if 'SETPREF ' in l]
        self.assertEqual(saved, ['camera_corner top-left'], 'one save: the second drag ended in the corner it started in')
        self.assertEqual([l for l in out.splitlines() if re.search(r'components/camera.*(TypeError|ReferenceError|Unable|error)', l, re.I)], [])


if __name__ == '__main__':
    unittest.main()
