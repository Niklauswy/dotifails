"""The recording flow of the shell: a picker overlay on every output, and stop/pause that stay reachable while drawing.

Static checks of the QML (no Quickshell in unit tests) plus ``ProbeTests``, which load the live annotation toolbar in
an offscreen Quickshell: point ``WYSUN_TEST_RUNTIME`` at a runtime prefix (the installed
``~/.local/share/wysun/runtime`` works); without it they are skipped.
"""
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

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


class PickerOutputsTests(unittest.TestCase):
    def test_every_output_gets_a_picker_overlay(self):
        text = source('modules/areapicker/AreaPicker.qml')
        windows = text[text.index('id: windows'):]
        self.assertRegex(windows, r'Variants \{\s*model: Screens\.screens\s')
        self.assertNotIn('filter(s => s.name === root.session?.screenName)', text,
                         'a window on another monitor could not be picked: only one output had an overlay')

    def test_the_pointer_entering_another_output_makes_it_the_active_one(self):
        body = function_body(source('modules/areapicker/Picker.qml'), 'moveDrag')
        self.assertIn('session.screenName = screen.name', body)
        self.assertIn('phase === "mode"', body)

    def test_only_the_active_output_takes_the_keyboard(self):
        text = source('modules/areapicker/AreaPicker.qml')
        self.assertIn('WlrLayershell.keyboardFocus: owner ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None', text)
        self.assertIn('readonly property bool owner: root.session?.screenName === modelData.name', text)


class AnnotationControlsTests(unittest.TestCase):
    def test_the_live_toolbar_offers_pause_and_stop(self):
        text = source('modules/areapicker/EditorToolbar.qml')
        self.assertIn('signal pause', text)
        self.assertIn('signal stop', text)
        self.assertIn('property bool paused', text)
        self.assertIn('objectName: "stopRecording"', text)
        self.assertIn('objectName: "pauseRecording"', text)
        self.assertIn('Ctrl+Shift+S', text)

    def test_the_annotation_layer_wires_them_to_the_recorder(self):
        text = source('modules/recorder/LiveAnnotations.qml')
        self.assertIn('paused: Recorder.paused', text)
        self.assertIn('onStop: Recorder.stop()', text)
        self.assertIn('onPause: Recorder.togglePause()', text)

    def test_the_stop_and_pause_shortcuts_also_work_inside_the_annotation_layer(self):
        text = source('modules/recorder/LiveAnnotations.qml')
        keys = text[text.index('Keys.onPressed'):text.index('Item {\n                    id: backdrop')]
        self.assertRegex(keys, r'ctrl && shift && event\.key === Qt\.Key_S\)\s*Recorder\.stop\(\)')
        self.assertRegex(keys, r'ctrl && shift && event\.key === Qt\.Key_R\)\s*Recorder\.togglePause\(\)')


@unittest.skipUnless(os.environ.get('WYSUN_TEST_RUNTIME'), 'needs WYSUN_TEST_RUNTIME (a built shell runtime)')
class ProbeTests(unittest.TestCase):
    def probe(self):
        runtime = Path(os.environ['WYSUN_TEST_RUNTIME']).expanduser()
        with tempfile.TemporaryDirectory(prefix='wysun-recording-') as tmp:
            home = Path(tmp)
            shell = home / 'shell'
            (shell / 'services').mkdir(parents=True)
            (shell / 'services/Colours.qml').symlink_to(SHELL / 'services/Colours.qml')
            (shell / 'services/Wallpapers.qml').write_text(
                'pragma Singleton\nimport Quickshell\nSingleton { property string current: "" }\n')
            for sub in ('utils', 'components'):
                (shell / sub).symlink_to(SHELL / sub)
            (shell / 'modules').mkdir()
            (shell / 'modules/areapicker').symlink_to(SHELL / 'modules/areapicker')
            (shell / 'shell.qml').write_text((ROOT / 'tests/shell_recording_probe.qml').read_text())
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

    def test_pause_and_stop_exist_only_while_recording_and_emit_their_signals(self):
        out = self.probe()
        line = next((l for l in out.splitlines() if 'BAR ' in l), None)
        self.assertIsNotNone(line, out)
        bar = json.loads(line.split('BAR ', 1)[1])
        self.assertTrue(bar['live']['stopRecording']['visible'])
        self.assertEqual(bar['live']['stopRecording']['icon'], 'stop')
        self.assertEqual(bar['live']['pauseRecording']['icon'], 'pause')
        self.assertEqual(bar['paused']['pauseRecording']['icon'], 'play_arrow')
        for name in ('pauseRecording', 'stopRecording'):
            self.assertFalse(bar['capture'][name]['visible'], 'a screenshot has nothing to stop')
        signals = [l.split('SIGNAL ', 1)[1] for l in out.splitlines() if 'SIGNAL ' in l]
        self.assertEqual(sorted(signals), ['pause', 'stop'])
        self.assertEqual([l for l in out.splitlines() if re.search(r'EditorToolbar\.qml.*(TypeError|ReferenceError|Unable|error)', l, re.I)], [])


if __name__ == '__main__':
    unittest.main()
