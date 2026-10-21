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
var session = {logout: ['logout'], hibernate: ['hibernate'], reboot: ['reboot'], shutdown: ['poweroff']};
var commands = globalThis.tools([], session).map(a => a.argv.join(' '));
for (var mode of ['files', 'music', 'music-mini', 'notes', 'colors', 'processes', 'tools',
                  'connections', 'audio', 'notifications', 'calendar', 'recorder', 'screenshot', 'settings'])
    check(commands.includes('wysun ' + mode), 'lost utility: ' + mode);
var views = globalThis.views();
for (var view of ['clipboard', 'snippets', 'windows', 'files', 'apps', 'calc-history', 'system'])
    check(views.some(v => v.view === view), 'lost view: ' + view);
check(views.some(v => v.emoji), 'emoji command lost');
var power = globalThis.system(session);
check(power.every(c => c.argv && c.argv.length), 'system command without argv');
check(power.filter(c => c.confirm).length === 4, 'destructive system commands must ask for confirmation');
var custom = {name: 'Custom Settings', command: ['wysun', 'settings'], enabled: false};
var dangerous = {name: 'Danger', command: ['poweroff-now'], enabled: true, dangerous: true};
var invalid = {name: 'Random', command: ['wysun', 'wallpaper', '-r'], enabled: true};
var legacy = {name: 'Scheme', command: ['autocomplete', 'scheme'], enabled: true};
var duplicate = {name: 'Shutdown', command: ['poweroff'], enabled: true};
var original = JSON.stringify([custom, dangerous, invalid, legacy, duplicate]);
var items = globalThis.tools([custom, dangerous, invalid, legacy, duplicate], session);
check(!items.some(a => a.title === 'Custom Settings'), 'disabled user action re-added');
check(items.find(a => a.title === 'Danger').confirm === true, 'dangerous action must be confirmed');
check(!items.some(a => a.argv.join(' ') === 'wysun wallpaper -r'), 'obsolete argv retained');
check(!items.some(a => a.argv[0] === 'autocomplete'), 'obsolete autocomplete action retained');
check(!items.some(a => a.title === 'Shutdown'), 'duplicate of a built-in command shown twice');
check(JSON.stringify([custom, dangerous, invalid, legacy, duplicate]) === original, 'user config mutated');
""")

    def test_apps_keep_desktop_entry_execution_and_terminal_working_directory(self):
        source = (ROOT / 'apps/shell/modules/launcher/services/Apps.qml').read_text()
        launch = re.search(r'    function launch\(row: var\): void \{(.*?)\n    }', source, re.S)[1]
        run = re.search(r'    function run\(entry: var, inTerminal: bool\): void \{(.*?)\n    }', source, re.S)[1]
        self.run_js("""
var calls = [], executions = 0;
var appDb = {incrementFrequency: id => calls.push(id)};
var GlobalConfig = {general: {apps: {terminal: ['wysun-terminal']}}};
var Quickshell = {shellDir: '/synthetic/shell', execDetached: value => calls.push(value)};
var root = {};
function run(entry, inTerminal) { RUN }
root.run = run;
function launch(row) { LAUNCH }
launch({id: 'normal.desktop', runInTerminal: false, entry: {execute: () => ++executions}});
if (executions !== 1 || calls.length !== 1) throw Error('normal app not launched once');
launch({id: 'terminal.desktop', runInTerminal: true, entry: {command: ['program', 'arg with spaces'], workingDirectory: '/synthetic/cwd'}});
var request = calls[2];
if (executions !== 1 || request.workingDirectory !== '/synthetic/cwd' ||
    JSON.stringify(request.command) !== JSON.stringify(['wysun-terminal', '/synthetic/shell/assets/wrap_term_launch.sh', 'program', 'arg with spaces']))
    throw Error('terminal argv/cwd changed');
""".replace('LAUNCH', launch).replace('RUN', run))


if __name__ == '__main__':
    unittest.main()
