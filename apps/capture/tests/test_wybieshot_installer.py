import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('shot_installer',Path(__file__).parents[1]/'scripts/install-screenshot.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class InstallerTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'source';(source/'wybieshot/ui').mkdir(parents=True);(source/'loomrec/ui').mkdir(parents=True);(source/'assets').mkdir()
        for name in ('wybieshot/__init__.py','wybieshot/ui/main.py','loomrec/ui/tokens.py'):(source/name).write_text('# safe fixture')
        (source/'assets/wybie-screenshot.svg').write_text('<svg/>')
        installer=module.Installer(source,root/'data',root/'bin')
        return source,installer

    def test_dry_install_update_preserve_sessions_uninstall(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,installer=self.fixture(root)
            dry=installer.install(True);self.assertFalse(installer.base.exists())
            first=installer.install();self.assertEqual(first['release'],dry['release'])
            launcher=root/'bin/wybie-screenshot';self.assertTrue(launcher.stat().st_mode&0o111)
            session=installer.base/'sessions/private';session.mkdir(parents=True);(session/'source').write_text('private fixture')
            recorder=root/'data/loomrec/settings.json';recorder.parent.mkdir();recorder.write_text('preserve')
            (source/'wybieshot/ui/main.py').write_text('# v2')
            second=installer.install();self.assertNotEqual(first['release'],second['release'])
            result=installer.uninstall();self.assertFalse(result['preserved'])
            self.assertFalse(launcher.exists());self.assertEqual((session/'source').read_text(),'private fixture')
            self.assertEqual(recorder.read_text(),'preserve')

    def test_conflicts_preflight_and_modified_uninstall(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,installer=self.fixture(root);installer.install()
            launcher=root/'bin/wybie-screenshot';launcher.write_text('user custom')
            with self.assertRaises(ValueError):installer.install()
            result=installer.uninstall();self.assertIn(str(launcher),result['preserved'])
            self.assertEqual(launcher.read_text(),'user custom')

    def test_symlink_and_incomplete_ui(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,installer=self.fixture(root)
            (source/'wybieshot/ui/main.py').unlink()
            with self.assertRaises(ValueError):installer.install()
            (source/'wybieshot/ui/main.py').write_text('# restored')
            target=root/'elsewhere';target.mkdir();installer.bin.symlink_to(target,target_is_directory=True)
            with self.assertRaises(ValueError):installer.install()

    def test_tampered_manifest_cannot_delete_unrelated(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,installer=self.fixture(root);installer.install()
            other=root/'unrelated';other.write_text('mine')
            installer.manifest.write_text(json.dumps({'files':{str(other):module.digest(b'mine')}}))
            with self.assertRaises(ValueError):installer.uninstall()
            self.assertEqual(other.read_text(),'mine')

if __name__=='__main__':unittest.main()
