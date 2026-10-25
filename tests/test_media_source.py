"""Local-source validation and classification: nothing remote, nothing that is not a regular file."""
import os
import socket
import tempfile
import unittest
from pathlib import Path

import media_support as support

support.app()
from wysun_media.errors import MediaError  # noqa: E402
from wysun_media.source import group_of, kind_of, natural_key, open_source, to_path  # noqa: E402


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = support.fixtures()

    def category(self, value):
        with self.assertRaises(MediaError) as caught:
            open_source(value)
        return caught.exception.category

    def test_classifies_by_name_and_mime(self):
        expected = {'h264.mp4': 'video', 'vp9.webm': 'video', 'hevc.mkv': 'video', 'h264.mov': 'video', 'tone.mp3': 'audio',
                    'tone.flac': 'audio', 'tone.opus': 'audio', 'plain.png': 'image', 'plain.jpg': 'image', 'anim.gif': 'image'}
        for name, kind in expected.items():
            self.assertEqual(kind_of(self.files / name), kind, name)
        self.assertEqual(kind_of(self.files / 'list.m3u'), '')
        self.assertEqual(group_of('video'), group_of('audio'))
        self.assertNotEqual(group_of('image'), group_of('video'))

    def test_source_describes_the_file(self):
        source = open_source(self.files / 'tone.mp3')
        self.assertEqual((source.kind, source.name), ('audio', 'tone.mp3'))
        self.assertEqual(source.size, (self.files / 'tone.mp3').stat().st_size)
        self.assertIn(str(source.size), source.fingerprint)

    def test_rejects_what_is_not_a_local_regular_file(self):
        self.assertEqual(self.category(self.files / 'does-not-exist.mp4'), 'missing')
        self.assertEqual(self.category(self.files), 'rejected')
        self.assertEqual(self.category('/dev/null'), 'rejected')
        self.assertEqual(self.category('http://example.invalid/a.mp4'), 'rejected')
        self.assertEqual(self.category('https://example.invalid/a.mp4'), 'rejected')
        self.assertEqual(self.category('smb://host/share/a.mp4'), 'rejected')
        self.assertEqual(self.category('file://evil.example/etc/passwd'), 'rejected')
        self.assertEqual(self.category('rtsp://camera.invalid/stream'), 'rejected')

    def test_rejects_fifos_and_sockets(self):
        with tempfile.TemporaryDirectory() as root:
            fifo = Path(root) / 'pipe.mp4'
            os.mkfifo(fifo)
            self.assertEqual(self.category(fifo), 'rejected')
            sock_path = Path(root) / 's.mp4'
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(str(sock_path))
            try:
                self.assertEqual(self.category(sock_path), 'rejected')
            finally:
                listener.close()

    def test_rejects_playlists_and_manifests_and_unknown_types(self):
        self.assertEqual(self.category(self.files / 'list.m3u'), 'unsupported')
        with tempfile.TemporaryDirectory() as root:
            for name in ('x.m3u8', 'x.pls', 'x.mpd', 'x.txt'):
                path = Path(root) / name
                path.write_text('#EXTM3U\n')
                self.assertEqual(self.category(path), 'unsupported', name)

    def test_file_urls_are_decoded_and_local_only(self):
        with tempfile.TemporaryDirectory() as root:
            odd = Path(root) / 'sé ñ #1 %20.png'
            odd.write_bytes((self.files / 'plain.png').read_bytes())
            from urllib.parse import quote
            self.assertEqual(open_source('file://' + quote(str(odd))).path, odd)
            self.assertEqual(open_source('file://localhost' + quote(str(odd))).path, odd)

    def test_unusual_names_are_plain_paths(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ('-dash.png', '--quit.png', 'with space.png', 'ünï©ode 日本語.png', 'quote"s.png', "it's.png", 'new\nline.png'):
                path = Path(root) / name
                path.write_bytes((self.files / 'plain.png').read_bytes())
                self.assertEqual(open_source(path).name, name)
            self.assertEqual(open_source(Path(root) / '-dash.png').kind, 'image')

    def test_nul_in_path_is_rejected(self):
        self.assertEqual(self.category('/tmp/a\0b.mp4'), 'rejected')

    def test_replaced_file_has_a_new_fingerprint(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'a.png'
            path.write_bytes((self.files / 'plain.png').read_bytes())
            before = open_source(path).fingerprint
            path.write_bytes((self.files / 'alpha.png').read_bytes())
            self.assertNotEqual(open_source(path).fingerprint, before)

    def test_natural_order(self):
        names = ['img10.png', 'img2.png', 'Img1.png', 'img1b.png']
        self.assertEqual(sorted(names, key=natural_key), ['Img1.png', 'img1b.png', 'img2.png', 'img10.png'])

    def test_to_path_passes_paths_through(self):
        self.assertEqual(to_path(Path('/a/b')), Path('/a/b'))
        self.assertEqual(to_path('/a/b c'), Path('/a/b c'))


if __name__ == '__main__':
    unittest.main()
