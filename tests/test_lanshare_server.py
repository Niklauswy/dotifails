"""LANShare HTTP server: access, uploads, ranges, zips and theme (real server on 127.0.0.1, temp HOME)."""
import http.client
import io
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))

from wysun_lanshare import options as opts, server, status  # noqa: E402


class Running:
    """A server for one test: start(paths, **options) → port."""

    def __init__(self, case, paths, **kw):
        o = opts.Options(paths=[str(p) for p in paths], **kw)
        self.app = server.App(o, environ={'XDG_RUNTIME_DIR': case.home})
        self.srv, self.port = server.make_server(self.app, host='127.0.0.1', port=case.free_port())
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        case.addCleanup(self.close)

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response, data


class ServerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = os.path.realpath(tmp.name)
        env = {'HOME': self.home, 'XDG_CACHE_HOME': self.home + '/.cache', 'XDG_STATE_HOME': self.home + '/.local/state',
               'XDG_CONFIG_HOME': self.home + '/.config', 'XDG_DATA_HOME': self.home + '/.local/share',
               'XDG_RUNTIME_DIR': self.home}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.folder = Path(self.home) / 'Videos'
        self.folder.mkdir()
        (self.folder / 'x.txt').write_text('hola mundo')
        (self.folder / 'Clases').mkdir()
        (self.folder / 'Clases' / 'y.txt').write_text('y')

    def free_port(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def test_listing_and_range(self):
        s = Running(self, [self.folder])
        response, data = s.request('GET', '/api/ls?path=')
        self.assertEqual(response.status, 200)
        listing = json.loads(data)
        self.assertEqual(sorted(e['name'] for e in listing['entries']), ['Clases', 'x.txt'])
        self.assertFalse(listing['uploads'])
        response, data = s.request('GET', '/raw/x.txt', headers={'Range': 'bytes=0-1'})
        self.assertEqual((response.status, data), (206, b'ho'))
        response, data = s.request('GET', '/raw/x.txt?dl=1')
        self.assertIn('attachment', response.getheader('Content-Disposition'))
        self.assertEqual(s.request('GET', '/raw/../secreto')[0].status, 404)
        response, data = s.request('GET', '/api/info')
        info = json.loads(data)
        self.assertEqual((info['title'], info['mode'], info['locked'], info['uploads']), ('Videos', 'folder', False, False))

    def test_uploads_need_the_option(self):
        s = Running(self, [self.folder])
        self.assertEqual(s.request('PUT', '/api/upload?dir=&name=n.txt', body=b'abc')[0].status, 403)
        self.assertEqual(s.request('POST', '/api/mkdir?dir=&name=Nueva')[0].status, 403)
        self.assertFalse((self.folder / 'n.txt').exists())

    def test_upload_with_option(self):
        s = Running(self, [self.folder], uploads=True)
        notify = mock.patch.object(server, 'notify').start()
        self.addCleanup(mock.patch.stopall)
        response, data = s.request('PUT', '/api/upload?dir=Clases&name=n.txt', body=b'abc')
        self.assertEqual(response.status, 200)
        self.assertEqual((self.folder / 'Clases' / 'n.txt').read_bytes(), b'abc')
        notify.assert_called_once_with('n.txt', 'Videos/Clases')
        response, data = s.request('PUT', '/api/upload?dir=Clases&name=n.txt', body=b'de')
        self.assertEqual(json.loads(data)['name'], 'n (2).txt')
        self.assertEqual(s.request('POST', '/api/mkdir?dir=&name=Nueva')[0].status, 200)
        self.assertTrue((self.folder / 'Nueva').is_dir())

    def test_password(self):
        s = Running(self, [self.folder], password='k3m9rt')
        version = s.app.activity.version
        response, data = s.request('GET', '/api/ls?path=')
        self.assertEqual(response.status, 401)
        self.assertEqual(s.request('GET', '/raw/x.txt')[0].status, 401)
        self.assertTrue(json.loads(s.request('GET', '/api/info')[1])['locked'])
        self.assertEqual(s.app.activity.version, version)
        self.assertEqual(s.request('GET', '/theme.css')[0].status, 200)
        statuses = [s.request('POST', '/api/login', body=json.dumps({'clave': 'nope'}))[0].status for _ in range(5)]
        self.assertEqual(statuses, [403, 403, 403, 403, 429])
        self.assertEqual(s.request('POST', '/api/login', body=json.dumps({'clave': 'k3m9rt'}))[0].status, 429)
        self.assertEqual(s.app.activity.version, version)
        s.app.gate.fails.clear()
        response, _ = s.request('POST', '/api/login', body=json.dumps({'clave': ' k3m9rt '}))
        self.assertEqual(response.status, 200)
        cookie = response.getheader('Set-Cookie')
        self.assertIn('HttpOnly', cookie)
        token = cookie.split(';')[0]
        response, _ = s.request('GET', '/api/ls?path=', headers={'Cookie': token})
        self.assertEqual(response.status, 200)
        self.assertFalse(json.loads(s.request('GET', '/api/info', headers={'Cookie': token})[1])['locked'])
        self.assertGreater(s.app.activity.version, version)

    def test_theme_is_local(self):
        s = Running(self, [self.folder])
        response, data = s.request('GET', '/theme.css')
        text = data.decode()
        self.assertIn('--m3primary:#', text)
        self.assertIn('@font-face', text)
        self.assertNotIn('http', text)
        response, data = s.request('GET', '/fonts/GoogleSansFlex.ttf')
        self.assertEqual(response.status, 200)
        self.assertEqual(s.request('GET', '/fonts/../server.py')[0].status, 404)
        response, data = s.request('GET', '/')
        self.assertIn(b'<html', data)

    def test_zip_of_a_list(self):
        other = Path(self.home) / 'informe.pdf'
        other.write_bytes(b'%PDF')
        s = Running(self, [self.folder, other])
        response, data = s.request('GET', '/zip/')
        self.assertEqual(response.status, 200)
        names = sorted(zipfile.ZipFile(io.BytesIO(data)).namelist())
        self.assertEqual(names, ['Videos/Clases/y.txt', 'Videos/x.txt', 'informe.pdf'])
        self.assertEqual(s.request('PUT', '/api/upload?dir=Videos&name=n.txt', body=b'a')[0].status, 403)

    def test_busy_port_moves_on(self):
        with socket.socket() as busy:
            busy.bind(('127.0.0.1', 0))
            busy.listen()
            port = busy.getsockname()[1]
            app = server.App(opts.Options(paths=[str(self.folder)]), environ={'XDG_RUNTIME_DIR': self.home})
            srv, chosen = server.make_server(app, host='127.0.0.1', port=port)
            srv.server_close()
        self.assertGreater(chosen, port)
        self.assertLessEqual(chosen, port + 20)

    def test_stop_option(self):
        with mock.patch.object(status, 'stop', return_value=True) as stop:
            self.assertEqual(server.main(['--detener', '4321']), 0)
        stop.assert_called_once_with(4321)
        with mock.patch.object(status, 'stop', return_value=False):
            with mock.patch('sys.stderr', io.StringIO()):
                self.assertEqual(server.main(['--detener', '4321']), 1)


if __name__ == '__main__':
    unittest.main()
