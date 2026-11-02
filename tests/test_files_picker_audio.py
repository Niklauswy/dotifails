"""wysun_files.picker: document requests (documents) and audio files/folders (Wysun Music import)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))


class PickerRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.home.cleanup)

    def selector(self, **request):
        from wysun_files.core.chooser import ChooserSession
        from wysun_files.picker import request_options
        return ChooserSession(*request_options(dict(initial=self.home.name, **request)))

    def test_audio_files_are_multiple_with_an_audio_filter(self):
        chooser = self.selector(kind='audio', multiple=True, title='Importar música')
        self.assertTrue(chooser.multiple)
        self.assertFalse(chooser.directory)
        name, patterns = chooser.filters[0]
        self.assertEqual(name, 'Audio')
        self.assertEqual(sorted(p for _, p in patterns),
                         sorted(f'*.{s}' for s in ('m4a', 'opus', 'mp3', 'flac', 'ogg', 'wav', 'aac')))

    def test_audio_folder(self):
        chooser = self.selector(kind='audio', directory=True)
        self.assertTrue(chooser.directory)

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            self.selector(kind='spreadsheet')

    def test_media_for_wysun_player_is_multiple_with_video_audio_and_image_filters(self):
        chooser = self.selector(kind='media')
        self.assertTrue(chooser.multiple)
        names = [name for name, _ in chooser.filters]
        self.assertEqual(names, ['Videos, audio e imágenes', 'Videos', 'Audio', 'Imágenes'])
        patterns = {p for _, p in chooser.filters[0][1]}
        self.assertTrue({'*.mp4', '*.mkv', '*.mp3', '*.flac', '*.jpg', '*.png'} <= patterns)
        self.assertNotIn('*.m3u', patterns)

    def test_subtitles_for_wysun_player(self):
        chooser = self.selector(kind='subtitles')
        self.assertTrue(chooser.multiple)
        self.assertEqual({p for _, p in chooser.filters[0][1]}, {'*.srt', '*.ass', '*.ssa', '*.vtt', '*.sub'})

    def test_document_requests_are_unchanged(self):
        chooser = self.selector(suffix='md')
        self.assertFalse(chooser.multiple)
        self.assertEqual(chooser.filters[0][0], 'MD')


if __name__ == '__main__':
    unittest.main()
