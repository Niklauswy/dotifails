"""Animated wallpapers: detection, cached thumbnails, scheme frame and `wallpaper set` for video."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
import wallpaper_media  # noqa: E402

HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def make_video(path, kind='mp4'):
    codec = ['-c:v', 'libx264', '-pix_fmt', 'yuv420p'] if kind == 'mp4' else ['-c:v', 'libvpx-vp9', '-b:v', '200k']
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=10', '-t', '1', *codec, str(path)],
                   check=True)


class DetectionTests(unittest.TestCase):
    def test_extensions(self):
        for name in ('a.mp4', 'a.WEBM', 'a.mkv', 'a.gif'):
            self.assertTrue(wallpaper_media.is_animated(name), name)
        for name in ('a.png', 'a.jpg', 'a.webp', 'a.txt'):
            self.assertFalse(wallpaper_media.is_animated(name), name)
        self.assertTrue(wallpaper_media.is_wallpaper('a.png'))
        self.assertFalse(wallpaper_media.is_wallpaper('a.txt'))


@unittest.skipUnless(HAVE_FFMPEG, 'ffmpeg/ffprobe not installed')
class MediaTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.walls = self.home / 'walls'
        self.walls.mkdir()
        os.environ['XDG_CACHE_HOME'] = str(self.home / 'cache')
        self.addCleanup(os.environ.pop, 'XDG_CACHE_HOME', None)
        Image.new('RGB', (1920, 1080), (200, 40, 90)).save(self.walls / 'still.png')
        make_video(self.walls / 'clip.mp4')
        make_video(self.walls / 'clip.webm', 'webm')

    def test_scan_lists_stills_and_videos(self):
        found = {entry['name']: entry['animated'] for entry in wallpaper_media.scan([self.walls])}
        self.assertEqual(found, {'still': False, 'clip': True})  # clip.mp4 and clip.webm share a stem; one survives

    def test_thumbnails_are_cached_outside_the_wallpaper_folder(self):
        for name in ('still.png', 'clip.mp4', 'clip.webm'):
            thumb = wallpaper_media.thumbnail(self.walls / name)
            self.assertTrue(thumb.is_file(), name)
            self.assertTrue(str(thumb).startswith(str(self.home / 'cache')))
            from PIL import Image
            with Image.open(thumb) as image:
                self.assertEqual(image.size, wallpaper_media.THUMB_SIZE)
            self.assertEqual(wallpaper_media.cached_thumbnail(self.walls / name), thumb)
        self.assertEqual(sorted(p.name for p in self.walls.iterdir()), ['clip.mp4', 'clip.webm', 'still.png'])

    def test_thumbnail_worker_protocol(self):
        import io
        out = io.StringIO()
        wallpaper_media.serve(io.StringIO(f'{self.walls / "clip.mp4"}\n{self.walls / "missing.mp4"}\n'), out)
        ok, bad = out.getvalue().splitlines()
        self.assertTrue(Path(ok.split('\t')[1]).is_file())
        self.assertEqual(bad.split('\t')[1], '')

    def test_scheme_frame_comes_from_the_video(self):
        frame = wallpaper_media.scheme_frame(self.walls / 'clip.mp4')
        self.assertEqual(frame.suffix, '.png')
        self.assertEqual(wallpaper_media.scheme_frame(self.walls / 'still.png'), self.walls / 'still.png')

    def test_dynamic_scheme_accepts_video(self):
        import wysun_scheme
        scheme = wysun_scheme.generate_dynamic(self.walls / 'clip.mp4')
        self.assertEqual(scheme['name'], 'dynamic')
        self.assertIn('primary', scheme['colours'])
        self.assertEqual(scheme['wallpaper_hash'], wallpaper_media.content_hash(self.walls / 'clip.mp4'))

    def test_set_wallpaper_validates_video(self):
        import wysun_scheme
        broken = self.walls / 'broken.mp4'
        broken.write_bytes(b'not a video')
        with self.assertRaises(ValueError):
            wysun_scheme.set_wallpaper(broken, home=self.home)

    def test_list_command_prints_json(self):
        result = subprocess.run([sys.executable, '-I', str(ROOT / 'apps/wysun/wallpaper_media.py'), 'list', str(self.walls)],
                                capture_output=True, text=True, check=True, env={**os.environ})
        self.assertTrue(json.loads(result.stdout))


if __name__ == '__main__':
    unittest.main()
