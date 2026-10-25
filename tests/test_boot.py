import importlib.util
import sys
import json
from pathlib import Path
import subprocess
import re
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
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

    def preview(self, mode, steps):
        from plymouth_preview import records, run
        try:dump=run(mode,steps)
        except FileNotFoundError:self.skipTest('Plymouth interpreter not installed')
        return list(records(dump))

    def texts(self, sprites):
        return [s['name'][5:] for s in sprites if s['name'].startswith('text:') and s['opacity']>0]

    def status(self, sprites):
        return next(s['name'][7:-4] for s in sprites if s['name'].startswith('status-') and s['name']!='status-skip.png' and s['opacity']>0)

    def file(self, sprites):
        return next(s for s in sprites if s['z']==3 and s['name'].split('-')[0] in ('card','flip','click.png','fade'))

    def shown(self, sprites, name):
        return any(s['name']==name and s['opacity']>0 for s in sprites)

    def test_boot_leafs_through_the_index_then_opens_cold_harbor(self):
        sprites=self.preview('boot',['refresh();'])
        self.assertEqual(self.file(sprites)['name'],'card-0.png')
        self.assertEqual(self.status(sprites),'browsing')
        sprites=self.preview('boot',['for (j=0;j<30;j++) refresh();'])
        self.assertEqual(self.file(sprites)['name'],'flip-0-4.png')
        sprites=self.preview('boot',['for (j=0;j<100;j++) refresh();'])
        self.assertEqual(self.file(sprites)['name'],'card-3.png')
        sprites=self.preview('boot',['for (j=0;j<210;j++) refresh();'])
        self.assertEqual(self.file(sprites)['name'],'click.png')
        self.assertEqual(self.status(sprites),'opening')

    def test_open_file_leaves_the_data_and_the_real_progress(self):
        sprites=self.preview('boot',['boot_progress(10, 0.5); for (j=0;j<320;j++) refresh();'])
        self.assertEqual(self.status(sprites),'loading')
        self.assertEqual(self.file(sprites)['opacity'],0)
        self.assertTrue(self.shown(sprites,'field-a.png') or self.shown(sprites,'field-b.png'))
        gauge=next(s for s in sprites if s['name']=='fill.png')
        self.assertAlmostEqual(gauge['w'],614*0.5,delta=10)
        sprites=self.preview('boot',['boot_progress(10, 1); for (j=0;j<320;j++) refresh();'])
        self.assertEqual(self.status(sprites),'ready')
        address=[s for s in sprites if s['name'].startswith('glyph-')]
        self.assertEqual(len(address),17)  # 0x + 6 digits, a colon, 0x + 6 digits
        self.assertLess(len(sprites),50,'the script must stay light')

    def test_shutdown_and_reboot_send_the_mascot_walking_and_never_go_blank(self):
        for mode,first in (('shutdown','goodbye'),('reboot','back')):
            walking=self.preview(mode,['for (j=0;j<60;j++) refresh();'])
            mascot=next(s for s in walking if s['name'].startswith('mascot-') and s['opacity']>0)
            self.assertTrue(mascot['name'].startswith('mascot-walk-r-'))
            later=self.preview(mode,['for (j=0;j<90;j++) refresh();'])
            moved=next(s for s in later if s['name'].startswith('mascot-') and s['opacity']>0)
            self.assertGreater(moved['x'],mascot['x'],'it walks across the glass')
            sprites=self.preview(mode,['for (j=0;j<200;j++) refresh();'])
            self.assertTrue(self.shown(sprites,f'balloon-{first}.png'))
            self.assertTrue(any(s['name'].startswith('mascot-wave-') and s['opacity']>0 for s in sprites))
            sad=self.preview(mode,['for (j=0;j<300;j++) refresh();'])
            self.assertTrue(any(s['name'].startswith('mascot-idle-woe-') and s['opacity']>0 for s in sad),'it has tempers')
            hop=self.preview(mode,['for (j=0;j<365;j++) refresh();'])
            jumping=next(s for s in hop if s['name'].startswith('mascot-hop-'))
            self.assertLess(jumping['y'],mascot['y'],'the hop leaves the floor')
            sprites=self.preview(mode,['for (j=0;j<3000;j++) refresh();'])
            self.assertTrue(any(s['name'].startswith('mascot-') and s['opacity']==1 for s in sprites))
            self.assertEqual(self.file(sprites)['opacity'],0)
            background=next(s for s in sprites if s['name']=='background.png')
            self.assertEqual(background['opacity'],1)
            self.assertEqual(self.status(sprites),'closing' if mode=='shutdown' else 'reboot')
            self.assertTrue(self.shown(sprites,'status-skip.png'),'the farewell says how to skip it')

    def test_passphrase_is_asked_by_the_terminal_program(self):
        sprites=self.preview('boot',['for (j=0;j<300;j++) refresh();','password("Unlock disk",3); refresh();'])
        self.assertTrue(self.shown(sprites,'dialog.png'))
        self.assertTrue(self.shown(sprites,'pass-3.png'))
        self.assertEqual(self.texts(sprites),[],'no system text drawn over the glass')
        sprites=self.preview('boot',['refresh();','test_mode="shutdown"; refresh();','password("Unlock disk",40); refresh();'])
        self.assertEqual(self.status(sprites),'closing')
        self.assertTrue(self.shown(sprites,'pass-16.png'))
        sprites=self.preview('boot',['password("Unlock disk",3); refresh(); normal(); refresh();'])
        self.assertFalse(self.shown(sprites,'dialog.png'))

    def test_every_image_the_script_loads_is_shipped(self):
        script=(SOURCE/'system/boot/plymouth/orbit.script').read_text()
        theme=SOURCE/'system/boot/plymouth'
        self.assertIn('projects = 6;',script)
        self.assertIn('flip_frames = 4;',script)
        self.assertIn('fade_frames = 4;',script)
        names=[f'card-{i}.png' for i in range(6)]+[f'flip-{i}-{k}.png' for i in range(5) for k in range(1,5)]
        names+=[f'fade-{k}.png' for k in range(1,5)]+[f'pass-{k}.png' for k in range(17)]
        names += [f'mascot-walk-{d}-{k}.png' for d in 'rl' for k in range(12)]+[f'mascot-turn-{d}-{k}.png' for d in 'rl' for k in range(4)]
        names += [f'mascot-wave-{k}.png' for k in range(16)]+[f'mascot-idle-{m}-{k}.png' for m in ('cheer','woe','frolic','dread') for k in range(8)]+[f'mascot-hop-{k}.png' for k in range(10)]
        names += [f'balloon-{key}.png' for key in ('goodbye','tomorrow','thanks','back','moment','miss','dark')]+['shadow.png']
        names+=['click.png','dialog.png','field-a.png','field-b.png','background.png','fill.png','pointer.png']
        names+=['glyph-x.png','glyph-colon.png']+[f'glyph-{digit}.png' for digit in '0123456789ABCDEF']
        names+=[f'status-{key}.png' for key in re.findall(r'say\("(\w+)"\)',script)]
        for name in names:
            self.assertTrue((theme/name).is_file(),name)

    def test_grub_background_stays_light(self):
        size=(SOURCE/'system/boot/grub/background.png').stat().st_size
        self.assertLess(size,400*1024,'GRUB decodes PNGs slowly; a heavy background makes the menu crawl')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for path in ('boot/grub','etc/default/grub.d','usr/share/plymouth/themes','etc/plymouth','etc/X11','etc/greetd','usr/sbin','usr/lib/qt6/bin'):
            (self.root/path).mkdir(parents=True,exist_ok=True)
        self.put('etc/default/grub','GRUB_TIMEOUT=7\nGRUB_DEFAULT=saved\nGRUB_CMDLINE_LINUX="quiet splash cryptdevice=keep"\n')
        self.put('boot/grub/grub.cfg','original working boot menu\n').chmod(0o600)
        self.put('etc/X11/default-display-manager','/usr/sbin/lightdm\n')
        self.put('etc/plymouth/plymouthd.conf','[Daemon]\nTheme=parrot6\nShowDelay=3\n')
        self.put('usr/sbin/greetd','fixture')
        self.put('usr/lib/qt6/bin/qsb','fixture')
        self.put('etc/default/keyboard','XKBMODEL="pc105"\nXKBLAYOUT="es"\nXKBVARIANT="deadtilde"\nXKBOPTIONS=""\n')
        self.commands=[]

    def put(self,path,text):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text);return target

    def runner(self,command):
        self.commands.append(command)
        if command[0]=='grub-mkconfig':Path(command[-1]).write_text('generated valid boot menu\n')
        if command[0].endswith('/qsb'):Path(command[command.index('-o')+1]).write_bytes(b'qsb fixture')

    def deployment(self,runner=None,components=('grub','plymouth','greeter')):return boot.BootDeployment(SOURCE,self.root,runner or self.runner,components)
    def tearDown(self):self.temp.cleanup()

    def test_apply_preserves_boot_switches_to_greetd_then_idempotent(self):
        original=(self.root/'etc/default/grub').read_bytes()
        d=self.deployment();ident=d.apply()
        self.assertEqual((self.root/'etc/default/grub').read_bytes(),original)
        greeter=self.root/'usr/local/share/wysun/greeter'
        self.assertTrue((greeter/'greeter.qml').is_file())
        self.assertTrue((greeter/'shaders/field.frag.qsb').is_file())
        compositor=(greeter/'hyprland.conf').read_text()
        self.assertIn('kb_layout = es',compositor);self.assertIn('kb_variant = deadtilde',compositor)
        launcher=self.root/'usr/local/libexec/wysun-greeter'
        self.assertEqual(launcher.stat().st_mode & 0o777,0o755)
        self.assertIn('agreety',launcher.read_text())
        self.assertIn('command = "/usr/local/libexec/wysun-greeter"',(self.root/'etc/greetd/config.toml').read_text())
        self.assertEqual((self.root/'etc/X11/default-display-manager').read_text(),'/usr/sbin/greetd\n')
        systemctl=[c for c in self.commands if c[0]=='systemctl']
        self.assertEqual([c[2:] for c in systemctl],[['disable','lightdm.service'],['enable','--force','greetd.service']])
        self.assertFalse(any('restart' in c or 'start' in c or 'stop' in c for c in systemctl))
        self.assertIn('ShowDelay = 0',(self.root/'etc/plymouth/plymouthd.conf').read_text())
        self.assertIn('vt = 7',(self.root/'etc/greetd/config.toml').read_text())
        self.assertIn('chvt 7',(self.root/'etc/systemd/system/greetd.service.d/wysun-vt.conf').read_text())
        self.assertFalse((self.root/'etc/systemd/system/plymouth-quit.service.d').exists(),'never retain the splash')
        dropin=(self.root/'etc/default/grub.d/99-orbit-theme.cfg').read_text()
        self.assertIn('GRUB_GFXPAYLOAD_LINUX=keep',dropin);self.assertIn('vt.global_cursor_default=0',dropin)
        farewell=self.root/'usr/local/libexec/wysun-farewell'
        self.assertEqual(farewell.stat().st_mode & 0o777,0o755)
        self.assertIn('plymouth --ping',farewell.read_text());self.assertIn('watch-keystroke',farewell.read_text())
        self.assertIn('TimeoutStartSec=20',(self.root/'etc/systemd/system/wysun-farewell.service').read_text())
        for target in ('poweroff','reboot','halt'):
            self.assertIn('Wants=wysun-farewell.service',(self.root/f'etc/systemd/system/{target}.target.d/wysun-farewell.conf').read_text())
        quiet=self.root/'etc/grub.d/06_wysun'
        self.assertEqual(quiet.stat().st_mode & 0o777,0o755)
        self.assertIn('set color_normal=blue/black',quiet.read_text())
        self.assertIn('background_image -m stretch',quiet.read_text())
        self.assertEqual((self.root/'boot/grub/grub.cfg').stat().st_mode & 0o777,0o600)
        self.assertFalse(any('grub-install' in c for c in self.commands))
        self.assertEqual(list((self.root/'boot/grub/themes/orbit').glob('*.in')),[])
        self.commands=[];second=self.deployment().apply()
        self.assertEqual([c for c in self.commands if c[0]!='/'+str(self.root/'usr/lib/qt6/bin/qsb')[1:]],[])
        self.assertEqual(json.loads((d.state/'backups'/second/'journal.json').read_text())['operations'],[])
        self.commands=[];d.restore(ident)
        self.assertEqual((self.root/'boot/grub/grub.cfg').read_text(),'original working boot menu\n')
        self.assertEqual((self.root/'boot/grub/grub.cfg').stat().st_mode & 0o777,0o600)
        self.assertFalse((self.root/'etc/default/grub.d/99-orbit-theme.cfg').exists())
        self.assertFalse((self.root/'etc/grub.d/06_wysun').exists())
        self.assertFalse((self.root/'etc/systemd/system/wysun-farewell.service').exists())
        self.assertEqual((self.root/'etc/X11/default-display-manager').read_text(),'/usr/sbin/lightdm\n')
        self.assertFalse(greeter.exists())
        self.assertIn('ShowDelay=3',(self.root/'etc/plymouth/plymouthd.conf').read_text())
        self.assertEqual([c[2:] for c in self.commands if c[0]=='systemctl'],[['disable','greetd.service'],['enable','--force','lightdm.service']])

    def test_greeter_ships_only_the_portable_scene(self):
        d=self.deployment();d.apply()
        greeter=self.root/'usr/local/share/wysun/greeter'
        names={p.name for p in (greeter/'modules/lockscreen').glob('*.qml')}
        self.assertEqual(names,set(boot.GREETER_FILES))
        for path in greeter.rglob('*.qml'):
            self.assertNotIn('Wysun.Config',path.read_text(),path)
        scheme=json.loads((greeter/'scheme.json').read_text())
        self.assertEqual(set(scheme['colours']),{'surface','primary','error','onSurface','onSurfaceVariant','success','warning','info'})

    def test_greeter_compositor_passes_hyprland_verification(self):
        import shutil as tools
        if not tools.which('Hyprland'):self.skipTest('Hyprland not installed')
        config=self.put('greeter-hyprland.conf',boot.greeter_compositor(boot.keyboard(self.root/'etc/default/keyboard')))
        result=subprocess.run(['Hyprland','--verify-config','-c',str(config)],capture_output=True,text=True,timeout=30)
        self.assertIn('config ok',result.stdout+result.stderr)

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
        self.put('etc/greetd/config.toml','# my own greetd\n')
        with self.assertRaisesRegex(RuntimeError,'cambios locales'):self.deployment().apply()
        self.assertEqual(self.commands,[])
        self.assertIn('my own greetd',(self.root/'etc/greetd/config.toml').read_text())

    def test_restore_preserves_later_changes_separately(self):
        d=self.deployment();ident=d.apply()
        self.put('etc/greetd/config.toml','my later settings')
        d.restore(ident)
        self.assertEqual((d.state/'backups'/ident/'changes-before-restore/etc/greetd/config.toml').read_text(),'my later settings')

    def test_greetd_login_is_never_planned_by_default(self):
        groups={group for group,_,_ in boot.BootDeployment(SOURCE,self.root,self.runner).plan()}
        self.assertEqual(groups,{'grub','plymouth'})
        from install_model import InstallOptions
        self.assertNotIn('greetd',InstallOptions(SOURCE,components=('boot',)).summary()['packages'])

    def test_greeter_needs_greetd_installed(self):
        (self.root/'usr/sbin/greetd').unlink()
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
        (self.root/'usr/share/plymouth/themes/orbit/flip-2-3.png').unlink()
        with self.assertRaisesRegex(RuntimeError,'incompleto'):d.verify()

    def test_shell_dropin_does_not_duplicate_splash_or_change_flags(self):
        payload=next(p for _,rel,p in self.deployment().plan() if rel.endswith('99-orbit-theme.cfg'))
        drop=self.put('drop.cfg',payload)
        for flags in ('quiet splash cryptdevice=keep','cryptdevice=keep'):
            result=subprocess.check_output(['sh','-c','GRUB_CMDLINE_LINUX="$1"; GRUB_CMDLINE_LINUX_DEFAULT="resume=keep"; . "$2"; printf "%s" "$GRUB_CMDLINE_LINUX $GRUB_CMDLINE_LINUX_DEFAULT"','sh',flags,str(drop)],text=True)
            self.assertEqual(result.split().count('splash'),1)
            self.assertIn('cryptdevice=keep',result);self.assertIn('resume=keep',result)

if __name__=='__main__':unittest.main()
