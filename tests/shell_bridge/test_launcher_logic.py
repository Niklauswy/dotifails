"""Launcher result logic (calculator, fuzzy search, grouping) executed as plain JS."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / 'apps/shell/modules/launcher/services'


class LauncherLogicTests(unittest.TestCase):
    def run_js(self, body):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node JavaScript engine unavailable')
        parts = []
        for name in ('Calc.js', 'Search.js', 'Results.js', 'Files.js'):
            text = (SERVICES / name).read_text().replace('.pragma library', '')
            parts.append('\n'.join(l for l in text.splitlines() if not l.startswith('.import')))
        # Results.js uses Search./Calc. namespaces from .import; provide them over the shared scope.
        script = '\n'.join(parts) + '\nvar Search = {terms, rank, rankScored, score}; var Calc = {evaluate};\n' + body
        result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_calculator_and_conversions(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
check(evaluate('2+3*4').value === '14', 'precedence');
check(evaluate('15% of 80').value === '12', 'percent of');
check(evaluate('24 x 8 / 16').value === '12', 'x as times');
check(evaluate('10 km to mi').result.startsWith('6.2137'), 'unit conversion');
check(evaluate('100 c to f').result === '212 °F', 'temperature');
check(evaluate('42') === null && evaluate('hola') === null, 'not calculations');
check(evaluate('2026-01-13') === null, 'dates are not arithmetic');
check(evaluate('1/0') === null, 'division by zero');
check(evaluate('2^2000') === null, 'huge power');
""")

    def test_fuzzy_ranking_is_fast_and_sensible(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
var items = [];
for (var i = 0; i < 3000; i++) items.push({l: 'application ' + i, a: 'generic keywords ' + i});
items.push({l: 'visual studio code', a: ''}, {l: 'firefox', a: ''}, {l: 'files', a: ''});
var t0 = Date.now();
for (var n = 0; n < 20; n++) rank(terms('vsc'), items, 8);
check((Date.now() - t0) / 20 < 16, 'a keystroke must filter in under 16 ms');
check(rank(terms('vsc'), items, 3)[0].l === 'visual studio code', 'initials');
check(rank(terms('fire'), items, 3)[0].l === 'firefox', 'prefix');
check(rank(terms('zzzqq'), items, 3).length === 0, 'no match');
""")

    def test_results_group_only_non_empty_sections_and_lead_with_calculator(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
function app(name, freq) { return {kind: 'app', key: 'app:' + name, title: name, l: name.toLowerCase(), a: '', freq: freq}; }
var ctx = {apps: [app('Firefox', 5), app('Files', 0), app('Terminal', 9)], commands: [{kind: 'cmd', key: 'cmd:clipboard', title: 'Clipboard History', l: 'clipboard history', a: ''}],
    windows: [], clips: [], snippets: [], files: [], recentFiles: [], calcHistory: [], pins: [], recents: [], maxApps: 6, systemCommands: []};
var empty = root('', ctx);
check(empty.length && empty.every(r => r.section === 'Suggestions'), 'suggestions with an empty query');
check(empty[0].title === 'Terminal', 'suggestions sorted by frequency');
var calc = root('2+2*3', ctx);
check(calc[0].kind === 'calc' && calc[0].title === '8', 'calculator card first');
var rows = root('clip', ctx);
var sections = rows.map(r => r.section).filter((s, i, a) => a.indexOf(s) === i);
check(sections[0] === 'Commands' && !sections.includes('Applications') && !sections.includes('Files'), 'only sections with results, best first: ' + sections);
check(rows[rows.length - 1].kind === 'run', 'fallbacks last');
var clips = view('clipboard', '', {clips: [{kind: 'clip', key: 'clip:1', stamp: Date.now() / 1000, l: 'abc', a: ''}]}, null);
check(clips[0].section === 'Today', 'clipboard grouped by day');
""")


if __name__ == '__main__':
    unittest.main()
