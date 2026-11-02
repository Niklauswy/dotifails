"""AI usage data sources beside the log scan: credentials, provider APIs, OpenCode, status, agents and disk.

Every credential here is synthetic and carries SENTINEL, so a leak into any output or file is caught.
"""
import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

AIUSAGE = Path(__file__).resolve().parents[2] / 'apps/shell/modules/aiusage'
SENTINEL = 'sk-SENTINEL-do-not-leak-7f3a'


def module(name):
    spec = importlib.util.spec_from_file_location('wysun_ai_usage_' + name, AIUSAGE / f'{name}.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class FakeResponse(io.BytesIO):
    def __init__(self, status, body):
        super().__init__(json.dumps(body).encode() if body is not None else b'')
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Opener:
    """Records requests; answers from a {url-prefix: (status, body)} table."""

    def __init__(self, answers=None, error=None):
        self.answers = answers or {}
        self.error = error
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append({'url': request.full_url, 'timeout': timeout, 'headers': dict(request.header_items())})
        if self.error:
            raise self.error
        for prefix, (status, body) in self.answers.items():
            if request.full_url.startswith(prefix):
                if status >= 400:
                    import urllib.error
                    raise urllib.error.HTTPError(request.full_url, status, 'error', {}, io.BytesIO(json.dumps(body or {}).encode()))
                return FakeResponse(status, body)
        raise OSError('no answer')


class CredentialsTests(unittest.TestCase):
    def setUp(self):
        self.credentials = module('credentials')

    def test_rejects_other_hosts_and_plain_http(self):
        allowed = frozenset({'api.anthropic.com'})
        with self.assertRaises(ValueError):
            self.credentials.get_json('https://evil.example/x', {}, allowed, opener=Opener())
        with self.assertRaises(ValueError):
            self.credentials.get_json('http://api.anthropic.com/x', {}, allowed, opener=Opener())
        with self.assertRaises(ValueError):
            self.credentials.get_json('https://api.anthropic.com.evil.example/x', {}, allowed, opener=Opener())

    def test_network_error_returns_zero_without_secret(self):
        opener = Opener(error=OSError('boom'))
        status, body = self.credentials.get_json('https://api.anthropic.com/x', {'Authorization': 'Bearer ' + SENTINEL},
                                                 frozenset({'api.anthropic.com'}), opener=opener)
        self.assertEqual((status, body), (0, None))

    def test_http_error_returns_its_status(self):
        opener = Opener({'https://api.anthropic.com/': (401, {'error': 'nope'})})
        status, body = self.credentials.get_json('https://api.anthropic.com/x', {}, frozenset({'api.anthropic.com'}),
                                                 opener=opener)
        self.assertEqual(status, 401)
        self.assertEqual(body, {'error': 'nope'})

    def test_timeout_is_bounded(self):
        opener = Opener({'https://api.anthropic.com/': (200, {})})
        self.credentials.get_json('https://api.anthropic.com/x', {}, frozenset({'api.anthropic.com'}), timeout=60,
                                  opener=opener)
        self.assertLessEqual(opener.calls[0]['timeout'], 5)

    def test_unreadable_file_is_none(self):
        self.assertIsNone(self.credentials.read_json(Path('/nonexistent/creds.json')))
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'creds.json'
            bad.write_text('{"token": "' + SENTINEL)
            self.assertIsNone(self.credentials.read_json(bad))


def iso(epoch):
    return time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(epoch))


class BackendHome(unittest.TestCase):
    """A temporary HOME with the backend loaded against it."""

    def setUp(self):
        from tests.shell_bridge.test_ai_usage import load
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.now = time.time()
        (self.home / '.claude').mkdir()
        (self.home / '.codex').mkdir()
        self.backend = load(self.home)
        # No real CLI is ever started from these tests.
        self.backend.find_codex = lambda: None

    def tearDown(self):
        self.tmp.cleanup()

    def leaked(self, result):
        """Places where SENTINEL ended up: the backend output or any file it wrote."""
        places = ['output'] if SENTINEL in json.dumps(result) else []
        for base in ('state', 'cache', 'config'):
            for path in (self.home / base).rglob('*'):
                if path.is_file() and SENTINEL in path.read_text(errors='ignore'):
                    places.append(str(path))
        return places


