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
    def test_audio_and_notification_history_generate_actions_only(self):
        import system_panels as panels
        answers={'get-default-sink':'own-sink','get-sink-volume':'Volume: 32768 / 50%', 'sinks':json.dumps([dict(name='own-sink',description='Synthetic sink')]),'status':'{"dnd": true, "count": 0}','history_unused':json.dumps({'data':[[dict(summary={'data':'Own notice'},appname={'data':'Own app'},body={'data':'<b>Fixture</b>'},id={'data':42})]]})}
        def cmd(args):return answers['sinks' if args[-1]=='sinks' else 'status' if args[-1]=='status' else args[1]]
        with patch.object(panels,'cmd',side_effect=cmd):
            scan=panels.StatusScan('audio');audio=[];scan.done.connect(lambda rows,extra:audio.append((rows,extra)));scan.run()
            self.assertEqual(audio[0][1]['volume'],50);self.assertEqual(audio[0][0][1]['action'],['pactl','set-default-sink','own-sink'])
            scan=panels.StatusScan('notifications');notices=[];scan.done.connect(lambda rows,extra:notices.extend(rows));scan.run()
            self.assertEqual(notices[0]['title'],'Reanudar notificaciones');self.assertEqual(notices[0]['action'][1:],['dnd','toggle']);self.assertEqual(len(notices),1)
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

if __name__=='__main__':unittest.main()
