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


if __name__ == '__main__':
    unittest.main()
