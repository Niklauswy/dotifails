"""Lookup transport works with QtCore only; tests never contact online services."""
import io
import json
import sys
import time
import unittest
from unittest import mock
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication
from wysun_pdf.lookup import LookupClient, request_url, parse_results
from wysun_pdf.lookup_worker import fetch, MAX_RESPONSE


class LookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait(self, condition):
        end = time.monotonic() + 3
        while not condition() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(condition())

    def client(self, code):
        client = LookupClient()
        client.command = lambda: [sys.executable, '-c', code]
        def clean():
            process = client.process
            client.cancel()
            if process:
                process.waitForFinished(1000)
            self.app.processEvents()
            # As the app's event loop would: delete finished processes while their client
            # still exists, never later from Python GC with deletions queued (heap corruption).
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.addCleanup(clean)
        return client

    def test_request_limits_are_utf8_bytes_and_hosts_fixed(self):
        with self.assertRaises(ValueError):
            request_url('translation', 'é' * 251)
        with self.assertRaises(ValueError):
            request_url('concept', 'word', target='file://')
        self.assertIn('q=justice&', request_url('concept', 'justice'))

    def test_malformed_provider_data_does_not_crash(self):
        with self.assertRaises(ValueError):
            parse_results('translation', {'responseStatus': 200, 'responseData': None}, 'word', 'es')
        with self.assertRaises(ValueError):
            parse_results('concept', {'pages': None}, 'word', 'es')

    def test_reference_is_plain_text_and_has_attribution(self):
        result = parse_results('concept', {'pages': [{'key': 'Justice', 'title': 'Justice',
            'excerpt': 'A <span>concept</span> &amp; an idea'}]}, 'justice', 'en')[0]
        self.assertEqual(result['body'], 'A concept & an idea')
        self.assertEqual(result['url'], 'https://en.wikipedia.org/wiki/Justice')
        self.assertIn('CC BY-SA', result['attribution'])

    def test_fetch_limits_body_and_rejects_other_hosts(self):
        with self.assertRaises(ValueError):
            fetch('https://example.com/private')
        response = io.BytesIO(b'x' * (MAX_RESPONSE + 1))
        response.status = 200
        opener = mock.Mock()
        opener.open.return_value = response
        with self.assertRaises(ValueError):
            fetch('https://en.wikipedia.org/w/rest.php/v1/search/page?q=x', opener)

    def test_real_process_roundtrip_without_network_module(self):
        body = {'result': {'responseStatus': 200, 'responseData': {'translatedText': 'justicia'}}}
        client = self.client('import sys; sys.stdin.readline(); print(' + repr(json.dumps(body)) + ')')
        results = []
        client.completed.connect(results.append)
        client.search('translation', 'justice')
        self.wait(lambda: len(results) == 1)
        self.assertEqual(results[0][0]['body'], 'justicia')
        self.assertIsNone(client.process)

    def test_cancel_discards_old_process_response(self):
        client = self.client('import time; time.sleep(1); print("{}")')
        results, failures = [], []
        client.completed.connect(results.append)
        client.failed.connect(failures.append)
        client.search('concept', 'justice')
        old = client.process
        client.cancel()
        old.waitForFinished(1000)
        self.app.processEvents()
        self.assertEqual(results, [])
        self.assertEqual(failures, [])

    def test_timeout_is_one_error(self):
        client = self.client('import time; time.sleep(5)')
        client.timeout_ms = 30
        failures = []
        client.failed.connect(failures.append)
        client.search('concept', 'justice')
        self.wait(lambda: client.process is None)
        self.assertEqual(len(failures), 1)
        self.assertIn('demasiado', failures[0])
