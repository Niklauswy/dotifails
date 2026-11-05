"""wysun_cloud.monitoring asks Cloud Monitoring for CPU history without leaking the token.

The fake gcloud prints the synthetic token ``ya29.SYNTHETIC-TEST-TOKEN``; no test
here talks to the network (``monitoring.OPENER.open`` is always patched) and no
test reads or writes a real credential.
"""
from datetime import datetime
import io
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/python'
FIXTURES = ROOT / 'tests/fixtures/cloud'
sys.path.insert(0, str(APP))

from wysun_cloud import monitoring  # noqa: E402
from wysun_cloud.gcloud import Gcloud, GcloudError  # noqa: E402
from wysun_cloud.model import Instance  # noqa: E402

TOKEN = 'ya29.SYNTHETIC-TEST-TOKEN'
METRIC = 'compute.googleapis.com/instance/cpu/utilization'


def epoch(text):
    """A Cloud Monitoring timestamp as seconds since the epoch."""
    return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()


def payload(points, next_page=None):
    """A Cloud Monitoring ``timeSeries.list`` answer with one aligned series."""
    data = {
        'timeSeries': [{
            'points': [
                {'interval': {'endTime': when}, 'value': {'doubleValue': value}}
                for when, value in points
            ],
        }],
    }
    if next_page:
        data['nextPageToken'] = next_page
    return data


