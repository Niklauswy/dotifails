"""«Añadir música»: YouTube search (fake yt-dlp), playing and selecting results, link validation, choosing songs of
a Spotify list before downloading, the Files selector for imports, download batches and failed songs."""
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
        self.assertEqual(self.add.status, '1 canción en camino a tu biblioteca.')

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

    def test_spotify_list_is_chosen_before_downloading(self):
        link = 'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M'
        first = music_fixture.keys_by_title()['first']
        result = {'collections': [{'id': 'spotify-x', 'title': 'Lista', 'source': link, 'cover_url': None, 'tracks': [
            {'id': 'a' * 22, 'title': 'Nueva', 'artist': 'X', 'duration': 100},
            {'id': 'b' * 22, 'title': 'Otra', 'artist': 'Y', 'duration': 100},
            {'id': first, 'title': 'first', 'artist': 'Synth', 'duration': 12}]}]}
        with patch.object(self.music.covers.metadata, 'request') as request:
            self.add.search(link)
            self.assertEqual(request.call_args.args[:2], ('spotify-import', link))
            self.music.covers.metadata.ready.emit('spotify-import', link, result)
        preview = self.add.preview
        self.assertEqual((preview['title'], preview['total'], preview['owned'], preview['chosen']), ('Lista', 3, 1, 2))
        self.assertEqual(self.rows(self.add.previewRows, 'owned'), [False, False, True])
        self.add.togglePreview(2)                         # owned songs cannot be picked again
        self.add.togglePreview(1)
        self.assertEqual(self.add.preview['action'], 'Descargar 1')
        self.add.selectPreview('none')
        self.assertEqual(self.add.preview['chosen'], 0)
        self.add.selectPreview('all')
        self.add.togglePreview(0)
        with patch('wysun_music.data.enqueue') as enqueue, patch('wysun_music.data.start_worker'), \
                patch.object(self.music.library.store, 'import_references'), \
                patch.object(self.music.library, 'refresh_references'):
            self.add.downloadPreview()
        collection = enqueue.call_args.args[0]['collections'][0]
        self.assertEqual((collection['id'], collection['title']), ('spotify-x', 'Lista'))
        self.assertEqual([t['id'] for t in collection['tracks']], ['b' * 22])
        self.assertEqual(self.add.preview, {})

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

    def test_selector_that_cannot_start_reports_it(self):
        with patch('wysun_core.launch.argv', return_value=['/nonexistent/python', '-c', '']):
            self.add.importFiles()
            self.assertTrue(self.h.wait_for(lambda: self.add.picker is None, 4000))
        self.assertEqual(self.add.status, 'No se pudo abrir el selector de Wysun Files.')
        with patch('wysun_core.launch.argv', return_value=[sys.executable, '-c', 'import sys; sys.exit(3)']):
            self.add.importFiles()
            self.assertTrue(self.h.wait_for(lambda: self.add.picker is None, 4000))
        self.assertEqual(self.add.status, 'El selector de Wysun Files se cerró con un error.')

    def test_queue_summary(self):
        self.add.render_queue()
        self.assertEqual(self.add.summary, 'No hay descargas en curso')
        self.assertFalse(self.add.counts['canRetry'])

    def test_batches_and_failed_songs(self):
        from wysun_music import data as music_data
        music_data.enqueue({'collections': [{'id': 'lote', 'title': 'Mi lote', 'append': True, 'source': 'x', 'tracks': [
            {'id': 'c' * 22, 'title': 'Uno', 'artist': 'A', 'duration': 10},
            {'id': 'd' * 22, 'title': 'Dos', 'artist': 'B', 'duration': 10}]}]})
        music_data.set_paused(True)
        music_data.update_track('d' * 22, status='missing', error='nada')
        try:
            self.music.library.reload(force=True)
            self.add.render_queue()
            self.assertEqual(self.rows(self.add.batches, 'title'), ['Mi lote'])
            self.assertEqual(self.rows(self.add.batches, 'detail'), ['0 de 2 · en pausa'])
            self.assertEqual(self.rows(self.add.failures, 'detail'), ['No encontrada en YouTube'])
            self.assertEqual(self.add.counts['failedText'], '1 canción no se pudo descargar')
            self.assertTrue(self.add.counts['canResume'])
            token = self.music.library.state['tracks']['c' * 22]['batch']
            self.add.cancelBatch(token)
            self.add.forget('d' * 22)
            self.assertEqual(self.add.batches.rowCount(), 0)
            self.assertEqual(self.add.failures.rowCount(), 0)
        finally:
            music_data.set_paused(False)
            self.music.library.reload(force=True)


if __name__ == '__main__':
    unittest.main()
