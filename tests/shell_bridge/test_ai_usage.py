"""AI usage backend: accounts, limits from CLI snapshots and incremental token accounting from session logs."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SOURCE = Path(__file__).resolve().parents[2] / 'apps/shell/modules/aiusage/backend.py'
HOOK = SOURCE.with_name('statusline-hook.py')


def load(home):
    env = {'HOME': str(home), 'XDG_STATE_HOME': str(home / 'state'), 'XDG_CACHE_HOME': str(home / 'cache'),
           'XDG_CONFIG_HOME': str(home / 'config'), 'CLAUDE_CONFIG_DIR': str(home / '.claude'),
           'CODEX_HOME': str(home / '.codex'), 'XDG_DATA_HOME': str(home / '.local/share')}
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

    def configure(self, accounts):
        (self.home / 'config/wysun').mkdir(parents=True, exist_ok=True)
        (self.home / 'config/wysun/ai-accounts.json').write_text(json.dumps({'accounts': accounts}))

    def limits_payload(self, used):
        """What Claude Code pipes to its status line command."""
        return {'model': {'display_name': 'Sonnet 5.5'},
                'rate_limits': {'five_hour': {'used_percentage': used, 'resets_at': int(self.now) + 600}}}

    def run_hook(self, payload, config_dir):
        env = dict(os.environ, HOME=str(self.home), XDG_STATE_HOME=str(self.home / 'state'),
                   CLAUDE_CONFIG_DIR=str(config_dir))
        subprocess.run([sys.executable, '-I', str(HOOK)], input=json.dumps(payload).encode(), env=env, check=True)

    def write_snapshot(self, name, used, captured_at=None):
        folder = self.home / 'state/wysun/ai-usage'
        folder.mkdir(parents=True, exist_ok=True)
        limits = {'five_hour': {'used_percentage': used, 'resets_at': int(self.now) + 600}} if used is not None else None
        (folder / name).write_text(json.dumps({'captured_at': captured_at or time.time(), 'rate_limits': limits}))

    def claude_accounts(self):
        return [a for a in self.collect()['accounts'] if a['provider'] == 'claude']

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

    def test_homes_with_the_same_folder_name_keep_their_own_limits(self):
        homes = [self.home / 'one/claude', self.home / 'two/claude']
        for home, used in zip(homes, (11, 77)):
            home.mkdir(parents=True)
            self.run_hook(self.limits_payload(used), home)
        self.configure([{'provider': 'claude', 'home': str(h)} for h in homes])
        self.assertEqual([a['limits'][0]['usedPercent'] for a in self.claude_accounts()[1:]], [11, 77])

    def test_fresh_session_without_limits_keeps_the_known_ones(self):
        self.run_hook(self.limits_payload(40), self.home / '.claude')
        self.run_hook({'model': {'display_name': 'Sonnet 5.5'}, 'rate_limits': None}, self.home / '.claude')
        self.assertEqual(self.account('claude')['limits'][0]['usedPercent'], 40)

    def test_snapshot_without_limits_does_not_hide_newer_limits_from_another_hook(self):
        self.run_hook(self.limits_payload(25), self.home / '.claude')
        self.write_snapshot('claude.json', None, captured_at=time.time() + 60)
        self.assertEqual(self.account('claude')['limits'][0]['usedPercent'], 25)

    def test_snapshot_named_after_the_folder_still_works_for_a_single_home(self):
        work = self.home / 'claude-work'
        work.mkdir()
        self.configure([{'provider': 'claude', 'home': str(work)}])
        self.write_snapshot('claude-claude-work.json', 31)
        self.assertEqual(self.claude_accounts()[1]['limits'][0]['usedPercent'], 31)

    def test_snapshot_named_after_a_shared_folder_name_is_not_guessed(self):
        homes = [self.home / 'one/claude', self.home / 'two/claude']
        for home in homes:
            home.mkdir(parents=True)
        self.configure([{'provider': 'claude', 'home': str(h)} for h in homes])
        self.write_snapshot('claude-claude.json', 31)
        self.assertEqual([a['available'] for a in self.claude_accounts()[1:]], [False, False])

    def test_logs_reached_through_a_symlinked_projects_folder_count_once(self):
        self.claude_log([self.claude_entry('a')])
        shared = self.home / 'claude-shared'
        shared.mkdir()
        (shared / 'projects').symlink_to(self.home / '.claude/projects')
        self.configure([{'provider': 'claude', 'home': str(shared)}])
        result = self.collect()
        self.assertEqual(result['usage']['24h']['totals']['output'], 1000)
        self.assertEqual([a['usage']['24h']['totals']['output'] for a in result['accounts'] if a['provider'] == 'claude'], [1000, 0])

    def seen_home(self, name='extra/claude-two', email='ana@example.com', display=None):
        """A signed-in Claude home that nobody listed in ai-accounts.json."""
        home = self.home / name
        home.mkdir(parents=True)
        (home / '.claude.json').write_text(json.dumps({'oauthAccount': {
            'emailAddress': email, 'organizationType': 'claude_pro', 'displayName': display}}))
        return home

    def test_claude_home_seen_by_the_hook_needs_no_configuration(self):
        home = self.seen_home()
        self.run_hook(self.limits_payload(30), home)
        claude = self.claude_accounts()
        self.assertEqual([a['home'] for a in claude], ['~/.claude', '~/extra/claude-two'])
        self.assertEqual(claude[1]['label'], 'ana')
        self.assertEqual(claude[1]['limits'][0]['usedPercent'], 30)

    def test_home_seen_by_the_hook_is_forgotten_when_its_folder_is_gone(self):
        home = self.seen_home()
        self.run_hook(self.limits_payload(30), home)
        (home / '.claude.json').unlink()
        home.rmdir()
        self.assertEqual([a['home'] for a in self.claude_accounts()], ['~/.claude'])

    def shared_logs(self):
        """~/.claude/projects holds a session of each home; the second home reaches the folder by symlink."""
        self.claude_log([self.claude_entry('a')])
        other = self.home / '.claude/projects/p/s-two.jsonl'
        other.write_text(json.dumps(self.claude_entry('b', output=7)) + '\n')
        shared = self.seen_home('claude-shared')
        (shared / 'projects').symlink_to(self.home / '.claude/projects')
        return shared

    def test_sessions_of_homes_sharing_logs_are_split_by_the_account_that_ran_them(self):
        shared = self.shared_logs()
        self.run_hook(dict(self.limits_payload(30), session_id='s-two'), shared)
        result = self.collect()
        claude = [a for a in result['accounts'] if a['provider'] == 'claude']
        self.assertEqual([a['usage']['24h']['totals']['output'] for a in claude], [1000, 7])
        self.assertEqual(result['usage']['24h']['totals']['output'], 1007)

    def test_subagent_logs_follow_the_session_that_started_them(self):
        shared = self.shared_logs()
        agent = self.home / '.claude/projects/p/s-two/subagents/agent-1.jsonl'
        agent.parent.mkdir(parents=True)
        agent.write_text(json.dumps(self.claude_entry('c', output=3)) + '\n')
        self.run_hook(dict(self.limits_payload(30), session_id='s-two'), shared)
        claude = [a for a in self.collect()['accounts'] if a['provider'] == 'claude']
        self.assertEqual([a['usage']['24h']['totals']['output'] for a in claude], [1000, 10])

    def test_session_of_a_vanished_home_still_counts_for_the_home_that_read_its_log(self):
        self.claude_log([self.claude_entry('a')])
        sessions = self.home / 'state/wysun/ai-usage/sessions'
        sessions.mkdir(parents=True)
        (sessions / 'session').write_text('0123456789')
        self.assertEqual(self.account('claude')['usage']['24h']['totals']['output'], 1000)

    def test_hook_ignores_session_ids_that_are_not_plain_names(self):
        self.run_hook(dict(self.limits_payload(30), session_id='../../escape'), self.home / '.claude')
        written = sorted(p.relative_to(self.home / 'state').as_posix() for p in (self.home / 'state').rglob('*') if p.is_file())
        self.assertEqual(len(written), 1)
        self.assertTrue(written[0].startswith('wysun/ai-usage/claude-'))

    def test_old_session_markers_are_dropped(self):
        sessions = self.home / 'state/wysun/ai-usage/sessions'
        sessions.mkdir(parents=True)
        old, recent = sessions / 'old', sessions / 'recent'
        old.write_text('0123456789')
        recent.write_text('0123456789')
        os.utime(old, (self.now - 91 * 86400,) * 2)
        self.collect()
        self.assertEqual(sorted(p.name for p in sessions.iterdir()), ['recent'])

    def test_accounts_with_the_same_name_are_told_apart_by_email(self):
        for name, email in (('one', 'ana@one.test'), ('two', 'ana.b@two.test')):
            self.run_hook(self.limits_payload(30), self.seen_home(name, email, display='Ana'))
        self.assertEqual([a['label'] for a in self.claude_accounts()[1:]], ['ana', 'ana.b'])

    def test_a_label_the_user_gave_survives_a_name_clash(self):
        for name, email in (('one', 'ana@one.test'), ('two', 'ana.b@two.test')):
            self.run_hook(self.limits_payload(30), self.seen_home(name, email, display='Ana'))
        self.configure([{'provider': 'claude', 'home': str(self.home / 'one'), 'label': 'Ana'}])
        self.assertEqual([a['label'] for a in self.claude_accounts()[1:]], ['Ana', 'ana.b'])

    def test_accounts_that_clash_even_by_email_are_told_apart_by_folder(self):
        for name in ('one', 'two'):
            self.run_hook(self.limits_payload(30), self.seen_home(name, 'ana@same.test', display='Ana'))
        self.assertEqual([a['label'] for a in self.claude_accounts()[1:]], ['ana (one)', 'ana (two)'])

    def test_claude_plan_comes_from_the_cached_profile(self):
        (self.home / '.claude.json').write_text(json.dumps({'oauthAccount': {
            'organizationType': 'claude_max', 'userRateLimitTier': 'default_claude_max_20x', 'displayName': 'Ana'}}))
        claude = self.account('claude')
        self.assertEqual(claude['plan'], 'Max 20x')
        self.assertEqual(claude['label'], 'Ana')

    def codex_history(self, label):
        """Sessions of another Codex account in this home, and a label the user gave that account by id."""
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
        self.configure([{'provider': 'codex', 'accountId': 'acct-other-123', 'label': label}])

    def test_codex_sessions_of_another_account_get_a_history_tab(self):
        self.codex_history('Uni')
        result = self.collect()
        history = next(a for a in result['accounts'] if a.get('source') == 'history')
        self.assertEqual(history['label'], 'Uni')
        self.assertEqual(history['plan'], 'Free')
        self.assertEqual(history['limits'][0]['usedPercent'], 92.0)
        self.assertEqual(history['usage']['24h']['totals']['output'], 5)
        self.assertEqual(self.account('codex', result)['usage']['24h']['totals']['output'], 5)
        self.assertEqual(len(result['accounts']), 3)

    def test_a_label_given_to_a_codex_account_by_id_survives_a_name_clash(self):
        second = self.home / '.codex-2'
        for folder, account in ((self.home / '.codex', 'acct-a'), (second, 'acct-b')):
            log = folder / 'sessions/2026/rollout.jsonl'
            log.parent.mkdir(parents=True)
            log.write_text(json.dumps({'type': 'session_meta', 'payload': {'creator_account_id': account}}) + '\n')
        self.configure([{'provider': 'codex', 'home': str(second)},
                        {'provider': 'codex', 'accountId': 'acct-a', 'label': 'Codex'}])
        labels = [a['label'] for a in self.collect()['accounts'] if a['provider'] == 'codex']
        self.assertEqual(labels, ['Codex', 'Codex (.codex-2)'])

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

    def limits_snapshot(self, session, weekly, session_reset, weekly_reset, at):
        (self.home / 'state/wysun/ai-usage').mkdir(parents=True, exist_ok=True)
        (self.home / 'state/wysun/ai-usage/claude.json').write_text(json.dumps({'captured_at': at, 'rate_limits': {
            'five_hour': {'used_percentage': session, 'resets_at': session_reset},
            'seven_day': {'used_percentage': weekly, 'resets_at': weekly_reset}}}))

    def collect_at(self, now):
        return self.backend.collect(now=now, live=False)

    def test_history_keeps_points_of_the_current_window(self):
        reset = self.now + 4 * 86400
        for i, used in enumerate((10, 12, 15)):
            at = self.now - (2 - i) * 1800
            self.limits_snapshot(1, used, at + 3600, reset, at)
            result = self.collect_at(at)
        weekly = next(l for l in self.account('claude', result)['limits'] if l['id'] == 'weekly')
        self.assertEqual([p[1] for p in weekly['history']], [10, 12, 15])
        self.assertEqual(weekly['windows'], [])

    def test_previous_windows_split_at_each_reset(self):
        old_reset = self.now - 3600
        self.limits_snapshot(1, 70, old_reset - 600, old_reset, old_reset - 7200)
        self.collect_at(old_reset - 7200)
        self.limits_snapshot(1, 88, old_reset - 600, old_reset, old_reset - 1800)
        self.collect_at(old_reset - 1800)
        self.limits_snapshot(1, 5, self.now + 600, self.now + 7 * 86400 - 3600, self.now)
        weekly = next(l for l in self.account('claude', self.collect_at(self.now))['limits'] if l['id'] == 'weekly')
        self.assertEqual([p[1] for p in weekly['history']], [5])
        self.assertEqual(len(weekly['windows']), 1)
        self.assertEqual(weekly['windows'][0]['usedPercent'], 88)
        self.assertEqual(weekly['windows'][0]['endedAt'], int(old_reset))
        self.assertIsNone(weekly['windows'][0]['exhaustedAt'])

    def test_exhausted_time_is_recorded(self):
        old_reset = self.now - 3600
        self.limits_snapshot(1, 90, old_reset - 600, old_reset, old_reset - 7200)
        self.collect_at(old_reset - 7200)
        self.limits_snapshot(1, 100, old_reset - 600, old_reset, old_reset - 5400)
        self.collect_at(old_reset - 5400)
        self.limits_snapshot(1, 2, self.now + 600, self.now + 86400, self.now)
        weekly = next(l for l in self.account('claude', self.collect_at(self.now))['limits'] if l['id'] == 'weekly')
        self.assertAlmostEqual(weekly['windows'][0]['exhaustedAt'], old_reset - 5400, delta=1)

    def test_points_older_than_90_days_are_dropped(self):
        old = self.now - 91 * 86400
        self.limits_snapshot(1, 50, old + 600, old + 3600, old)
        self.collect_at(old)
        self.limits_snapshot(1, 5, self.now + 600, self.now + 86400, self.now)
        self.collect_at(self.now)
        stored = (self.home / 'state/wysun/ai-usage/limits.jsonl').read_text().splitlines()
        self.assertTrue(stored)
        self.assertTrue(all(json.loads(line)['t'] >= self.now - 90 * 86400 for line in stored))

    def test_unchanged_limits_are_not_stored_again_within_15_minutes(self):
        self.limits_snapshot(1, 50, self.now + 600, self.now + 3600, self.now)
        self.collect_at(self.now)
        self.collect_at(self.now + 60)
        stored = (self.home / 'state/wysun/ai-usage/limits.jsonl').read_text().splitlines()
        self.assertEqual(len(stored), 2)  # session and weekly, once each

    def test_year_and_hourly_ranges_exist(self):
        usage = self.collect()['usage']
        self.assertEqual(usage['365d']['points'], 365)
        self.assertEqual(usage['hours90']['points'], 2160)
        self.assertEqual(usage['hours90']['step'], 3600)

    def test_daily_unpriced_flag(self):
        self.claude_log([self.claude_entry('a', model='mystery-model-1')])
        usage = self.collect()['usage']['30d']
        key = self.account('claude')['id']
        self.assertTrue(usage['series'][key]['unpriced'][-1])
        self.assertFalse(usage['series'][key]['unpriced'][0])

    def test_agent_session_details_come_from_its_newest_log(self):
        path = self.claude_log([dict(self.claude_entry('a', model='claude-opus-5-5', output=500, ago=30), cwd='/work/site')])
        files = self.backend.scan(self.backend.load_accounts(), self.now)
        account = self.account('claude')['id']
        details = self.backend.session_details(files, 'claude', account, '/work/site', self.now - 120, self.now)
        self.assertEqual(details['model'], 'claude-opus-5-5')
        self.assertEqual(details['tokens'], 100 + 1000 + 10 + 500)
        self.assertTrue(details['busy'])
        os.utime(path, (self.now - 60, self.now - 60))
        self.assertFalse(self.backend.session_details(files, 'claude', account, '/work/site', self.now - 120, self.now)['busy'])
        self.assertIsNone(self.backend.session_details(files, 'claude', account, '/elsewhere', self.now - 120, self.now))

    def test_snapshot_lists_agents(self):
        self.assertIsInstance(self.collect()['agents'], list)

    def test_prepare_claude_account_writes_hook_settings(self):
        (self.home / '.claude-2').mkdir()
        folder = Path(self.backend.prepare_account('claude'))
        self.assertEqual(folder, self.home / '.claude-3')
        settings = json.loads((folder / 'settings.json').read_text())
        self.assertIn('statusline-hook.py', settings['statusLine']['command'])
        self.assertEqual(settings['statusLine']['type'], 'command')

    def test_prepare_codex_account_registers_home(self):
        self.configure([{'provider': 'codex', 'home': '~/.codex-work', 'label': 'Work'}])
        folder = Path(self.backend.prepare_account('codex'))
        self.assertEqual(folder, self.home / '.codex-2')
        self.assertTrue(folder.is_dir())
        accounts = json.loads((self.home / 'config/wysun/ai-accounts.json').read_text())['accounts']
        self.assertEqual(accounts[0]['label'], 'Work')
        self.assertEqual(accounts[-1], {'provider': 'codex', 'home': str(folder)})

    def test_prepare_other_providers_creates_nothing(self):
        self.assertIsNone(self.backend.prepare_account('opencode'))

    def test_sibling_modules_load_by_path(self):
        credentials = self.backend._sibling('credentials')
        self.assertTrue(callable(credentials.get_json))
        self.assertIs(self.backend._sibling('credentials'), credentials)


if __name__ == '__main__':
    unittest.main()
