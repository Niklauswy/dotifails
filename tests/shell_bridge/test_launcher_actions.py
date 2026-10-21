"""Exercise native utility catalogue and application launching with inert JS stubs."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class LauncherActionsTests(unittest.TestCase):
    def run_js(self, script):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node JavaScript engine unavailable')
        result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_utility_catalogue_preserves_modes_and_user_preferences(self):
        source = (ROOT / 'apps/shell/modules/launcher/services/Catalog.js').read_text().replace('.pragma library', '')
        self.run_js(source + """
function check(v, why) { if (!v) throw Error(why); }
var commands = actions('', [], false).map(a => a.argv.join(' '));
for (var mode of ['files', 'emoji', 'music', 'music-mini', 'notes', 'colors', 'processes', 'tools',
                  'connections', 'audio', 'notifications', 'calendar', 'system', 'power', 'recorder', 'screenshot', 'settings'])
    check(commands.includes('wysun ' + mode), 'lost utility: ' + mode);
for (var mode of ['clip', 'snippets', 'calc', 'windows'])
    check(commands.includes('autocomplete ' + mode), 'lost category: ' + mode);
var custom = {name: 'Custom Settings', command: ['wysun', 'settings'], enabled: false};
var dangerous = {command: ['poweroff'], enabled: true, dangerous: true};
var invalid = {command: ['wysun', 'wallpaper', '-r'], enabled: true};
var original = JSON.stringify([custom, dangerous, invalid]);
var items = actions('', [custom, dangerous, invalid], false);
check(!items.some(a => a.argv.join(' ') === 'wysun settings'), 'disabled user action re-added');
check(!items.some(a => a.argv[0] === 'poweroff'), 'dangerous action enabled');
check(!items.some(a => a.argv.join(' ') === 'wysun wallpaper -r'), 'obsolete argv retained');
check(actions('', [dangerous], true).some(a => a.argv[0] === 'poweroff'), 'explicit dangerous setting lost');
check(JSON.stringify([custom, dangerous, invalid]) === original, 'user config mutated');
var aliases = [{command: ['custom'], enabled: true}, {command: ['custom'], enabled: true}];
check(actions('', aliases, false).filter(a => a.argv[0] === 'custom').length === 2, 'user aliases removed');
""")

    def test_apps_keep_desktop_entry_execution_and_terminal_working_directory(self):
        source = (ROOT / 'apps/shell/modules/launcher/services/Apps.qml').read_text()
        launch = re.search(r'    function launch\(entry: DesktopEntry\): void \{(.*?)\n    }', source, re.S)[1]
        self.run_js("""
var calls = [], executions = 0;
var appDb = {incrementFrequency: id => calls.push(id)};
var GlobalConfig = {general: {apps: {terminal: ['wysun-terminal']}}};
var Quickshell = {shellDir: '/synthetic/shell', execDetached: value => calls.push(value)};
function launch(entry) { LAUNCH }
launch({id: 'normal.desktop', runInTerminal: false, execute: () => ++executions});
if (executions !== 1 || calls.length !== 1) throw Error('normal app not launched once');
launch({id: 'terminal.desktop', runInTerminal: true, command: ['program', 'arg with spaces'], workingDirectory: '/synthetic/cwd'});
var request = calls[2];
if (executions !== 1 || request.workingDirectory !== '/synthetic/cwd' ||
    JSON.stringify(request.command) !== JSON.stringify(['wysun-terminal', '/synthetic/shell/assets/wrap_term_launch.sh', 'program', 'arg with spaces']))
    throw Error('terminal argv/cwd changed');
""".replace('LAUNCH', launch))


if __name__ == '__main__':
    unittest.main()
