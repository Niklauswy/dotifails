"""Owned control pipes only: no compositor, FFmpeg, audio, or input devices."""
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from loomrec.worker import end_portal_segment


class PortalSegmentPipeTests(unittest.TestCase):
    def test_finished_producer_releases_command_pipe_without_gc(self):
        # A real PIPE/child establishes that closure reaches the peer, rather
        # than merely asserting that a mock close method was called.
        child=subprocess.Popen([sys.executable,'-c','import sys; assert sys.stdin.buffer.read()==b""'],stdin=subprocess.PIPE)
        fd=child.stdin.fileno()
        try:
            self.assertFalse(end_portal_segment(child,Mock()))
            self.assertEqual(child.returncode,0)
            self.assertTrue(child.stdin.closed)
            with self.assertRaises(OSError):os.fstat(fd)
        finally:
            child.stdin.close()
            if child.poll() is None:child.kill()
            child.wait(timeout=3)

    def test_producer_teardown_error_still_releases_control_writer(self):
        read,write=os.pipe();stream=os.fdopen(write,'wb');child=Mock(stdin=stream)
        producer=Mock();producer.finish.side_effect=RuntimeError('own teardown fixture')
        try:
            with self.assertRaisesRegex(RuntimeError,'teardown'):
                end_portal_segment(child,producer)
            self.assertTrue(stream.closed)
            self.assertEqual(os.read(read,1),b'')
            child.poll.assert_not_called()
        finally:
            stream.close();os.close(read)

    def test_poll_timeout_keeps_control_writer_closed(self):
        read,write=os.pipe();stream=os.fdopen(write,'wb');child=Mock(stdin=stream,args=['own-child'])
        child.poll.return_value=None
        try:
            with patch('loomrec.worker.time.monotonic',side_effect=[0,11]):
                with self.assertRaises(subprocess.TimeoutExpired):
                    end_portal_segment(child,Mock())
            self.assertTrue(stream.closed)
            self.assertEqual(os.read(read,1),b'')
        finally:
            stream.close();os.close(read)
