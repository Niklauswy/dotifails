import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('boot',SOURCE/'installer/boot.py')
boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)


class BootTests(unittest.TestCase):
    def test_selection_omits_unselected_screens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'etc/default').mkdir(parents=True)
            (root/'etc/default/grub').write_text('GRUB_TIMEOUT=7\n')
            (root/'boot/grub').mkdir(parents=True)
            (root/'usr/share/plymouth/themes').mkdir(parents=True)
            deployment=boot.BootDeployment(SOURCE,root,components=['grub'])
            self.assertEqual({group for group,_,_ in deployment.plan()},{'grub'})
            with self.assertRaises(ValueError):boot.BootDeployment(SOURCE,root,components=['unknown'])

    def test_animation_parses_with_installed_plymouth_engine(self):
        import ctypes
        library=Path('/usr/lib/x86_64-linux-gnu/plymouth/script.so')
        if not library.exists():self.skipTest('Plymouth script plugin not installed')
        engine=ctypes.CDLL(str(library))
        engine.script_parse_file.argtypes=[ctypes.c_char_p]
        engine.script_parse_file.restype=ctypes.c_void_p
        engine.script_parse_op_free.argtypes=[ctypes.c_void_p]
        parsed=engine.script_parse_file(str(SOURCE/'system/boot/plymouth/orbit.script').encode())
        self.assertTrue(parsed,'Plymouth rejected the custom animation')
        engine.script_parse_op_free(parsed)

    def test_boot_shutdown_and_reboot_execute_different_frames(self):
        from plymouth_runtime import Engine, PRELUDE
        for mode,prefix in (('boot','frame'),('shutdown','shutdown'),('reboot','reboot')):
            try:engine=Engine()
            except FileNotFoundError:self.skipTest('Plymouth interpreter not installed')
            try:
                engine.execute(PRELUDE+'\ntest_mode="'+mode+'";\n'+(SOURCE/'system/boot/plymouth/orbit.script').read_text())
                engine.execute('for(j=0;j<12;j++) refresh(); result=logo.image.name;')
                self.assertEqual(engine.string('result'),prefix+'-6.png')
                engine.execute('quit(); result=logo.image.name;')
                self.assertEqual(engine.string('result'),prefix+'-6.png','Quit must not flash the startup frame')
            finally:engine.close()

    def test_live_mode_switch_and_password_pause(self):
        from plymouth_runtime import Engine, PRELUDE
        try:engine=Engine()
        except FileNotFoundError:self.skipTest('Plymouth interpreter not installed')
        try:
            engine.execute(PRELUDE+'\ntest_mode="boot";\n'+(SOURCE/'system/boot/plymouth/orbit.script').read_text())
            engine.execute('test_mode="shutdown"; refresh(); result=logo.image.name;')
            self.assertEqual(engine.string('result'),'shutdown-0.png')
            engine.execute('password("Unlock disk",3); for(j=0;j<12;j++) refresh(); result=logo.image.name; dots_result=entry_sprite.image.name;')
            self.assertEqual(engine.string('result'),'shutdown-0.png')
            self.assertEqual(engine.string('dots_result'),'•••')
            engine.execute('normal(); refresh(); result=logo.image.name;')
            self.assertEqual(engine.string('result'),'shutdown-7.png')
        finally:engine.close()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for path in ('boot/grub','etc/default/grub.d','usr/share/plymouth/themes','etc/plymouth','etc/X11','etc/lightdm'):
            (self.root/path).mkdir(parents=True,exist_ok=True)
        self.put('etc/default/grub','GRUB_TIMEOUT=7\nGRUB_DEFAULT=saved\nGRUB_CMDLINE_LINUX="quiet splash cryptdevice=keep"\n')
        self.put('boot/grub/grub.cfg','original working boot menu\n').chmod(0o600)
        self.put('etc/X11/default-display-manager','/usr/sbin/lightdm\n')
        self.put('etc/plymouth/plymouthd.conf','[Daemon]\nTheme=parrot6\nShowDelay=3\n')
        self.put('etc/lightdm/slick-greeter.conf','[Greeter]\nshow-a11y=true\nhidden-users=private\nbackground=old.png\n')
        self.commands=[]
        def fake_build(deployment,source,target):
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(b'fixture-gtk-module');target.chmod(0o644)
        self.build_patch=patch.object(boot.BootDeployment,'build_module',fake_build)
        self.build_patch.start()
        self.addCleanup(self.build_patch.stop)

    def put(self,path,text):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text);return target

    def runner(self,command):
        self.commands.append(command)
        if command[0]=='grub-mkconfig':Path(command[-1]).write_text('generated valid boot menu\n')

    def deployment(self,runner=None):return boot.BootDeployment(SOURCE,self.root,runner or self.runner)
    def tearDown(self):self.temp.cleanup()

    def test_apply_preserves_boot_and_accessibility_then_idempotent(self):
        original=(self.root/'etc/default/grub').read_bytes()
        d=self.deployment();ident=d.apply()
        self.assertEqual((self.root/'etc/default/grub').read_bytes(),original)
        config=(self.root/'etc/lightdm/slick-greeter.conf').read_text()
        self.assertIn('show-a11y = true',config);self.assertIn('hidden-users = private',config)
        self.assertIn('draw-user-backgrounds = false',config)
        self.assertIn('greeter-session=blue-crt',(self.root/'etc/lightdm/lightdm.conf.d/99-orbit-greeter.conf').read_text())
        self.assertTrue((self.root/'usr/local/lib/dotifails/blue-crt.so').exists())
        self.assertIn('ShowDelay = 3',(self.root/'etc/plymouth/plymouthd.conf').read_text())
        self.assertEqual((self.root/'boot/grub/grub.cfg').stat().st_mode & 0o777,0o600)
        self.assertFalse(any('grub-install' in c or 'systemctl' in c for c in self.commands))
        self.commands=[];second=self.deployment().apply()
        self.assertEqual(self.commands,[])
        self.assertEqual(json.loads((d.state/'backups'/second/'journal.json').read_text())['operations'],[])
        d.restore(ident)
        self.assertEqual((self.root/'boot/grub/grub.cfg').read_text(),'original working boot menu\n')
        self.assertEqual((self.root/'boot/grub/grub.cfg').stat().st_mode & 0o777,0o600)
        self.assertFalse((self.root/'etc/default/grub.d/99-orbit-theme.cfg').exists())

    def test_invalid_generated_grub_restores_original_and_themes(self):
        def fail(command):
            self.runner(command)
            if command[0]=='grub-script-check':raise subprocess.CalledProcessError(1,command)
        d=self.deployment(fail)
        with self.assertRaises(subprocess.CalledProcessError):d.apply()
        self.assertEqual((self.root/'boot/grub/grub.cfg').read_text(),'original working boot menu\n')
        self.assertIn('Theme=parrot6',(self.root/'etc/plymouth/plymouthd.conf').read_text())
        self.assertFalse((self.root/'boot/grub/themes/orbit').exists())
        self.assertFalse((self.root/'boot/grub/grub.cfg.orbit-new').exists())

    def test_initramfs_failure_rolls_back_grub_exactly(self):
        failed=False
        def fail_once(command):
            nonlocal failed
            self.runner(command)
            if command[0]=='update-initramfs' and not failed:
                failed=True;raise subprocess.CalledProcessError(1,command)
        d=self.deployment(fail_once)
        with self.assertRaises(subprocess.CalledProcessError):d.apply()
        self.assertEqual((self.root/'boot/grub/grub.cfg').read_text(),'original working boot menu\n')
        self.assertEqual(json.loads(next((d.state/'backups').glob('*/journal.json')).read_text())['status'],'restored')

    def test_admin_change_blocks_update_before_any_mutation(self):
        d=self.deployment();d.apply();self.commands=[]
        self.put('etc/lightdm/slick-greeter.conf','[Greeter]\nbackground=my-own.png\n')
        with self.assertRaisesRegex(RuntimeError,'cambios locales'):self.deployment().apply()
        self.assertEqual(self.commands,[])
        self.assertIn('my-own.png',(self.root/'etc/lightdm/slick-greeter.conf').read_text())

    def test_restore_preserves_later_changes_separately(self):
        d=self.deployment();ident=d.apply()
        self.put('etc/lightdm/slick-greeter.conf','my later settings')
        d.restore(ident)
        self.assertEqual((d.state/'backups'/ident/'changes-before-restore/etc/lightdm/slick-greeter.conf').read_text(),'my later settings')

    def test_other_display_manager_is_not_replaced(self):
        self.put('etc/X11/default-display-manager','/usr/bin/sddm\n')
        self.assertFalse(any(group=='greeter' for group,_,_ in self.deployment().plan()))

    def test_serial_console_is_preserved(self):
        self.put('etc/default/grub.d/serial.cfg','GRUB_TERMINAL_OUTPUT="console serial"\n')
        payload=next(p for _,rel,p in self.deployment().plan() if rel.endswith('99-orbit-theme.cfg'))
        self.assertNotIn('GRUB_TERMINAL_OUTPUT=',payload)

    def test_parent_symlink_is_rejected(self):
        (self.root/'boot/grub').rename(self.root/'old-grub')
        (self.root/'boot/grub').symlink_to(self.root/'old-grub')
        with self.assertRaisesRegex(RuntimeError,'Enlace'):self.deployment().plan()

    def test_verify_detects_an_incomplete_deployment(self):
        d=self.deployment();d.apply();d.verify()
        (self.root/'usr/share/plymouth/themes/orbit/frame-17.png').unlink()
        with self.assertRaisesRegex(RuntimeError,'incompleto'):d.verify()

    def test_shell_dropin_does_not_duplicate_splash_or_change_flags(self):
        payload=next(p for _,rel,p in self.deployment().plan() if rel.endswith('99-orbit-theme.cfg'))
        drop=self.put('drop.cfg',payload)
        for flags in ('quiet splash cryptdevice=keep','cryptdevice=keep'):
            result=subprocess.check_output(['sh','-c','GRUB_CMDLINE_LINUX="$1"; GRUB_CMDLINE_LINUX_DEFAULT="resume=keep"; . "$2"; printf "%s" "$GRUB_CMDLINE_LINUX $GRUB_CMDLINE_LINUX_DEFAULT"','sh',flags,str(drop)],text=True)
            self.assertEqual(result.split().count('splash'),1)
            self.assertIn('cryptdevice=keep',result);self.assertIn('resume=keep',result)

if __name__=='__main__':unittest.main()
