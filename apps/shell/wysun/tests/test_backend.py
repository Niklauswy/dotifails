"""Bounded adapter contracts; all files/commands are synthetic."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'backend.py'
spec=importlib.util.spec_from_file_location('wysun_cael_backend',SOURCE)
backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)

class AdapterTests(unittest.TestCase):
    def test_dunst_history_keeps_real_ids_and_disables_unavailable_actions(self):
        row={k:{'data':v} for k,v in {'id':9,'summary':'Fixture','body':'Texto','urgency':'CRITICAL','appname':'Correo'}.items()}
        with patch.object(backend,'run',return_value=json.dumps({'data':[[row]]})):
            result=backend.history()
        self.assertEqual(result[0]['notificationId'],'9')
        self.assertEqual(result[0]['urgency'],2)
        self.assertEqual(result[0]['actions'],[])
        self.assertFalse(result[0]['popup'])

    def test_apps_do_not_inherit_parallel_qt_environment(self):
        with patch.dict(os.environ,{'LD_LIBRARY_PATH':'sdk','QML_IMPORT_PATH':'sdk','QT_PLUGIN_PATH':'sdk','DISPLAY':':91'}):
            env=backend.environment()
        self.assertNotIn('LD_LIBRARY_PATH',env)
        self.assertNotIn('QML_IMPORT_PATH',env)
        self.assertEqual(env['DISPLAY'],':91')

    def test_invalid_actions_and_ids_never_dispatch(self):
        for argv in [('launch','sh'),('dismiss','9;touch /tmp/no')]:
            result=subprocess.run(['/usr/bin/python3',str(SOURCE),*argv],capture_output=True)
            self.assertEqual(result.returncode,2)

    def test_fixed_schemes_use_the_existing_producer_with_temporary_data(self):
        with tempfile.TemporaryDirectory() as home:
            env=dict(os.environ,HOME=home,XDG_CONFIG_HOME=home+'/config',XDG_STATE_HOME=home+'/state')
            result=subprocess.run(['/usr/bin/python3',str(SOURCE),'schemes'],env=env,capture_output=True,text=True,check=True)
            schemes=json.loads(result.stdout)
            self.assertEqual(set(schemes),{'space-black','tokyo','severance','fluent:light','fluent:dark'})
            self.assertIn('primary',schemes['tokyo']['default'])

if __name__=='__main__':unittest.main()
