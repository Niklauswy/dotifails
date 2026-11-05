"""`wysun drive …` end to end in a temporary HOME against the fake Nextcloud (no clipboard, no notifications)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_nextcloud import PASSWORD, USER, FakeNextcloud  # noqa: E402
from wysun_drive import cli  # noqa: E402


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.cloud = FakeNextcloud().__enter__()
        self.addCleanup(self.cloud.__exit__)
        bindir = self.base / 'bin'
        bindir.mkdir()
        # Record clipboard and notifications instead of touching the session.
        for name in ('wl-copy', 'notify-send', 'xdg-open'):
            tool = bindir / name
            tool.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{self.base}/{name}.log"\n')
            tool.chmod(0o755)
        runtime = self.base / 'run'
        runtime.mkdir(mode=0o700)
        self.env = {'HOME': str(self.base), 'XDG_DATA_HOME': str(self.base / 'data'),
                    'XDG_CONFIG_HOME': str(self.base / 'config'), 'XDG_RUNTIME_DIR': str(runtime),
                    'PATH': f'{bindir}:/usr/bin:/bin', 'PYTHONPATH': str(ROOT / 'apps/python')}
        (self.base / 'informe.pdf').write_bytes(b'pdf!')

    def login(self):
        account = self.base / 'data/wysun/drive/account.json'
        account.parent.mkdir(parents=True, mode=0o700)
        account.write_text(json.dumps({'server': self.cloud.url, 'user': USER, 'password': PASSWORD}))
        config = self.base / 'config/wysun/drive.json'
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({'server': self.cloud.url}))
        account.chmod(0o600)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-P', '-m', 'wysun_drive', *args], env=self.env, cwd=self.base,
                              capture_output=True, text=True, timeout=60)

    def log(self, name):
        path = self.base / f'{name}.log'
        return path.read_text() if path.exists() else ''

    def test_without_session_exits_3(self):
        done = self.run_cli('up', 'informe.pdf')
        self.assertEqual(done.returncode, 3)
        self.assertIn('wysun drive login', done.stderr)

    def test_up_link_json_copies_and_never_prints_secret(self):
        self.login()
        done = self.run_cli('up', '--link', '--json', '--notificar', '--', 'informe.pdf')
        self.assertEqual(done.returncode, 0, done.stderr)
        [line] = done.stdout.splitlines()
        data = json.loads(line)
        self.assertTrue(data['ok'])
        self.assertEqual(data['remote'], 'Wysun/informe.pdf')
        self.assertIn('/s/tok1', data['url'])
        self.assertIn('/s/tok1', self.log('wl-copy'))
        self.assertIn('Link copiado', self.log('notify-send'))
        for text in (done.stdout, done.stderr, self.log('notify-send'), self.log('wl-copy')):
            self.assertNotIn(PASSWORD, text)
        self.assertEqual(list((self.base / 'run/wysun-drive').glob('*.json')), [])

    def test_clave_generates_password_and_name(self):
        self.login()
        done = self.run_cli('up', '--clave', '--nombre', 'Captura.png', '--json', '--sin-copiar', 'informe.pdf')
        data = json.loads(done.stdout)
        self.assertEqual(data['remote'], 'Wysun/Captura.png')
        self.assertEqual(len(data['password']), 10)
        self.assertEqual(self.log('wl-copy'), '')

    def test_usage_errors_exit_2(self):
        self.assertEqual(self.run_cli('up').returncode, 2)
        self.assertEqual(self.run_cli('up', '--nombre', 'x', 'a', 'b').returncode, 2)
        self.assertEqual(self.run_cli('up', '--caduca', 'mañana', 'a').returncode, 2)
        self.assertEqual(self.run_cli('nada').returncode, 2)

    def test_recientes(self):
        self.login()
        self.run_cli('up', '--link', '--sin-copiar', 'informe.pdf')
        done = self.run_cli('recientes', '--json')
        self.assertEqual(json.loads(done.stdout.splitlines()[0])['remote'], 'Wysun/informe.pdf')
        self.assertIn('/s/tok1', self.run_cli('recientes').stdout)

    def test_ajustes_changes_server_and_session_follows_it(self):
        self.login()
        done = self.run_cli('ajustes', '--servidor', 'otro.example/', '--carpeta', '/Trabajo/Compartido/')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('otro servidor', done.stdout)
        state = json.loads(self.run_cli('estado', '--json').stdout)
        self.assertEqual((state['server'], state['folder'], state['user']),
                         ('https://otro.example', 'Trabajo/Compartido', None))
        self.assertEqual(state['other_server'], self.cloud.url)
        up = self.run_cli('up', 'informe.pdf')
        self.assertEqual(up.returncode, 3)
        self.assertIn('https://otro.example', up.stderr)
        # Back to the fake server: the session works again, into the chosen folder.
        self.run_cli('ajustes', '--servidor', self.cloud.url)
        self.assertEqual(self.run_cli('up', 'informe.pdf').returncode, 0)
        self.assertIn('Trabajo/Compartido/informe.pdf', self.cloud.state.files)

    def test_ajustes_rejects_plain_http(self):
        self.assertEqual(self.run_cli('ajustes', '--servidor', 'http://cloud.example').returncode, 2)

    def test_manual_login_with_app_password(self):
        bad = subprocess.run([sys.executable, '-P', '-m', 'wysun_drive', 'login', '--manual', self.cloud.url],
                             input=f'{USER}\nSYNTHETIC-wrong\n', env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(bad.returncode, 3)
        self.assertIn('rechazó', bad.stderr)
        self.assertNotIn('SYNTHETIC-wrong', bad.stdout + bad.stderr)
        done = subprocess.run([sys.executable, '-P', '-m', 'wysun_drive', 'login', '--manual', self.cloud.url],
                              input=f'{USER}\n{PASSWORD}\n', env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn(PASSWORD, done.stdout + done.stderr)
        state = json.loads(self.run_cli('estado', '--json').stdout)
        self.assertEqual((state['server'], state['user']), (self.cloud.url, USER))
        self.assertEqual(self.run_cli('up', 'informe.pdf').returncode, 0)

    def test_result_file_and_deferred_notification(self):
        self.login()
        result = self.base / 'run/res.json'
        done = self.run_cli('up', '--link', '--origen', 'files', '--resultado', str(result), 'informe.pdf')
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(result.read_text())
        self.assertTrue(data['copied'])
        self.assertEqual(data['results'][0]['remote'], 'Wysun/informe.pdf')
        self.assertNotIn(PASSWORD, result.read_text())
        self.assertEqual(oct(result.stat().st_mode & 0o777), '0o600')
        self.assertEqual(self.log('notify-send'), '', 'no notification unless asked')
        self.assertEqual(json.loads(self.run_cli('recientes', '--json').stdout.splitlines()[0])['source'], 'files')

    def test_human_size(self):
        self.assertEqual(cli.human_size(512), '512 B')
        self.assertEqual(cli.human_size(1536), '1,5 KB')
        self.assertEqual(cli.parse_days('7d'), 7)


if __name__ == '__main__':
    unittest.main()
