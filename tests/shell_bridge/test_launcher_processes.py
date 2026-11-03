"""The launcher and Wysun Processes: open apps under «En ejecución» with a live process pane, kill rows grouped by
program, per-program figures from `ps` (ProcLogic.js, node) and the wiring of the pane and its keys."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / 'apps/shell/modules/launcher'


def js(body, files=('services/Quick.js', 'services/ProcLogic.js')):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node not available')
    parts = []
    for name in files:
        text = (LAUNCHER / name).read_text().replace('.pragma library', '')
        parts.append('\n'.join(l for l in text.splitlines() if not l.startswith('.import')))
    script = '\n'.join(parts) + '\nprocess.stdout.write(JSON.stringify((() => {' + body + '})()));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


WINDOWS = '''[{address: "0xaa", cls: "firefox", title: "GitHub", pid: 10, workspace: 1},
              {address: "0xab", cls: "firefox", title: "Docs", pid: 10, workspace: 2},
              {address: "0xbb", cls: "kitty", title: "btop", pid: 20, workspace: 2},
              {address: "0xcc", cls: "quickshell", title: "", pid: 5, workspace: 1}]'''


class RunningRowsTests(unittest.TestCase):
    def test_matches_class_title_or_app_name(self):
        rows = js(f'return runningRows("fire", {WINDOWS}, {{firefox: "Firefox"}})')
        self.assertEqual([(r['kind'], r['title'], r['section']) for r in rows], [('proc', 'Firefox', 'En ejecución')])
        self.assertEqual(rows[0]['addresses'], ['0xaa', '0xab'])
        self.assertEqual(rows[0]['pids'], [10])
        self.assertEqual(rows[0]['subtitle'], '2 ventanas')
        self.assertEqual(js(f'return runningRows("btop", {WINDOWS}, {{}}).map(r => r.app)'), ['kitty'])

    def test_needs_two_letters_and_hides_the_session(self):
        self.assertEqual(js(f'return runningRows("f", {WINDOWS}, {{}})'), [])
        self.assertEqual(js(f'return runningRows("quick", {WINDOWS}, {{}})'), [])

    def test_kill_rows_are_quit_rows_with_spanish_copy(self):
        rows = js('return killRows(["firefox\\t3\\t40\\t900", "Hyprland\\t1\\t5\\t200"], false)')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['title'], 'Cerrar firefox')
        self.assertEqual(rows[0]['section'], 'Usando más CPU')
        self.assertIn('3 procesos', rows[0]['subtitle'])


class ProcLogicTests(unittest.TestCase):
    PS = '"1 0 0.0 1000 systemd\\n10 1 20.5 300000 firefox\\n11 10 9.5 200000 Isolated Web Co\\n12 11 1.0 1000 forkserver\\n20 1 3.0 50000 kitty\\n"'

    def test_parse_and_aggregate_a_tree(self):
        out = js(f'const t = parsePs({self.PS}); return aggregate(t, [10])')
        self.assertEqual(out, {'cpu': 31.0, 'memory': 501000 * 1024, 'count': 3})

    def test_by_name(self):
        out = js(f'const t = parsePs({self.PS}); return byName(t, "kitty")')
        self.assertEqual(out['count'], 1)
        self.assertEqual(out['pids'], [20])

    def test_rates_between_two_samples(self):
        out = js('const a = parsePs("10 1 100 5 firefox\\n11 10 3 1 child\\n"), b = parsePs("10 1 101.5 5 firefox\\n11 10 3 1 child\\n12 10 0 1 new\\n");'
                 'const r = withRates(b, a, 1.0); return [r[10].cpu, r[11].cpu, r[12].cpu]')
        self.assertEqual(out, [150, 0, 0])

    def test_history_is_bounded(self):
        self.assertEqual(js('let h = []; for (let i = 0; i < 80; i++) h = pushSample(h, i); return [h.length, h[0], h[59]]'), [60, 20, 79])


class WiringTests(unittest.TestCase):
    def test_panel_shows_the_process_pane_and_handles_its_keys(self):
        panel = (LAUNCHER / 'LauncherPanel.qml').read_text()
        self.assertIn('ProcessPane {', panel)
        for snippet in ('Qt.Key_W', 'Qt.Key_L', '"wysun", "processes"', 'WindowTools.locate'):
            self.assertIn(snippet, panel, snippet)
        pane = (LAUNCHER / 'ProcessPane.qml').read_text()
        self.assertIn('ScreencopyView', pane)
        for label in ('Ir a la ventana', 'Abrir en Processes', 'Localizar en pantalla', 'Cerrar', 'Forzar cierre'):
            self.assertIn(label, pane, label)


if __name__ == '__main__':
    unittest.main()
