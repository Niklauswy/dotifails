"""«Añadir música»: YouTube search (fake yt-dlp), selection and download, link validation, Spotify import, the
Files selector for imports, and the download queue."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support, music_fixture  # noqa: E402

FOUND = {'entries': [{'id': 'aaa', 'title': 'Canción A', 'channel': 'Canal', 'duration': 200},
                     {'id': 'bbb', 'title': 'Canción B', 'uploader': 'Otro', 'duration': 61}]}


class AddMusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import Qt
        cls.Qt = Qt
        cls.h = support.Harness.get()
        music_fixture.setup()
        cls.music = music_fixture.app()
        cls.window = cls.music.window.window
        cls.add = cls.music.window.addmusic
        cls.music.window.bridge.setReducedMotion(True)
        cls.music.window.present()
        cls.window.resize(1100, 800)

    def fake_ytdlp(self):
        script = 'import json,sys; print(json.dumps(%r))' % FOUND
        return patch('wysun_music.data.ytdlp', return_value=[sys.executable, '-c', script])

    def rows(self, model, role):
        names = {bytes(v).decode(): k for k, v in model.roleNames().items()}
        return [model.data(model.index(i), names[role]) for i in range(model.rowCount())]

    def test_search_select_download(self):
        with self.fake_ytdlp():
            self.add.search('cancion')
            self.assertTrue(self.add.busy)
            self.assertTrue(self.h.wait_for(lambda: not self.add.busy, 8000))
        self.assertEqual(self.rows(self.add.results, 'title'), ['Canción A', 'Canción B'])
        self.assertEqual(self.rows(self.add.results, 'detail'), ['Canal · 3:20', 'Otro · 1:01'])
        self.add.toggleResult(1)
        with patch('wysun_music.data.enqueue') as enqueue, patch('wysun_music.data.start_worker') as worker:
            self.add.downloadSelected()
        manifest = enqueue.call_args.args[0]
        self.assertEqual([t['id'] for t in manifest['collections'][0]['tracks']], ['yt-bbb'])
        worker.assert_called_once()
        self.assertEqual(self.add.status, '1 añadidas a la cola de descargas.')

    def test_ctrl_enter_downloads_from_the_list(self):
        self.h.call(self.window, 'navigate', 'downloads', True)
        with self.fake_ytdlp():
            self.add.search('cancion')
            self.assertTrue(self.h.wait_for(lambda: not self.add.busy, 8000))
        results = self.h.find_in(self.window.contentItem(), 'addResults')
        results.forceActiveFocus()
        results.setProperty('currentIndex', 0)
        self.h.key(self.window, self.Qt.Key_Space, text=' ')
        with patch('wysun_music.data.enqueue') as enqueue, patch('wysun_music.data.start_worker'):
            self.h.key(self.window, self.Qt.Key_Return, self.Qt.ControlModifier, '\r')
        self.assertEqual([t['id'] for t in enqueue.call_args.args[0]['collections'][0]['tracks']], ['yt-aaa'])

    def test_links_other_than_youtube_or_spotify_are_refused(self):
        self.add.search('https://example.com/song')
        self.assertEqual(self.add.status, 'Usa un enlace de YouTube o Spotify, o escribe el nombre de la canción.')

    def test_spotify_import(self):
        link = 'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M'
        result = {'collections': [{'id': 'spotify-x', 'title': 'Lista', 'tracks': [{'id': 'a', 'title': 't', 'artist': 'x', 'duration': 1}]}]}
        routes = []
        self.add.navigateRequested.connect(routes.append)
        with patch.object(self.music.covers.metadata, 'request') as request, \
                patch('wysun_music.data.enqueue'), patch('wysun_music.data.start_worker'), \
                patch.object(self.music.library.store, 'import_references'), \
                patch.object(self.music.library, 'refresh_references'):
            self.add.search(link)
            self.assertEqual(request.call_args.args[:2], ('spotify-import', link))
            self.music.covers.metadata.ready.emit('spotify-import', link, result)
        self.assertEqual(self.add.status, '1 canciones de Spotify · 0 ya estaban · 1 en cola')
        self.assertEqual(routes, ['collection:spotify-x'])

    def test_import_through_the_files_selector(self):
        target = music_fixture.setup()['files'][0]
        response = json.dumps({'code': 0, 'uris': [target.as_uri()]})
        script = f'import sys; sys.stdin.readline(); print({response!r})'
        with patch('wysun_core.launch.argv', return_value=[sys.executable, '-c', script]) as argv, \
                patch('wysun_music.data.import_files', return_value=[target]) as imported:
            self.add.importFiles()
            self.assertTrue(self.h.wait_for(lambda: imported.called and self.add.importer is None, 8000))
        self.assertEqual(argv.call_args.args[0], 'wysun_files.picker')
        self.assertEqual(imported.call_args.args[0], [str(target)])
        self.assertEqual(self.add.status, '1 canción importadas a tu biblioteca.')

    def test_queue_summary(self):
        self.add.render_queue()
        self.assertTrue(self.add.summary.startswith('3 guardadas · 0 en cola · 0 requieren atención'))
        self.assertFalse(self.add.counts['canRetry'])


if __name__ == '__main__':
    unittest.main()
