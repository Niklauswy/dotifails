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
        self.app = server.App(o)
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
        response, data = s.request('PUT', '/api/upload?dir=Clases&name=n.txt', body=b'abc', headers={'X-Wysun': '1'})
        self.assertEqual(response.status, 200)
        self.assertEqual((self.folder / 'Clases' / 'n.txt').read_bytes(), b'abc')
        notify.assert_called_once_with('n.txt', 'Videos/Clases')
        response, data = s.request('PUT', '/api/upload?dir=Clases&name=n.txt', body=b'de', headers={'X-Wysun': '1'})
        self.assertEqual(json.loads(data)['name'], 'n (2).txt')
        self.assertEqual(s.request('POST', '/api/mkdir?dir=&name=Nueva', headers={'X-Wysun': '1'})[0].status, 200)
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
        statuses = [s.request('POST', '/api/login', body=json.dumps({'clave': 'nope'}), headers={'X-Wysun': '1'})[0].status for _ in range(5)]
        self.assertEqual(statuses, [403, 403, 403, 403, 429])
        self.assertEqual(s.request('POST', '/api/login', body=json.dumps({'clave': 'k3m9rt'}), headers={'X-Wysun': '1'})[0].status, 429)
        self.assertEqual(s.app.activity.version, version)
        s.app.gate.fails.clear()
        response, _ = s.request('POST', '/api/login', body=json.dumps({'clave': ' k3m9rt '}), headers={'X-Wysun': '1'})
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

    # ---------------------------------------------------------------- security
    def test_uploads_need_the_page_header_and_same_origin(self):
        s = Running(self, [self.folder], uploads=True)
        mock.patch.object(server, 'notify').start()
        self.addCleanup(mock.patch.stopall)
        self.assertEqual(s.request('PUT', '/api/upload?dir=&name=a.txt', body=b'a', headers={})[0].status, 403,
                         'a plain cross-site form cannot send the custom header')
        evil = {'X-Wysun': '1', 'Origin': 'http://evil.example'}
        self.assertEqual(s.request('PUT', '/api/upload?dir=&name=a.txt', body=b'a', headers=evil)[0].status, 403)
        self.assertEqual(s.request('POST', '/api/mkdir?dir=&name=X', headers=evil)[0].status, 403)
        ok = {'X-Wysun': '1', 'Origin': f'http://127.0.0.1:{s.port}'}
        self.assertEqual(s.request('PUT', '/api/upload?dir=&name=a.txt', body=b'a', headers=ok)[0].status, 200)
        self.assertFalse((self.folder / 'a.txt').stat().st_mode & 0o111, 'never executable')

    def test_unknown_host_is_refused(self):
        s = Running(self, [self.folder])
        self.assertEqual(s.request('GET', '/api/ls?path=', headers={'Host': 'evil.example'})[0].status, 421,
                         'DNS rebinding: a foreign name pointing at us gets nothing')
        self.assertEqual(s.request('GET', '/', headers={'Host': 'evil.example:8000'})[0].status, 421)
        host = server.socket.gethostname().split('.')[0].lower()
        self.assertEqual(s.request('GET', '/', headers={'Host': f'{host}.lan:8000'})[0].status, 200)
        self.assertEqual(s.request('GET', '/', headers={'Host': f'{host}.evil.example'})[0].status, 421)

    def test_active_content_is_served_as_text_in_a_sandbox(self):
        (self.folder / 'evil.html').write_text('<script>alert(1)</script>')
        (self.folder / 'evil.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        s = Running(self, [self.folder])
        for name in ('evil.html', 'evil.svg'):
            response, _ = s.request('GET', '/raw/' + name)
            self.assertTrue(response.getheader('Content-Type').startswith('text/plain'), name)
            self.assertEqual(response.getheader('X-Content-Type-Options'), 'nosniff')
            self.assertIn('sandbox', response.getheader('Content-Security-Policy'))
        page, _ = s.request('GET', '/')
        self.assertIn("script-src 'self'", page.getheader('Content-Security-Policy'))
        self.assertIn("frame-ancestors 'none'", page.getheader('Content-Security-Policy'))

    def test_strange_paths_do_not_break_the_server(self):
        s = Running(self, [self.folder])
        for path in ('/raw/x%00.txt', '/api/ls?path=%00', '/raw/%2e%2e/%2e%2e/etc/passwd', '/zip/..%2f..'):
            self.assertIn(s.request('GET', path)[0].status, (400, 404), path)
        self.assertEqual(s.request('GET', '/raw/x.txt')[0].status, 200, 'still alive')

    def test_upload_larger_than_the_free_space_is_refused(self):
        s = Running(self, [self.folder], uploads=True)
        headers = {'X-Wysun': '1', 'Content-Length': str(10 ** 15)}
        conn = http.client.HTTPConnection('127.0.0.1', s.port, timeout=10)
        conn.putrequest('PUT', '/api/upload?dir=&name=big.bin')
        for key, value in headers.items():
            conn.putheader(key, value)
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 507)
        conn.close()
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ['Clases', 'x.txt'])

    def test_upload_never_overwrites(self):
        s = Running(self, [self.folder], uploads=True)
        mock.patch.object(server, 'notify').start()
        self.addCleanup(mock.patch.stopall)
        real = server.unique_name
        with mock.patch.object(server, 'unique_name', side_effect=lambda d, n: 'x.txt'):   # a race: the name was free
            response, data = s.request('PUT', '/api/upload?dir=&name=x.txt', body=b'nuevo', headers={'X-Wysun': '1'})
        self.assertEqual(response.status, 200)
        self.assertEqual((self.folder / 'x.txt').read_text(), 'hola mundo')
        self.assertNotEqual(json.loads(data)['name'], 'x.txt')
        self.assertTrue(callable(real))

    def test_notification_text_is_escaped(self):
        with mock.patch.object(server.shutil, 'which', return_value='/usr/bin/notify-send'), \
                mock.patch.object(server.threading, 'Thread') as thread:
            server.notify('<b>x</b>&.txt', 'Videos')
        argv = thread.call_args.kwargs['target'].__closure__[0].cell_contents
        self.assertIn('&lt;b&gt;x&lt;/b&gt;&amp;.txt · Videos', argv)

    def test_busy_port_moves_on(self):
        with socket.socket() as busy:
            busy.bind(('127.0.0.1', 0))
            busy.listen()
            port = busy.getsockname()[1]
            app = server.App(opts.Options(paths=[str(self.folder)]))
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
