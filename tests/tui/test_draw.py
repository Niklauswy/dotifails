"""Drawing pieces: boxes, braille graphs, bars, tabs, spinner frames and truncation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from wysun_core.tui.anim import Rect  # noqa: E402
from wysun_core.tui.canvas import Canvas, Style  # noqa: E402
from wysun_core.tui.draw import (bar, box, braille_graph, spinner_frame, tabs,  # noqa: E402
                                 truncate)

WHITE = (255, 255, 255)
RED = (200, 0, 0)
BLACK = (0, 0, 0)


class GraphTests(unittest.TestCase):
    def test_braille_graph_levels(self):
        self.assertEqual(braille_graph([0, 1], 2, 2), ['⠀⣿', '⣀⣿'])
        # Newest value is the rightmost column; short lists are left-padded with zero.
        self.assertEqual(braille_graph([1], 3, 1), ['⣀⣀⣿'])
        # Every row is exactly `width` cells and values are clamped.
        rows = braille_graph([-1, 0.5, 2, 0.25, 1], 5, 3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(len(row) == 5 for row in rows))


class BarTests(unittest.TestCase):
    def test_bar_partial_and_empty(self):
        self.assertEqual(bar(0.5, 4), ('██', '░░'))
        self.assertEqual(bar(0.55, 4), ('██▏', '░'))
        self.assertEqual(bar(0, 4), ('', '░░░░'))
        self.assertEqual(bar(-2, 4), ('', '░░░░'))
        self.assertEqual(bar(1, 4), ('████', ''))
        self.assertEqual(bar(2, 4), ('████', ''))
        for fraction in (0, 0.05, 0.13, 0.25, 0.5, 0.55, 0.75, 0.99, 1):
            filled, empty = bar(fraction, 7)
            self.assertEqual(len(filled) + len(empty), 7, fraction)

    def test_bar_uses_eighths_for_the_partial_cell(self):
        self.assertEqual(bar(0.25, 1), ('▎', ''))
        self.assertEqual(bar(0.75, 1), ('▊', ''))


class BoxTests(unittest.TestCase):
    def test_box_title_truncated(self):
        canvas = Canvas(14, 3, BLACK)
        box(canvas, Rect(0, 0, 14, 3), Style(fg=WHITE),
            [('Resumen ', Style(fg=WHITE)), ('largo', Style(fg=RED))])
        self.assertEqual(canvas.row_text(0), '╭ Resumen l… ╮')
        self.assertEqual(canvas.row_text(1), '│            │')
        self.assertEqual(canvas.row_text(2), '╰────────────╯')
        # The interior is not filled: it stays as the canvas background.
        self.assertEqual(canvas.cell(3, 1), (' ', Style(bg=BLACK)))
        # The ellipsis keeps the style of the last visible title segment.
        self.assertEqual(canvas.cell(0, 0), ('╭', Style(fg=WHITE, bg=canvas.bg)))
        self.assertEqual(canvas.cell(11, 0), ('…', Style(fg=RED, bg=canvas.bg)))

    def test_selected_box_uses_heavy_border(self):
        canvas = Canvas(8, 3, BLACK)
        box(canvas, Rect(0, 0, 8, 3), Style(fg=WHITE), [('VM', Style(fg=RED))],
            selected_style=Style(fg=RED))
        self.assertEqual(canvas.row_text(0), '┏ VM ━━┓')
        self.assertEqual(canvas.row_text(1), '┃      ┃')
        self.assertEqual(canvas.row_text(2), '┗━━━━━━┛')
        self.assertEqual(canvas.cell(0, 0), ('┏', Style(fg=RED, bg=canvas.bg)))
        self.assertNotIn('─', canvas.row_text(0))
        self.assertNotIn('│', canvas.row_text(1))

    def test_box_without_title_and_too_narrow_for_one(self):
        canvas = Canvas(10, 3, BLACK)
        box(canvas, Rect(1, 0, 4, 3), Style(fg=WHITE), [('ignored', Style(fg=RED))])
        self.assertEqual(canvas.row_text(0), ' ╭──╮     ')
        self.assertEqual(canvas.row_text(1), ' │  │     ')
        self.assertEqual(canvas.row_text(2), ' ╰──╯     ')


class TabTests(unittest.TestCase):
    def test_tabs_returns_hitboxes(self):
        canvas = Canvas(40, 1, BLACK)
        styles = {'active': Style(fg=WHITE, bg=RED), 'normal': Style(fg=WHITE)}
        boxes = tabs(canvas, 2, 0, ['Resumen', 'Procesos'], 0, styles,
                     {1: ('●', Style(fg=RED))})
        text = canvas.row_text(0)
        self.assertTrue(text.startswith('   1 Resumen   2 Procesos ● '))
        self.assertEqual(boxes, [Rect(2, 0, 11, 1), Rect(14, 0, 13, 1)])
        self.assertEqual(canvas.cell(3, 0), ('1', Style(fg=WHITE, bg=RED)))
        self.assertEqual(canvas.cell(15, 0), ('2', Style(fg=WHITE, bg=canvas.bg)))
        self.assertEqual(canvas.cell(26, 0), ('●', Style(fg=RED, bg=canvas.bg)))
        self.assertEqual(canvas.cell(13, 0), (' ', Style(bg=BLACK)))


class TextTests(unittest.TestCase):
    def test_truncate(self):
        self.assertEqual(truncate('abcdef', 6), 'abcdef')
        self.assertEqual(truncate('abcdef', 4), 'abc…')
        self.assertEqual(truncate('abcdef', 1), '…')
        self.assertEqual(truncate('abcdef', 0), '')
        self.assertEqual(truncate('abcdef', -3), '')

    def test_spinner_frame(self):
        self.assertEqual([spinner_frame(n) for n in range(5)], ['◐', '◓', '◑', '◒', '◐'])


if __name__ == '__main__':
    unittest.main()
