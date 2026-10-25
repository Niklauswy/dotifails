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
        for name in ('Calc.js', 'Search.js', 'Translate.js', 'Quick.js', 'Usage.js', 'Results.js', 'Files.js'):
            text = (SERVICES / name).read_text().replace('.pragma library', '')
            parts.append('\n'.join(l for l in text.splitlines() if not l.startswith('.import')))
        # Results.js uses Search./Calc. namespaces from .import; provide them over the shared scope.
        script = '\n'.join(parts) + '\nvar Search = {terms, rank, rankScored, score, termScore}; var Usage = {normal, frecency, hourAffinity, record, queryBoosts, booster, suggested, suggestionScore, fromRecent}; var Calc = {evaluate}; var Files = {isImage, icon, row, isEditable}; var Quick = {link, duration, timer, tools, killRows, rows, base64, unbase64}; var Translate = {splitQuery, guessTarget, otherTarget, languageName, googleUrl, memoryUrl, parseGoogle, parseMemory, openUrl, atUrl, parseAt, parseSuggest, suggestUrl, sameText};\n' + body
        result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_file_search_is_recursive_scoped_and_narrows_incrementally(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node JavaScript engine unavailable')
        text = (SERVICES / 'FileSearch.mjs').read_text().replace('export function ', 'function ')
        script = text + """
function check(v, why) { if (!v) throw Error(why); }
const idx = parse(['dDocuments', 'dDocuments/Facturas', 'dDocuments/Facturas/2024', 'fDocuments/Facturas/2024/marzo.pdf',
    'fDocuments/Facturas/2024/abril.pdf', 'fDocuments/notas.txt', 'dMusic', 'fMusic/marzo-mix.mp3', 'dCafetería', 'fCafetería/menú.txt'].join('\\n'));
const names = r => r.rows.map(h => idx.p[h.i]);
let r = search(idx, 'marzo', '', 10, null);
check(names(r).length === 2, 'finds both marzo files in different subfolders');
r = search(idx, 'fact pdf', '', 10, null);
check(names(r).sort().join() === 'Documents/Facturas/2024/abril.pdf,Documents/Facturas/2024/marzo.pdf', 'folder + name tokens: ' + names(r));
r = search(idx, 'marzo', 'Music', 10, null);
check(names(r).join() === 'Music/marzo-mix.mp3', 'scope limits to the subtree');
let a = search(idx, 'mar', '', 10, null);
let b = search(idx, 'marz', '', 10, a);
check(b.candidates.length === 2 && b.candidates.length <= a.candidates.length, 'narrowed candidates');
check(search(idx, 'cafeteria menu', '', 5, null).rows.length === 1, 'accent folding');
check(search(idx, 'mrz', '', 5, null).rows.length >= 2, 'subsequence');
check(search(idx, 'documents', '', 5, null).rows[0].i === 0, 'folder named exactly first');
check(search(idx, 'zzz', '', 5, null).rows.length === 0, 'no match');
const hid = parse(['f.zshrc', 'fDocuments/zshrc-notes.txt', 'd.config', 'f.config/nvim/init.lua', 'fnvim-init.txt'].join('\\n'));
check(search(hid, '.zshrc', '', 5, null).rows[0].i === 0, 'dot query finds hidden file first');
check(search(hid, 'zshrc', '', 5, null).rows.length === 2, 'hidden file still found without the dot');
check(hid.p[search(hid, 'zshrc', '', 5, null).rows[0].i] === 'Documents/zshrc-notes.txt', 'visible ranks above hidden without a dot');
check(search(hid, 'init', '', 5, null).rows.length === 2, 'files inside hidden folders are found');
"""
        result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_editable_files_open_in_neovim(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
var Files2 = {isEditable, isDotfile};
check(isEditable('/h/.zshrc') && isDotfile('/h/.zshrc'), 'dotfile');
check(isEditable('/h/a/main.py') && isEditable('/h/notes.md') && isEditable('/h/Makefile') && isEditable('/h/x.toml'), 'source and config');
check(isEditable('/h/init.lua.bak') && isEditable('/h/hyprland.lua.bak-20261021-152346-recover') && isEditable('/h/a.conf.backed') && isEditable('/h/x.conf~') && isEditable('/h/weird.rules') && isEditable('/h/noext'), 'backups and unknown extensions');
check(!isEditable('/h/photo.png.bak') && !isEditable('/h/a.zip') && !isEditable('/h/lib.so'), 'backups of binaries stay binary');
check(icon('/h/init.lua.bak', false) === 'code' && icon('/h/.zshrc.bak', false) === 'code', 'backup takes the original icon');
check(!isEditable('/h/photo.png') && !isEditable('/h/clip.mp4') && !isEditable('/h/doc.pdf') && !isEditable('/h/a.zip'), 'binary kinds stay with their app');
check(row('/h/.zshrc', false, '/h').editable && !row('/h/docs', true, '/h').editable, 'rows carry the flag');
check(icon('/h/.zshrc', false) === 'code', 'dotfile icon');
""")

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
var ctx = {browse: browse, places: [], recentFiles: [], files: [browse[2]]};
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

    def test_prefixes_go_straight_to_google_or_the_terminal(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
var ctx = {apps: [{kind: 'app', key: 'app:Firefox', title: 'Firefox', l: 'firefox', a: '', freq: 5}], commands: [], windows: [], clips: [], snippets: [], files: [],
    recentFiles: [], calcHistory: [], pins: [], recents: [], maxApps: 6, systemCommands: []};
var web = root('?como se cocina en da', ctx);
check(web.length === 1 && web[0].kind === 'web' && web[0].brand === 'google' && !web[0].browser, 'one Google row for ?; the browser comes from Settings');
check(web[0].url === 'https://www.google.com/search?q=como%20se%20cocina%20en%20da', 'encoded Google url: ' + web[0].url);
var run = root('> ls -la ~', ctx);
check(run.length === 1 && run[0].kind === 'run' && run[0].command === 'ls -la ~', 'one terminal row for >');
var yt = root('!lofi beats', ctx);
check(yt.length === 1 && yt[0].title === 'Search YouTube for “lofi beats”' && yt[0].url === 'https://www.youtube.com/results?search_query=lofi%20beats', 'YouTube row for !: ' + yt[0].url);
check(root('?', ctx).length === 1 && root('?', ctx)[0].kind === 'hero' && root('?', ctx)[0].header === true, 'a bare prefix is a welcome card, never selectable');
check(root('>  ', ctx)[0].kind === 'hero', 'bare > with no history is a welcome card');
var plain = root('fire', ctx).find(r => r.kind === 'web');
check(plain && plain.subtitle === 'DuckDuckGo' && plain.url === 'https://duckduckgo.com/?q=fire', 'plain text keeps the DuckDuckGo fallback');
var viaGoogle = root('fire', ctx, {engine: 'google'}).find(r => r.kind === 'web');
check(viaGoogle.subtitle === 'Google' && viaGoogle.url === 'https://www.google.com/search?q=fire' && viaGoogle.brand === 'google', 'the search engine setting picks the fallback');
check(root('fire', ctx, {engine: 'nonsense'}).find(r => r.kind === 'web').subtitle === 'DuckDuckGo', 'an unknown engine falls back to DuckDuckGo');
""")

    def test_translator_prefix_direction_and_responses(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
var ctx = {apps: [], commands: [], windows: [], clips: [], snippets: [], files: [], recentFiles: [], calcHistory: [], pins: [], recents: [], maxApps: 6, systemCommands: []};
var t = root(';hello how are you', ctx);
check(t.length === 1 && t[0].kind === 'translate' && t[0].text === 'hello how are you' && t[0].target === '', 'plain ; row: ' + JSON.stringify(t));
var forced = root(';en hola amigo', ctx)[0];
check(forced.target === 'en' && forced.text === 'hola amigo', 'a leading language code sets the target');
check(root(';en', ctx)[0].text === 'en' && root(';en', ctx)[0].target === '', 'a lone code is just text');
check(root(';xx hola', ctx)[0].text === 'xx hola', 'unknown codes stay in the text');
check(root(';', ctx)[0].kind === 'hero' && root(';', ctx)[0].examples.length > 0, 'bare ; teaches by example');
check(Translate.guessTarget('¿cómo se cocina en Colombia?') === 'en', 'Spanish goes to English');
check(Translate.guessTarget('hello how are you') === 'es', 'English goes to Spanish');
check(Translate.guessTarget('apple') === 'es', 'unknown goes to Spanish');
check(Translate.guessTarget('gracias por todo') === 'en', 'Spanish stopwords');
var g = Translate.parseGoogle('[["Hola. ¿Cómo estás?","en"]]');
check(g.text === 'Hola. ¿Cómo estás?' && g.from === 'en', 'google response');
var threw = false; try { Translate.parseGoogle('<html>Sorry...</html>'); } catch (e) { threw = true; }
check(threw, 'a block page is an error, so the fallback runs');
check(Translate.parseMemory('{"responseData":{"translatedText":"hola"},"responseStatus":200}').text === 'hola', 'memory response');
threw = false; try { Translate.parseMemory('{"responseData":{"translatedText":""},"responseStatus":403}'); } catch (e) { threw = true; }
check(threw, 'memory error');
check(Translate.googleUrl('a b&c', 'es') === 'https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=es&q=a%20b%26c', 'encoded url');
check(Translate.languageName('es') === 'Spanish' && Translate.otherTarget('es') === 'en' && Translate.otherTarget('en') === 'es', 'names and flip');
check(Translate.openUrl('hola', 'en') === 'https://translate.google.com/?sl=auto&tl=en&text=hola&op=translate', 'open url');
""")

    def test_prefixes_fill_the_list_with_live_results_only_while_they_match(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
var base = {apps: [], commands: [], windows: [], clips: [], snippets: [], files: [], recentFiles: [], calcHistory: [], pins: [], recents: [], maxApps: 6, systemCommands: []};
function withLive(live) { return {live: live}; }
var sug = {kind: 'google', query: 'video de esquiz', items: ['video de esquizofrenia', 'video de un esquizofrénico']};
var rows = root('?video de esquiz', base, withLive({suggest: sug}));
check(rows.length === 3 && rows[0].key === 'web' && rows[1].section === 'Suggestions' && rows[1].url.indexOf('google.com/search?q=video%20de%20esquizofrenia') > 0, 'typed row, then suggestions: ' + JSON.stringify(rows.map(r => r.key)));
check(root('?video de esquizo', base, withLive({suggest: sug})).length === 1, 'suggestions for an older text are not shown');
check(root('!video de esquiz', base, withLive({suggest: sug})).length === 1, 'nor for another site');
var yt = root('!maluma', base, withLive({suggest: {kind: 'youtube', query: 'maluma', items: ['maluma 4 babys']}}));
check(yt[1].url.indexOf('youtube.com/results?search_query=maluma%204%20babys') > 0 && yt[1].brand === '', 'youtube suggestions');
var hist = root('>', base, withLive({suggest: {kind: 'run', query: '', items: ['git status', 'ls -la']}}));
check(hist.length === 2 && hist[0].kind === 'run' && hist[0].command === 'git status' && hist[0].section === 'Recent commands', 'bare > lists recent commands');
var cmd = root('>git', base, withLive({suggest: {kind: 'run', query: 'git', items: ['git', 'git status']}}));
check(cmd.length === 2 && cmd[0].key === 'run' && cmd[1].command === 'git status', 'typed command first, history without the duplicate');
var tr = root(';porque lo dices', base, withLive({translation: {state: 'done', answered: 'porque lo dices', variants: ['Why do you say that?'], meanings: []}}));
check(tr.length === 2 && tr[0].kind === 'translate' && tr[1].kind === 'variant' && tr[1].value === 'Why do you say that?' && tr[1].section === 'Other ways to say it', 'alternatives under the card');
check(root(';otra cosa', base, withLive({translation: {state: 'done', answered: 'porque lo dices', variants: ['x'], meanings: []}})).length === 1, 'alternatives of an older text are hidden');
var word = root(';manzana', base, withLive({translation: {state: 'done', answered: 'manzana', variants: [], meanings: [{pos: 'noun', words: ['block', 'square']}]}}));
check(word.length === 3 && word[1].section === 'Noun' && word[2].title === 'square', 'meanings by part of speech');
var dup = root(';manzana', base, withLive({translation: {state: 'done', answered: 'manzana', variants: ['block'], meanings: [{pos: 'noun', words: ['block', 'square']}]}}));
check(dup.map(r => r.title).join() === 'manzana,block,square', 'a meaning already offered as an alternative is not repeated: ' + dup.map(r => r.title));
var parsed = Translate.parseAt('[[["Because you said so?","¿Por qué lo dices?",null,null,10]],null,"es",null,null,[["¿Por qué lo dices?",null,[["Because you said so?",null,true,false,[10]],["Why do you say it?",null,true,false,[3]],["Why do you say that?",null,true,false,[8]]],[[0,18]],"¿Por qué lo dices?",0,0]]]');
check(parsed.text === 'Because you said so?' && parsed.from === 'es' && parsed.alternatives.join('|') === 'Why do you say that?|Why do you say it?', 'alternatives best first, main excluded: ' + JSON.stringify(parsed));
var dict = Translate.parseAt('[[["apple","manzana",null,null,10]],[["noun",["apple","block","square"],[]]],"es",null,null,[["manzana",null,[["apple",null,true,false,[10]],["block",null,true,false,[2]]],[[0,7]],"manzana",0,0]]]');
check(dict.meanings.length === 1 && dict.meanings[0].words.join() === 'block,square' && dict.alternatives.join() === 'block', 'single word meanings: ' + JSON.stringify(dict));
check(Translate.parseSuggest('["q",["q","q uno","q dos"],[],{}]', 'q').join() === 'q uno,q dos', 'suggestions skip the query itself');
check(Translate.suggestUrl('youtube', 'a b').indexOf('ds=yt') > 0 && Translate.suggestUrl('google', 'a').indexOf('ds=yt') < 0, 'youtube uses its own suggestions');
""")

    def test_quick_answers_cover_links_timers_tools_and_quitting(self):
        self.run_js("""
function check(v, why) { if (!v) throw Error(why); }
var base = {apps: [{kind: 'app', key: 'app:Firefox', title: 'Firefox', l: 'firefox', a: '', freq: 5}], commands: [], windows: [], clips: [], snippets: [], files: [],
    recentFiles: [], calcHistory: [], pins: [], recents: [], maxApps: 6, systemCommands: []};
var now = Date.UTC(2026, 9, 24, 3, 0, 0);
var more = {now: now, random: () => 0.5, seed: 1};
function first(q, extra) { return root(q, base, Object.assign({}, more, extra))[0]; }
check(first('youtube.com').kind === 'link' && first('youtube.com').url === 'https://youtube.com', 'a domain opens');
check(first('https://a.b/c?d=1').url === 'https://a.b/c?d=1' && first('localhost:3000').url === 'http://localhost:3000', 'schemes and localhost');
check(first('notes.txt').kind !== 'link' && first('main.py').kind !== 'link' && first('v1.2').kind !== 'link', 'files and versions are not links');
check(first('timer 10m tea').kind === 'timer' && first('timer 10m tea').seconds === 600 && first('timer 10m tea').label === 'tea', 'timer');
check(first('in 1h30m').seconds === 5400 && first('timer 90').seconds === 5400 && first('timer 45s').seconds === 45, 'durations');
check(first('timer 0m').kind !== 'timer' && first('timer 99h').kind !== 'timer' && first('in a while').kind !== 'timer', 'not a duration, not a timer');
check(first('uuid').value === '88888888-8888-4888-8888-888888888888' && first('uuid').kind === 'value', 'uuid');
check(Quick.base64('hola ñ') === 'aG9sYSDDsQ==' && Quick.unbase64('aG9sYSDDsQ==') === 'hola ñ' && Quick.base64('') === '', 'base64 round trip with utf-8');
check(first('b64 hola ñ').value === 'aG9sYSDDsQ==' && first('urlenc a b&c').value === 'a%20b%26c' && first('urldec a%20b').value === 'a b', 'encoders');
check(first('ts 1700000000').value.indexOf('2023-11-1') === 0 && first('ts').value === String(Math.floor(now / 1000)), 'timestamps');
var kill = root('kill bra', base, {live: {procs: {query: 'bra', items: ['brave\t19\t139\t3425', 'Hyprland\t1\t15\t116', 'brave-browser-s\t1\t0\t3']}}});
check(kill.length === 2 && kill[0].kind === 'kill' && kill[0].name === 'brave' && kill[0].subtitle === '19 processes · 139% CPU · 3425 MB' && kill[0].section === 'Matching processes', 'kill rows, the session is never offered: ' + JSON.stringify(kill.map(r => r.name)));
check(root('kill', base, {live: {procs: {query: '', items: ['brave\t19\t139\t3425']}}})[0].section === 'Using the most CPU', 'bare kill lists the busiest');
check(root('kill bra', base, {live: {procs: {query: 'old', items: ['brave\t19\t139\t3425']}}}).length === 0, 'stale process lists are not shown');
check(root('killer queen', base, more).some(r => r.kind !== 'kill'), 'only the word kill starts it');
var order = root('fire.com', base, more);
check(order[0].kind === 'link', 'quick answers come before the fuzzy matches');
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

    def test_launcher_learns_what_each_query_leads_to(self):
        catalog = (SERVICES / 'Catalog.js').read_text().replace('.pragma library', '')
        # Catalog.js has its own tools(); kept in a closure so it does not replace Quick's.
        self.run_js('var Catalog = (function () {' + catalog + '\nreturn {settings};})();' + """
function check(v, why) { if (!v) throw Error(why); }
function app(name, freq) { return {kind: 'app', key: 'app:' + name, title: name, l: name.toLowerCase(), a: '', freq: freq}; }
var DAYMS = 86400000, now = Date.UTC(2026, 9, 24, 15);
var ctx = {apps: [app('Telegram', 40), app('Terminal', 0), app('Thunar', 0)], commands: [], settings: Catalog.settings(), clips: [], files: [],
    recentFiles: [], calcHistory: [], pins: [], usage: {}, picks: [], maxApps: 6};
var first = r => root('te', ctx, {now}).filter(x => x.section === 'Applications')[0].title;
check(first() === 'Telegram', 'without history the all-time favourite leads');
// Picking Terminal after typing "te" twice is enough to put it first for "te" and for "t".
for (var i = 0; i < 2; i++) { var n = record(ctx.usage, ctx.picks, 'app:Terminal', 'te', now - i * 60000, null); ctx.usage = n.usage; ctx.picks = n.picks; }
check(first() === 'Terminal', 'learned for the same query');
check(root('t', ctx, {now}).filter(x => x.section === 'Applications')[0].title === 'Terminal', 'and while typing towards it');
check(root('tel', ctx, {now}).filter(x => x.section === 'Applications')[0].title === 'Telegram', 'learning never adds a non-matching entry');
// Old picks fade: three months later the favourite is back on top.
check(root('te', ctx, {now: now + 90 * DAYMS}).filter(x => x.section === 'Applications')[0].title === 'Telegram', 'old habits fade');
// Suggestions: frecency first, files kept from their snapshot, pins stay ahead.
var f = {kind: 'file', key: 'file:/home/u/notes.md', title: 'notes.md', path: '/home/u/notes.md'};
var m = record(ctx.usage, ctx.picks, f.key, '', now, f); ctx.usage = m.usage; ctx.picks = m.picks;
var s = root('', ctx, {now}).map(r => r.key);
check(s[0] === 'app:Terminal' && s.includes('file:/home/u/notes.md') && s.includes('app:Telegram'), 'suggestions: ' + s);
ctx.pins = [app('Thunar', 0)];
check(root('', ctx, {now})[0].key === 'app:Thunar', 'pins first');
// The hour matters for suggestions: something always opened at 9 leads at 9.
var u = {}, p = [];
for (var d = 0; d < 6; d++) { var x = record(u, p, 'app:Telegram', '', new Date(2026, 9, 10 + d, 9).getTime(), null); u = x.usage; p = x.picks; }
for (var d = 0; d < 6; d++) { var y = record(u, p, 'app:Terminal', '', new Date(2026, 9, 10 + d, 22).getTime(), null); u = y.usage; p = y.picks; }
check(suggested(u, new Date(2026, 9, 16, 9).getTime())[0] === 'app:Telegram', 'morning habit');
check(suggested(u, new Date(2026, 9, 16, 22).getTime())[0] === 'app:Terminal', 'night habit');
// Settings pages are found in Spanish and English.
var withFiles = Object.assign({}, ctx, {files: [1, 2, 3, 4, 5, 6, 7, 8].map(i => ({kind: 'file', key: 'file:/p' + i, title: 'Captura-de-Pantalla-' + i}))});
var sections = root('pantallas', withFiles, {now}).map(r => r.section);
check(sections[0] === 'Settings' && root('pantallas', ctx, {now})[0].key === 'cmd:settings:displays', 'pantallas, ahead of file names: ' + sections);
check(root('wifi', ctx, {now}).filter(r => r.section === 'Settings')[0].argv.join(' ') === 'wysun settings network', 'wifi');
// The old recent list migrates, and the stores stay bounded.
var mig = fromRecent([{key: 'cmd:files', row: null}, {key: 'file:/a', row: f}], now);
check(mig['cmd:files'].n === 1 && mig['file:/a'].row === f, 'migration');
// Twenty old recent files do not crowd out the apps used every day.
var many = [];
for (var q = 0; q < 20; q++) many.push({key: 'file:/f' + q, row: {kind: 'file', key: 'file:/f' + q, title: 'f' + q}});
var mixed = Object.assign({}, ctx, {pins: [], picks: [], usage: fromRecent(many, now)});
var shown = root('', mixed, {now});
check(shown.filter(r => r.kind === 'file').length === 3 && shown.some(r => r.key === 'app:Telegram'), 'files capped: ' + shown.map(r => r.key));
var big = {}, bp = [];
for (var k = 0; k < 450; k++) { var z = record(big, bp, 'app:' + k, 'q' + k, now + k, null); big = z.usage; bp = z.picks; }
check(Object.keys(big).length === 300 && bp.length === 400 && big['app:449'], 'bounded, newest kept');
var t0 = Date.now();
for (var r = 0; r < 50; r++) queryBoosts(bp, 'q4', now);
check((Date.now() - t0) / 50 < 4, 'query boosts are cheap per keystroke');
""")


if __name__ == '__main__':
    unittest.main()
