import configparser,importlib.util,tempfile,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if not (root/'installer/main.py').is_file():root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('file_integration_installer',root/'installer/main.py');module=importlib.util.module_from_spec(spec)
# The staging directory can use the unchanged installer helpers from the checkout.
import sys
if not (root/'installer/install_model.py').exists():sys.path.insert(0,str(Path.home()/'dotifails/installer'))
spec.loader.exec_module(module)
class FileIntegrationInstallerTests(unittest.TestCase):
 def test_clean_home_defaults_and_dependencies(self):
  import json
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);d=module.Deployment(home,root);d.begin()
   try:d.configure_files();d.finish()
   finally:d.lock.close()
   parser=configparser.ConfigParser();parser.read(home/'.config/mimeapps.list')
   self.assertEqual(parser['Default Applications']['inode/directory'],'orbit-files.desktop;')
   self.assertIn('orbit-files.desktop',parser['Added Associations']['inode/directory'])
   import os,subprocess
   env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(home/'.config'),XDG_DATA_HOME=str(home/'.local/share'),XDG_CURRENT_DESKTOP='bspwm',PATH=str(home/'.local/bin')+':/usr/bin:/bin')
   self.assertEqual(subprocess.check_output(['xdg-mime','query','default','inode/directory'],env=env,text=True).strip(),'orbit-files.desktop')
   self.assertTrue((home/'.local/share/applications/orbit-files.desktop').is_file())
   portal=configparser.ConfigParser();portal.read(home/'.config/xdg-desktop-portal/portals.conf')
   self.assertEqual(portal['preferred']['org.freedesktop.impl.portal.FileChooser'],'orbit;gtk;')
  packages=json.loads((root/'manifests/packages.json').read_text())['components']['desktop']
  self.assertTrue({'xdg-desktop-portal','xdg-desktop-portal-gtk','libglib2.0-bin'}.issubset(packages))
 def test_default_keeps_other_mime_preferences(self):
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);mime=home/'.config/mimeapps.list';mime.parent.mkdir(parents=True)
   mime.write_text('[Default Applications]\napplication/pdf=reader.desktop;\ninode/directory=old-files.desktop;\n[Added Associations]\ninode/directory=old-files.desktop;\n[Removed Associations]\ninode/directory=orbit-files.desktop;other.desktop;\n')
   d=module.Deployment(home,root);d.begin()
   try:d.configure_files();d.finish()
   finally:d.lock.close()
   parser=configparser.ConfigParser();parser.read(mime)
   self.assertEqual(parser['Default Applications']['application/pdf'],'reader.desktop;')
   self.assertEqual(parser['Default Applications']['inode/directory'],'orbit-files.desktop;')
   self.assertIn('old-files.desktop',parser['Added Associations']['inode/directory'])
   self.assertEqual(parser['Removed Associations']['inode/directory'],'other.desktop;')
 def test_registration_preserves_other_portals_and_is_idempotent(self):
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);config=home/'.config/xdg-desktop-portal/portals.conf';config.parent.mkdir(parents=True)
   config.write_text('[preferred]\ndefault=gtk;\norg.freedesktop.impl.portal.ScreenCast=gnome;\n')
   (home/'.xsessionrc').write_text('export KEEP_ME=1\n')
   for i in range(2):
    d=module.Deployment(home,root);d.begin()
    try:
     d.configure_files();d.finish()
     if i:self.assertEqual(d.journal['operations'],[])
    finally:d.lock.close()
   parser=configparser.ConfigParser();parser.read(config)
   self.assertEqual(parser['preferred']['org.freedesktop.impl.portal.ScreenCast'],'gnome;')
   self.assertEqual(parser['preferred']['org.freedesktop.impl.portal.FileChooser'],'orbit;gtk;')
   self.assertIn('export KEEP_ME=1',(home/'.xsessionrc').read_text())
   self.assertEqual((home/'.xsessionrc').read_text().count('export GTK_USE_PORTAL=1'),1)
   self.assertIn('org.freedesktop.FileManager1',(home/'.local/share/dbus-1/services/org.freedesktop.FileManager1.service').read_text())
   self.assertTrue((home/'.local/share/xdg-desktop-portal/portals/orbit.portal').is_file())
if __name__=='__main__':unittest.main()
