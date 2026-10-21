"""Service fixtures only; every host CLI/DBus response is replaced."""
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))

class PreservedServicesTests(unittest.TestCase):
    def test_ssh_include_profiles_and_argv_never_execute_match(self):
        import ssh_profiles as data
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'config';(root/'hosts').mkdir();(root/'hosts/own').write_text('Host own-fixture\n HostName 192.0.2.1\n User fixture\n Port 2222\nMatch exec "SHOULD NEVER EXECUTE"\n')
            config.write_text('Include hosts/*\nHost * !skip\n')
            with patch.object(data,'terminal_args',side_effect=lambda args,title:args):
                rows=data.ssh_hosts(config);self.assertEqual(len(rows),1);self.assertEqual(data.ssh_args(rows[0]),['ssh','--','own-fixture'])
                profiles=data.SSHProfiles(root/'ssh.json');profiles.save(dict(name='Own',host='192.0.2.2',user='fixture',port=2222));saved=profiles.saved()[0]
                self.assertEqual(data.ssh_args(saved),['ssh','-p','2222','-l','fixture','--','192.0.2.2'])
                with self.assertRaises(ValueError):data.ssh_args(dict(saved,host='--bad'))
    def test_audio_and_notification_history_generate_actions_only(self):
        import system_panels as panels
        answers={'get-default-sink':'own-sink','get-sink-volume':'Volume: 32768 / 50%', 'sinks':json.dumps([dict(name='own-sink',description='Synthetic sink')]),'is-paused':'true','history':json.dumps({'data':[[dict(summary={'data':'Own notice'},appname={'data':'Own app'},body={'data':'<b>Fixture</b>'},id={'data':42})]]})}
        def cmd(args):return answers['sinks' if args[-1]=='sinks' else args[1]]
        with patch.object(panels,'cmd',side_effect=cmd):
            scan=panels.StatusScan('audio');audio=[];scan.done.connect(lambda rows,extra:audio.append((rows,extra)));scan.run()
            self.assertEqual(audio[0][1]['volume'],50);self.assertEqual(audio[0][0][1]['action'],['pactl','set-default-sink','own-sink'])
            scan=panels.StatusScan('notifications');notices=[];scan.done.connect(lambda rows,extra:notices.extend(rows));scan.run()
            self.assertEqual(notices[0]['title'],'Reanudar notificaciones');self.assertEqual(notices[1]['detail'],'Fixture');self.assertEqual(notices[1]['action'],['dunstctl','history-pop','42'])
    def test_battery_and_resource_values_from_temporary_files(self):
        import system_panels as panels
        from energy_data import battery_snapshot
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);battery=root/'sys/BAT-fixture';battery.mkdir(parents=True)
            for key,value in dict(type='Battery',capacity='42',status='Discharging',energy_now='21000000',energy_full='42000000',energy_full_design='50000000',power_now='7000000',cycle_count='12').items():(battery/key).write_text(value)
            state=battery_snapshot(root/'sys');self.assertEqual(state['hours'],3);self.assertEqual(state['health'],84);self.assertEqual(state['capacity'],42)
            proc=root/'proc';proc.mkdir();(proc/'meminfo').write_text('MemTotal: 8388608 kB\nMemAvailable: 4194304 kB\n');(proc/'uptime').write_text('7200 0')
            original=Path
            def path(value):return root/'proc'/str(value).split('/')[-1] if str(value).startswith('/proc/') else root/'sys' if str(value)=='/sys/class/power_supply' else original(value)
            disk=types.SimpleNamespace(free=2**30,used=2**30,total=2**31);scan=panels.StatusScan('system');rows=[];scan.done.connect(lambda items,extra:rows.extend(items))
            with patch.object(panels,'Path') as paths,patch.object(panels.os,'getloadavg',return_value=(.1,.2,.3)),patch('shutil.disk_usage',return_value=disk):
                paths.side_effect=path;paths.home.return_value=root;scan.run()
            self.assertEqual(len(rows),5);self.assertEqual(rows[0]['subtitle'],'4.0 / 8.0 GB');self.assertIn('42%',rows[3]['subtitle'])
    def test_suspend_routes_only_through_lock_acquire_wrapper(self):
        from enhanced import OrbitV2
        owner=Mock()
        with patch.dict(os.environ,{'WAYLAND_DISPLAY':'fixture'}),patch('screen_lock.start_lock',return_value=True) as lock,patch('enhanced.run') as run:
            self.assertTrue(OrbitV2.power_action(owner,{'action':'suspend'}));lock.assert_called_once_with(owner,suspend=True);run.assert_not_called()

if __name__=='__main__':unittest.main()
