"""wysun_drive: account file, WebDAV/OCS client and login flow against a fake Nextcloud."""
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_nextcloud import PASSWORD, USER, FakeNextcloud  # noqa: E402
from wysun_drive import account, login  # noqa: E402
from wysun_drive.account import Account  # noqa: E402
from wysun_drive.client import AuthError, Client, DriveError, split_server  # noqa: E402


class TempHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.base = base
        patcher = mock.patch.dict(os.environ, {'HOME': str(base), 'XDG_DATA_HOME': str(base / 'data'),
                                               'XDG_CONFIG_HOME': str(base / 'config')})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)


class AccountTests(TempHome):
    def test_saved_private_and_loaded(self):
        account.save(Account('https://cloud.example/', USER, PASSWORD))
        path = account.account_path()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        loaded = account.load()
        self.assertEqual((loaded.server, loaded.user, loaded.password), ('https://cloud.example/'.rstrip('/'), USER, PASSWORD))
        self.assertNotIn(PASSWORD, repr(loaded))
        account.forget()
        self.assertIsNone(account.load())

    def test_settings_defaults_and_overrides(self):
        self.assertEqual(account.settings(), {'server': 'https://cloud.wysun.store', 'folder': 'Wysun'})
        cfg = self.base / 'config/wysun/drive.json'
        cfg.parent.mkdir(parents=True)
        cfg.write_text('{"server": "https://x.example/", "folder": "/a/../b/"}')
        self.assertEqual(account.settings(), {'server': 'https://x.example', 'folder': 'a/b'})


class ClientTests(TempHome):
    def setUp(self):
        super().setUp()
        self.cloud = FakeNextcloud().__enter__()
        self.addCleanup(self.cloud.__exit__)
        self.client = Client(Account(self.cloud.url, USER, PASSWORD), chunk_threshold=1000, chunk_size=300)
        self.local = self.base / 'local'
        self.local.mkdir()

    def file(self, name, data):
        path = self.local / name
        path.write_bytes(data)
        return path

    def test_small_upload_with_awkward_name(self):
        name = 'informe final á #1 %20?.pdf'
        self.client.mkdirs('Wysun/sub dir')
        seen = []
        self.client.put(f'Wysun/sub dir/{name}', self.file(name, b'hola' * 10), progress=seen.append)
        self.assertEqual(self.cloud.state.files[f'Wysun/sub dir/{name}'], b'hola' * 10)
        self.assertEqual(sum(seen), 40)
        self.assertTrue(self.client.exists(f'Wysun/sub dir/{name}'))
        self.assertFalse(self.client.exists('Wysun/nope'))

    def test_chunked_upload_retries_a_failed_chunk(self):
        data = os.urandom(2500)
        self.client.mkdirs('Wysun')
        self.cloud.state.fail_puts = 2
        seen = []
        with mock.patch('wysun_drive.client.time.sleep'):
            self.client.put('Wysun/big.bin', self.file('big.bin', data), progress=seen.append)
        self.assertEqual(self.cloud.state.files['Wysun/big.bin'], data)
        self.assertEqual(sum(seen), 2500)

    def test_wrong_password_is_auth_error_without_secret(self):
        bad = Client(Account(self.cloud.url, USER, 'SYNTHETIC-wrong'))
        with self.assertRaises(AuthError) as caught:
            bad.mkdirs('Wysun')
        self.assertEqual(caught.exception.code, 3)
        self.assertNotIn('SYNTHETIC', str(caught.exception))

    def test_share_and_ocs_error_message(self):
        self.client.mkdirs('Wysun')
        self.client.put('Wysun/a.txt', self.file('a.txt', b'x'))
        link = self.client.share('Wysun/a.txt', password='gato123', expire_days=7)
        self.assertTrue(link['url'].endswith('/s/tok1'))
        fields = self.cloud.state.shares[link['id']]
        self.assertEqual((fields['shareType'], fields['password']), ('3', 'gato123'))
        self.assertRegex(fields['expireDate'], r'^\d{4}-\d\d-\d\d$')
        self.cloud.state.share_error = (403, 'Passwords are enforced for link shares')
        with self.assertRaises(DriveError) as caught:
            self.client.share('Wysun/a.txt')
        self.assertIn('Passwords are enforced', str(caught.exception))
        self.client.unshare(link['id'])
        self.assertNotIn(link['id'], self.cloud.state.shares)

    def test_redirect_is_not_followed(self):
        self.cloud.state.redirect = True
        with self.assertRaises(DriveError) as caught:
            self.client.mkdirs('Wysun')
        self.assertIn('redirigió', str(caught.exception))
        self.assertEqual(len(self.cloud.state.requests), 1)

    def test_secret_never_in_any_error(self):
        for call in (lambda: self.client.share('nope'), lambda: self.client.put('a/b/c', self.file('c', b'1'))):
            with self.assertRaises(DriveError) as caught:
                call()
            self.assertNotIn(PASSWORD, str(caught.exception))

    def test_plain_http_only_to_loopback(self):
        with self.assertRaises(DriveError):
            split_server('http://cloud.example')
        self.assertEqual(split_server('https://cloud.example/nc/')[1:], ('cloud.example', None, '/nc'))

    def test_login_flow(self):
        url, poll = login.start(self.cloud.url)
        self.assertIn('/login/v2/flow/', url)
        got = login.wait(poll, interval=0, sleep=lambda s: None)
        self.assertEqual((got.user, got.password), (USER, PASSWORD))
        self.assertEqual(self.cloud.state.login_polls, 2)


if __name__ == '__main__':
    unittest.main()
