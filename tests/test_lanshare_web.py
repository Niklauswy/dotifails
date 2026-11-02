"""LANShare page: static guarantees (no leftovers of the old project, themed only by variables)."""
import re
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'apps/python/wysun_lanshare/static'


class WebTests(unittest.TestCase):
    def files(self):
        return {p.name: p.read_text() for p in STATIC.iterdir() if p.suffix in ('.html', '.js', '.css')}

    def test_nothing_from_the_old_project(self):
        for name, text in self.files().items():
            for word in ('yurai', 'canal', 'describe('):
                self.assertNotIn(word, text.lower(), name)

    def test_works_without_internet(self):
        for name, text in self.files().items():
            self.assertIsNone(re.search(r'https?://', text), name)

    def test_colours_come_from_the_theme(self):
        css = (STATIC / 'app.css').read_text()
        self.assertIsNone(re.search(r'#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(', css))
        for colour in re.findall(r'(?:color|background):\s*([^;}]+)', css):
            self.assertTrue(colour.strip().startswith(('var(--', 'none', 'inherit', 'currentColor', 'transparent', 'color-mix(in srgb, var(--')),
                            colour)

    def test_page_loads_the_generated_theme_first(self):
        html = (STATIC / 'index.html').read_text()
        self.assertLess(html.index('/theme.css'), html.index('/static/app.css'))

    def test_upload_controls_start_hidden(self):
        html = (STATIC / 'index.html').read_text()
        for element in ('id="upload"', 'id="fab"', 'id="mkdir"'):
            tag = html[html.rindex('<', 0, html.index(element)):html.index('>', html.index(element))]
            self.assertIn('hidden', tag, element)


if __name__ == '__main__':
    unittest.main()
