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
        script = '\n'.join(parts) + '\nvar Search = {terms, rank, rankScored, score}; var Calc = {evaluate}; var Files = {isImage, icon, row};\n' + body
        result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_clipboard_colours_parse_rgb_and_hsl(self):
        """Swatches and the colour preview accept the notations clipboard colours come in."""
        node = shutil.which('node')
        if not node:
            self.skipTest('Node JavaScript engine unavailable')
        text = (SERVICES / 'Colour.js').read_text().replace('.pragma library', '')
        stub = ('var Qt = {rgba: (r, g, b, a) => ["rgb", r, g, b], hsla: (h, s, l, a) => ["hsl", h, s, l], '
                'color: v => ["hex", v]};\n')
        script = stub + text + """
function check(v, why) { if (!v) throw Error(why); }
var a = parse('rgb(230, 230, 232)');
check(a[0] === 'rgb' && Math.abs(a[1] - 230 / 255) < 1e-9 && Math.abs(a[3] - 232 / 255) < 1e-9, 'rgb');
var b = parse('hsl(240, 4%, 91%)');
check(b[0] === 'hsl' && Math.abs(b[1] - 240 / 360) < 1e-9 && Math.abs(b[3] - 0.91) < 1e-9, 'hsl');
check(parse('#70140C')[0] === 'hex', 'hex goes to Qt');
check(parse('rgba(1 2 3 / 50%)')[0] === 'rgb', 'space separated');
"""
        result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_folder_browsing_groups_folders_first_and_filters(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
var browse = [row('/h/docs', true, '/h'), row('/h/notes.txt', false, '/h'), row('/h/photo.png', false, '/h')];
var ctx = {browse: browse, places: [], recentFiles: [], files: []};
var all = view('browse', '', ctx, '', 'all');
check(all[0].section === 'Folders' && all[0].title === 'docs', 'folders first');
check(all.filter(r => r.section === 'Files').length === 2, 'files after folders');
check(view('browse', 'photo', ctx, '', 'all').map(r => r.title).join() === 'photo.png', 'filter inside folder');
check(view('browse', '', ctx, '', 'image').map(r => r.title).join() === 'photo.png', 'image filter');
""")

    def test_shell_javascript_avoids_lookbehind(self):
        """QML's JavaScript engine has no regex lookbehind: such a pattern silently never matches
        (the launcher calculator ignored "2x2x2" because of one)."""
        shell = ROOT / 'apps/shell'
        offenders = [str(path.relative_to(ROOT)) for path in list(shell.rglob('*.js')) + list(shell.rglob('*.qml'))
                     if '(?<=' in path.read_text() or '(?<!' in path.read_text()]
        self.assertEqual(offenders, [])

    def test_calculator_and_conversions(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
check(evaluate('2+3*4').value === '14', 'precedence');
check(evaluate('15% of 80').value === '12', 'percent of');
check(evaluate('24 x 8 / 16').value === '12', 'x as times');
check(evaluate('2x2x2').value === '8', 'chained x without spaces');
check(evaluate('1,5 x 2').value === '3', 'decimal comma');
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

    def test_suggestions_keep_their_order_while_sources_update(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
function app(name, freq) { return {kind: 'app', key: 'app:' + name, title: name, l: name.toLowerCase(), a: '', freq: freq}; }
var names = ['Zed', 'Alpha', 'Beta', 'Gamma', 'Delta', 'Eps', 'Firefox', 'Foot', 'Gimp', 'Hexchat', 'Inkscape'];
function ctxFor(step) {
    // Sources reorder and tick on every update: shuffled index, equal frequencies, new entries.
    var apps = names.map((n, i) => app(n, 3 + (i % 2))).sort((a, b) => ((a.title.charCodeAt(0) * (step + 3)) % 7) - ((b.title.charCodeAt(0) * (step + 3)) % 7));
    if (step > 3) apps.push(app('Late' + step, 9));
    return {apps: apps, commands: [], windows: [], clips: [], snippets: [], files: [], recentFiles: [], calcHistory: [], pins: [], recents: [], maxApps: 6, systemCommands: []};
}
var snapshot = root('', ctxFor(0));
check(snapshot.length >= 5, 'suggestions present');
var first = JSON.stringify(snapshot.map(r => r.key));
for (var n = 1; n <= 50; n++) {
    var live = ctxFor(n);
    // Sometimes a source briefly lacks entries, sometimes it adds new ones.
    var apps = n % 3 === 0 ? live.apps.slice(0, 3) : live.apps;
    var seen = keepOrder(snapshot, apps).map(r => r.key);
    check(JSON.stringify(seen) === first, 'visible order changed at update ' + n);
}
// Ties are broken by name, deterministically.
var a = root('', ctxFor(1)).map(r => r.key), b = root('', ctxFor(2)).map(r => r.key);
check(JSON.stringify(a.filter(k => k.indexOf('Late') < 0)) === JSON.stringify(b.filter(k => k.indexOf('Late') < 0)), 'stable tie-break');
""")


if __name__ == '__main__':
    unittest.main()
