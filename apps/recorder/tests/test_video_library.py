import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from wysun_recorder.videolibrary import VideoLibrary, preferences, preferences_path, save_preferences


class VideoLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        env = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.base / 'config')})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_private_project_folders_live_inside_the_video_folder(self):
        library = VideoLibrary(self.base / 'Videos')
        self.assertEqual((library.videos, library.root), (self.base / 'Videos', self.base / 'Videos/.wybie/recordings'))
        self.assertEqual(library.new_directory().parent, library.root)

    def test_the_video_folder_comes_from_the_preferences(self):
        save_preferences(videos_folder=str(self.base / 'Elsewhere'))
        self.assertEqual(VideoLibrary().videos, self.base / 'Elsewhere')

    def test_preferences_ignore_a_file_that_is_not_an_object(self):
        preferences_path().parent.mkdir(parents=True, exist_ok=True)
        preferences_path().write_text('[]')
        self.assertEqual(preferences(), {})
        save_preferences(fps=24)
        self.assertEqual(preferences(), {'fps': 24})


if __name__ == '__main__':
    unittest.main()
