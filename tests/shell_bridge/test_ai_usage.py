"""AI usage backend: accounts, limits from CLI snapshots and incremental token accounting from session logs."""
import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SOURCE = Path(__file__).resolve().parents[2] / 'apps/shell/modules/aiusage/backend.py'


def load(home):
    env = {'HOME': str(home), 'XDG_STATE_HOME': str(home / 'state'), 'XDG_CACHE_HOME': str(home / 'cache'),
           'XDG_CONFIG_HOME': str(home / 'config'), 'CLAUDE_CONFIG_DIR': str(home / '.claude'),
           'CODEX_HOME': str(home / '.codex')}
    with mock.patch.dict(os.environ, env), mock.patch('pathlib.Path.home', return_value=home):
        spec = importlib.util.spec_from_file_location('wysun_ai_usage_backend', SOURCE)
        backend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend)
    return backend


def stamp(epoch):
    return time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(epoch))


class AiUsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.now = time.time()
        (self.home / '.claude').mkdir()
        (self.home / '.codex').mkdir()
        self.backend = load(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def claude_log(self, lines):
        path = self.home / '.claude/projects/p/session.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a') as handle:
            for line in lines:
                handle.write(json.dumps(line) + '\n')
        return path

    def claude_entry(self, ident, model='claude-sonnet-5-5', output=1000, ago=60):
        return {'type': 'assistant', 'requestId': 'r' + ident, 'timestamp': stamp(self.now - ago),
                'message': {'id': ident, 'model': model, 'usage': {'input_tokens': 100, 'cache_read_input_tokens': 1000,
                                                                    'cache_creation_input_tokens': 10, 'output_tokens': output}}}

    def collect(self):
        return self.backend.collect(now=self.now, live=False)

    def account(self, provider, result=None):
        result = result or self.collect()
        return next(a for a in result['accounts'] if a['provider'] == provider)

    def test_claude_tokens_dedupe_repeated_messages(self):
        entry = self.claude_entry('a')
        self.claude_log([entry, entry, self.claude_entry('b')])
        totals = self.collect()['usage']['24h']['totals']
        self.assertEqual(totals['output'], 2000)
        self.assertEqual(totals['cacheRead'], 2000)

    def test_appended_lines_are_read_incrementally(self):
        self.claude_log([self.claude_entry('a')])
        self.assertEqual(self.collect()['usage']['24h']['totals']['output'], 1000)
        self.claude_log([self.claude_entry('b', output=5)])
        self.assertEqual(self.collect()['usage']['24h']['totals']['output'], 1005)

    def test_partial_last_line_waits_for_next_run(self):
        path = self.claude_log([self.claude_entry('a')])
        with path.open('a') as handle:
            handle.write(json.dumps(self.claude_entry('b'))[:20])
        self.assertEqual(self.collect()['usage']['24h']['totals']['output'], 1000)

    def test_cost_uses_pricing_and_marks_unknown_models(self):
        self.claude_log([self.claude_entry('a'), self.claude_entry('b', model='mystery-model')])
        usage = self.collect()['usage']['24h']
        models = {m['model']: m for m in usage['models']}
        expected = (100 * 2.0 + 1000 * 0.1 + 10 * 2.5 + 1000 * 10.0) / 1_000_000
        self.assertAlmostEqual(models['claude-sonnet-5-5']['cost'], expected)
        self.assertIsNone(models['mystery-model']['cost'])
        self.assertGreater(usage['totals']['unpriced'], 0)

    def test_user_pricing_overrides_defaults(self):
        (self.home / 'config/wysun').mkdir(parents=True)
        (self.home / 'config/wysun/ai-pricing.json').write_text(json.dumps({'models': {'mystery': {'input': 1, 'output': 1}}}))
        self.claude_log([self.claude_entry('a', model='mystery-model')])
        model = self.collect()['usage']['24h']['models'][0]
        self.assertAlmostEqual(model['cost'], 1100 / 1_000_000)

    def test_codex_counts_only_growing_totals(self):
        path = self.home / '.codex/sessions/2026/rollout.jsonl'
        path.parent.mkdir(parents=True)
        usage = {'input_tokens': 500, 'cached_input_tokens': 400, 'output_tokens': 50}
        event = lambda total: {'timestamp': stamp(self.now - 60), 'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
            'last_token_usage': usage, 'total_token_usage': {'total_tokens': total}}}}
        lines = [{'type': 'turn_context', 'payload': {'model': 'gpt-6.1-sol'}}, event(550), event(550), event(1100)]
        path.write_text(''.join(json.dumps(l) + '\n' for l in lines))
        usage24 = self.collect()['usage']['24h']
        self.assertEqual(usage24['totals']['input'], 200)
        self.assertEqual(usage24['totals']['cacheRead'], 800)
        self.assertEqual(usage24['models'][0]['model'], 'gpt-6.1-sol')
        self.assertEqual(usage24['sessionCount'], 1)
        self.assertEqual(self.account('codex')['usage']['24h']['totals']['input'], 200)

    def test_old_activity_is_outside_the_day_but_inside_the_month(self):
        self.claude_log([self.claude_entry('a', ago=3 * 86400)])
        usage = self.collect()['usage']
        self.assertEqual(usage['24h']['totals']['processed'], 0)
        self.assertGreater(usage['7d']['totals']['processed'], 0)

    def test_claude_limits_come_from_status_line_snapshot(self):
        (self.home / 'state/wysun/ai-usage').mkdir(parents=True)
        (self.home / 'state/wysun/ai-usage/claude.json').write_text(json.dumps({'captured_at': self.now, 'rate_limits': {
            'five_hour': {'used_percentage': 31, 'resets_at': self.now + 600},
            'seven_day': {'used_percentage': 69, 'resets_at': self.now - 10}}}))
        claude = self.account('claude')
        self.assertTrue(claude['available'])
        session, weekly = claude['limits']
        self.assertEqual(session['usedPercent'], 31)
        # A window that already reset starts empty.
        self.assertEqual(weekly['usedPercent'], 0)
        self.assertIsNone(weekly['resetsAt'])

    def test_missing_claude_snapshot_is_explained(self):
        claude = self.account('claude')
        self.assertFalse(claude['available'])
        self.assertEqual(claude['reason'], 'statusline')

    def test_codex_limits_fall_back_to_latest_log(self):
        path = self.home / '.codex/sessions/2026/rollout.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'type': 'event_msg', 'payload': {'type': 'token_count', 'rate_limits': {
            'primary': {'used_percent': 38.0, 'window_minutes': 300, 'resets_at': int(self.now) + 3600},
            'secondary': {'used_percent': 85.0, 'window_minutes': 10080, 'resets_at': int(self.now) + 86400}}}}) + '\n')
        codex = self.account('codex')
        self.assertEqual(codex['source'], 'logs')
        self.assertEqual([l['usedPercent'] for l in codex['limits']], [38.0, 85.0])

    def test_configured_accounts_get_their_own_usage(self):
        work = self.home / 'claude-work'
        log = work / 'projects/p/s.jsonl'
        log.parent.mkdir(parents=True)
        log.write_text(json.dumps(self.claude_entry('w', output=7)) + '\n')
        self.claude_log([self.claude_entry('a')])
        (self.home / 'config/wysun').mkdir(parents=True)
        (self.home / 'config/wysun/ai-accounts.json').write_text(json.dumps({'accounts': [
            {'provider': 'claude', 'home': str(work), 'label': 'Work'},
            {'provider': 'claude', 'home': str(work)}]}))
        result = self.collect()
        claude = [a for a in result['accounts'] if a['provider'] == 'claude']
        self.assertEqual([a['label'] for a in claude][1], 'Work')
        self.assertEqual(len(claude), 2)
        self.assertEqual([a['usage']['24h']['totals']['output'] for a in claude], [1000, 7])
        self.assertEqual(result['usage']['24h']['totals']['output'], 1007)

    def test_claude_plan_comes_from_the_cached_profile(self):
        (self.home / '.claude.json').write_text(json.dumps({'oauthAccount': {
            'organizationType': 'claude_max', 'userRateLimitTier': 'default_claude_max_20x', 'displayName': 'Ana'}}))
        claude = self.account('claude')
        self.assertEqual(claude['plan'], 'Max 20x')
        self.assertEqual(claude['label'], 'Ana')

    def test_codex_sessions_of_another_account_get_a_history_tab(self):
        path = self.home / '.codex/sessions/2026/rollout.jsonl'
        path.parent.mkdir(parents=True)
        meta = {'type': 'session_meta', 'payload': {'creator_account_id': 'acct-other-123'}}
        event = {'timestamp': stamp(self.now - 60), 'type': 'event_msg', 'payload': {'type': 'token_count',
                 'info': {'last_token_usage': {'input_tokens': 10, 'output_tokens': 5}, 'total_token_usage': {'total_tokens': 15}},
                 'rate_limits': {'primary': {'used_percent': 92.0, 'window_minutes': 300, 'resets_at': int(self.now) + 60},
                                 'plan_type': 'free'}}}
        path.write_text(json.dumps(meta) + '\n' + json.dumps(event) + '\n')
        own = self.home / '.codex/sessions/2026/mine.jsonl'
        own_meta = {'type': 'session_meta', 'payload': {'creator_account_id': 'acct-mine'}}
        own.write_text(json.dumps(own_meta) + '\n' + json.dumps(dict(event, timestamp=stamp(self.now - 30))) + '\n')
        (self.home / 'config/wysun').mkdir(parents=True)
        (self.home / 'config/wysun/ai-accounts.json').write_text(json.dumps({'accounts': [
            {'provider': 'codex', 'accountId': 'acct-other-123', 'label': 'Uni'}]}))
        result = self.collect()
        history = next(a for a in result['accounts'] if a.get('source') == 'history')
        self.assertEqual(history['label'], 'Uni')
        self.assertEqual(history['plan'], 'Free')
        self.assertEqual(history['limits'][0]['usedPercent'], 92.0)
        self.assertEqual(history['usage']['24h']['totals']['output'], 5)
        self.assertEqual(self.account('codex', result)['usage']['24h']['totals']['output'], 5)
        self.assertEqual(len(result['accounts']), 3)

    def test_reset_credits_are_summarised(self):
        summary = {'availableCount': 2, 'credits': [
            {'id': 'c1', 'status': 'available', 'title': 'Weekly reset', 'expiresAt': 10},
            {'id': 'c2', 'status': 'redeemed', 'title': 'Old'}]}
        credits = self.backend.reset_credits(summary)
        self.assertEqual(credits['available'], 2)
        self.assertEqual([c['title'] for c in credits['credits']], ['Weekly reset'])
        self.assertNotIn('id', credits['credits'][0])
        self.assertIsNone(self.backend.reset_credits(None))

    def test_projects_fold_worktrees_into_their_repo(self):
        repo = dict(self.claude_entry('a'), cwd=str(self.home / 'repos/site'))
        tree = dict(self.claude_entry('b', output=10), cwd=str(self.home / '.ao/data/worktrees/site/feature-1'))
        self.claude_log([repo])
        other = self.home / '.claude/projects/q/s.jsonl'
        other.parent.mkdir(parents=True)
        other.write_text(json.dumps(tree) + '\n')
        projects = self.collect()['usage']['24h']['projects']
        self.assertEqual([p['name'] for p in projects], ['site'])
        self.assertEqual(projects[0]['path'], '~/repos/site')
        self.assertEqual((projects[0]['sessions'], projects[0]['worktrees']), (2, 1))
        self.assertEqual(projects[0]['tokens'], 2110 + 1120)

    def test_snapshot_is_saved_for_the_next_start(self):
        result = self.collect()
        saved = json.loads((self.home / 'cache/wysun/ai-usage/snapshot.json').read_text())
        self.assertEqual(saved['generatedAt'], result['generatedAt'])


if __name__ == '__main__':
    unittest.main()
