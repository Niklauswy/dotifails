"""Bounded adapter contracts; all files/commands are synthetic."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[2]/'apps/shell/wysun/backend.py'
spec=importlib.util.spec_from_file_location('wysun_cael_backend',SOURCE)
backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)

class AdapterTests(unittest.TestCase):
    def test_apps_do_not_inherit_parallel_qt_environment(self):
        with patch.dict(os.environ,{'LD_LIBRARY_PATH':'sdk','QML_IMPORT_PATH':'sdk','QT_PLUGIN_PATH':'sdk','DISPLAY':':91'}):
            env=backend.environment()
        self.assertNotIn('LD_LIBRARY_PATH',env)
        self.assertNotIn('QML_IMPORT_PATH',env)
        self.assertEqual(env['DISPLAY'],':91')

    def test_invalid_actions_and_ids_never_dispatch(self):
        for argv in [('launch','sh'),('history',),('dnd',)]:
            result=subprocess.run(['/usr/bin/python3',str(SOURCE),*argv],capture_output=True)
            self.assertEqual(result.returncode,2)

    def test_the_retired_scheme_listings_are_gone(self):
        for action in ('schemes','current'):
            result=subprocess.run(['/usr/bin/python3',str(SOURCE),action],capture_output=True)
            self.assertEqual(result.returncode,2,action)

    def test_preview_uses_the_existing_producer_and_the_stored_mode(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as home:
            image=Path(home,'bright.png');Image.new('RGB',(32,32),(245,240,225)).save(image)
            env=dict(os.environ,HOME=home,XDG_CONFIG_HOME=home+'/config',XDG_STATE_HOME=home+'/state')
            for key in ('WYSUN_THEME','ORBIT_THEME'):env.pop(key,None)
            def preview():
                result=subprocess.run(['/usr/bin/python3',str(SOURCE),'preview',str(image)],env=env,capture_output=True,text=True,check=True)
                return json.loads(result.stdout)
            scheme=preview()
            self.assertEqual((scheme['name'],scheme['mode']),('dynamic','light'),'auto: a bright wallpaper previews light')
            self.assertIn('primary',scheme['colours'])
            Path(home,'config/orbit').mkdir(parents=True);Path(home,'config/orbit/theme.json').write_text('{"mode":"dark"}')
            self.assertEqual(preview()['mode'],'dark')
            self.assertFalse(Path(home,'state').exists(),'a preview never writes the scheme')

if __name__=='__main__':unittest.main()
