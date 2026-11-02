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


def api_calls(opener):
    """Calls to provider APIs, leaving out the public status pages."""
    return [c for c in opener.calls if '//status.' not in c['url']]


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

    def test_redirects_are_never_followed(self):
        import urllib.request, urllib.response
        seen = []

        class Redirecting(urllib.request.BaseHandler):
            handler_order = 100  # ahead of the real HTTPS handler: nothing reaches the network

            def https_open(self, request):
                seen.append((request.full_url, request.get_header('Authorization')))
                headers = __import__('email.message').message.Message()
                headers['Location'] = 'http://evil.example/steal'
                response = urllib.response.addinfourl(io.BytesIO(b''), headers, request.full_url, 302)
                response.msg = 'Found'
                return response

            def http_open(self, request):
                seen.append((request.full_url, request.get_header('Authorization')))
                response = urllib.response.addinfourl(io.BytesIO(b'{}'), {}, request.full_url, 200)
                response.msg = 'OK'
                return response

        opener = self.credentials.build_opener(Redirecting())
        status, body = self.credentials.get_json('https://api.anthropic.com/x', {'Authorization': 'Bearer ' + SENTINEL},
                                                 frozenset({'api.anthropic.com'}), opener=opener.open)
        self.assertEqual(status, 302)
        self.assertEqual([url for url, _ in seen], ['https://api.anthropic.com/x'])

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
        self.assertEqual(api_calls(opener), [])
        self.assertEqual(claude['source'], 'statusline')
        self.assertTrue(claude['session']['expired'])
        self.assertEqual(claude['limits'][0]['usedPercent'], 31)

    def test_http_errors_fall_back(self):
        self.credentials()
        self.statusline(session=31)
        cases = {401: 'auth', 403: 'scope', 0: 'network'}
        for status, kind in cases.items():
            # Each case starts without the backoff the previous refusal left.
            (self.home / 'cache/wysun/ai-usage/claude-api.json').unlink(missing_ok=True)
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
        self.assertEqual(api_calls(opener), [])
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
        self.assertTrue(api_calls(opener))
        for call in api_calls(opener):
            self.assertTrue(call['url'].startswith('https://api.anthropic.com/'), call['url'])
            self.assertLessEqual(call['timeout'], 5)
            self.assertEqual(call['headers'].get('Anthropic-beta'), 'oauth-2025-04-20')
            self.assertRegex(call['headers'].get('User-agent', ''), r'^claude-cli/\S+ \(external, cli\)$')

    def test_api_is_asked_at_most_every_five_minutes(self):
        self.credentials()
        opener = Opener({'https://api.anthropic.com/': (200, self.usage_body())})
        self.backend.collect(now=self.now, live=True, opener=opener)
        self.backend.collect(now=self.now + 60, live=True, opener=opener)
        self.assertEqual(len(api_calls(opener)), 1)
        later = self.claude(self.backend.collect(now=self.now + 60, live=True, opener=opener))
        self.assertEqual(later['source'], 'api')
        self.assertEqual({l['id']: l['usedPercent'] for l in later['limits']}['session'], 12.0)
        self.backend.collect(now=self.now + 301, live=True, opener=opener)
        self.assertEqual(len(api_calls(opener)), 2)

    def test_rate_limit_backs_off_and_keeps_the_last_values(self):
        self.credentials()
        self.backend.collect(now=self.now, live=True, opener=Opener({'https://api.anthropic.com/': (200, self.usage_body())}))
        limited = Opener({'https://api.anthropic.com/': (429, {})})
        result = self.claude(self.backend.collect(now=self.now + 301, live=True, opener=limited))
        self.assertEqual(result['source'], 'api')
        self.assertEqual(result['updatedAt'], self.now)
        self.backend.collect(now=self.now + 600, live=True, opener=limited)
        self.assertEqual(len(api_calls(limited)), 1)

    def test_http_status_is_kept_for_diagnosis(self):
        self.credentials()
        claude = self.claude(self.collect(Opener({'https://api.anthropic.com/': (429, {'error': 'slow down'})})))
        self.assertEqual(claude['error'], {'kind': 'network', 'status': 429})

    def test_without_credentials_nothing_changes(self):
        self.statusline(session=31)
        opener = Opener()
        claude = self.claude(self.collect(opener))
        self.assertEqual(api_calls(opener), [])
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
        self.assertEqual(api_calls(opener), [])
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
        self.assertEqual(api_calls(opener), [])
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


