"""wysun_cloud.gcloud parses gcloud's JSON and turns failures into short Spanish messages."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/python'
FIXTURES = ROOT / 'tests/fixtures/cloud'
sys.path.insert(0, str(APP))

from wysun_core import launch  # noqa: E402
from wysun_cloud import __main__ as cli  # noqa: E402
from wysun_cloud.gcloud import Gcloud, GcloudAuth, GcloudError, GcloudMissing  # noqa: E402
from wysun_cloud.model import Instance  # noqa: E402


class GcloudTests(unittest.TestCase):
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
        }
        self.patcher = mock.patch.dict(os.environ, self.env)
        self.patcher.start()
        for name in ('FAKE_GCLOUD_SLEEP', 'FAKE_GCLOUD_AUTH_ERROR', 'FAKE_GCLOUD_FAIL_PROJECT',
                     'FAKE_GCLOUD_FAIL_ACTION', 'FAKE_GCLOUD_LOG'):
            os.environ.pop(name, None)
        self.gcloud = Gcloud()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def instance(self, project, name):
        return next(inst for inst in self.gcloud.instances(project) if inst.name == name)

    def test_projects_and_instances_parse(self):
        self.assertEqual(self.gcloud.projects(), ['mi-proyecto-prod', 'personal-lab', 'cliente-x', 'proyecto-sin-vms'])

        api = self.instance('mi-proyecto-prod', 'api-backend')
        self.assertIsInstance(api, Instance)
        self.assertEqual((api.project, api.name, api.zone), ('mi-proyecto-prod', 'api-backend', 'us-central1-a'))
        self.assertEqual(api.status, 'RUNNING')
        self.assertTrue(api.running)
        self.assertEqual(api.alias, 'api-backend.us-central1-a.mi-proyecto-prod')
        self.assertEqual(api.external_ip, '34.122.10.7')
        self.assertEqual(api.internal_ip, '10.128.0.2')
        self.assertEqual(api.machine_type, 'e2-small')
        self.assertFalse(api.spot)
        self.assertEqual(api.os, 'debian-12-bookworm')
        self.assertEqual(api.disks, ['api-backend'])
        self.assertEqual(api.network, 'default')
        self.assertEqual(api.tags, ['web', 'api'])
        self.assertIsNotNone(api.started)

        spot = self.instance('personal-lab', 'batch-spot')
        self.assertFalse(spot.running)
        self.assertTrue(spot.spot)
        self.assertIsNone(spot.external_ip)

        staging = self.instance('cliente-x', 'staging')
        self.assertEqual(staging.os, '')
        self.assertEqual(staging.tags, [])

    def test_one_project_failing_does_not_hide_others(self):
        os.environ['FAKE_GCLOUD_FAIL_PROJECT'] = 'personal-lab'
        instances, messages = self.gcloud.instances_all(['mi-proyecto-prod', 'personal-lab', 'cliente-x'])
        self.assertEqual({inst.name for inst in instances}, {'api-backend', 'worker-1', 'db-old', 'web-cliente', 'staging'})
        self.assertIn('personal-lab', messages)
        self.assertIsInstance(messages['personal-lab'], str)
        self.assertTrue(messages['personal-lab'])

    def test_disks_only_attached_to_exactly_this_vm(self):
        inst = self.gcloud.instances('mi-proyecto-prod')[0]
        base = f'https://www.googleapis.com/compute/v1/projects/{inst.project}/zones/{inst.zone}'
        answer = [
            {'name': 'mine', 'zone': base, 'users': [f'{base}/instances/{inst.name}']},
            {'name': 'loose', 'zone': base, 'users': []},
            {'name': 'cousin', 'zone': base, 'users': [f'{base}/instances/{inst.name}-worker']},
        ]
        with mock.patch.object(self.gcloud, 'json', return_value=answer):
            self.assertEqual([disk['name'] for disk in self.gcloud.disks(inst)], ['mine'])

    def test_missing_gcloud_raises_gcloud_missing(self):
        with mock.patch.dict(os.environ, {'PATH': ''}):
            with self.assertRaises(GcloudMissing) as caught:
                Gcloud().projects()
        self.assertIn('gcloud', caught.exception.message)

    def test_auth_error_is_gcloud_auth_with_spanish_message(self):
        os.environ['FAKE_GCLOUD_AUTH_ERROR'] = '1'
        with self.assertRaises(GcloudAuth) as caught:
            self.gcloud.projects()
        self.assertIn('gcloud auth login', caught.exception.message)
        self.assertIsInstance(caught.exception, GcloudError)

    def test_action_argv_has_name_zone_and_project(self):
        api = self.instance('mi-proyecto-prod', 'api-backend')
        for verb in ('start', 'stop', 'reset'):
            self.assertEqual(self.gcloud.action_argv(verb, api),
                             ['compute', 'instances', verb, 'api-backend', '--zone', 'us-central1-a',
                              '--project', 'mi-proyecto-prod'])

    def test_operations_firewall_and_disks(self):
        api = self.instance('mi-proyecto-prod', 'api-backend')
        operations = self.gcloud.operations(api)
        self.assertEqual([op['operationType'] for op in operations], ['insert', 'start'])
        self.assertEqual(len(self.gcloud.operations(api, limit=1)), 1)

        rules = self.gcloud.firewall(api)
        self.assertEqual([rule['name'] for rule in rules], ['allow-3000-dev', 'allow-iap-ssh'])
        self.assertEqual(rules[0]['sourceRanges'], ['0.0.0.0/0'])

        disks = self.gcloud.disks(api)
        self.assertEqual([disk['name'] for disk in disks], ['api-backend'])
        self.assertEqual(disks[0]['lastSnapshot']['name'], 'api-backend-snap-20261101')

    def test_terminal_argv_ghostty(self):
        found = {'ghostty': '/usr/bin/ghostty'}
        with mock.patch.object(launch.shutil, 'which', side_effect=found.get):
            self.assertEqual(launch.terminal_argv(['ssh', 'vm']),
                             ['/usr/bin/ghostty', '--gtk-single-instance=false', '-e', 'ssh', 'vm'])
        with mock.patch.object(launch.shutil, 'which', side_effect={'xterm': '/usr/bin/xterm'}.get):
            self.assertEqual(launch.terminal_argv(['ssh', 'vm']), ['/usr/bin/xterm', '-e', 'ssh', 'vm'])
        with mock.patch.object(launch.shutil, 'which', return_value=None):
            self.assertIsNone(launch.terminal_argv(['ssh', 'vm']))

    def test_terminal_option_launches_detached(self):
        argv = ['/usr/bin/ghostty', '--gtk-single-instance=false', '-e', 'wysun', 'cloud']
        with mock.patch.object(launch, 'terminal_argv', return_value=argv) as terminal_argv, \
                mock.patch('subprocess.Popen') as popen:
            self.assertEqual(cli.main(['--terminal']), 0)
        terminal_argv.assert_called_once_with(['wysun', 'cloud'])
        popen.assert_called_once_with(argv, start_new_session=True, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()
