"""wysun_drive: planning (conflicts, folders, skipped entries), running, history, bar status, api."""
import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_nextcloud import PASSWORD, USER, FakeNextcloud  # noqa: E402
from test_client import TempHome  # noqa: E402
from wysun_drive import account, api, history, status, upload  # noqa: E402
from wysun_drive.account import Account  # noqa: E402
from wysun_drive.client import AuthError, Cancelled, Client  # noqa: E402


class UploadTests(TempHome):
    def setUp(self):
        super().setUp()
        self.cloud = FakeNextcloud().__enter__()
        self.addCleanup(self.cloud.__exit__)
        self.acc = Account(self.cloud.url, USER, PASSWORD)
        self.client = Client(self.acc)
        self.local = self.base / 'local'
        (self.local / 'fotos/viaje').mkdir(parents=True)
        (self.local / 'fotos/a.jpg').write_bytes(b'a' * 10)
        (self.local / 'fotos/viaje/b.jpg').write_bytes(b'b' * 20)
        (self.local / 'fotos/enlace').symlink_to(self.local / 'fotos/a.jpg')
        (self.local / 'informe.pdf').write_bytes(b'pdf')

    def test_folder_upload_creates_tree_and_skips_links(self):
        plan = upload.plan(self.client, [self.local / 'fotos'], 'Wysun')
        self.assertEqual(plan.total, 30)
        self.assertTrue(any('enlace' in p for p in plan.problems))
        seen = []
        results = upload.run(self.client, plan, on_progress=lambda *a: seen.append(a))
        self.assertEqual([r.ok for r in results], [True])
        self.assertEqual(self.cloud.state.files['Wysun/fotos/viaje/b.jpg'], b'b' * 20)
        self.assertNotIn('Wysun/fotos/enlace', self.cloud.state.files)
        self.assertEqual(seen[-1][3:], (30, 30))

    def test_existing_names_get_numbered(self):
        self.client.mkdirs('Wysun')
        self.client.put('Wysun/informe.pdf', self.local / 'informe.pdf')
        self.client.put('Wysun/informe (2).pdf', self.local / 'informe.pdf')
        self.client.mkdirs('Wysun/fotos')
        plan = upload.plan(self.client, [self.local / 'informe.pdf', self.local / 'fotos'], 'Wysun')
        self.assertEqual([t.remote for t in plan.tops], ['Wysun/informe (3).pdf', 'Wysun/fotos (2)'])

    def test_missing_path_is_rejected_others_continue(self):
        results = api.upload([self.base / 'nope.txt', self.local / 'informe.pdf'], acc=self.acc)
        self.assertEqual([r.ok for r in results], [True, False])
        self.assertIn('No existe', results[1].error)

    def test_api_link_history_and_no_secret(self):
        [result] = api.upload([self.local / 'informe.pdf'], link=True, password='clave1', acc=self.acc)
        self.assertTrue(result.url.endswith('/s/tok1'))
        entries = history.load()
        self.assertEqual((entries[0]['remote'], entries[0]['url']), ('Wysun/informe.pdf', result.url))
        text = history.history_path().read_text()
        self.assertNotIn(PASSWORD, text)
        self.assertEqual(stat.S_IMODE(history.history_path().stat().st_mode), 0o600)

    def test_link_failure_keeps_the_upload(self):
        self.cloud.state.share_error = (403, 'Passwords are enforced for link shares')
        [result] = api.upload([self.local / 'informe.pdf'], link=True, acc=self.acc)
        self.assertTrue(result.ok)
        self.assertIn('Passwords are enforced', result.link_error)
        self.assertEqual(history.load()[0]['remote'], 'Wysun/informe.pdf')

    def test_no_account_is_auth_error(self):
        with self.assertRaises(AuthError):
            api.upload([self.local / 'informe.pdf'])

    def test_cancel(self):
        plan = upload.plan(self.client, [self.local / 'fotos'], 'Wysun')
        with self.assertRaises(Cancelled):
            upload.run(self.client, plan, cancelled=lambda: True)

    def test_history_limit(self):
        for n in range(history.LIMIT + 5):
            history.add([upload.Result('/x', f'Wysun/{n}', str(n), 1, False)])
        self.assertEqual(len(history.load()), history.LIMIT)
        self.assertEqual(history.load()[0]['remote'], f'Wysun/{history.LIMIT + 4}')


class StatusTests(TempHome):
    def test_status_file_private_and_removed(self):
        runtime = self.base / 'run'
        ticks = iter(range(1000, 2000, 5))
        sf = status.StatusFile(4242, 'informe.pdf', base=runtime, clock=lambda: next(ticks))
        sf.start()
        sf.progress('informe.pdf', 5, 10, 5, 10)
        data = json.loads(sf.path.read_text())
        self.assertEqual((data['pid'], data['title'], data['total']), (4242, 'informe.pdf', 10))
        self.assertEqual(stat.S_IMODE(sf.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(sf.path.parent.stat().st_mode), 0o700)
        sf.remove()
        self.assertFalse(sf.path.exists())

    def test_stop_refuses_other_processes(self):
        sleeper = subprocess.Popen(['sleep', '30'])
        self.addCleanup(sleeper.kill)
        self.assertFalse(status.stop(sleeper.pid))
        self.assertFalse(status.stop(1))
        self.assertFalse(status.stop(os.getpid()))
        self.assertIsNone(sleeper.poll())


if __name__ == '__main__':
    unittest.main()
