"""The instance cache, the bar state file, approximate prices and the `--estado` entry point."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/python'
FIXTURES = ROOT / 'tests/fixtures/cloud'
sys.path.insert(0, str(APP))

from wysun_cloud import cache, pricing, state  # noqa: E402
from wysun_cloud.model import Instance  # noqa: E402

PYTHON = shutil.which('python3') or sys.executable
RUNNING = [
    {'project': 'mi-proyecto-prod', 'name': 'api-backend', 'zone': 'us-central1-a'},
    {'project': 'mi-proyecto-prod', 'name': 'worker-1', 'zone': 'us-central1-b'},
    {'project': 'personal-lab', 'name': 'dev-box', 'zone': 'us-west1-b'},
    {'project': 'cliente-x', 'name': 'web-cliente', 'zone': 'southamerica-east1-a'},
]


def an_instance():
    return Instance(project='mi-proyecto-prod', name='api-backend', zone='us-central1-a', status='RUNNING',
                    machine_type='e2-small', external_ip='34.122.10.7', internal_ip='10.128.0.2', spot=False,
                    os='debian-12-bookworm', disks=['api-backend'], network='default', tags=['web', 'api'],
                    started=1_700_000_000.0)


class CacheStatePricingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        runtime = base / 'runtime'
        runtime.mkdir(mode=0o700)
        self.env = {
            'HOME': str(base),
            'XDG_CACHE_HOME': str(base / 'cache'),
            'XDG_CONFIG_HOME': str(base / 'config'),
            'XDG_DATA_HOME': str(base / 'data'),
            'XDG_STATE_HOME': str(base / 'state'),
            'XDG_RUNTIME_DIR': str(runtime),
            'PATH': f'{FIXTURES}{os.pathsep}{os.environ.get("PATH", "")}',
            'PYTHONPATH': str(APP),
        }
        self.patcher = mock.patch.dict(os.environ, self.env)
        self.patcher.start()
        for name in ('FAKE_GCLOUD_SLEEP', 'FAKE_GCLOUD_AUTH_ERROR', 'FAKE_GCLOUD_FAIL_PROJECT',
                     'FAKE_GCLOUD_FAIL_ACTION', 'FAKE_GCLOUD_LOG'):
            os.environ.pop(name, None)
        self.base = base

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def run_estado(self, **extra):
        env = dict(os.environ, **extra)
        return subprocess.run([PYTHON, '-P', '-m', 'wysun_cloud', '--estado'], env=env,
                              capture_output=True, text=True, timeout=60)

    def test_cache_roundtrip_and_projects_stale(self):
        self.assertIsNone(cache.load())
        self.assertTrue(cache.projects_stale(time.time()))

        instance = an_instance()
        cache.save(['mi-proyecto-prod'], [instance])
        loaded = cache.load()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['projects'], ['mi-proyecto-prod'])
        self.assertEqual(Instance.from_dict(loaded['instances'][0]), instance)
        self.assertEqual(loaded['instances'][0]['name'], 'api-backend')

        now = 1_800_000_000.0
        cache.save_projects(['mi-proyecto-prod'], now)
        self.assertEqual(cache.load_projects(), ['mi-proyecto-prod'])
        self.assertFalse(cache.projects_stale(now + 3600))
        self.assertTrue(cache.projects_stale(now + 24 * 3600 + 1))

    def test_pricing_known_and_unknown(self):
        self.assertAlmostEqual(pricing.hourly('e2-small', 'us-central1-a'), 0.0168, places=5)
        self.assertAlmostEqual(pricing.hourly('e2-small', 'europe-west1-b'), 0.0168 * 1.1, places=5)
        self.assertAlmostEqual(pricing.hourly('n1-standard-2', 'southamerica-east1-a'), 0.095 * 1.5, places=5)
        self.assertAlmostEqual(pricing.hourly('g2-standard-4', 'asia-east1-a'), 0.70 * 1.15, places=5)
        self.assertIsNone(pricing.hourly('mega-ultra-9', 'us-central1-a'))
        self.assertIsNone(pricing.hourly('', ''))

    def test_estado_writes_private_state_file(self):
        result = self.run_estado()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')

        directory = Path(self.env['XDG_RUNTIME_DIR']) / 'wysun-cloud'
        path = directory / 'state.json'
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        payload = json.loads(path.read_text(encoding='utf-8'))
        self.assertIsInstance(payload['updated'], (int, float))
        self.assertEqual(payload['total'], 7)
        self.assertEqual(sorted(payload['running'], key=lambda vm: (vm['project'], vm['name'])),
                         sorted(RUNNING, key=lambda vm: (vm['project'], vm['name'])))

        self.assertEqual(cache.load()['projects'], ['mi-proyecto-prod', 'personal-lab', 'cliente-x'])
        self.assertFalse(cache.projects_stale(time.time()))

    def test_estado_exits_zero_without_gcloud(self):
        path = state.write_state([an_instance()], 1_700_000_000.0)
        before = path.read_bytes()
        result = self.run_estado(PATH='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')
        self.assertEqual(path.read_bytes(), before)

    def test_state_file_is_private_and_atomic(self):
        path = state.write_state([an_instance()], 1234.5)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.parent, Path(self.env['XDG_RUNTIME_DIR']) / 'wysun-cloud')
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')),
                         {'updated': 1234.5,
                          'running': [{'project': 'mi-proyecto-prod', 'name': 'api-backend',
                                       'zone': 'us-central1-a'}],
                          'total': 1})
        self.assertFalse(stat.S_ISLNK(path.stat().st_mode))


if __name__ == '__main__':
    unittest.main()
