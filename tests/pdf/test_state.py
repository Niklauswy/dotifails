"""Per-document memory and reader preferences live in the user's private XDG dirs."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from wysun_pdf import state as pdf_state  # noqa: E402


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {'HOME': self.tmp.name, 'XDG_STATE_HOME': self.tmp.name + '/state',
                                               'XDG_CONFIG_HOME': self.tmp.name + '/config'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.doc = Path(self.tmp.name) / 'Secret plans.pdf'
        self.doc.write_bytes(b'%PDF')

    def test_position_roundtrip_is_private_and_anonymous(self):
        positions = pdf_state.Positions()
        positions.save(self.doc, {'page': 4, 'fx': .5, 'fy': .25, 'zoom_mode': 'custom', 'zoom': 1.5, 'view': 'spread'})
        loaded = pdf_state.Positions().load(self.doc)
        self.assertEqual((loaded['page'], loaded['zoom'], loaded['view']), (4, 1.5, 'spread'))
        target = Path(self.tmp.name) / 'state/wysun/pdf-reader/positions.json'
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertNotIn('Secret', target.read_text())

    def test_unknown_document_has_no_position(self):
        self.assertIsNone(pdf_state.Positions().load(self.doc.with_name('other.pdf')))

    def test_only_the_newest_documents_are_kept(self):
        positions = pdf_state.Positions()
        with mock.patch.object(pdf_state, 'LIMIT', 3):
            for n in range(5):
                with mock.patch('time.time', return_value=1000 + n):
                    positions.save(Path(self.tmp.name) / f'{n}.pdf', {'page': n})
        stored = json.loads((Path(self.tmp.name) / 'state/wysun/pdf-reader/positions.json').read_text())
        self.assertEqual(len(stored), 3)
        self.assertIsNone(positions.load(Path(self.tmp.name) / '0.pdf'))
        self.assertEqual(positions.load(Path(self.tmp.name) / '4.pdf')['page'], 4)

    def test_restore_clamps_to_page_count(self):
        clamped = pdf_state.clamp({'page': 40, 'zoom': 99, 'view': 'weird', 'zoom_mode': '?'}, 10)
        self.assertEqual(clamped['page'], 9)
        self.assertEqual(clamped['zoom'], 8.0)
        self.assertEqual(clamped['view'], 'single')
        self.assertEqual(clamped['zoom_mode'], 'width')
        self.assertEqual(pdf_state.clamp({'page': -3}, 10)['page'], 0)

    def test_preferences_keep_unknown_keys(self):
        target = Path(self.tmp.name) / 'config/wysun/pdf-reader.json'
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps({'mode': 'light', 'future': 1}))
        prefs = pdf_state.Preferences()
        self.assertEqual(prefs.get('mode'), 'light')
        prefs.set(sidebar=False)
        self.assertEqual(json.loads(target.read_text()), {'mode': 'light', 'future': 1, 'sidebar': False})
        self.assertEqual(pdf_state.Preferences().get('missing', 7), 7)

    def test_invalid_numbers_do_not_break_restore_or_history_pruning(self):
        for invalid in (None, 'oops', [], {}, float('nan'), float('inf')):
            result = pdf_state.clamp(dict(page=invalid, zoom=invalid, fx=invalid, fy=invalid), 10)
            self.assertEqual(result['page'], 0)
            self.assertEqual(result['zoom'], 1.)
            self.assertEqual(result['fx'], 0.)
        positions = pdf_state.Positions()
        positions.path.parent.mkdir(parents=True, exist_ok=True)
        positions.path.write_text('{"broken": {"t": "not a time"}}')
        positions.save(self.doc, {'page': 1})
        self.assertEqual(positions.load(self.doc)['page'], 1)

    def test_a_corrupt_file_reads_as_empty(self):
        target = Path(self.tmp.name) / 'state/wysun/pdf-reader/positions.json'
        target.parent.mkdir(parents=True)
        target.write_text('[1, 2')
        self.assertIsNone(pdf_state.Positions().load(self.doc))


if __name__ == '__main__':
    unittest.main()
