import importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('installer',Path(__file__).parents[1]/'installer/main.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class InstallerTests(unittest.TestCase):
 def test_mise_shim_keeps_command_name(self):
  import subprocess,tarfile
  bundle=self.root/'bundle';(bundle/'mise/bin').mkdir(parents=True)
  binary=bundle/'mise/bin/mise';binary.write_text('#!/bin/sh\nprintf "%s\\n" "${0##*/}"\n');binary.chmod(0o755)
  archive=self.root/'mise.tar'
  with tarfile.open(archive,'w') as tar:tar.add(bundle/'mise',arcname='mise')
  (self.source/'manifests').mkdir();(self.source/'manifests/artifacts.json').write_text(json.dumps({'mise':{'version':'test','sha256':'a'*64,'kind':'tar'}}))
  d=self.deploy()
  try:
   with patch.object(m,'fetch',return_value=archive):m.install_tools(d)
   shim=self.home/'node';shim.symlink_to(self.home/'.local/bin/mise')
   self.assertEqual(subprocess.check_output([str(shim)],text=True).strip(),'node')
  finally:d.lock.close()
 def test_orbit_only_preserves_other_configs_and_private_data(self):
  source=Path(__file__).parents[1]
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);nvim=home/'.config/nvim/init.lua';nvim.parent.mkdir(parents=True);nvim.write_text('my editor')
   note=home/'.local/share/orbit/notes/private.md';note.parent.mkdir(parents=True);note.write_text('private')
   self.assertEqual(m.main(['install','--source',str(source),'--target-home',tmp,'--orbit-only']),0)
   self.assertEqual(nvim.read_text(),'my editor');self.assertEqual(note.read_text(),'private');self.assertTrue((home/'.local/share/orbit/app/notes_window.py').is_file());self.assertFalse((home/'.config/sxhkd').exists())
   self.assertEqual(m.main(['install','--source',str(source),'--target-home',tmp,'--orbit-only']),0)
   backup=json.loads((home/'.local/state/dotifails/installed.json').read_text())['last_backup'];journal=json.loads((home/'.local/state/dotifails/backups'/backup/'journal.json').read_text());self.assertEqual(journal['operations'],[])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.home=self.root/'home';self.home.mkdir();self.source=self.root/'source';self.source.mkdir();self.input=self.source/'file';self.input.write_text('new')
 def tearDown(self):self.temp.cleanup()
 def deploy(self):d=m.Deployment(self.home,self.source);d.begin();return d
 def test_initial_backup_idempotence_conflict_restore(self):
  dest=self.home/'.config/app';dest.parent.mkdir();dest.write_text('original');d=self.deploy();d.deploy(self.input,Path('.config/app'));d.finish();first=d.journal['id'];d.lock.close();self.assertEqual(dest.read_text(),'new')
  d=self.deploy();d.deploy(self.input,Path('.config/app'));self.assertEqual(d.journal['operations'],[]);d.finish();d.lock.close()
  dest.write_text('my changes');self.input.write_text('updated');d=self.deploy();d.deploy(self.input,Path('.config/app'));self.assertEqual(d.conflicts,['.config/app']);self.assertEqual(dest.read_text(),'my changes');self.assertEqual((d.backup/'incoming/.config/app').read_text(),'updated');d.finish();d.lock.close()
  m.restore(self.home,first);self.assertEqual(dest.read_text(),'original');self.assertEqual((self.home/'.local/state/dotifails/backups'/first/'changes-before-restore/.config/app').read_text(),'my changes')
 def test_managed_symlink_replaces_without_following(self):
  outside=self.root/'outside';outside.write_text('untouched');dest=self.home/'file';dest.symlink_to(outside);d=self.deploy();d.deploy(self.input,Path('file'));d.finish();d.lock.close();self.assertEqual(outside.read_text(),'untouched');m.restore(self.home,d.journal['id']);self.assertTrue(dest.is_symlink())
 def test_parent_symlink_rejected(self):
  (self.home/'.config').symlink_to(self.source)
  with self.assertRaises(RuntimeError):self.deploy()
 def test_interrupted_rename_recovers(self):
  dest=self.home/'file';dest.write_text('original');d=self.deploy();original=Path.rename
  def fail(path,target):
   if '.dotifails-' in path.name:raise OSError('simulated interruption')
   return original(path,target)
  with patch.object(Path,'rename',fail):
   with self.assertRaises(OSError):d.deploy(self.input,Path('file'))
  d.lock.close();m.restore(self.home,d.journal['id']);self.assertEqual(dest.read_text(),'original')
 def test_deleted_user_file_stays_deleted_on_update(self):
  d=self.deploy();d.deploy(self.input,Path('file'));d.finish();d.lock.close();(self.home/'file').unlink();d=self.deploy();d.deploy(self.input,Path('file'));self.assertFalse((self.home/'file').exists());self.assertEqual(d.conflicts,['file']);d.lock.close()
 def test_tar_traversal_rejected(self):
  import io,tarfile
  archive=self.root/'bad.tar'
  with tarfile.open(archive,'w') as t:
   info=tarfile.TarInfo('../escape');info.size=1;t.addfile(info,io.BytesIO(b'x'))
  with self.assertRaises(tarfile.FilterError):m.extract(archive,self.root/'extract','tar')
  self.assertFalse((self.root/'escape').exists())
 def test_appimage_internal_directory_symlink(self):
  archive=self.root/'image';archive.write_text('fixture')
  def unpack(*args,**kwargs):
   target=Path(kwargs['cwd']);(target/'AppDir').mkdir();(target/'AppDir/AppRun').write_text('run');(target/'squashfs-root').symlink_to('AppDir')
  with patch.object(m.subprocess,'run',unpack):m.extract(archive,self.root/'extracted','appimage')
  self.assertTrue((self.root/'extracted/AppRun').is_file());self.assertFalse((self.root/'extracted').is_symlink())
if __name__=='__main__':unittest.main()
