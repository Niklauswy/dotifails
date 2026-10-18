import importlib.util,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('local_installer',Path(__file__).resolve().parents[1]/'scripts/install-local.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class InstallerTests(unittest.TestCase):
 def test_reinstall_uninstall_preserves_media_and_changes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'source';(source/'loomrec').mkdir(parents=True)
   (source/'loomrec/__main__.py').write_text('print("fixture")')
   installer=module.Installer(source,root/'data',root/'bin')
   installer.install();installer.install()
   import subprocess
   result=subprocess.check_output([str(installer.path('launcher'))],cwd='/',text=True)
   self.assertEqual(result.strip(),'fixture')
   recordings=root/'data/loomrec/recordings';recordings.mkdir();(recordings/'keep.txt').write_text('private')
   installer.path('desktop').write_text('user changed')
   with self.assertRaises(FileExistsError):installer.install()
   result=installer.uninstall()
   self.assertEqual((recordings/'keep.txt').read_text(),'private')
   self.assertEqual(installer.path('desktop').read_text(),'user changed')
   self.assertEqual(len(result['preserved_modified']),1)
   self.assertFalse(installer.path('launcher').exists())
 def test_unrelated_file_and_manifest_escape_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'source';(source/'loomrec').mkdir(parents=True);(source/'loomrec/__main__.py').write_text('')
   installer=module.Installer(source,root/'data',root/'bin')
   installer.path('launcher').parent.mkdir();installer.path('launcher').write_text('unrelated')
   with self.assertRaises(FileExistsError):installer.install()
   self.assertEqual(installer.path('launcher').read_text(),'unrelated')
   with self.assertRaises(ValueError):installer.path('app/../../private')

 def test_uninstall_removes_only_managed_shortcut_and_preserves_settings(self):
  from unittest.mock import patch
  import subprocess
  shortcut_spec=importlib.util.spec_from_file_location('shortcut_fixture',Path(__file__).resolve().parents[1]/'scripts/desktop-shortcut.py')
  shortcut=importlib.util.module_from_spec(shortcut_spec);shortcut_spec.loader.exec_module(shortcut)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'source';(source/'loomrec').mkdir(parents=True);(source/'loomrec/__main__.py').write_text('')
   installer=module.Installer(source,root/'data',root/'bin');installer.install()
   settings=installer.base/'settings.json';settings.write_text('{"keep":true}')
   config=root/'sxhkdrc';config.write_text('# original user binding\n')
   shortcut.install(config,installer.base/'shortcut.json',installer.path('launcher'))
   with patch('subprocess.run',return_value=subprocess.CompletedProcess([],1,stdout='',stderr='')):
    result=installer.uninstall()
   self.assertEqual(config.read_text(),'# original user binding\n')
   self.assertEqual(settings.read_text(),'{"keep":true}')
   self.assertTrue(result['shortcut']['removed'])

 def test_versioned_upgrade_preserves_old_process_bundle_and_media(self):
  from unittest.mock import patch
  import subprocess
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'source';(source/'loomrec').mkdir(parents=True)
   main=source/'loomrec/__main__.py';main.write_text('print("old")')
   installer=module.Installer(source,root/'data',root/'bin');installer.install()
   old=next((installer.base/'bundles').iterdir());before=(old/'loomrec/__main__.py').read_bytes()
   media=installer.base/'recordings';media.mkdir();(media/'keep').write_text('keep')
   main.write_text('print("new")');installer.install()
   self.assertEqual((old/'loomrec/__main__.py').read_bytes(),before)
   self.assertEqual(subprocess.check_output([str(installer.path('launcher'))],cwd='/',text=True).strip(),'new')
   with patch.object(module,'active_bundle_paths',return_value={old}):
    installer.install();result=installer.uninstall()
   self.assertTrue(result['preserved_active_files']);self.assertEqual((old/'loomrec/__main__.py').read_bytes(),before)
   self.assertEqual((media/'keep').read_text(),'keep');self.assertFalse(installer.path('launcher').exists())
   with patch.object(module,'active_bundle_paths',return_value=set()):installer.uninstall()
   self.assertFalse((old/'loomrec/__main__.py').exists())
