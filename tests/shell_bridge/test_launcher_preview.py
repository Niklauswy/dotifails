"""Content classification and bounded webpage previews without external requests."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
import launcher_web


class PreviewTests(unittest.TestCase):
    def test_short_content_classification(self):
        source = (ROOT / 'apps/shell/modules/launcher/services/Content.js').read_text().replace('.pragma library', '')
        result = subprocess.run(['node'], input=source + '''
for (const [text, expected] of [
 ['👨‍👩‍👧‍👦', 'emoji'], ['👍🏽', 'emoji'], ['🇲🇽', 'emoji'], ['1️⃣', 'emoji'],
 ['🙂 🙂', 'emoji'], ['hello 🙂', 'text'], ['', 'text'], ['42', 'number'],
 ['-1,25', 'number'], ['12e3', 'number'], ['12345678901234567890', 'number'],
 ['https://example.org/a?x=1', 'link'], ['text https://example.org', 'text']]) {
 if (textKind(text) !== expected) throw Error(text + ': ' + textKind(text));
}
''', capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_web_title_description_and_relative_image(self):
        html = b'<title>Fallback</title><meta property="og:title" content="A &amp; B"><meta name="description" content="Summary"><meta property="og:image" content="/cover.png">'
        with patch.object(launcher_web, 'fetch', side_effect=[(html, 'https://example.org/post', 'utf-8', 'text/html'), (b'image', '', '', 'image/png')]) as fetch:
            result = launcher_web.preview('https://example.org/post')
        self.assertEqual(result['title'], 'A & B')
        self.assertEqual(result['description'], 'Summary')
        self.assertTrue(result['image'].startswith('data:image/png;base64,'))
        self.assertEqual(fetch.call_args.args[0], 'https://example.org/cover.png')

    def test_unavailable_site_and_image_keep_useful_fallback(self):
        with patch.object(launcher_web, 'fetch', side_effect=TimeoutError):
            self.assertEqual(launcher_web.preview('https://example.org')['status'], 'unavailable')
        html = b'<title>Still useful</title><meta property="og:image" content="/missing.png">'
        with patch.object(launcher_web, 'fetch', side_effect=[(html, 'https://example.org', 'utf-8', 'text/html'), ValueError()]):
            self.assertEqual(launcher_web.preview('https://example.org')['title'], 'Still useful')

    def test_metadata_arrives_before_image_and_cache_skips_network(self):
        html = b'<title>Fast preview</title><meta property="og:image" content="/hero.png">'
        events = []
        def fetch(url, *args):
            if url.endswith('/hero.png'):
                self.assertEqual(events[0]['title'], 'Fast preview')
                self.assertEqual(events[0]['image'], '')
                return b'image', '', '', 'image/png'
            return html, url, 'utf-8', 'text/html'
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'XDG_CACHE_HOME': folder}):
            with patch.object(launcher_web, 'fetch', side_effect=fetch):
                first = launcher_web.cached_preview('https://example.org', events.append)
            with patch.object(launcher_web, 'fetch', side_effect=AssertionError('cache missed')):
                self.assertEqual(launcher_web.cached_preview('https://example.org'), first)

    def test_local_addresses_and_credentials_are_not_fetched(self):
        for url in ['file:///etc/passwd', 'https://user:secret@example.org']:
            with self.assertRaises(ValueError): launcher_web.public_url(url)
        with patch.object(launcher_web.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
            with self.assertRaises(ValueError): launcher_web.public_url('http://localhost')
