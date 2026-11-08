"""Automatic power-off: rules, conf, scripts, what the VM reports and the guard itself."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_cloud import autostop, ssh  # noqa: E402
from wysun_cloud.autostop import Live, Once, Rules  # noqa: E402

GUARD = ROOT / 'apps/python/wysun_cloud/autostop_guard.sh'
TZ = 'America/Tijuana'


def at(text, tz=TZ):
    """Epoch of ``YYYY-MM-DD HH:MM`` in ``tz``."""
    return int(datetime.strptime(text, '%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo(tz)).timestamp())


class RulesTests(unittest.TestCase):
    def test_round_trip(self):
        rules = Rules(schedule_at='02:00', days='12345', tz=TZ, schedule_from=100, max_hours=8,
                      max_from=200, idle_minutes=30, idle_cpu=5, idle_ssh=False,
                      idle_procs=('claude', 'codex'), warn_minutes=3)
        self.assertEqual(autostop.parse_conf(autostop.render_conf(rules)), rules)

    def test_render_refuses_what_root_could_misread(self):
        bad = [Rules(schedule_at='25:00'), Rules(schedule_at='02:00; reboot'),
               Rules(tz='UTC; rm -rf /'), Rules(tz='$(id)'), Rules(days='18'),
               Rules(idle_procs=('claude;id',)), Rules(idle_procs=('a b',)),
               Rules(idle_procs=('x"y',)), Rules(max_hours=-1)]
        for rules in bad:
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                autostop.render_conf(rules)

    def test_parse_turns_invalid_values_off(self):
        rules = autostop.parse_conf('SCHEDULE_AT=99:99\nMAX_HOURS=abc\nIDLE_MINUTES=20\n'
                                    'IDLE_PROCS="ok bad;name"\nSCHEDULE_TZ=$(id)\n')
        self.assertIsNone(rules.schedule_at)
        self.assertEqual(rules.max_hours, 0)
        self.assertEqual(rules.idle_minutes, 20)
        self.assertEqual(rules.idle_procs, ('ok',))
        self.assertEqual(rules.tz, 'UTC')
        self.assertFalse(Rules().any)
        self.assertTrue(rules.any)

    def test_stamp_counts_a_rule_from_when_it_changed(self):
        old = Rules(schedule_at='02:00', schedule_from=10, max_hours=4, max_from=20)
        same = autostop.stamp(Rules(schedule_at='02:00', max_hours=4, idle_minutes=30), old, 999)
        self.assertEqual((same.schedule_from, same.max_from), (10, 20))
        changed = autostop.stamp(Rules(schedule_at='03:00', max_hours=6), old, 999)
        self.assertEqual((changed.schedule_from, changed.max_from), (999, 999))
        off = autostop.stamp(Rules(), old, 999)
        self.assertEqual((off.schedule_from, off.max_from), (0, 0))
        fresh = autostop.stamp(Rules(max_hours=2), None, 5)
        self.assertEqual(fresh.max_from, 5)


class ReportTests(unittest.TestCase):
    def test_parse_live(self):
        self.assertEqual(autostop.parse_live('1 1794218400 schedule 0 proc:claude 0'),
                         Live(True, 1794218400, 'schedule', 0, 'proc:claude', 0))
        self.assertEqual(autostop.parse_live('0 0 - 0 - 1794159729'),
                         Live(False, 0, '', 0, '', 1794159729))
        self.assertIsNone(autostop.parse_live('garbage'))
        self.assertIsNone(autostop.parse_live(None))

    def test_parse_status(self):
        lines = ['SCHEDULE_AT=02:00', 'SCHEDULE_DAYS=12345', f'SCHEDULE_TZ={TZ}', 'IDLE_MINUTES=30',
                 '@@state', 'CHECKED=100', 'NEXT_AT=200', 'NEXT_REASON=schedule', 'IDLE_SINCE=0',
                 'BUSY=cpu', 'CPU=42', '@@postpone', '300', '@@once',
                 'USEC=1794159729869332', 'WARN_WALL=1', 'MODE=poweroff', '@@timer', 'active']
        status = autostop.parse_status(lines)
        self.assertTrue(status.installed and status.active)
        self.assertEqual(status.rules.schedule_at, '02:00')
        self.assertEqual((status.next_at, status.reason, status.busy, status.cpu), (200, 'schedule', 'cpu', 42))
        self.assertEqual(status.postpone, 300)
        self.assertEqual(status.once_at, 1794159729)

    def test_a_scheduled_reboot_is_not_a_power_off(self):
        status = autostop.parse_status(['@@once', 'USEC=1794159729000000', 'MODE=reboot', '@@timer', 'inactive'])
        self.assertEqual(status.once_at, 0)
        self.assertFalse(status.installed)

    def test_next_stop_is_the_soonest_still_ahead(self):
        live = Live(True, 2000, 'idle', 1000, '', 1500)
        self.assertEqual(autostop.next_stop(live, 1000), (1500, 'once'))
        self.assertEqual(autostop.next_stop(Live(True, 2000, 'max', 0, '', 0), 1000), (2000, 'max'))
        self.assertIsNone(autostop.next_stop(Live(True, 100, 'max', 0, '', 0), 1000))
        self.assertIsNone(autostop.next_stop(Live(False, 2000, 'max', 0, '', 0), 1000))

    def test_probe_line_carries_the_auto_field(self):
        parser = ssh.ProbeParser()
        base = ('cpu=200 0 100 1700 0 0 0 0 cores=1000,850 load=1 0.5 0.2 mem=16384000 8192000 2048000 0 0 '
                'net=1 1 disk=1 1 df=/:1:2 up=60 auto=1 1794218400 schedule 0 cpu 0 top=1:0.5:100:sh')
        self.assertIsNone(parser.feed('S 1 ' + base))
        sample = parser.feed('S 2 ' + base.replace('up=60', 'up=61'))
        self.assertEqual(sample.autostop, Live(True, 1794218400, 'schedule', 0, 'cpu', 0))
        self.assertEqual(sample.top[0][3], 'sh')
        old = ssh.ProbeParser()
        line = base.replace(' auto=1 1794218400 schedule 0 cpu 0', '')
        old.feed('S 1 ' + line)
        self.assertIsNone(old.feed('S 2 ' + line).autostop)


class ScriptTests(unittest.TestCase):
    def test_apply_installs_guard_units_and_conf(self):
        script = autostop.apply_script(Rules(schedule_at='02:00', tz=TZ), Once('set', 90), guard='echo guard\n')
        self.assertIn("cat > /usr/local/libexec/wysun-autostop.tmp <<'WYSUN_GUARD_EOF'", script)
        self.assertIn('SCHEDULE_AT=02:00', script)
        self.assertIn('systemctl restart wysun-autostop.timer', script)
        self.assertIn("shutdown -h +90 'Wysun Cloud: apagado programado'", script)
        self.assertTrue(script.rstrip().endswith('echo WYSUN_AUTOSTOP_OK'))
        subprocess.run(['sh', '-n'], input=script, text=True, check=True)

    def test_no_rule_left_uninstalls(self):
        script = autostop.apply_script(Rules(), Once('cancel'))
        self.assertIn('systemctl disable --now wysun-autostop.timer', script)
        self.assertIn('rm -rf /var/lib/wysun-autostop', script)
        self.assertIn('shutdown -c', script)
        self.assertNotIn('WYSUN_GUARD_EOF', script)
        subprocess.run(['sh', '-n'], input=script, text=True, check=True)

    def test_keep_leaves_the_one_off_alone(self):
        script = autostop.apply_script(Rules(max_hours=2), Once('keep'), guard='true\n')
        self.assertNotIn('shutdown', script)

    def test_heredoc_marker_inside_content_is_refused(self):
        with self.assertRaises(ValueError):
            autostop.apply_script(Rules(max_hours=1), guard='x\nWYSUN_GUARD_EOF\ny\n')

    def test_real_guard_is_valid_sh(self):
        subprocess.run(['sh', '-n', str(GUARD)], check=True)
        script = autostop.apply_script(Rules(idle_minutes=30))
        subprocess.run(['sh', '-n'], input=script, text=True, check=True)

    def test_postpone(self):
        script = autostop.postpone_script(5000, once_minutes=75)
        self.assertIn('echo 5000 > /var/lib/wysun-autostop/postpone.tmp', script)
        self.assertIn('shutdown -h +75', script)
        subprocess.run(['sh', '-n'], input=script, text=True, check=True)


class TextTests(unittest.TestCase):
    def test_durations(self):
        self.assertEqual(autostop.fmt_duration(30), 'menos de 1 min')
        self.assertEqual(autostop.fmt_duration(35 * 60), '35 min')
        self.assertEqual(autostop.fmt_duration(4 * 3600 + 12 * 60), '4 h 12 min')
        self.assertEqual(autostop.fmt_duration(3 * 3600), '3 h')
        self.assertEqual(autostop.fmt_duration(51 * 3600), '2 d 3 h')

    def test_when(self):
        now = datetime(2026, 11, 8, 12, 0).timestamp()
        self.assertEqual(autostop.fmt_when(datetime(2026, 11, 8, 17, 42).timestamp(), now), '17:42')
        self.assertEqual(autostop.fmt_when(datetime(2026, 11, 9, 2, 0).timestamp(), now), 'mañana 02:00')
        self.assertEqual(autostop.fmt_when(datetime(2026, 11, 11, 2, 0).timestamp(), now), 'mié 02:00')
        self.assertEqual(autostop.fmt_when(datetime(2026, 11, 20, 2, 0).timestamp(), now), '20 nov 02:00')

    def test_days(self):
        self.assertEqual(autostop.describe_days('1234567'), 'todos los días')
        self.assertEqual(autostop.describe_days('12345'), 'de lunes a viernes')
        self.assertEqual(autostop.describe_days('135'), 'lun, mié y vie')
        self.assertEqual(autostop.describe_days('7'), 'solo dom')

    def test_step(self):
        self.assertEqual(autostop.step(autostop.IDLE_STEPS, 30, 1), 45)
        self.assertEqual(autostop.step(autostop.IDLE_STEPS, 10, -1), 10)
        self.assertEqual(autostop.step(autostop.IDLE_STEPS, 33, 1), 45)
        self.assertEqual(autostop.step(autostop.IDLE_STEPS, 33, -1), 30)


class EditorTests(unittest.TestCase):
    """The editor's rows and values, without a terminal."""

    def setUp(self):
        from types import SimpleNamespace
        from wysun_cloud.model import Instance
        from wysun_cloud.ui.autostop_editor import Editor

        def view(name, running=True):
            inst = Instance(project='p', name=name, zone='z', status='RUNNING' if running else 'TERMINATED',
                            machine_type='e2', external_ip=None, internal_ip=None, spot=False, os='',
                            disks=[], network='n', tags=[], started=None)
            return SimpleNamespace(inst=inst)

        self.views = [view('a'), view('b'), view('c', running=False)]
        self.Key = lambda name, char=None: SimpleNamespace(name=name, char=char)
        status = autostop.parse_status(['SCHEDULE_AT=02:00', 'SCHEDULE_DAYS=12345', '@@timer', 'active'])
        self.editor = Editor(self.views, self.views[0].inst.alias, status, now=0)

    def key(self, name, char=None):
        return self.editor.key(self.Key(name, char))

    def test_rows_follow_the_switches(self):
        self.assertEqual(self.editor.rows(), ['schedule', 'days', 'max', 'idle', 'once', 'target'])
        self.editor.row = 3
        self.key('char', ' ')
        self.assertEqual(self.editor.rows(), ['schedule', 'days', 'max', 'idle', 'idle_cpu', 'idle_ssh',
                                              'once', 'target'])

    def test_time_steps_and_wraps(self):
        self.key('left')
        self.assertEqual(self.editor.at, '01:45')
        self.key('pageup')
        self.assertEqual(self.editor.at, '02:45')
        self.editor.at = '23:45'
        self.key('right')
        self.assertEqual(self.editor.at, '00:00')

    def test_days_presets_and_single_days_never_empty(self):
        self.editor.row = 1
        self.key('right')
        self.assertEqual(self.editor.days, '67')
        self.key('char', '6')
        self.assertEqual(self.editor.days, '7')
        self.key('char', '7')
        self.assertEqual(self.editor.days, '7')

    def test_once_is_kept_until_touched(self):
        self.assertEqual(self.editor.once(), Once('keep'))
        self.editor.row = 4
        self.key('char', ' ')
        self.assertEqual(self.editor.once(), Once('set', 60))
        self.key('char', ' ')
        self.assertEqual(self.editor.once(), Once('cancel'))

    def test_targets(self):
        self.editor.row = 5
        self.assertEqual(self.editor.targets(), ['a.z.p'])
        self.key('right')
        self.assertEqual(self.editor.targets(), ['a.z.p', 'b.z.p'])      # running only
        self.key('right')
        self.assertEqual(self.editor.rows()[-2:], ['vm:a.z.p', 'vm:b.z.p'])
        self.editor.row = len(self.editor.rows()) - 1
        self.key('char', ' ')
        self.assertEqual(self.editor.targets(), ['a.z.p', 'b.z.p'])
        self.editor.row -= 1
        self.key('char', ' ')
        self.key('char', ' ')
        self.editor.row += 1
        self.key('char', ' ')
        self.assertEqual(self.editor.targets(), ['a.z.p'])
        self.assertEqual(self.key('escape'), 'cancel')
        self.assertEqual(self.key('enter'), 'save')

    def test_rules_carry_the_values(self):
        rules = self.editor.rules(tz='UTC')
        self.assertEqual((rules.schedule_at, rules.days, rules.max_hours, rules.idle_minutes),
                         ('02:00', '12345', 0, 0))


