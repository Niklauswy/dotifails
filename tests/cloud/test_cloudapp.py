"""CloudApp: cached first paint, live data, transitions, actions, filter and help."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/python'
FIXTURES = ROOT / 'tests/fixtures/cloud'
sys.path.insert(0, str(APP))

from wysun_core.tui.testing import VirtualTerminal  # noqa: E402
from wysun_cloud import cache  # noqa: E402
from wysun_cloud.model import Instance  # noqa: E402
from wysun_cloud.ui import cloudapp  # noqa: E402
from wysun_cloud.ui.cloudapp import CloudApp  # noqa: E402

PROJECTS = ['mi-proyecto-prod', 'personal-lab', 'cliente-x']
API = 'api-backend.us-central1-a.mi-proyecto-prod'
DB = 'db-old.us-central1-a.mi-proyecto-prod'
STAGING = 'staging.us-central1-f.cliente-x'


def read_instances(project):
    data = json.loads((FIXTURES / f'instances-{project}.json').read_text(encoding='utf-8'))
    return [Instance.from_gcloud(project, item) for item in data]


def all_instances():
    found = []
    for project in PROJECTS:
        found.extend(read_instances(project))
    return found


def frame_text(term):
    return '\n'.join(term.canvas_text())


class CloudAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / '.ssh').mkdir()
        # Synthetic SSH config only: the real one is never read or written.
        (self.home / '.ssh' / 'config').write_text(
            'Host api-backend.us-central1-a.mi-proyecto-prod\n    HostName 34.122.10.7\n'
            'Host dev-box.us-central1-a.personal-lab\n    HostName 35.1.2.3\n'
            'Host web-cliente.us-west1-a.cliente-x\n    HostName 34.83.9.120\n',
            encoding='utf-8',
        )
        self.runtime = self.home / 'run'
        self.log = self.home / 'gcloud.log'
        env = {
            'HOME': str(self.home),
            'XDG_CACHE_HOME': str(self.home / 'cache'),
            'XDG_CONFIG_HOME': str(self.home / 'config'),
            'XDG_DATA_HOME': str(self.home / 'data'),
            'XDG_STATE_HOME': str(self.home / 'state'),
            'XDG_RUNTIME_DIR': str(self.runtime),
            'PATH': f'{FIXTURES}{os.pathsep}{os.environ.get("PATH", "")}',
            'WYSUN_THEME': '',
            'WYSUN_REDUCED_MOTION': '1',
            'FAKE_GCLOUD_LOG': str(self.log),
            'FAKE_SSH_LOG': str(self.home / 'ssh.log'),
        }
        self.patcher = mock.patch.dict(os.environ, env)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        for name in ('FAKE_GCLOUD_SLEEP', 'FAKE_GCLOUD_AUTH_ERROR',
                     'FAKE_GCLOUD_FAIL_PROJECT', 'FAKE_GCLOUD_FAIL_ACTION',
                     'FAKE_SSH_FAIL', 'FAKE_SSH_STDERR', 'FAKE_SSH_OUTPUT'):
            os.environ.pop(name, None)

    # -- helpers ----------------------------------------------------------
    def seed_cache(self, projects=None, instances=None):
        cache.save(projects or PROJECTS, instances if instances is not None else all_instances())

    def make_app(self, width=120, height=36):
        term = VirtualTerminal(width, height)
        self.addCleanup(term.close)
        app = CloudApp(term=term, home=str(self.home))
        self.addCleanup(app.close)
        return app, term

    def settle(self, app, term, seconds=0.4):
        app.run_for(seconds)
        return term.canvas_text()

    def ssh_log_lines(self):
        path = self.home / 'ssh.log'
        return path.read_text(encoding='utf-8').splitlines() if path.exists() else []

    def gcloud_calls(self):
        if not self.log.exists():
            return []
        return [line for line in self.log.read_text(encoding='utf-8').splitlines() if line]

    def press(self, app, term, data, wait=0.05):
        term.feed_input(data)
        app.step()
        app.run_for(wait)

    # -- first paint ------------------------------------------------------
    def test_first_paint_comes_from_cache_before_gcloud_answers(self):
        os.environ['FAKE_GCLOUD_SLEEP'] = '2'
        self.seed_cache()
        app, term = self.make_app()
        app.step()                     # exactly one loop iteration
        rows = term.canvas_text()
        text = '\n'.join(rows)
        self.assertIn('api-backend', text)
        self.assertIn('dev-box', text)
        self.assertIn('actualizando', text)   # the refresh is still in flight

    # -- detail transitions ----------------------------------------------
    def test_enter_opens_detail_and_escape_returns(self):
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term)
        self.assertEqual(app.selected, API)
        self.press(app, term, b'\r')
        text = frame_text(term)
        self.assertIn('Resumen', text)
        self.assertIn('Procesos', text)
        self.assertIn('mosaico ›', text)
        self.press(app, term, b'\x1b', 0.08)
        text = frame_text(term)
        self.assertNotIn('Resumen', text)
        self.assertIn('api-backend', text)

    def test_m_sorts_processes_and_d_recalculates_du(self):
        os.environ['FAKE_SSH_OUTPUT'] = '4\t/usr'
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term)
        self.press(app, term, b'\r')
        self.press(app, term, b'2')
        self.press(app, term, b'm')
        self.assertEqual(app.sort, 'ram')
        self.press(app, term, b'm')
        self.assertEqual(app.sort, 'cpu')
        self.press(app, term, b'3')
        app.run_for(1.5)
        before = sum('du -x' in line for line in self.ssh_log_lines())
        self.press(app, term, b'd')
        app.run_for(1.5)
        self.assertGreater(sum('du -x' in line for line in self.ssh_log_lines()), before)

    # -- review regressions ------------------------------------------------
    def test_a_vm_never_gets_a_second_action_while_one_runs(self):
        os.environ['FAKE_GCLOUD_SLEEP'] = '3'
        self.seed_cache()
        app, term = self.make_app()
        app.step()
        app._start_action(app._view(API), 'stop')
        others = [inst for inst in all_instances() if inst.alias != API]
        app._set_inventory(PROJECTS, others)              # the VM vanishes from a refresh...
        app._set_inventory(PROJECTS, all_instances())     # ...and comes back as a new view
        self.assertIsNotNone(app._view(API).busy)
        app._start_action(app._view(API), 'reset')
        app.run_for(0.3)
        actions = [line for line in self.gcloud_calls() if 'compute instances' in line
                   and (' stop ' in line or ' reset ' in line)]
        self.assertEqual(len(actions), 1)

    def test_a_refresh_read_before_an_action_ended_is_not_applied(self):
        self.seed_cache()
        app, term = self.make_app()
        app.step()
        app.refreshing = True
        app._refresh_gen = app._action_gen
        app._action_done(API, 'stop', 0, None)            # the action ends mid-refresh
        self.assertTrue(app._refresh_again)
        before = app.loaded_at
        stopped = [inst for inst in all_instances() if inst.alias != API]
        app._refresh_done(PROJECTS, stopped, {})           # the stale answer lands
        self.assertEqual(app.loaded_at, before)
        self.assertIsNotNone(app._view(API))

    def test_probe_follows_a_new_external_ip(self):
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term)
        moved = []
        for inst in all_instances():
            if inst.alias == API:
                inst = Instance(**{**inst.__dict__, 'external_ip': '203.0.113.99'})
            moved.append(inst)
        app._set_inventory(PROJECTS, moved)
        self.assertEqual(app.probes[API].inst.external_ip, '203.0.113.99')

    def test_reopening_the_detail_does_not_pile_up_tab_commands(self):
        os.environ['FAKE_SSH_LINE_DELAY'] = '5'        # every ssh call stays in flight
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term)
        for _ in range(5):
            self.press(app, term, b'\r')
            self.press(app, term, b'\x1b')
        journal = [line for line in self.ssh_log_lines() if 'journalctl' in line]
        # One request: the sudo -n try (the fake refuses it at once) and its plain retry.
        self.assertEqual(sum('sudo -n' in line for line in journal), 1)
        self.assertEqual(sum('sudo -n' not in line for line in journal), 1)

    def test_resize_during_the_intro_snaps_to_the_new_layout(self):
        os.environ['WYSUN_REDUCED_MOTION'] = '0'
        os.environ['FAKE_GCLOUD_SLEEP'] = '3'          # no refresh re-snaps the layout meanwhile
        self.seed_cache()
        app, term = self.make_app()
        app.step()
        term.resize(140, 40)
        app.run_for(1.0)
        rects = app._layout_rects()
        for alias, layer in app._vm_layers.items():
            if alias in rects:
                self.assertEqual(tuple(layer.rect), tuple(rects[alias]))

    def test_monitoring_failure_is_shown_in_historial(self):
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term)
        error = cloudapp.GcloudError('Monitoring respondió 403')
        with mock.patch.object(cloudapp.monitoring, 'cpu_history', side_effect=error):
            self.press(app, term, b'\r')
            self.press(app, term, b'7')
            app.run_for(0.5)
        self.assertIn('Monitoring respondió 403', frame_text(term))

    def test_open_animation_grows_the_card(self):
        os.environ.pop('WYSUN_REDUCED_MOTION', None)
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term, 1.2)
        layer = app._vm_layers[API]
        start = layer.rect.w
        term.feed_input(b'\r')
        app.step()
        widths = []
        for _ in range(10):
            app.step(0.05)
            widths.append(layer.rect.w)
        app.run_for(0.6)
        widths.append(layer.rect.w)
        self.assertEqual(widths, sorted(widths))
        self.assertLess(start, 120)
        self.assertEqual(widths[-1], 120)

    # -- actions ----------------------------------------------------------
    def test_stop_needs_confirmation_and_runs_gcloud(self):
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term)
        self.press(app, term, b'x')
        self.assertIn('¿Apagar api-backend?', frame_text(term))
        self.press(app, term, b'\x1b', 0.08)
        self.assertNotIn('¿Apagar', frame_text(term))
        self.assertFalse([call for call in self.gcloud_calls() if 'compute instances stop' in call])

        self.press(app, term, b'x')
        self.press(app, term, b'\r')
        app.run_for(0.8)
        stops = [call for call in self.gcloud_calls() if 'compute instances stop' in call]
        self.assertTrue(stops)
        self.assertIn(
            'compute instances stop api-backend --zone us-central1-a --project mi-proyecto-prod',
            stops[0],
        )

    def test_failed_action_toast_shows_gcloud_error(self):
        os.environ['FAKE_GCLOUD_FAIL_ACTION'] = '1'
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term)
        self.press(app, term, b'x')
        self.press(app, term, b'\r')
        app.run_for(0.8)
        text = frame_text(term)
        self.assertIn('no se pudo modificar', text)
        self.assertNotIn('Traceback', text)

    def test_start_relayouts_off_line_into_card(self):
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term)
        self.press(app, term, b'\x1b[B')       # worker-1
        self.press(app, term, b'\x1b[B')       # db-old
        self.assertEqual(app.selected, DB)
        self.assertEqual(app._vm_layers[DB].rect.h, 1)

        # After the action, gcloud reports the VM as running (the fakest possible
        # next refresh): the off line must become an 8-row card.
        original = app.gcloud.instances_all

        def instances_all(projects):
            found, messages = original(projects)
            for inst in found:
                if inst.name == 'db-old':
                    inst.status = 'RUNNING'
            return found, messages

        app.gcloud.instances_all = instances_all
        self.press(app, term, b's')
        app.run_for(1.0)
        self.assertTrue(app._view(DB).inst.running)
        self.assertIsNone(app._view(DB).busy)
        self.assertEqual(app._vm_layers[DB].rect.h, 8)
        self.assertTrue([call for call in self.gcloud_calls() if 'compute instances start' in call])

    # -- errors -----------------------------------------------------------
    def test_gcloud_auth_error_shows_message_not_traceback(self):
        os.environ['FAKE_GCLOUD_AUTH_ERROR'] = '1'
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term, 0.6)
        text = frame_text(term)
        self.assertIn('gcloud no tiene sesión: ejecuta gcloud auth login', text)
        self.assertIn('api-backend', text)
        self.assertIn('sin actualizar', text)
        self.assertNotIn('Traceback', text)

    # -- terminal and bar -------------------------------------------------
    def test_ssh_key_launches_terminal(self):
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term)
        calls = {}

        def popen(argv, **kwargs):
            calls['argv'] = argv
            calls['kwargs'] = kwargs
            return SimpleNamespace(pid=1234)

        fake = SimpleNamespace(Popen=popen, DEVNULL=subprocess.DEVNULL)
        with mock.patch.object(cloudapp, 'terminal_argv',
                               lambda command: ['xterm', '-e', *command]), \
                mock.patch.object(cloudapp, 'subprocess', fake):
            self.press(app, term, b'c')
        self.assertEqual(calls['argv'][:2], ['xterm', '-e'])
        self.assertTrue(any('api-backend' in part for part in calls['argv']))
        self.assertTrue(calls['kwargs']['start_new_session'])
        self.assertEqual(calls['kwargs']['stdin'], subprocess.DEVNULL)

    def test_state_file_written_after_refresh(self):
        self.seed_cache()
        app, term = self.make_app()
        app.run_for(0.6)
        path = self.runtime / 'wysun-cloud' / 'state.json'
        self.assertTrue(path.is_file(), path)
        payload = json.loads(path.read_text(encoding='utf-8'))
        self.assertIn('api-backend', [item['name'] for item in payload['running']])
        self.assertEqual(payload['total'], 7)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    # -- layouts ----------------------------------------------------------
    def test_narrow_terminal_shows_selected_card(self):
        self.seed_cache()
        app, term = self.make_app(80, 24)
        self.settle(app, term)
        self.assertEqual(app.selected, API)
        for _ in range(6):
            self.press(app, term, b'\x1b[B')
        self.assertEqual(app.selected, STAGING)
        self.assertIn('staging', frame_text(term))
        self.assertEqual(app._vm_layers[STAGING].visible, True)

    def test_resize_mid_transition_does_not_crash(self):
        os.environ.pop('WYSUN_REDUCED_MOTION', None)
        self.seed_cache()
        app, term = self.make_app()
        self.settle(app, term, 1.2)
        term.feed_input(b'\r')
        app.step()
        app.step(0.06)                 # inside the open tween
        self.assertTrue(app.animator)
        term.resize(70, 20)
        app.step()
        self.assertFalse(app.animator)
        self.assertEqual(app.size, (70, 20))
        self.assertEqual(len(term.canvas_text()), 20)
        self.assertIn('Resumen', frame_text(term))

        term.resize(120, 36)
        app.step()
        self.assertEqual(app.size, (120, 36))
        self.assertEqual(len(term.canvas_text()), 36)
        self.assertIn('Resumen', frame_text(term))
        self.assertEqual(app._vm_layers[API].rect.w, 120)


if __name__ == '__main__':
    unittest.main()
