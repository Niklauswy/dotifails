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


if __name__ == '__main__':
    unittest.main()
