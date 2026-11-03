"""Unresponsive windows: recognising Hyprland's ANR dialog, reading which window hung from its command line and
matching it with a toplevel (AnrLogic.js, node), plus the module's static wiring."""
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
    source = (SHELL / 'modules/anr/AnrLogic.js').read_text().replace('.pragma library', '')
    script = source + '\nprocess.stdout.write(JSON.stringify((() => {' + body + '})()));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


CMDLINE = ('hyprland-dialog\\u0000--title\\u0000Application Not Responding\\u0000--text\\u0000'
           'An application GitHub - wysun - Firefox - firefox is not responding.\\u0000--buttons\\u0000Terminate;Wait\\u0000')


class LogicTests(unittest.TestCase):
    def test_recognises_the_dialog(self):
        self.assertTrue(js('return isAnrDialog("hyprland-dialog", "Application Not Responding")'))
        self.assertTrue(js('return isAnrDialog("", "Application Not Responding")'))
        self.assertFalse(js('return isAnrDialog("hyprland-dialog", "Permission request")'))

    def test_reads_title_and_class_from_the_command_line(self):
        self.assertEqual(js(f'return parseCmdline("{CMDLINE}")'), {'title': 'GitHub - wysun - Firefox', 'cls': 'firefox'})
        self.assertIsNone(js('return parseCmdline("hyprland-dialog\\u0000--title\\u0000x")'))

    def test_matches_the_hung_window(self):
        out = js('''return matchWindow([
            {address: "0x1", cls: "firefox", title: "Other", pid: 5},
            {address: "0x2", cls: "firefox", title: "GitHub - wysun - Firefox", pid: 6},
            {address: "0x3", cls: "hyprland-dialog", title: "Application Not Responding", pid: 9}],
            {title: "GitHub - wysun - Firefox", cls: "firefox"})''')
        self.assertEqual(out, {'address': '0x2', 'cls': 'firefox', 'title': 'GitHub - wysun - Firefox', 'pid': 6})
        self.assertIsNone(js('return matchWindow([], {title: "x", cls: "y"})'))

    def test_falls_back_to_the_only_window_of_the_class(self):
        out = js('''return matchWindow([{address: "0x7", cls: "kitty", title: "btop (changed)", pid: 3}],
                                       {title: "btop", cls: "kitty"}).address''')
        self.assertEqual(out, '0x7')

    def test_never_offers_to_kill_the_session(self):
        self.assertIsNone(js('return matchWindow([{address: "0x1", cls: "quickshell", title: "q", pid: 2}], {title: "q", cls: "quickshell"})'))


class WiringTests(unittest.TestCase):
    def test_module_is_in_the_shell_and_keeps_hyprlands_option(self):
        self.assertIn('Anr {}', (SHELL / 'shell.qml').read_text())
        qml = (SHELL / 'modules/anr/Anr.qml').read_text()
        self.assertIn('special:wysun-anr', qml)
        self.assertNotIn('enable_anr_dialog', qml + (ROOT / 'config/.config/wysun/hyprland.lua').read_text())


if __name__ == '__main__':
    unittest.main()
