"""wysun_cloud.ssh: probe parsing, SSH routes and tab commands against a fake ssh."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/python'
FIXTURES = ROOT / 'tests/fixtures/cloud'
sys.path.insert(0, str(APP))

from wysun_core.tui.app import App  # noqa: E402
from wysun_core.tui.testing import VirtualTerminal  # noqa: E402
from wysun_cloud import ssh  # noqa: E402
from wysun_cloud.model import Instance  # noqa: E402

PROBE = APP / 'wysun_cloud/probe.sh'
ALIAS = 'api-backend.us-central1-a.mi-proyecto-prod'


def make_instance(**overrides):
    values = dict(
        project='mi-proyecto-prod', name='api-backend', zone='us-central1-a',
        status='RUNNING', machine_type='e2-small',
        external_ip='34.122.10.7', internal_ip='10.128.0.2',
        spot=False, os='debian-12', disks=['api-backend'],
        network='default', tags=[], started=None,
    )
    values.update(overrides)
    return Instance(**values)


class SshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / '.ssh').mkdir()
        # Only synthetic keys/config: the real ~/.ssh is never touched.
        (self.home / '.ssh' / 'config').write_text(
            'Host other-vm.us-central1-a.otro\n    HostName 10.0.0.9\n'
            f'Host {ALIAS}\n    HostName 34.122.10.7\n'
            f'# Host {ALIAS}.disabled\n',
            encoding='utf-8',
        )
        self.env = {
            'HOME': str(self.home),
            'XDG_CACHE_HOME': str(self.home / 'cache'),
            'XDG_CONFIG_HOME': str(self.home / 'config'),
            'XDG_DATA_HOME': str(self.home / 'data'),
            'XDG_STATE_HOME': str(self.home / 'state'),
            'PATH': f'{FIXTURES}{os.pathsep}{os.environ.get("PATH", "")}',
            'WYSUN_THEME': '',
            'FAKE_SSH_LOG': str(self.home / 'ssh.log'),
        }
        self.patcher = mock.patch.dict(os.environ, self.env)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        for name in ('FAKE_SSH_FAIL', 'FAKE_SSH_STDERR', 'FAKE_SSH_LINES',
                     'FAKE_SSH_LINE_DELAY', 'FAKE_SSH_OUTPUT'):
            os.environ.pop(name, None)
        self.inst = make_instance()

    def make_app(self):
        app = App(term=VirtualTerminal(120, 36), home=str(self.home))
        self.addCleanup(app.close)
        return app

    def ssh_calls(self):
        log = self.home / 'ssh.log'
        if not log.exists():
            return []
        return [line for line in log.read_text(encoding='utf-8').splitlines() if line]

    # -- the probe script -------------------------------------------------
    def test_probe_script_runs_locally_and_parses(self):
        env = dict(os.environ, INTERVAL='0.2')
        process = subprocess.Popen(
            ['sh', str(PROBE)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env,
        )
        try:
            first = process.stdout.readline()
            second = process.stdout.readline()
        finally:
            process.kill()
            process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()

        self.assertTrue(first.startswith('S '), first)
        self.assertTrue(second.startswith('S '), second)
        parser = ssh.ProbeParser()
        self.assertIsNone(parser.feed(first.strip()))
        sample = parser.feed(second.strip())
        self.assertIsNotNone(sample)
        self.assertGreaterEqual(sample.cpu, 0.0)
        self.assertLessEqual(sample.cpu, 1.0)
        self.assertGreater(sample.ram_total_gb, 0.0)
        self.assertTrue(sample.mounts)
        self.assertTrue(sample.top)
        self.assertIsInstance(sample.uptime_s, int)

    def test_parser_rates_from_recorded_lines(self):
        lines = (FIXTURES / 'probe-lines.txt').read_text(encoding='utf-8').splitlines()
        parser = ssh.ProbeParser()
        self.assertIsNone(parser.feed(lines[0]))
        sample = parser.feed(lines[1])
        self.assertIsNotNone(sample)

        self.assertAlmostEqual(sample.cpu, 0.15)
        self.assertEqual(len(sample.cores), 2)
        for core in sample.cores:
            self.assertAlmostEqual(core, 0.15)
        self.assertEqual(sample.load, (1.2, 0.6, 0.3))
        self.assertAlmostEqual(sample.ram_total_gb, 15.625)
        self.assertAlmostEqual(sample.ram_used_gb, 8384000 / 1048576)
        self.assertAlmostEqual(sample.cache_gb, 2000000 / 1048576)
        self.assertAlmostEqual(sample.swap_total_gb, 2.0)
        self.assertAlmostEqual(sample.swap_used_gb, 1097152 / 1048576)
        self.assertAlmostEqual(sample.rx_mbs, 1.5)
        self.assertAlmostEqual(sample.tx_mbs, 0.4)
        self.assertAlmostEqual(sample.read_mbs, 0.6144)
        self.assertAlmostEqual(sample.write_mbs, 1.024)
        self.assertEqual(sample.mounts,
                         [('/', 10240000 / 1048576, 51200000 / 1048576),
                          ('/boot', 512000 / 1048576, 1.0)])
        self.assertEqual(sample.uptime_s, 3601)
        self.assertEqual(sample.top, [(1200, 55.0, 3.0, 'node server.js')])

        self.assertIsNone(parser.feed('not a probe line'))

    # -- routes -----------------------------------------------------------
    def test_ssh_command_alias_with_fresh_hostname(self):
        argv = ssh.ssh_command(self.inst, ['true'])
        self.assertEqual(argv[:9], [
            'ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
            '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
        ])
        self.assertEqual(argv[9:], ['-o', 'HostName=34.122.10.7', ALIAS, 'true'])
        # The config is only read; its bytes (comments included) stay untouched.
        self.assertIn('# Host', (self.home / '.ssh' / 'config').read_text(encoding='utf-8'))

    def test_ssh_command_iap_without_external_ip(self):
        inst = make_instance(external_ip=None)
        argv = ssh.ssh_command(inst, ['sh', '-s'])
        self.assertEqual(argv[:11], [
            'gcloud', 'compute', 'ssh', 'api-backend', '--zone', 'us-central1-a',
            '--project', 'mi-proyecto-prod', '--tunnel-through-iap', '--quiet', '--',
        ])
        self.assertEqual(argv[11:], [
            '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
            '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
            'sh', '-s',
        ])
        self.assertEqual(ssh.ssh_command(inst, []), argv[:-2])

        # An external IP alone is not enough: the alias must be in the config.
        writable = self.home / '.ssh' / 'config'
        writable.write_text('Host otro\n    HostName 10.0.0.9\n', encoding='utf-8')
        self.assertEqual(ssh.ssh_command(self.inst, ['true'])[0], 'gcloud')

    # -- persistent sessions ---------------------------------------------
    def test_session_reconnects_after_drop(self):
        self.assertEqual(ssh.BACKOFF, (2, 5, 15, 30))
        os.environ['FAKE_SSH_LINES'] = '3'
        app = self.make_app()
        states = []
        samples = []
        session = ssh.ProbeSession(app, self.inst, samples.append,
                                   lambda state, reason: states.append((state, reason)))
        self.addCleanup(session.stop)
        with mock.patch.object(ssh, 'BACKOFF', (0.2,)):
            session.start()
            app.run_for(1.5)

        self.assertEqual([state for state, _reason in states[:4]],
                         ['conectando', 'activo', 'reconectando', 'activo'])
        self.assertTrue(samples)
        self.assertGreaterEqual(len(self.ssh_calls()), 2)

        session.stop()
        seen = len(states)
        app.run_for(0.3)
        self.assertEqual(len(states), seen)

    def test_session_permission_denied_reason(self):
        os.environ['FAKE_SSH_STDERR'] = 'Permission denied (publickey).'
        app = self.make_app()
        states = []
        session = ssh.ProbeSession(app, self.inst, lambda sample: None,
                                   lambda state, reason: states.append((state, reason)))
        self.addCleanup(session.stop)
        session.start()
        app.run_for(0.5)

        self.assertIn(('sin-ssh', 'llave rechazada'), states)
        for _state, reason in states:
            self.assertNotIn('Permission', reason)

    # -- tab commands -----------------------------------------------------
    def test_tab_command_falls_back_without_sudo(self):
        os.environ['FAKE_SSH_OUTPUT'] = 'LISTEN 0 128 0.0.0.0:22 0.0.0.0:*'
        app = self.make_app()
        results = []
        ssh.run_tab_command(app, self.inst, 'ports', results.append)
        app.run_for(1.0)

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.kind, 'ports')
        self.assertTrue(result.limited)
        self.assertIsNone(result.error)
        self.assertEqual(result.lines, ['LISTEN 0 128 0.0.0.0:22 0.0.0.0:*'])

        calls = self.ssh_calls()
        self.assertEqual(len(calls), 2)
        self.assertIn('sudo -n', calls[0])
        self.assertNotIn('sudo', calls[1])


if __name__ == '__main__':
    unittest.main()
