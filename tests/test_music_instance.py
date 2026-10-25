"""A second Music launch that loses the race to start still reaches the instance that won."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wysun'))
from wysun_music import app  # noqa: E402


class MusicInstanceTests(unittest.TestCase):
    def test_launch_that_loses_the_claim_retries_delivery(self):
        sent = []
        def send(endpoint, message, **options):
            sent.append((message, options))
            return False if len(sent) == 1 else True       # the winner is not polling yet, then it is
        with mock.patch.object(app, 'send', side_effect=send), \
                mock.patch.object(app.SingleInstance, 'claim', return_value=False):
            self.assertEqual(app.main(['music_app.py']), 0)
        self.assertEqual([message for message, _ in sent], [b'present', b'present'])
        self.assertGreater(sent[1][1].get('retry', 0), 0)


if __name__ == '__main__':
    unittest.main()