class ClaudeApiTests(BackendHome):
    def credentials(self, expires_in=3600, scopes=('user:inference', 'user:profile')):
        (self.home / '.claude/.credentials.json').write_text(json.dumps({'claudeAiOauth': {
            'accessToken': SENTINEL, 'refreshToken': SENTINEL + '-refresh',
            'expiresAt': int((self.now + expires_in) * 1000), 'scopes': list(scopes)}}))

    def statusline(self, session=31):
        (self.home / 'state/wysun/ai-usage').mkdir(parents=True, exist_ok=True)
        (self.home / 'state/wysun/ai-usage/claude.json').write_text(json.dumps({'captured_at': self.now, 'rate_limits': {
            'five_hour': {'used_percentage': session, 'resets_at': self.now + 600}}}))

    def usage_body(self):
        return {
            'five_hour': {'utilization': 12.0, 'resets_at': iso(self.now + 3 * 3600)},
            'seven_day': {'utilization': 40.0, 'resets_at': iso(self.now + 4 * 86400)},
            'seven_day_opus': {'utilization': 6.0, 'resets_at': iso(self.now + 4 * 86400)},
            'seven_day_sonnet': None,
            'extra_usage': {'is_enabled': True, 'monthly_limit': 5000, 'used_credits': 420, 'utilization': 8.4,
                            'currency': 'USD'},
            'iguana_necktie': {'limit_dollars': 25, 'used_dollars': 6.5, 'resets_at': iso(self.now + 20 * 86400)},
            'cedar_ember': {'eligible': True, 'grants': [{'resets_left': 1, 'ends_at': iso(self.now + 11 * 86400)}]},
        }

    def collect(self, opener):
        return self.backend.collect(now=self.now, live=True, opener=opener)

    def claude(self, result):
        return next(a for a in result['accounts'] if a['provider'] == 'claude')

    def test_api_limits_win_over_statusline(self):
        self.credentials()
        self.statusline(session=31)
        claude = self.claude(self.collect(Opener({'https://api.anthropic.com/api/oauth/usage': (200, self.usage_body())})))
        self.assertEqual(claude['source'], 'api')
        limits = {l['id']: l for l in claude['limits']}
        self.assertEqual(limits['session']['usedPercent'], 12.0)
        self.assertEqual(limits['weekly']['usedPercent'], 40.0)
        self.assertEqual(limits['weekly_opus']['label'], 'Opus')
        self.assertNotIn('weekly_sonnet', limits)
        self.assertAlmostEqual(limits['session']['resetsAt'], self.now + 3 * 3600, delta=2)

    def test_extra_usage_and_cloud_credits_are_mapped(self):
        self.credentials()
        claude = self.claude(self.collect(Opener({'https://api.anthropic.com/': (200, self.usage_body())})))
        extra = claude['extra']
        self.assertEqual((extra['spent'], extra['cap'], extra['currency']), (4.2, 50.0, 'USD'))
        first = time.gmtime(self.now)
        year, month = (first.tm_year + 1, 1) if first.tm_mon == 12 else (first.tm_year, first.tm_mon + 1)
        import calendar
        self.assertEqual(extra['resetsAt'], calendar.timegm((year, month, 1, 0, 0, 0)))
        self.assertEqual(claude['cloud']['remaining'], 18.5)
        self.assertEqual(claude['resetCredits']['available'], 1)

    def test_expired_token_falls_back_to_statusline(self):
        self.credentials(expires_in=-60)
        self.statusline(session=31)
        opener = Opener({'https://api.anthropic.com/': (200, self.usage_body())})
        claude = self.claude(self.collect(opener))
        self.assertEqual(opener.calls, [])
        self.assertEqual(claude['source'], 'statusline')
        self.assertTrue(claude['session']['expired'])
        self.assertEqual(claude['limits'][0]['usedPercent'], 31)

    def test_http_errors_fall_back(self):
        self.credentials()
        self.statusline(session=31)
        cases = {401: 'auth', 403: 'scope', 0: 'network'}
        for status, kind in cases.items():
            opener = Opener(error=OSError('down')) if status == 0 else Opener(
                {'https://api.anthropic.com/': (status, {'error': {'message': 'missing scope user:profile'}})})
            claude = self.claude(self.collect(opener))
            self.assertEqual(claude['error']['kind'], kind, status)
            self.assertEqual(claude['source'], 'statusline')
            self.assertEqual(claude['limits'][0]['usedPercent'], 31)

    def test_without_profile_scope_the_api_is_not_called(self):
        self.credentials(scopes=('user:inference',))
        opener = Opener({'https://api.anthropic.com/': (200, self.usage_body())})
        claude = self.claude(self.collect(opener))
        self.assertEqual(opener.calls, [])
        self.assertEqual(claude['error']['kind'], 'scope')

    def test_token_never_leaves_the_process(self):
        self.credentials()
        result = self.collect(Opener({'https://api.anthropic.com/': (200, self.usage_body())}))
        self.assertEqual(self.leaked(result), [])
        failed = self.collect(Opener({'https://api.anthropic.com/': (401, {'error': SENTINEL})}))
        self.assertEqual(self.leaked(failed), [])

    def test_only_anthropic_is_contacted_with_a_bounded_timeout(self):
        self.credentials()
        opener = Opener({'https://api.anthropic.com/': (200, self.usage_body())})
        self.collect(opener)
        self.assertTrue(opener.calls)
        for call in opener.calls:
            self.assertTrue(call['url'].startswith('https://api.anthropic.com/'), call['url'])
            self.assertLessEqual(call['timeout'], 5)
            self.assertEqual(call['headers'].get('Anthropic-beta'), 'oauth-2025-04-20')

    def test_without_credentials_nothing_changes(self):
        self.statusline(session=31)
        opener = Opener()
        claude = self.claude(self.collect(opener))
        self.assertEqual(opener.calls, [])
        self.assertEqual(claude['source'], 'statusline')
        self.assertIsNone(claude['session'])
        self.assertIsNone(claude['error'])


