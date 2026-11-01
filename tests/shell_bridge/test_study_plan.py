"""Study mode: pure session logic (StudyPlan.js) and app rules (StudyApps.js), run with node."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import wave

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / 'apps/shell/services'
SOUNDS = ROOT / 'apps/shell/assets/sounds'
MIN = 60000
T0 = 1_793_000_000_000  # fixed epoch ms


def run_js(files, body):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node not available')
    source = ''
    for name in files:
        source += (SERVICES / name).read_text().replace('.pragma library', '') + '\n'
    script = source + '\nconst __out = (() => {' + body + '})();\nprocess.stdout.write(JSON.stringify(__out));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def plan(body):
    return run_js(['StudyPlan.js'], body)


def cfg(duration=120, rhythm=25):
    return f'({{duration: {duration}, rhythm: {rhythm}, blocked: ["brave-browser"], hideTime: true}})'


class StudyPlanTests(unittest.TestCase):
    def test_block_count(self):
        self.assertEqual(plan('return [blockCount(120,25), blockCount(30,90), blockCount(240,50), blockCount(60,50), blockCount(0,25)]'),
                         [4, 1, 4, 1, None])

    def test_long_breaks(self):
        self.assertEqual(plan('return [longBreakAfter(4), longBreakAfter(5), longBreakAfter(3), longBreakAfter(null)]'), [2, 3, None, None])
        self.assertEqual(plan('return [breakMinutes(2,4,25), breakMinutes(1,4,25), breakMinutes(4,null,25), breakMinutes(3,null,50)]'),
                         [15, 5, 15, 10])

    def test_summary_line(self):
        self.assertEqual(plan('return [summaryLine(120,25), summaryLine(30,90), summaryLine(0,25)]'),
                         ['4 bloques de 25 min · descanso largo a mitad', '1 bloque de 90 min', 'Bloques de 25 min hasta que pares'])

    def test_focus_break_ready_next(self):
        out = plan(f'''let s = start({cfg()}, {T0});
            const a = tick(s, {T0} + 25*{MIN});
            const b = tick(a, {T0} + 31*{MIN});
            const c = startNext(b, {T0} + 32*{MIN});
            return [a.phase, a.phaseEnd, b.phase, c.block, c.phase, c.phaseEnd];''')
        self.assertEqual(out, ['break', T0 + 30 * MIN, 'ready', 2, 'focus', T0 + 57 * MIN])

    def test_suspend_jump_stops_at_ready(self):
        out = plan(f'const s = tick(start({cfg()}, {T0}), {T0} + 180*{MIN}); return [s.phase, s.block, s.focusMs];')
        self.assertEqual(out, ['ready', 1, 25 * MIN])

    def test_last_block_finishes(self):
        out = plan(f'const s = tick(start({cfg(30)}, {T0}), {T0} + 25*{MIN}); return [s.phase, s.done, s.focusMs];')
        self.assertEqual(out, ['done', True, 25 * MIN])

    def test_pause_freezes_and_resume_shifts(self):
        out = plan(f'''let s = pause(start({cfg()}, {T0}), {T0} + 10*{MIN});
            const t = tick(s, {T0} + 40*{MIN});
            const p = progress(t, {T0} + 40*{MIN});
            const r = resume(t, {T0} + 40*{MIN});
            return [t.phase, t.paused, Math.round(p*100), remainingMin(r, {T0} + 40*{MIN}), r.paused];''')
        self.assertEqual(out, ['focus', True, 40, 15, False])

    def test_serialized_session_resumes_identically(self):
        out = plan(f'''const s = start({cfg()}, {T0});
            const a = tick(s, {T0} + 26*{MIN});
            const b = tick(JSON.parse(JSON.stringify(s)), {T0} + 26*{MIN});
            return JSON.stringify(a) === JSON.stringify(b);''')
        self.assertTrue(out)

    def test_skip_to_break_counts_partial_focus(self):
        out = plan(f'const s = skipToBreak(start({cfg()}, {T0}), {T0} + 12*{MIN}); return [s.phase, s.focusMs, s.phaseEnd];')
        self.assertEqual(out, ['break', 12 * MIN, T0 + 17 * MIN])

    def test_stop_and_history(self):
        out = plan(f'''let s = start({cfg(0)}, {T0});
            s = tick(s, {T0} + 25*{MIN}); s = startNext(s, {T0} + 30*{MIN});
            s = stop(s, {T0} + 40*{MIN});
            return [s.done, historyRecord(s, {T0} + 40*{MIN})];''')
        self.assertTrue(out[0])
        self.assertEqual(out[1], {'start': T0, 'end': T0 + 40 * MIN, 'rhythm': 25, 'blocksDone': 1, 'blocksPlanned': None,
                                  'focusMin': 35, 'distractions': 0})

    def test_week_totals_monday_to_sunday(self):
        out = plan('''const mon = new Date(2026, 9, 26, 10).getTime(), sun = new Date(2026, 10, 1, 10).getTime();
            const now = new Date(2026, 9, 31, 12).getTime();
            const prev = new Date(2026, 9, 25, 10).getTime();
            return weekTotals([{start: mon, focusMin: 50}, {start: sun, focusMin: 20}, {start: prev, focusMin: 99}], now);''')
        self.assertEqual(out, [50, 0, 0, 0, 0, 0, 20])


class StudyAppsTests(unittest.TestCase):
    def apps(self, body):
        return run_js(['StudyApps.js'], body)

    def test_only_listed_apps_are_blocked(self):
        out = self.apps('''return [isBlocked("brave-browser", ["brave-browser"]), isBlocked("Brave-Browser", ["brave-browser"]),
            isBlocked("com.mitchellh.ghostty", ["brave-browser"]), isBlocked("wysun-music", ["wysun-music"]),
            isBlocked("org.kde.polkit-kde-authentication-agent-1", ["org.kde.polkit-kde-authentication-agent-1"]), isBlocked("", ["brave-browser"])];''')
        self.assertEqual(out, [True, True, False, False, False, False])

    def test_to_hide_skips_special_workspaces_and_unlisted_apps(self):
        out = self.apps('''return toHide([{address: "a", class: "brave-browser", workspace: "special:magic"},
            {address: "b", class: "brave-browser", workspace: "2"}, {address: "c", class: "com.mitchellh.ghostty", workspace: "1"}], ["brave-browser"]);''')
        self.assertEqual(out, [{'address': 'b', 'workspace': '2'}])

    def test_workspace_selector_prefixes_names(self):
        out = self.apps('return [workspaceSelector("3"), workspaceSelector("code"), workspaceSelector("special:wysun-study"), workspaceSelector("-1")];')
        self.assertEqual(out, ['3', 'name:code', 'special:wysun-study', 'name:-1'])

    def test_history_is_appended_not_rewritten(self):
        service = (SERVICES / 'Study.qml').read_text()
        self.assertNotIn('history.setText', service)
        self.assertIn('>>', service)

    def test_restore_target(self):
        out = self.apps('return [restoreTarget("notas", ["1"], "2"), restoreTarget("1", ["1", "2"], "2"), restoreTarget("5", ["1"], "1"), restoreTarget("", ["1"], "2")];')
        self.assertEqual(out, ['notas', '1', '5', '2'])


class StudyChimeTests(unittest.TestCase):
    def test_chimes_exist_and_are_short(self):
        import array
        for name in ('study-chime.wav', 'study-chime-soft.wav'):
            with wave.open(str(SOUNDS / name)) as w:
                self.assertEqual((w.getnchannels(), w.getframerate(), w.getsampwidth()), (1, 44100, 2), name)
                self.assertLess(w.getnframes() / w.getframerate(), 1.2, name)
                samples = array.array('h', w.readframes(w.getnframes()))
                self.assertLess(max(abs(s) for s in samples) / 32768, 0.8, name)


if __name__ == '__main__':
    unittest.main()
