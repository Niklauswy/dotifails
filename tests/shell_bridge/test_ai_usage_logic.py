"""AI usage panel logic (services/AiUsageLogic.js): pace, visibility, refresh, staleness, alerts, focus. Run with node."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

LOGIC = Path(__file__).resolve().parents[2] / 'apps/shell/services/AiUsageLogic.js'
NOW = 1_793_600_000  # seconds; Tuesday
DAY, HOUR = 86400, 3600


def js(body):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node not available')
    source = LOGIC.read_text().replace('.pragma library', '')
    script = f'{source}\nconst NOW = {NOW};\nconst __out = (() => {{ {body} }})();\nprocess.stdout.write(JSON.stringify(__out === undefined ? null : __out));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def weekly(used, elapsed_fraction, ident='weekly'):
    return f'({{id: "{ident}", usedPercent: {used}, windowMinutes: 10080, resetsAt: NOW + {round((1 - elapsed_fraction) * 7 * DAY)}}})'


def account(ident, provider, limits, **extra):
    fields = ', '.join(f'{k}: {json.dumps(v)}' for k, v in extra.items())
    return f'({{id: "{ident}", provider: "{provider}", providerName: "{provider}", label: "{ident}", limits: [{", ".join(limits)}]{", " + fields if fields else ""}}})'


class PaceTests(unittest.TestCase):
    def test_pace_hidden_before_three_percent(self):
        self.assertEqual(js(f'return pace({weekly(1, 0.02)}, NOW, "auto")'), {'early': True})
        self.assertIsNone(js('return pace({usedPercent: 5, windowMinutes: 300, resetsAt: null}, NOW, "auto")'))

    def test_pace_reserve_and_deficit(self):
        reserve = js(f'return pace({weekly(23, 0.45)}, NOW, "auto")')
        self.assertEqual(reserve['delta'], -22)
        self.assertTrue(reserve['lasts'])
        deficit = js(f'return pace({weekly(80, 0.45)}, NOW, "auto")')
        self.assertEqual(deficit['delta'], 35)
        self.assertFalse(deficit['lasts'])

    def test_runs_out_estimate(self):
        # 80 % used after 45 % of 7 days: 20 % left at 80/(0.45*7d) per second.
        result = js(f'return pace({weekly(80, 0.45)}, NOW, "auto")')
        self.assertAlmostEqual(result['runsOutIn'], 20 / (80 / (0.45 * 7 * DAY)), delta=2)

    def test_exhausted(self):
        self.assertTrue(js(f'return pace({weekly(100, 0.5)}, NOW, "auto")')['exhausted'])

    def test_work_days_five_skip_weekend(self):
        # A window from Saturday 00:00 to next Saturday: after the weekend (2 days) nothing is expected yet.
        body = '''
            const sat = new Date(2026, 9, 31, 0, 0, 0).getTime() / 1000;  // Saturday 31 Oct 2026, local
            const now = sat + 2 * 86400 + 3600;
            const limit = {usedPercent: 10, windowMinutes: 10080, resetsAt: sat + 7 * 86400};
            return [pace(limit, now, "5").expected, pace(limit, now, "7").expected];'''
        five, seven = js(body)
        self.assertLess(five, 2)
        self.assertGreater(seven, 29)


class VisibilityTests(unittest.TestCase):
    def accounts(self):
        return f'[{account("a", "claude", [weekly(95, 0.5)])}, {account("b", "claude", [weekly(40, 0.5)])}, {account("c", "codex", [weekly(60, 0.5)])}]'

    def test_hidden_and_disabled_accounts_are_filtered(self):
        ids = js(f'return visibleAccounts({self.accounts()}, ["a"], ["claude"]).map(a => a.id)')
        self.assertEqual(ids, ['b'])

    def test_hidden_tightest(self):
        result = js(f'const v = visibleAccounts({self.accounts()}, ["a"], ["claude", "codex"]); return tightest(v).account.id')
        self.assertEqual(result, 'c')

    def test_all_hidden(self):
        self.assertIsNone(js(f'return tightest(visibleAccounts({self.accounts()}, ["a", "b", "c"], ["claude", "codex"]))'))

    def test_history_accounts_never_win(self):
        accounts = f'[{account("h", "codex", [weekly(99, 0.5)], source="history")}, {account("b", "claude", [weekly(40, 0.5)])}]'
        self.assertEqual(js(f'return tightest({accounts}).account.id'), 'b')

    def test_indicator_follows_focused_provider(self):
        a = self.accounts()
        self.assertEqual(js(f'return indicatorTarget({a}, "focused", "codex", "").account.id'), 'c')
        self.assertEqual(js(f'return indicatorTarget({a}, "focused", "", "").account.id'), 'a')
        self.assertEqual(js(f'return indicatorTarget({a}, "selected", "", "b").account.id'), 'b')
        self.assertEqual(js(f'return indicatorTarget({a}, "tightest", "codex", "b").account.id'), 'a')
        self.assertIsNone(js('return indicatorTarget([], "focused", "codex", "")'))

    def test_masked_names(self):
        result = js(f'return mask({account("a", "claude", [], email="me@uabc.edu.mx")}, true, 2)')
        self.assertEqual(result, {'label': 'Account 3', 'email': '••••@uabc.edu.mx'})
        self.assertEqual(js(f'return mask({account("a", "claude", [], email="me@x.y")}, false, 2).label'), 'a')


class RefreshTests(unittest.TestCase):
    TOKENS = '{refreshInterval: 60000, idleInterval: 900000}'

    def test_adaptive_interval(self):
        self.assertEqual(js(f'return refreshInterval("adaptive", true, false, {self.TOKENS})'), 60000)
        self.assertEqual(js(f'return refreshInterval("adaptive", false, true, {self.TOKENS})'), 60000)
        self.assertEqual(js(f'return refreshInterval("adaptive", false, false, {self.TOKENS})'), 900000)
        self.assertEqual(js(f'return refreshInterval("300000", false, false, {self.TOKENS})'), 300000)
        self.assertEqual(js(f'return refreshInterval("manual", true, true, {self.TOKENS})'), 0)

    def test_stale_after_three_intervals(self):
        self.assertFalse(js('return isStale({updatedAt: NOW - 100}, NOW, 60000)'))
        self.assertTrue(js('return isStale({updatedAt: NOW - 1000}, NOW, 60000)'))
        self.assertFalse(js('return isStale({updatedAt: NOW - 1000}, NOW, 900000)'))
        self.assertTrue(js('return isStale({updatedAt: NOW, error: {kind: "auth"}}, NOW, 60000)'))


class AlertTests(unittest.TestCase):
    SETTINGS = '{notifyLow: true, notifyReset: true, upcoming: true, confetti: true}'

    def run_alerts(self, prev, nxt, seen='{}', now='NOW', settings=None):
        return js(f'return alerts({prev}, {nxt}, {settings or self.SETTINGS}, {seen}, {now}, 10)')

    def test_low_alert_once_per_window(self):
        low = '({id: "session", usedPercent: 92, windowMinutes: 300, resetsAt: NOW + 3600})'
        accounts = f'[{account("a", "claude", [low])}]'
        first = self.run_alerts('[]', accounts)
        self.assertEqual([n['kind'] for n in first['notify']], ['low'])
        again = self.run_alerts('[]', accounts, seen=json.dumps(first['seen']))
        self.assertEqual(again['notify'], [])

    def test_upcoming_alert_once_per_stage(self):
        limit = '({id: "weekly", usedPercent: 40, windowMinutes: 10080, resetsAt: NOW + 20 * 3600})'
        accounts = f'[{account("a", "claude", [limit])}]'
        first = self.run_alerts('[]', accounts)
        self.assertEqual([n['kind'] for n in first['notify']], ['upcoming'])
        same = self.run_alerts('[]', accounts, seen=json.dumps(first['seen']))
        self.assertEqual(same['notify'], [])
        later = self.run_alerts('[]', accounts, seen=json.dumps(first['seen']), now='NOW + 19.5 * 3600')
        self.assertEqual([n['kind'] for n in later['notify']], ['upcoming'])
        off = self.run_alerts('[]', accounts, settings='{upcoming: false}')
        self.assertEqual(off['notify'], [])

    def test_expiry_alert_once(self):
        accounts = f'[{account("a", "claude", [], session={"expiresAt": NOW + 3 * HOUR, "expired": False})}]'
        first = self.run_alerts('[]', accounts)
        self.assertEqual([n['kind'] for n in first['notify']], ['expiry'])
        self.assertEqual(self.run_alerts('[]', accounts, seen=json.dumps(first['seen']))['notify'], [])

    def test_weekly_reset_is_reported(self):
        old = '({id: "weekly", usedPercent: 70, windowMinutes: 10080, resetsAt: NOW - 60})'
        new = '({id: "weekly", usedPercent: 0, windowMinutes: 10080, resetsAt: NOW + 7 * 86400 - 60})'
        before = f'[{account("a", "claude", [old])}]'
        after = f'[{account("a", "claude", [new])}]'
        self.assertTrue(self.run_alerts(before, after)['weeklyReset'])
        self.assertFalse(self.run_alerts(after, after)['weeklyReset'])


class FocusTests(unittest.TestCase):
    def test_window_for_session(self):
        agent = '{cwd: "/home/u/loom", provider: "claude", windowPids: [200, 100]}'
        self.assertEqual(js(f'return windowForSession({agent}, [{{pid: 100, address: "0xa", title: "loom"}}])'), '0xa')
        self.assertIsNone(js(f'return windowForSession({agent}, [{{pid: 999, address: "0xb", title: "x"}}])'))

    def test_ambiguous_window_is_told_apart_by_title_or_skipped(self):
        agent = '{cwd: "/home/u/loom", provider: "claude", windowPids: [200, 100]}'
        windows = '[{pid: 100, address: "0xa", title: "nvim"}, {pid: 100, address: "0xb", title: "✳ loom"}]'
        self.assertEqual(js(f'return windowForSession({agent}, {windows})'), '0xb')
        same = '[{pid: 100, address: "0xa", title: "zsh"}, {pid: 100, address: "0xb", title: "zsh"}]'
        self.assertIsNone(js(f'return windowForSession({agent}, {same})'))


if __name__ == '__main__':
    unittest.main()
