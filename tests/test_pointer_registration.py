"""Root helper distribution boundaries, tested only under disposable roots."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'installer'))
import pointer_registration as pointer


class PointerRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name);self.root=self.folder/'system';self.root.mkdir(mode=0o700)
        self.source=self.folder/'source'
        helper=self.source/'apps/capture/privileged/wysun-pointer-helper';helper.parent.mkdir(parents=True)
        helper.write_text('#!/usr/bin/python3 -I\nraise SystemExit("synthetic fixture: never run")\n')
        policy=self.source/'installer/wysun-pointer.policy';policy.parent.mkdir()
        policy.write_bytes((ROOT/'installer/wysun-pointer.policy').read_bytes())

    def call(self,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()):return pointer.register(self.source,self.root,**kwargs)

    def test_opt_in_registration_idempotence_and_recovery(self):
        self.assertEqual(self.call(dry_run=True),0);self.assertEqual(list(self.root.iterdir()),[])
        self.assertEqual(self.call(),0)
        helper=self.root/'usr/libexec/wysun-pointer-helper';policy=self.root/'usr/share/polkit-1/actions/org.wysun.pointer.policy'
        self.assertEqual(helper.stat().st_mode&0o777,0o755);self.assertEqual(policy.stat().st_mode&0o777,0o644)
        self.assertEqual(self.call(),0)
        helper.write_text('custom local edit')
        self.assertEqual(self.call(restore=True),2);self.assertTrue(policy.is_file())
        helper.write_bytes((self.source/'apps/capture/privileged/wysun-pointer-helper').read_bytes())
        self.assertEqual(self.call(restore=True),0);self.assertFalse(helper.exists());self.assertFalse(policy.exists())

    def test_unowned_files_and_writable_or_linked_parents_are_rejected(self):
        (self.root/'usr').mkdir(mode=0o755)
        target=self.root/'usr/libexec/wysun-pointer-helper';target.parent.mkdir(mode=0o755);target.write_text('unowned');target.chmod(0o755)
        self.assertEqual(self.call(),2);self.assertEqual(target.read_text(),'unowned')
        self.assertFalse((self.root/'usr/share/polkit-1/actions/org.wysun.pointer.policy').exists())
        target.parent.chmod(0o777)
        with self.assertRaises(ValueError):self.call()
        target.parent.chmod(0o755);target.unlink();target.parent.rmdir();target.parent.symlink_to(self.source)
        with self.assertRaises(ValueError):self.call()

    def test_linked_root_and_ancestor_rejected_before_any_write(self):
        link=self.folder/'redirect';link.symlink_to(self.root,target_is_directory=True)
        for root in (link,link/'nested'):
            with self.assertRaises(ValueError):pointer.register(self.source,root)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_policy_requires_active_auth_each_time_and_only_root_helper_path(self):
        action=ET.parse(ROOT/'installer/wysun-pointer.policy').getroot().find('action')
        defaults=action.find('defaults')
        self.assertEqual(defaults.findtext('allow_any'),'no');self.assertEqual(defaults.findtext('allow_inactive'),'no')
        self.assertEqual(defaults.findtext('allow_active'),'auth_self')
        annotations={node.attrib['key']:node.text for node in action.findall('annotate')}
        self.assertEqual(annotations,{'org.freedesktop.policykit.exec.path':'/usr/libexec/wysun-pointer-helper'})

if __name__=='__main__':unittest.main()
