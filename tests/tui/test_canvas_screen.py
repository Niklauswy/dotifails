"""Canvas cells, clipping, blending and the diffing ANSI screen writer."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from wysun_core.tui.canvas import Canvas, Style  # noqa: E402
from wysun_core.tui.screen import Screen  # noqa: E402

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
CURSOR = re.compile(rb'\x1b\[\d+;\d+H')


class CanvasTests(unittest.TestCase):
    def test_text_clips_to_width(self):
        canvas = Canvas(10, 2, BLACK)
        with canvas.clip((2, 0, 4, 2)):
            written = canvas.text(0, 0, 'abcdef', Style(fg=WHITE))
            canvas.put(0, 1, 'Z', Style(fg=WHITE))
        self.assertEqual(written, 4)
        self.assertEqual(canvas.row_text(0), '  cdef    ')

        canvas.text(0, 1, 'abcdef', Style(fg=WHITE), max_width=3)
        self.assertEqual(canvas.row_text(1), 'abc       ')

    def test_blend_half_mixes_colours(self):
        canvas = Canvas(2, 1, BLACK)
        canvas.fill((0, 0, 1, 1), '#', Style(fg=(200, 0, 0), bg=(200, 0, 0)))
        canvas.blend((0, 0, 1, 1), (0, 0, 0), 0.5)
        char, style = canvas.cell(0, 0)
        self.assertEqual(char, '#')
        self.assertEqual(style.fg, (100, 0, 0))
        self.assertEqual(style.bg, (100, 0, 0))
        self.assertEqual(canvas.cell(1, 0), (' ', Style(bg=BLACK)))

    def test_paste_with_opacity_blends_toward_bg(self):
        dest = Canvas(2, 1, (10, 20, 30))
        source = Canvas(1, 1, (100, 100, 100))
        source.put(0, 0, 'X', Style(fg=(200, 0, 0), bg=(100, 100, 100)))
        dest.paste(source, 0, 0, 0.5)
        self.assertEqual(dest.cell(0, 0), ('X', Style(fg=(105, 10, 15), bg=(55, 60, 65))))


class ScreenTests(unittest.TestCase):
    def test_render_full_then_only_changed_cells(self):
        prev = Canvas(6, 2, BLACK)
        prev.text(0, 0, 'hello', Style(fg=WHITE))
        prev.text(0, 1, 'world', Style(fg=WHITE))
        screen = Screen()
        first = screen.render(None, prev)
        self.assertTrue(first.startswith(b'\x1b[?2026h'))
        self.assertTrue(first.endswith(b'\x1b[?2026l'))

        cur = Canvas(6, 2, BLACK)
        cur.text(0, 0, 'hello', Style(fg=WHITE))
        cur.text(0, 1, 'world', Style(fg=WHITE))
        cur.put(2, 1, 'X', Style(fg=WHITE))

        second = screen.render(prev, cur)
        self.assertTrue(second.startswith(b'\x1b[?2026h'))
        self.assertTrue(second.endswith(b'\x1b[?2026l'))
        self.assertEqual(CURSOR.findall(second), [b'\x1b[2;3H'])
        self.assertIn(b'X', second)
        self.assertNotIn(b'\x1b[1;', second)
        self.assertNotIn(b'world', second)

    def test_render_256_colour_fallback(self):
        canvas = Canvas(1, 1, BLACK)
        canvas.put(0, 0, 'A', Style(fg=(200, 0, 0), bg=BLACK))
        output = Screen(truecolor=False).render(None, canvas)
        self.assertIn(b'38;5;', output)
        self.assertNotIn(b'38;2;', output)


    def test_foreground_only_text_keeps_the_background_under_it(self):
        canvas = Canvas(4, 1, (10, 10, 10))
        canvas.fill((0, 0, 4, 1), ' ', Style(bg=(50, 60, 70)))
        canvas.text(0, 0, 'ab', Style(fg=(200, 200, 200)))
        self.assertEqual(canvas.cell(0, 0)[1].bg, (50, 60, 70))
        self.assertNotIn(b'[0;38;2;200;200;200m', Screen().render(None, canvas))

    def test_zero_opacity_paste_leaves_the_destination(self):
        canvas = Canvas(3, 1, (0, 0, 0))
        canvas.text(0, 0, 'abc', Style(fg=(255, 255, 255)))
        layer = Canvas(3, 1, (0, 0, 0))
        layer.text(0, 0, 'xyz', Style(fg=(255, 0, 0)))
        canvas.paste(layer, 0, 0, opacity=0.0)
        self.assertEqual(canvas.row_text(0), 'abc')

    def test_partial_paste_fades_toward_each_destination_cell(self):
        canvas = Canvas(2, 1, (0, 0, 0))
        canvas.fill((1, 0, 1, 1), ' ', Style(bg=(200, 200, 200)))
        layer = Canvas(2, 1, (100, 0, 0))
        canvas.paste(layer, 0, 0, opacity=0.5)
        self.assertEqual(canvas.cell(0, 0)[1].bg, (50, 0, 0))
        self.assertEqual(canvas.cell(1, 0)[1].bg, (150, 100, 100))


    def test_control_characters_never_reach_the_terminal(self):
        canvas = Canvas(12, 1, (0, 0, 0))
        canvas.text(0, 0, '1024\t/\x1b[2J\x9b\x07', Style(fg=(255, 255, 255)))
        rendered = Screen().render(None, canvas)
        self.assertNotIn(b'\x1b[2J', rendered)
        self.assertNotIn('\x9b'.encode(), rendered)
        self.assertNotIn(b'\x07', rendered)
        self.assertTrue(canvas.row_text(0).startswith('1024 /'))


if __name__ == '__main__':
    unittest.main()