class OpenCodeTests(BackendHome):
    def setUp(self):
        super().setUp()
        self.data = self.home / '.local/share/opencode'
        self.data.mkdir(parents=True)
        self.db = self.data / 'opencode.db'
        with sqlite3.connect(self.db) as db:
            db.execute('create table message (id text primary key, session_id text, time_created int, time_updated int, data text)')
            db.execute('create table session_message (id text primary key, session_id text, type text, seq int, '
                       'time_created int, time_updated int, data text)')
            db.execute('create table session (id text primary key, directory text)')
            db.execute('create table session_v2 (id text primary key, directory text)')
            db.execute('create table credential (id text, integration_id text, label text, value text, connector_id text, '
                       'method_id text, active int, time_created int, time_updated int)')
            db.execute("insert into session values ('s1', '/home/u/loom')")
            db.execute("insert into session_v2 values ('s2', '/home/u/tesis')")

    def legacy(self, ident, provider, model, output=100, cost=0.5, ago=60):
        data = {'role': 'assistant', 'providerID': provider, 'modelID': model, 'cost': cost,
                'path': {'cwd': '/home/u/loom'}, 'time': {'created': int((self.now - ago) * 1000)},
                'tokens': {'input': 10, 'output': output, 'reasoning': 0, 'cache': {'read': 1000, 'write': 5}}}
        with sqlite3.connect(self.db) as db:
            db.execute('insert into message values (?, ?, 0, 0, ?)', (ident, 's1', json.dumps(data)))

    def v2(self, ident, provider, model, output=100, cost=0.25, ago=60):
        data = {'agent': 'build', 'model': {'id': model, 'providerID': provider}, 'cost': cost,
                'time': {'created': int((self.now - ago) * 1000)},
                'tokens': {'input': 20, 'output': output, 'reasoning': 0, 'cache': {'read': 0, 'write': 0}}}
        with sqlite3.connect(self.db) as db:
            db.execute("insert into session_message values (?, 's2', 'assistant', 1, 0, 0, ?)", (ident, json.dumps(data)))

    def credential(self, integration='opencode-go', kind='key', expires_in=3600):
        value = {'type': kind, 'key': SENTINEL} if kind == 'key' else {
            'type': 'oauth', 'access': SENTINEL, 'refresh': SENTINEL, 'expires': int((self.now + expires_in) * 1000)}
        with sqlite3.connect(self.db) as db:
            db.execute("insert into credential values ('c1', ?, 'x', ?, null, null, 1, 0, 0)", (integration, json.dumps(value)))

    def collect(self, opener=None):
        return self.backend.collect(now=self.now, live=True, opener=opener or Opener())

    def opencode(self, result):
        return next(a for a in result['accounts'] if a['provider'] == 'opencode')

    def test_history_counts_each_message_once(self):
        self.legacy('m1', 'deepseek', 'deepseek-v4', output=100)
        self.v2('m1', 'deepseek', 'deepseek-v4', output=100)
        self.v2('m2', 'deepseek', 'deepseek-v4', output=200)
        rows = self.backend._sibling('opencode').history(self.db, self.now - 86400)
        self.assertEqual(sorted(r['output'] for r in rows), [100, 200])

    def test_models_are_prefixed_by_provider_and_keep_their_cost(self):
        self.legacy('m1', 'deepseek', 'deepseek-v4', cost=0.5)
        self.v2('m2', 'openai', 'gpt-5.4', cost=0.25)
        usage = self.opencode(self.collect())['usage']['24h']
        models = {m['model']: m for m in usage['models']}
        self.assertEqual(set(models), {'deepseek/deepseek-v4', 'openai/gpt-5.4'})
        self.assertAlmostEqual(models['deepseek/deepseek-v4']['cost'], 0.5)
        self.assertAlmostEqual(usage['totals']['cost'], 0.75)
        self.assertEqual({p['name'] for p in usage['projects']}, {'loom', 'tesis'})

    def test_no_login_keeps_history(self):
        self.legacy('m1', 'deepseek', 'deepseek-v4')
        opener = Opener()
        account = self.opencode(self.collect(opener))
        self.assertEqual(opener.calls, [])
        self.assertEqual(account['limits'], [])
        self.assertEqual(account['reason'], 'subscription')
        self.assertGreater(account['usage']['30d']['totals']['output'], 0)

    def test_go_quota_is_mapped(self):
        self.credential()
        body = {'usage': {'rolling': {'usagePercent': 12, 'resetInSec': 3600},
                          'weekly': {'usagePercent': 30, 'resetInSec': 86400},
                          'monthly': {'usagePercent': 50, 'resetInSec': 864000}}}
        opener = Opener({'https://opencode.ai/zen/go/v1/usage': (200, body)})
        account = self.opencode(self.collect(opener))
        limits = {l['id']: l for l in account['limits']}
        self.assertEqual(limits['session']['usedPercent'], 12)
        self.assertAlmostEqual(limits['session']['resetsAt'], self.now + 3600, delta=2)
        self.assertEqual(limits['monthly']['windowMinutes'], 43200)
        self.assertEqual(account['source'], 'opencode-api')
        self.assertEqual(opener.calls[0]['headers'].get('Authorization'), 'Bearer ' + SENTINEL)

    def test_expired_oauth_login_is_not_used(self):
        self.credential(integration='opencode', kind='oauth', expires_in=-10)
        opener = Opener({'https://opencode.ai/': (200, {})})
        account = self.opencode(self.collect(opener))
        self.assertEqual(opener.calls, [])
        self.assertTrue(account['session']['expired'])

    def test_db_opened_read_only(self):
        self.legacy('m1', 'deepseek', 'deepseek-v4')
        self.db.chmod(0o444)
        self.data.chmod(0o555)
        try:
            account = self.opencode(self.collect())
        finally:
            self.data.chmod(0o755)
            self.db.chmod(0o644)
        self.assertGreater(account['usage']['24h']['totals']['output'], 0)

    def test_opencode_token_never_leaves_the_process(self):
        self.credential()
        result = self.collect(Opener({'https://opencode.ai/': (401, {'error': SENTINEL})}))
        self.assertEqual(self.leaked(result), [])
        self.assertEqual(self.opencode(result)['error']['kind'], 'auth')

    def test_without_opencode_there_is_no_account(self):
        self.db.unlink()
        self.data.rmdir()
        self.assertFalse([a for a in self.collect()['accounts'] if a['provider'] == 'opencode'])


if __name__ == '__main__':
    unittest.main()