class FakeResponse:
    """The minimum ``urlopen`` answer the module reads."""

    def __init__(self, data):
        self.payload = data if isinstance(data, bytes) else json.dumps(data).encode('utf-8')

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class LogCollector(logging.Handler):
    """Collect every log line the call might emit, at any level."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        runtime = self.base / 'runtime'
        runtime.mkdir(mode=0o700)
        self.env = {
            'HOME': str(self.base),
            'XDG_CACHE_HOME': str(self.base / 'cache'),
            'XDG_CONFIG_HOME': str(self.base / 'config'),
            'XDG_DATA_HOME': str(self.base / 'data'),
            'XDG_STATE_HOME': str(self.base / 'state'),
            'XDG_RUNTIME_DIR': str(runtime),
            'PATH': f'{FIXTURES}{os.pathsep}{os.environ.get("PATH", "")}',
        }
        self.patcher = mock.patch.dict(os.environ, self.env)
        self.patcher.start()
        for name in ('FAKE_GCLOUD_SLEEP', 'FAKE_GCLOUD_AUTH_ERROR', 'FAKE_GCLOUD_FAIL_PROJECT',
                     'FAKE_GCLOUD_FAIL_ACTION', 'FAKE_GCLOUD_LOG'):
            os.environ.pop(name, None)
        self.log = self.base / 'gcloud.log'
        os.environ['FAKE_GCLOUD_LOG'] = str(self.log)
        monitoring.clear_cache()
        self.gcloud = Gcloud()
        self.inst = Instance(
            project='mi-proyecto-prod', name='api-backend', zone='us-central1-a', status='RUNNING',
            machine_type='e2-small', external_ip='34.122.10.7', internal_ip='10.128.0.2',
            spot=False, os='debian-12-bookworm', disks=['api-backend'], network='default',
            tags=['web', 'api'], started=None,
        )

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def patch_urlopen(self, answers):
        """Patch ``urllib.request.urlopen`` and return the list of captured ``(request, timeout)``."""
        calls = []

        def fake(request, timeout=None):
            calls.append((request, timeout))
            answer = answers.pop(0)
            if isinstance(answer, BaseException):
                raise answer
            return FakeResponse(answer)

        patcher = mock.patch.object(monitoring.OPENER, 'open', side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def query(self, request):
        return urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)

    def auth_calls(self):
        """The fake gcloud log lines for ``auth print-access-token``."""
        if not self.log.exists():
            return []
        return [line for line in self.log.read_text(encoding='utf-8').splitlines()
                if line.startswith('auth print-access-token')]

    def test_request_shape_and_parse(self):
        first = payload([
            ('2026-11-04T10:05:00Z', 0.25),
            ('2026-11-04T10:00:00Z', -0.2),
        ], next_page='page-2')
        second = payload([('2026-11-04T10:10:00Z', 1.5)])
        weekly = payload([('2026-11-01T00:00:00Z', 0.4)])
        calls = self.patch_urlopen([first, second, weekly])

        points = monitoring.cpu_history(self.gcloud, self.inst, 24)
        self.assertEqual(points, [
            (epoch('2026-11-04T10:00:00Z'), 0.0),
            (epoch('2026-11-04T10:05:00Z'), 0.25),
            (epoch('2026-11-04T10:10:00Z'), 1.0),
        ])

        self.assertEqual(len(calls), 2)
        request, timeout = calls[0]
        self.assertEqual(timeout, 15)
        self.assertEqual(request.get_method(), 'GET')
        parts = urllib.parse.urlsplit(request.full_url)
        self.assertEqual((parts.scheme, parts.netloc), ('https', 'monitoring.googleapis.com'))
        self.assertEqual(parts.path, '/v3/projects/mi-proyecto-prod/timeSeries')

        query = self.query(request)
        self.assertEqual(query['filter'], [
            f'metric.type="{METRIC}" AND metric.labels.instance_name="api-backend"'])
        self.assertEqual(query['aggregation.alignmentPeriod'], ['300s'])
        self.assertEqual(query['aggregation.perSeriesAligner'], ['ALIGN_MEAN'])
        self.assertEqual(query['aggregation.crossSeriesReducer'], ['REDUCE_MEAN'])
        self.assertTrue(query['interval.startTime'][0].endswith('Z'))
        self.assertTrue(query['interval.endTime'][0].endswith('Z'))
        span = epoch(query['interval.endTime'][0]) - epoch(query['interval.startTime'][0])
        self.assertAlmostEqual(span, 24 * 3600, delta=2)
        self.assertNotIn('pageToken', query)

        self.assertEqual(self.query(calls[1][0])['pageToken'], ['page-2'])

        weekly_points = monitoring.cpu_history(self.gcloud, self.inst, 168)
        self.assertEqual(weekly_points, [(epoch('2026-11-01T00:00:00Z'), 0.4)])
        self.assertEqual(self.query(calls[2][0])['aggregation.alignmentPeriod'], ['3600s'])
        span = (epoch(self.query(calls[2][0])['interval.endTime'][0])
                - epoch(self.query(calls[2][0])['interval.startTime'][0]))
        self.assertAlmostEqual(span, 168 * 3600, delta=2)

    def test_token_only_in_authorization_header(self):
        calls = self.patch_urlopen([payload([])])
        monitoring.cpu_history(self.gcloud, self.inst, 24)

        request = calls[0][0]
        parts = urllib.parse.urlsplit(request.full_url)
        self.assertEqual(parts.scheme, 'https')
        self.assertEqual(parts.hostname, 'monitoring.googleapis.com')
        self.assertNotIn(TOKEN, request.full_url)

        headers = request.header_items()
        authorization = [value for name, value in headers if name.lower() == 'authorization']
        self.assertEqual(authorization, [f'Bearer {TOKEN}'])
        for name, value in headers:
            if name.lower() != 'authorization':
                self.assertNotIn(TOKEN, value, name)

        # The token comes from gcloud on demand and is never kept on the object.
        self.assertNotIn(TOKEN, repr(vars(self.gcloud)))
        self.assertNotIn(TOKEN, repr(monitoring.__dict__))

    def test_errors_never_contain_the_token(self):
        body = json.dumps({
            'error': {
                'code': 403,
                'status': 'PERMISSION_DENIED',
                'message': f'Request had invalid authentication credentials: {TOKEN}',
            },
        }).encode('utf-8')
        error = urllib.error.HTTPError(
            'https://monitoring.googleapis.com/v3/projects/p/timeSeries',
            403, 'Forbidden', {'Content-Type': 'application/json'}, io.BytesIO(body))
        calls = self.patch_urlopen([error])

        collector = LogCollector()
        root = logging.getLogger()
        previous = root.level
        root.addHandler(collector)
        root.setLevel(logging.DEBUG)
        try:
            with self.assertRaises(GcloudError) as caught:
                monitoring.cpu_history(self.gcloud, self.inst, 24)
        finally:
            root.removeHandler(collector)
            root.setLevel(previous)

        self.assertEqual(len(calls), 1)
        exception = caught.exception
        self.assertIn('403', exception.message)
        self.assertIn('PERMISSION_DENIED', exception.message)
        self.assertNotIn(TOKEN, str(exception))
        self.assertNotIn(TOKEN, repr(exception))

        node = exception
        while node is not None:
            self.assertNotIn(TOKEN, str(node))
            self.assertNotIn(TOKEN, repr(node))
            node = node.__cause__ or node.__context__
        self.assertIsNone(exception.__cause__)

        self.assertEqual(collector.messages, [])

        # A network failure is a short Spanish message too, never the URL or the token.
        self.patch_urlopen([urllib.error.URLError(f'connection refused {TOKEN}')])
        with self.assertRaises(GcloudError) as network:
            monitoring.cpu_history(self.gcloud, self.inst, 24)
        self.assertEqual(network.exception.message, 'Monitoring no respondió')
        self.assertNotIn(TOKEN, str(network.exception))
        self.assertIsNone(network.exception.__context__)
        self.assertIsNone(network.exception.__cause__)

    def test_token_never_written_to_disk(self):
        self.patch_urlopen([payload([('2026-11-04T10:00:00Z', 0.5)])])
        monitoring.cpu_history(self.gcloud, self.inst, 24)

        for path in sorted(self.base.rglob('*')):
            if not path.is_file():
                continue
            self.assertNotIn(TOKEN.encode('utf-8'), path.read_bytes(), path)
        for name, value in os.environ.items():
            self.assertNotIn(TOKEN, value, name)

    def test_results_cached_not_token(self):
        self.patch_urlopen([
            payload([('2026-11-04T10:00:00Z', 0.5)]),
            payload([('2026-11-04T11:00:00Z', 0.75)]),
        ])

        first = monitoring.cpu_history(self.gcloud, self.inst, 24)
        second = monitoring.cpu_history(self.gcloud, self.inst, 24)

        self.assertEqual(first, second)
        self.assertEqual(len(self.auth_calls()), 1)
        self.assertEqual(len(self.log.read_text(encoding='utf-8').splitlines()), 1)
        self.assertNotIn(TOKEN, repr(monitoring._cache))

        # A different range is a different cache key, so gcloud answers again.
        monitoring.cpu_history(self.gcloud, self.inst, 168)
        self.assertEqual(len(self.auth_calls()), 2)


    def test_redirects_are_refused_so_the_header_never_moves(self):
        handler = next(h for h in monitoring.OPENER.handlers
                       if isinstance(h, urllib.request.HTTPRedirectHandler))
        request = urllib.request.Request('https://monitoring.googleapis.com/v3/x',
                                         headers={'Authorization': f'Bearer {TOKEN}'})
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(request, io.BytesIO(b''), 302, 'Found', {},
                                     'http://evil.example/steal')


if __name__ == '__main__':
    unittest.main()