def statuspage(indicator='none', description='All Systems Operational', components=(), incidents=()):
    return {'status': {'indicator': indicator, 'description': description},
            'components': [{'id': n, 'name': n, 'status': s, 'group_id': None, 'group': False} for n, s in components],
            'incidents': [{'name': n, 'status': 'investigating', 'updated_at': '2026-11-01T17:12:00Z'} for n in incidents]}


class ServiceStatusTests(BackendHome):
    def test_incident_is_summarised(self):
        status = self.backend._sibling('service_status')
        opener = Opener({'https://status.claude.com/': (200, statuspage(
            'minor', 'Partially Degraded Service',
            [('claude.ai', 'operational'), ('Claude Code', 'degraded_performance'), ('Claude API (api.anthropic.com)', 'partial_outage'),
             ('Something else', 'operational')], ['Elevated errors on Claude Code']))})
        result = status.fetch('claude', opener=opener)
        self.assertEqual(result['indicator'], 'minor')
        self.assertEqual(result['description'], 'Elevated errors on Claude Code')
        self.assertEqual([c['name'] for c in result['components']], ['claude.ai', 'Claude Code', 'Claude API (api.anthropic.com)'])
        self.assertEqual(result['components'][1]['status'], 'degraded_performance')
        self.assertEqual(result['url'], 'https://status.claude.com')
        self.assertTrue(opener.calls[0]['url'].startswith('https://status.claude.com/api/v2/summary.json'))

    def test_offline_status_is_unknown(self):
        result = self.backend._sibling('service_status').fetch('codex', opener=Opener(error=OSError('down')))
        self.assertEqual(result['indicator'], 'unknown')

    def test_provider_without_status_page(self):
        self.assertEqual(self.backend._sibling('service_status').fetch('opencode', opener=Opener())['indicator'], 'unknown')

    def test_status_is_cached_for_two_minutes(self):
        opener = Opener({'https://status.claude.com/': (200, statuspage()),
                         'https://status.openai.com/': (200, statuspage())})
        first = self.backend.collect(now=self.now, live=True, opener=opener)
        calls = len(opener.calls)
        self.backend.collect(now=self.now + 60, live=True, opener=opener)
        self.assertEqual(len([c for c in opener.calls if 'status.' in c['url']]),
                         len([c for c in opener.calls[:calls] if 'status.' in c['url']]))
        self.assertEqual(first['status']['claude']['indicator'], 'none')
        self.backend.collect(now=self.now + 200, live=True, opener=opener)
        self.assertGreater(len([c for c in opener.calls if 'status.' in c['url']]), 2)


