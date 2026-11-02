"""Wysun Player's per-window controller (venv Python), on synthetic media: what it shows for each kind, the folder
collection and its ends, broken and deleted files, volume and speed steps, subtitle cycling without tracks, moving to
the trash, remembered positions, audio covers and tags, image information and file drops."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
os.environ['WYSUN_MPV_OPTIONS'] = 'ao=null,hwdec=no'
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

FF = ['ffmpeg', '-v', 'error', '-y']


def build_media(folder):
    folder = Path(folder)
    subprocess.run(FF + ['-f', 'lavfi', '-i', 'testsrc=size=320x180:rate=30:duration=12', '-pix_fmt', 'yuv420p',
                         str(folder / 'clip.mp4')], check=True, timeout=60)
    subprocess.run(FF + ['-f', 'lavfi', '-i', 'color=c=red:s=64x64', '-frames:v', '1', str(folder / 'cover.png')],
                   check=True, timeout=30)
    subprocess.run(FF + ['-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', '-i', str(folder / 'cover.png'),
                         '-map', '0:a', '-map', '1:v', '-c:v', 'png', '-disposition:v', 'attached_pic',
                         '-metadata', 'title=Tono', '-metadata', 'artist=Wysun', '-metadata', 'album=Pruebas',
                         str(folder / 'tone.mka')], check=True, timeout=30)
    pictures = folder / 'pictures'
    pictures.mkdir()
    for name in ('a.png', 'b.png', 'c.png'):
        shutil.copy(folder / 'cover.png', pictures / name)
    return folder


class FakePositions:
    def __init__(self, start=None):
        self.start, self.saved = start, []

    def get(self, source):
        return self.start

    def put(self, source, position, duration):
        self.saved.append((source.name, position, duration))


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg needed for synthetic media')
class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(prefix='player-ctl-', dir=scratch)
        cls.media = build_media(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def controller(self, **options):
        from wysun_player.quick.controller import PlayerController
        options.setdefault('positions', FakePositions())
        ctl = PlayerController(renderer='software', **options)
        ctl.toasts = []
        ctl.toast.connect(lambda text, icon: ctl.toasts.append(text))
        self.addCleanup(ctl.shutdown)
        return ctl

    def with_surface(self, ctl):
        from wysun_player.quick.video import MpvSoftwareVideo
        item = MpvSoftwareVideo()
        item.setWidth(320)
        item.setHeight(180)
        item.session = ctl.session
        self.addCleanup(item.release)
        return item

    def test_video_plays_and_shows_its_name(self):
        ctl = self.controller()
        self.with_surface(ctl)
        ctl.open(str(self.media / 'clip.mp4'))
        self.assertEqual(ctl.property('kindName'), 'video')
        self.assertEqual(ctl.property('title'), 'clip.mp4')
        self.assertTrue(self.h.wait_for(lambda: ctl.property('state') == 'playing', 8000))
        self.assertTrue(self.h.wait_for(lambda: abs(ctl.property('duration') - 12) < .5, 4000))
        labels = [row['label'] for row in ctl.property('info')]
        self.assertIn('Resolución', labels)

    def test_folder_collection_and_its_ends(self):
        ctl = self.controller()
        ctl.open(str(self.media / 'pictures/b.png'), browse='folder')
        self.assertTrue(self.h.wait_for(lambda: ctl.property('count') == 3, 4000))
        self.assertTrue(ctl.property('hasNext'))
        self.assertTrue(ctl.stepCollection(1))
        self.assertEqual(ctl.property('title'), 'c.png')
        self.assertFalse(ctl.property('hasNext'))
        self.assertFalse(ctl.stepCollection(1))
        self.assertIn('No hay más archivos', ctl.toasts)

    def test_missing_file_sets_the_error(self):
        ctl = self.controller()
        ctl.open(str(self.media / 'nowhere.mp4'))
        self.assertIn('No se encuentra', ctl.property('error'))

    def test_volume_and_speed_steps(self):
        ctl = self.controller()
        ctl.open(str(self.media / 'tone.mka'))
        self.assertTrue(self.h.wait_for(lambda: ctl.property('state') in ('playing', 'paused', 'ended'), 8000))
        ctl.setVolume(148)
        self.assertTrue(self.h.wait_for(lambda: ctl.property('volume') == 148, 2000))
        ctl.nudgeVolume(5)
        self.assertTrue(self.h.wait_for(lambda: ctl.property('volume') == 150, 2000))
        self.assertEqual(ctl.toasts[-1], 'Volumen 150 %')
        ctl.nudgeSpeed(1)
        self.assertTrue(self.h.wait_for(lambda: ctl.property('speed') == 1.25, 2000))
        ctl.nudgeSpeed(-1)
        self.assertTrue(self.h.wait_for(lambda: ctl.property('speed') == 1.0, 2000))
        ctl.nudgeSpeed(-1)
        self.assertTrue(self.h.wait_for(lambda: ctl.property('speed') == .75, 2000))
        self.assertEqual(ctl.toasts[-1], '0.75×')

    def test_cycling_subtitles_without_tracks(self):
        ctl = self.controller()
        ctl.open(str(self.media / 'tone.mka'))
        ctl.cycleSubtitles()
        self.assertEqual(ctl.toasts[-1], 'Sin subtítulos')

    def test_audio_cover_and_tags(self):
        ctl = self.controller()
        ctl.open(str(self.media / 'tone.mka'))
        self.assertEqual(ctl.property('kindName'), 'audio')
        self.assertTrue(self.h.wait_for(lambda: ctl.property('coverUrl').startswith('image://cover/'), 6000))
        key = ctl.property('coverUrl').split('/', 3)[-1]
        self.assertFalse(ctl.covers().images[key].isNull())
        self.assertTrue(self.h.wait_for(lambda: ctl.property('audioTitle') == 'Tono', 6000))
        self.assertEqual(ctl.property('audioDetail'), 'Wysun · Pruebas')

    def test_trash_opens_the_neighbour_or_reports_failure(self):
        trashed = []
        ctl = self.controller(trash=lambda path: trashed.append(path) or True)
        paths = [str(self.media / 'pictures' / n) for n in ('a.png', 'b.png', 'c.png')]
        ctl.open_many(paths, current=1)
        ctl.trash()
        self.assertEqual(trashed, [paths[1]])
        self.assertEqual(ctl.property('title'), 'c.png')
        self.assertEqual(ctl.property('count'), 2)
        self.assertEqual(ctl.toasts[-1], 'Movido a la papelera')
        failing = self.controller(trash=lambda path: False)
        failing.open(paths[0])
        failing.trash()
        self.assertEqual(failing.toasts[-1], 'No se pudo mover a la papelera')
        self.assertEqual(failing.property('title'), 'a.png')

    def test_position_is_restored_and_saved(self):
        positions = FakePositions(start=4.0)
        ctl = self.controller(positions=positions)
        self.with_surface(ctl)
        ctl.open(str(self.media / 'clip.mp4'))
        self.assertTrue(self.h.wait_for(lambda: ctl.property('position') >= 4.0, 8000))
        ctl.open(str(self.media / 'pictures/a.png'))
        self.assertEqual(positions.saved[-1][0], 'clip.mp4')
        self.assertGreaterEqual(positions.saved[-1][1], 4.0)

    def test_image_information_comes_from_qml(self):
        ctl = self.controller()
        ctl.open(str(self.media / 'pictures/a.png'))
        ctl.setImageInfo(64, 64, 1)
        info = {row['label']: row['value'] for row in ctl.property('info')}
        self.assertEqual(info['Dimensiones'], '64 × 64')
        self.assertEqual(info['Formato'], 'PNG')

    def test_dropping_files_opens_media_and_adds_subtitles_to_a_video(self):
        from PySide6.QtCore import QUrl
        ctl = self.controller()
        ctl.drop([QUrl.fromLocalFile(str(self.media / 'pictures/a.png')).toString()])
        self.assertEqual(ctl.property('title'), 'a.png')
        added = []
        ctl.session.add_subtitle = added.append
        ctl.kind = 'video'
        srt = self.media / 'subs.srt'
        srt.write_text('1\n00:00:00,000 --> 00:00:01,000\nHola\n')
        ctl.drop([QUrl.fromLocalFile(str(srt)).toString()])
        self.assertEqual(added, [str(srt)])


if __name__ == '__main__':
    unittest.main()
