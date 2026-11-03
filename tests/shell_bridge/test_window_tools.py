"""Window tools for Wysun Processes in the shell: address parsing, halo placement on the right monitor, when locating
has to focus the window first (WindowToolsLogic.js, node) and the IPC wiring (thumbs/locate)."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / 'apps/shell'


def js(body):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node not available')
    source = (SHELL / 'services/WindowToolsLogic.js').read_text().replace('.pragma library', '')
    script = source + '\nprocess.stdout.write(JSON.stringify((() => {' + body + '})()));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class LogicTests(unittest.TestCase):
    def test_addresses_are_validated_and_bounded(self):
        out = js('return parseAddresses("0xaa,0xBB, nope,0x1;rm,0xcc,0xaa")')
        self.assertEqual(out, ['aa', 'bb', 'cc'])
        self.assertEqual(len(js('return parseAddresses(Array.from({length: 40}, (_, i) => "0x" + (i + 10)).join(","))')), 24)

    def test_same_address_in_both_forms(self):
        self.assertTrue(js('return sameAddress("0x55dE", "55de")'))
        self.assertFalse(js('return sameAddress("0x55de", "55df")'))

    def test_one_address_actions_accept_exactly_one_valid_address(self):
        self.assertEqual(js('return singleAddress("0xaa")'), 'aa')
        self.assertEqual(js('return singleAddress(" 0xAB ")'), 'ab')
        self.assertEqual(js('return singleAddress("0xaa,0xbb")'), '')
        self.assertEqual(js('return singleAddress("0xaa; rm -rf")'), '')
        self.assertEqual(js('return singleAddress("")'), '')

    def test_halo_on_the_monitor_of_the_window(self):
        out = js('''return placement({at: [1992, 22], size: [1826, 1036]}, {name: "DP-2", x: 1920, y: 0, width: 1920, height: 1080},
                                    {name: "DP-2", activeWs: 8}, 8)''')
        self.assertEqual(out, {'visible': True, 'x': 72, 'y': 22, 'width': 1826, 'height': 1036})

    def test_other_monitor_or_workspace_hides_the_halo(self):
        self.assertFalse(js('return placement({at: [10, 10], size: [100, 100]}, {name: "DP-1", x: 0, y: 0, width: 1920, height: 1080}, {name: "DP-2", activeWs: 1}, 1).visible'))
        self.assertFalse(js('return placement({at: [10, 10], size: [100, 100]}, {name: "DP-1", x: 0, y: 0, width: 1920, height: 1080}, {name: "DP-1", activeWs: 2}, 1).visible'))

    def test_locating_elsewhere_focuses_the_window_first(self):
        self.assertTrue(js('return needsFocus(3, null)'))                    # no monitor known
        self.assertTrue(js('return needsFocus(3, {activeWorkspace: 1})'))    # another workspace on its monitor
        self.assertFalse(js('return needsFocus(3, {activeWorkspace: 3})'))

    def test_capture_width_defaults_and_is_clamped(self):
        self.assertEqual(js('return thumbWidth(undefined)'), 480)       # existing callers keep the 480 px capture
        self.assertEqual(js('return thumbWidth("")'), 480)
        self.assertEqual(js('return thumbWidth("nope")'), 480)
        self.assertEqual(js('return thumbWidth("900")'), 900)
        self.assertEqual(js('return thumbWidth(100)'), 160)
        self.assertEqual(js('return thumbWidth(5000)'), 1920)
        self.assertEqual(js('return thumbWidth("720.5")'), 480)          # not an integer: the safe default

    def test_thumbnail_path_is_per_address_and_width(self):
        self.assertEqual(js('return thumbPath("/run/user/1000", "0xAB", 480)'),
                         '/run/user/1000/wysun-processes/thumbs/ab@480.png')
        self.assertEqual(js('return thumbPath("/run/user/1000", "0xAB", 900)'),
                         '/run/user/1000/wysun-processes/thumbs/ab@900.png')
        # A large capture has its own file: it never replaces the row's small one.
        self.assertNotEqual(js('return thumbPath("/run/x", "0xaa", 480)'),
                            js('return thumbPath("/run/x", "0xaa", 1920)'))
        self.assertEqual(js('return thumbPath("/run/x", "../evil", 480)'), '')
        self.assertNotEqual(js('return thumbKey("0xaa", 480)'), js('return thumbKey("0xaa", 900)'))

    def test_capture_size_follows_the_window(self):
        self.assertEqual(js('return thumbSize([1600, 900], 800)'), {'width': 800, 'height': 450})
        self.assertEqual(js('return thumbSize([700, 1200], 800)'), {'width': 800, 'height': 1371})
        self.assertEqual(js('return thumbSize(null, 480)'), {'width': 480, 'height': 270})


class WiringTests(unittest.TestCase):
    def test_bridge_exposes_thumbs_and_locate(self):
        qml = (SHELL / 'wysun/WysunBridge.qml').read_text()
        self.assertIn('function thumbs(addresses: string, width: string): string', qml)
        self.assertIn('WindowTools.requestThumbs(addresses, width)', qml)
        self.assertIn('function locate(address: string): bool', qml)

    def test_launcher_script_forwards_them(self):
        script = (ROOT / 'bin/wysun-shell').read_text()
        self.assertIn('thumbs) shift; exec "$runtime" ipc call wysunShell thumbs "${1:-}" "${2:-}"', script)
        self.assertIn('locate) shift; exec "$runtime" ipc call wysunShell locate', script)

    def test_locate_focuses_the_window_instead_of_offering_a_capsule(self):
        service = (SHELL / 'services/WindowTools.qml').read_text()
        self.assertIn('Logic.needsFocus', service)
        self.assertIn('focusTarget();', service)
        self.assertNotIn('targetLabel', service)                  # the capsule text is gone
        focus = service.split('function focusTarget()', 1)[1].split('// Returns the thumbnails', 1)[0]
        self.assertNotIn('showing = false', focus)                # the halo stays after focusing
        module = (SHELL / 'modules/windowtools/WindowTools.qml').read_text()
        self.assertNotIn('capsule', module)
        self.assertIn('mask: Region {}', module)                  # every click passes through

    def test_windowinfo_opens_the_bar_panel_for_a_validated_window(self):
        qml = (SHELL / 'wysun/WysunBridge.qml').read_text()
        self.assertIn('function windowinfo(address: string): bool', qml)
        self.assertIn('WindowTools.windowInfo(address)', qml)
        script = (ROOT / 'bin/wysun-shell').read_text()
        self.assertIn('windowinfo) shift; exec "$runtime" ipc call wysunShell windowinfo', script)
        service = (SHELL / 'services/WindowTools.qml').read_text()
        self.assertIn('function windowInfo(address): bool', service)
        self.assertIn('Logic.singleAddress(address)', service)
        self.assertIn('"wysun-processes"', service)               # picks the monitor showing Processes
        self.assertIn('popouts.openWinfo(t)', service)
        wrapper = (SHELL / 'modules/bar/popouts/Wrapper.qml').read_text()
        self.assertIn('property var winfoClient: null', wrapper)
        self.assertIn('readonly property var winfoTarget: winfoClient ?? Hypr.activeToplevel', wrapper)
        self.assertIn('function openWinfo(client): void', wrapper)
        self.assertIn('client: root.winfoTarget', wrapper)
        self.assertIn('winfoClient = null;', wrapper)             # reset on close (and on the bar's own path)

    def test_service_caches_per_address_and_width(self):
        service = (SHELL / 'services/WindowTools.qml').read_text()
        self.assertIn('property int pendingWidth', service)
        self.assertIn('Logic.thumbKey(a, pixels)', service)
        self.assertIn('Logic.thumbKey(address, width)', service)
        module = (SHELL / 'modules/windowtools/WindowTools.qml').read_text()
        self.assertIn('Logic.thumbSize(toplevel?.lastIpcObject?.size, WindowTools.pendingWidth)', module)
        self.assertIn('WindowTools.captured(modelData, width, path)', module)

    def test_module_is_loaded_by_the_shell(self):
        self.assertIn('WindowTools {}', (SHELL / 'shell.qml').read_text())


if __name__ == '__main__':
    unittest.main()