class AgentsTests(unittest.TestCase):
    """A synthetic /proc: terminal 100 → shell 200 → claude 300 (→ child 301); codex 400 started by pid 1."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.proc = self.root / 'proc'
        self.proc.mkdir()
        (self.proc / 'stat').write_text('cpu 1 2 3\nbtime 1000000\n')
        self.repo = self.root / 'repo'
        (self.repo / '.git').mkdir(parents=True)
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/feat/export\n')
        (self.repo / 'src').mkdir()
        self.process(100, 1, 'ghostty', ['ghostty'])
        self.process(200, 100, 'zsh', ['-zsh'])
        self.process(300, 200, 'claude', ['claude'], cwd=self.repo / 'src',
                     env={'CLAUDE_CONFIG_DIR': str(self.root / 'claude-2'), 'API_KEY': SENTINEL})
        self.process(301, 300, 'claude', ['claude', '--child'], cwd=self.repo)
        self.process(400, 1, 'codex', ['/usr/lib/node_modules/@openai/codex/bin/codex'], cwd=self.root,
                     env={'CODEX_HOME': str(self.root / 'codex-home')})
        self.process(500, 100, 'vim', ['vim'])
        self.agents = module('agents')

    def tearDown(self):
        self.tmp.cleanup()

    def process(self, pid, ppid, comm, argv, cwd=None, env=None, start_ticks=5000):
        folder = self.proc / str(pid)
        folder.mkdir()
        (folder / 'comm').write_text(comm + '\n')
        (folder / 'cmdline').write_bytes(b'\0'.join(a.encode() for a in argv) + b'\0')
        (folder / 'environ').write_bytes(b'\0'.join(f'{k}={v}'.encode() for k, v in (env or {}).items()) + b'\0')
        (folder / 'status').write_text(f'Name:\t{comm}\nPPid:\t{ppid}\nUid:\t{os.getuid()}\t{os.getuid()}\n')
        fields = ['x'] * 52
        fields[18] = str(start_ticks)  # field 22; after ")" field 3 (state) is the first one
        (folder / 'stat').write_text(f'{pid} ({comm}) S ' + ' '.join(fields[:3] + fields[3:]) + '\n')
        (folder / 'cwd').symlink_to(cwd or self.root)

    def scan(self, logs=None):
        homes = {('claude', str((self.root / 'claude-2').resolve())): 'claude:abc', ('codex', str((self.root / 'codex-home').resolve())): 'codex:def'}
        return {a['pid']: a for a in self.agents.scan(self.proc, homes, 1_000_100.0, logs or (lambda *a: None))}

    def test_agents_are_found_with_their_folder_and_branch(self):
        found = self.scan()
        self.assertEqual(set(found), {300, 400})
        claude = found[300]
        self.assertEqual((claude['provider'], claude['accountId']), ('claude', 'claude:abc'))
        self.assertEqual(claude['cwd'], str(self.repo / 'src'))
        self.assertEqual(claude['branch'], 'feat/export')
        self.assertAlmostEqual(claude['startedAt'], 1_000_000 + 5000 / os.sysconf('SC_CLK_TCK'))
        self.assertEqual(found[400]['accountId'], 'codex:def')

    def test_only_home_variables_are_kept(self):
        self.assertNotIn(SENTINEL, json.dumps(list(self.scan().values())))

    def test_child_processes_are_not_counted_twice(self):
        self.assertNotIn(301, self.scan())

    def test_session_without_terminal_has_no_window_pids(self):
        found = self.scan()
        self.assertEqual(found[400]['windowPids'], [])
        self.assertEqual(found[300]['windowPids'], [200, 100])

    def test_busy_and_usage_come_from_the_session_log(self):
        def logs(provider, account, cwd, started):
            if provider == 'claude':
                return {'model': 'claude-opus-5-5', 'tokens': 1200, 'cost': 0.42, 'busy': True}
        claude = self.scan(logs)[300]
        self.assertEqual((claude['model'], claude['tokens'], claude['cost'], claude['busy']),
                         ('claude-opus-5-5', 1200, 0.42, True))
        self.assertFalse(self.scan(logs)[400]['busy'])


class DiskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / '.claude'
        self.now = time.time()
        self.file('projects/p/a.jsonl', 1000)
        self.file('projects/p/old.jsonl', 300, age_days=120)
        self.file('file-history/x', 200)
        self.file('settings.json', 50)
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        (outside / 'big').write_bytes(b'x' * 100000)
        (self.root / 'linked').symlink_to(outside)
        self.disk = module('disk')

    def tearDown(self):
        self.tmp.cleanup()

    def file(self, relative, size, age_days=0):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'x' * size)
        if age_days:
            stamp = self.now - age_days * 86400
            os.utime(path, (stamp, stamp))

    def test_sizes_by_part(self):
        result = self.disk.measure(self.root, 'claude', self.now)
        parts = {p['name']: p['size'] for p in result['parts']}
        self.assertEqual(parts['projects/'], 1300)
        self.assertEqual(parts['file-history/'], 200)
        self.assertEqual(result['measuredAt'], self.now)

    def test_symlinks_outside_root_are_not_followed(self):
        self.assertLess(self.disk.measure(self.root, 'claude', self.now)['total'], 100000)

    def test_old_logs_tip_counts_only_files_older_than_90_days(self):
        tips = {t['kind']: t['size'] for t in self.disk.measure(self.root, 'claude', self.now)['tips']}
        self.assertEqual(tips['old-logs'], 300)
        self.assertEqual(tips['file-history'], 200)


class DiskCacheTests(BackendHome):
    def test_measured_at_most_once_a_day(self):
        (self.home / '.claude/projects').mkdir()
        first = next(a for a in self.backend.collect(now=self.now, live=False)['accounts'] if a['provider'] == 'claude')
        (self.home / '.claude/projects/new.jsonl').write_bytes(b'x' * 5000)
        later = next(a for a in self.backend.collect(now=self.now + 3600, live=False)['accounts'] if a['provider'] == 'claude')
        self.assertEqual(later['disk']['total'], first['disk']['total'])
        nextday = next(a for a in self.backend.collect(now=self.now + 90000, live=False)['accounts'] if a['provider'] == 'claude')
        self.assertGreaterEqual(nextday['disk']['total'], first['disk']['total'] + 5000)


if __name__ == '__main__':
    unittest.main()
