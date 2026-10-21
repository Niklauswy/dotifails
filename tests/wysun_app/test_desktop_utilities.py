import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QImage,QColor,QIcon,QKeyEvent
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
from connections_data import ssh_hosts,SSHProfiles,ssh_args,ConnectionScan
from desktop_common import vim_args,is_text_file
from data_v2 import StoreV2
from media import png_bytes
from orbit import STYLE

def wait(ms):
    until=time.monotonic()+ms/1000
    while time.monotonic()<until:QApplication.processEvents();time.sleep(.005)

class IntegrationDataTests(unittest.TestCase):
    def test_ssh_includes_profiles_and_option_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'more').write_text('Host staging\n HostName staging.local\n User deploy\n Port 2222\n');(root/'config').write_text('Include more\nHost prod\n HostName prod.local\nMatch exec "touch /tmp/never-execute-orbit"\n User wrong\nHost *\n User shared\n')
            rows=ssh_hosts(root/'config');self.assertEqual([r['alias'] for r in rows],['staging','prod']);self.assertEqual(rows[0]['user'],'deploy');self.assertEqual(rows[1]['user'],'');self.assertNotIn('wrong',str(rows))
            store=SSHProfiles(root/'ssh.json');store.save({'name':'Local','host':'localhost','user':'nicolas','port':2222});self.assertEqual(store.saved()[0]['port'],2222);self.assertEqual((root/'ssh.json').stat().st_mode&0o777,0o600)
            with self.assertRaises(ValueError):store.save({'name':'Bad','host':'-oProxyCommand=bad','port':22})
            with patch('connections_data.terminal_args',side_effect=lambda args,title:args):args=ssh_args(store.saved()[0]);self.assertEqual(args,['ssh','-p','2222','-l','nicolas','--','localhost'])
    def test_vim_paths_are_separate_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'space $(unsafe).py';path.write_text('print("hello")');args=vim_args(path);self.assertEqual(args[-2:],['--',str(path)]);self.assertTrue(is_text_file(path));binary=Path(tmp)/'binary';binary.write_bytes(b'a\0b');self.assertFalse(is_text_file(binary))

