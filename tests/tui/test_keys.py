"""Input events and the incremental key/mouse/paste parser."""
import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from wysun_core.tui.keys import Key, Mouse, Parser, Paste  # noqa: E402


class ParserTests(unittest.TestCase):
    def test_arrows_and_ctrl_c(self):
        events = Parser().feed(b'\x1b[A\x1b[B\x1b[C\x1b[D\x03')
        self.assertEqual(events, [
            Key('up'),
            Key('down'),
            Key('right'),
            Key('left'),
            Key('c', ctrl=True),
        ])

    def test_alt_letter(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\x1ba'), [Key('char', char='a', alt=True)])
        self.assertFalse(parser.pending)

    def test_alt_letter_split_across_feeds(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\x1b'), [])
        self.assertTrue(parser.pending)
        self.assertEqual(parser.feed(b'a'), [Key('char', char='a', alt=True)])

    def test_sgr_mouse_press_and_wheel(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\x1b[<0;10;5M'), [Mouse('press', 0, 9, 4)])
        self.assertEqual(parser.feed(b'\x1b[<2;4;1M'), [Mouse('press', 2, 3, 0)])
        self.assertEqual(parser.feed(b'\x1b[<0;10;5m'), [Mouse('release', 0, 9, 4)])
        self.assertEqual(parser.feed(b'\x1b[<64;10;5M'), [Mouse('wheelup', 0, 9, 4)])
        self.assertEqual(parser.feed(b'\x1b[<65;10;5M'), [Mouse('wheeldown', 0, 9, 4)])
        self.assertEqual(parser.feed(b'\x1b[<32;3;4M'), [Mouse('drag', 0, 2, 3)])

    def test_bracketed_paste(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\x1b[200~hola\x1b[201~'), [Paste('hola')])
        self.assertEqual(parser.feed('\x1b[200~a\nñ\x1b[201~'.encode()), [Paste('a\nñ')])

    def test_bracketed_paste_split_across_feeds(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\x1b[200~ho'), [])
        self.assertTrue(parser.pending)
        self.assertEqual(parser.feed(b'la'), [])
        self.assertEqual(parser.feed(b'\x1b[201~'), [Paste('hola')])
        self.assertFalse(parser.pending)

    def test_split_escape_sequence_across_feeds(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\x1b['), [])
        self.assertTrue(parser.pending)
        self.assertEqual(parser.feed(b'<0;1'), [])
        self.assertEqual(parser.feed(b'0;5M'), [Mouse('press', 0, 9, 4)])
        self.assertFalse(parser.pending)

    def test_lone_escape_needs_flush(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\x1b'), [])
        self.assertTrue(parser.pending)
        self.assertEqual(parser.flush(), [Key('escape')])
        self.assertFalse(parser.pending)
        self.assertEqual(parser.flush(), [])

    def test_flush_drops_incomplete_sequences(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\x1b['), [])
        self.assertEqual(parser.flush(), [])
        self.assertFalse(parser.pending)

    def test_flush_keeps_a_slow_paste_and_split_utf8(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\x1b[200~hello'), [])
        self.assertEqual(parser.flush(), [])
        self.assertEqual(parser.feed(b'x\x1b[201~'), [Paste('hellox')])
        self.assertEqual(parser.feed('ñ'.encode()[:1]), [])
        self.assertEqual(parser.flush(), [])
        self.assertEqual(parser.feed('ñ'.encode()[1:]), [Key('char', char='ñ')])

    def test_control_keys_and_text_entry(self):
        self.assertEqual(Parser().feed(b'\x01\x09\x0d\x0a\x7f\x08'), [
            Key('a', ctrl=True),
            Key('tab'),
            Key('enter'),
            Key('enter'),
            Key('backspace'),
            Key('backspace'),
        ])
        self.assertEqual(Parser().feed(b'z Z~1'), [
            Key('char', char='z'),
            Key('char', char=' '),
            Key('char', char='Z'),
            Key('char', char='~'),
            Key('char', char='1'),
        ])

    def test_navigation_and_function_keys(self):
        events = Parser().feed(
            b'\x1b[H\x1b[F\x1b[5~\x1b[6~\x1b[3~\x1b[4~\x1b[Z'
            b'\x1bOP\x1b[15~\x1b[24~\x1bOQ'
        )
        self.assertEqual(events, [
            Key('home'),
            Key('end'),
            Key('pageup'),
            Key('pagedown'),
            Key('delete'),
            Key('end'),
            Key('backtab'),
            Key('f1'),
            Key('f5'),
            Key('f12'),
            Key('f2'),
        ])

    def test_utf8_printable(self):
        self.assertEqual(Parser().feed('ñ'.encode()), [Key('char', char='ñ')])
        self.assertEqual(Parser().feed('☁'.encode()), [Key('char', char='☁')])

    def test_utf8_split_across_feeds(self):
        parser = Parser()
        self.assertEqual(parser.feed(b'\xc3'), [])
        self.assertTrue(parser.pending)
        self.assertEqual(parser.feed(b'\xb1'), [Key('char', char='ñ')])

    def test_events_are_frozen_and_hashable(self):
        events = {Key('up'), Key('up'), Mouse('press', 0, 1, 2), Paste('x')}
        self.assertEqual(len(events), 3)
        self.assertEqual(Key('c', ctrl=True), Key('c', ctrl=True))
        self.assertNotEqual(Key('c', ctrl=True), Key('char', char='c'))
        with self.assertRaises(FrozenInstanceError):
            Key('up').name = 'down'


if __name__ == '__main__':
    unittest.main()