@unittest.skipUnless(shutil.which('date') and subprocess.run(['date', '-d', '@0'], capture_output=True).returncode == 0,
                     'needs GNU date')
class GuardTests(unittest.TestCase):
    """The real guard script, with a fake clock, CPU counters, sessions and processes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.conf = self.dir / 'conf'
        self.stat = self.dir / 'stat'
        self.state_dir = self.dir / 'state'
        self.set_cpu(100, 800)

    def set_cpu(self, busy, idle):
        self.stat.write_text(f'cpu  {busy} 0 0 {idle} 0 0 0 0\n', encoding='utf-8')

    def write(self, rules):
        self.conf.write_text(autostop.render_conf(rules), encoding='utf-8')

    def run_guard(self, now, uptime, sessions=0, running=''):
        env = dict(os.environ, WYSUN_AUTOSTOP_CONF=str(self.conf), WYSUN_AUTOSTOP_DIR=str(self.state_dir),
                   WYSUN_AUTOSTOP_STAT=str(self.stat), WYSUN_AUTOSTOP_NOW=str(now),
                   WYSUN_AUTOSTOP_UPTIME=str(uptime), WYSUN_AUTOSTOP_SESSIONS=str(sessions),
                   WYSUN_AUTOSTOP_RUNNING=running, WYSUN_AUTOSTOP_DRY='1')
        result = subprocess.run(['sh', str(GUARD)], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def state(self):
        text = (self.state_dir / 'state').read_text(encoding='utf-8')
        return dict(line.split('=', 1) for line in text.splitlines())

    def test_schedule_matches_python_and_powers_off_on_time(self):
        rules = Rules(schedule_at='02:00', days='12345', tz=TZ)
        self.write(rules)
        now = at('2026-11-08 12:00')                     # a Sunday
        self.assertEqual(self.run_guard(now, 3600), '')
        expected = at('2026-11-09 02:00')
        self.assertEqual(int(self.state()['NEXT_AT']), expected)
        self.assertEqual(autostop.next_schedule(rules, now - 3600), expected)
        self.assertEqual(self.run_guard(expected, 99999), 'poweroff schedule')

    def test_starting_after_the_time_waits_for_the_next_day(self):
        rules = Rules(schedule_at='02:00', days='1234567', tz=TZ)
        self.write(rules)
        now = at('2026-11-09 03:00')
        self.assertEqual(self.run_guard(now, 600), '')
        self.assertEqual(int(self.state()['NEXT_AT']), at('2026-11-10 02:00'))

    def test_saving_the_rule_late_does_not_power_off_on_the_spot(self):
        now = at('2026-11-08 12:00')
        rules = autostop.stamp(Rules(schedule_at='02:00', tz=TZ, max_hours=2), None, now)
        self.write(rules)
        self.assertEqual(self.run_guard(now, 10 * 3600), '')     # up 10 h, both rules just saved
        self.assertEqual(self.state()['NEXT_REASON'], 'max')
        self.assertEqual(int(self.state()['NEXT_AT']), now + 2 * 3600)

    def test_daylight_saving_night_is_skipped_like_python(self):
        rules = Rules(schedule_at='02:30', days='1234567', tz=TZ)
        self.write(rules)
        now = at('2026-03-07 12:00')
        self.run_guard(now, 100)
        self.assertEqual(int(self.state()['NEXT_AT']), autostop.next_schedule(rules, now - 100))
        self.assertEqual(int(self.state()['NEXT_AT']), at('2026-03-09 02:30'))

    def test_max_hours_warns_once_then_powers_off(self):
        self.write(Rules(max_hours=2, warn_minutes=5))
        now = at('2026-11-08 12:00')
        self.assertEqual(self.run_guard(now, 3600), '')
        deadline = now + 3600
        self.assertEqual(self.run_guard(deadline - 240, 3600 + 3360), f'warn {deadline}')
        self.assertEqual(self.run_guard(deadline - 180, 3600 + 3420), '')
        self.assertEqual(self.run_guard(deadline, 7200), 'poweroff max')

    def test_idle_needs_quiet_checks_and_counts_from_the_first_quiet_window(self):
        self.write(Rules(idle_minutes=10, idle_cpu=10, idle_procs=('claude',)))
        now = at('2026-11-08 12:00')
        self.run_guard(now, 9999)                         # first check: unknown CPU = busy
        self.assertEqual(self.state()['BUSY'], 'cpu')
        self.set_cpu(101, 1800)
        self.run_guard(now + 60, 9999)
        self.assertEqual(int(self.state()['IDLE_SINCE']), now)
        self.assertEqual(int(self.state()['NEXT_AT']), now + 600)
        self.set_cpu(102, 2800)
        self.assertEqual(self.run_guard(now + 600, 9999), 'poweroff idle')

    def test_cpu_ssh_and_processes_count_as_use(self):
        self.write(Rules(idle_minutes=10, idle_cpu=10, idle_ssh=True, idle_procs=('claude', 'codex')))
        now = at('2026-11-08 12:00')
        self.run_guard(now, 9999)
        self.set_cpu(600, 1300)                           # 50 % busy
        self.run_guard(now + 60, 9999)
        self.assertEqual(self.state()['BUSY'], 'cpu')
        self.set_cpu(601, 2300)
        self.run_guard(now + 120, 9999, sessions=1)
        self.assertEqual(self.state()['BUSY'], 'ssh')
        self.set_cpu(602, 3300)
        self.run_guard(now + 180, 9999, running='codex')
        self.assertEqual(self.state()['BUSY'], 'proc:codex')
        self.assertEqual(self.state()['NEXT_AT'], '0')
        self.set_cpu(603, 4300)
        self.run_guard(now + 240, 9999)
        self.assertEqual(self.state()['BUSY'], '')
        self.assertEqual(int(self.state()['IDLE_SINCE']), now + 180)

    def test_ssh_does_not_count_when_turned_off(self):
        self.write(Rules(idle_minutes=10, idle_ssh=False, idle_procs=()))
        now = at('2026-11-08 12:00')
        self.run_guard(now, 9999)
        self.set_cpu(101, 1800)
        self.run_guard(now + 60, 9999, sessions=3)
        self.assertEqual(self.state()['BUSY'], '')

    def test_postpone_delays_the_power_off(self):
        self.write(Rules(max_hours=1))
        now = at('2026-11-08 12:00')
        self.state_dir.mkdir()
        (self.state_dir / 'postpone').write_text(str(now + 7200), encoding='utf-8')
        self.assertEqual(self.run_guard(now + 3600, 3600), '')
        self.assertEqual(int(self.state()['NEXT_AT']), now + 7200)
        self.assertEqual(self.run_guard(now + 7200, 7200), 'poweroff max')


if __name__ == '__main__':
    unittest.main()
