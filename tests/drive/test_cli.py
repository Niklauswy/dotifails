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

    def test_human_size(self):
        self.assertEqual(cli.human_size(512), '512 B')
        self.assertEqual(cli.human_size(1536), '1,5 KB')
        self.assertEqual(cli.parse_days('7d'), 7)


if __name__ == '__main__':
    unittest.main()
