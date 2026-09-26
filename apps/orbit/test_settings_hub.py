"""Settings integration checks use temporary homes and never apply a live layout."""
import copy
import json
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from environment_settings import (EnvironmentSettings,DisplayTrial,parse_xrandr,display_plan,display_command,profile_key,configured_bar_monitors,render_wallpaper,restore_display)
from settings_runtime import guard,restore_workspaces,start_applications
from settings_shortcuts import expanded_rows,change_binding,application_shortcuts
from settings_data import ShortcutFile,SCHEMA
from settings_hub import SettingsHub

XRANDR='''Screen 0: minimum 8 x 8, current 1600 x 600, maximum 16384 x 16384
eDP-1 connected 800x600+0+0 (normal left inverted right x axis y axis)
   800x600       60.00*+  59.94
   640x480       60.00
DP-1 connected primary 800x600+800+0 (normal left inverted right x axis y axis)
   800x600       60.00*+  59.94
   640x480       60.00
HDMI-1 disconnected (normal left inverted right x axis y axis)
'''
BAR='''[colors]
bg = #A6101118
fg = #EBECF3
accent = #B8C8FA
[bar/base]
height = 36
offset-y = 10
radius = 12
enable-ipc = true
[bar/left]
modules-left = orbit title
[bar/center]
modules-center = bspwm
[bar/right]
modules-right = resources network volume date tray
[bar/right-secondary]
modules-right = resources network volume date
'''
PICOM='''backend = "glx";
corner-radius = 12;
blur-strength = 3;
shadow-radius = 18;
shadow-opacity = 0.25;
blur-background = true;
shadow = true;
fading = true;
vsync = true;
rules = (
 { match = "class_g = 'Ghostty'"; animations = ( { triggers = ["open"]; preset = "appear"; duration = 0.12; } ); },
 { match = "fullscreen"; corner-radius = 0; shadow = false; blur-background = false; }
);
'''
TERMINAL='''font-family = "FiraCode Nerd Font"
font-size = 20
background-opacity = 0.6
window-padding-x = 10
window-padding-y = 10
scrollback-limit = 10000
background = 1a1b26
foreground = c0caf5
shell-integration = none
keybind = ctrl+shift+a=select_all
'''
DUNST='''[global]
font = Inter 10
origin = top-right
transparency = 5
corner_radius = 12
notification_limit = 4
padding = 18
gap_size = 10
[urgency_normal]
timeout = 6
[urgency_critical]
timeout = 0
'''
SHORTCUTS='''# Leave this preamble
# desktop focus
super + {1,2,3}
    bspc desktop -f ^{1,2,3}

# Connections
super + n
    orbit network
'''

class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name);self.calls=[]
        for relative,text in [('bspwm/polybar/config',BAR),('bspwm/picom.conf',PICOM),('ghostty/config',TERMINAL),('bspwm/dunstrc',DUNST),('sxhkd/sxhkdrc',SHORTCUTS)]:
            path=self.home/'.config'/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        self.env=EnvironmentSettings(self.home,self.runner)
        self.backup_patch=patch('settings_data.HOME',self.home);self.backup_patch.start()
    def tearDown(self):self.backup_patch.stop();self.tmp.cleanup()
    def runner(self,args):
        self.calls.append(args)
        if args[:2]==['xrandr','--query']:return XRANDR
        if args[:3]==['bspc','wm','-d']:return json.dumps({'monitors':[{'name':'eDP-1','focusedDesktopId':1,'desktops':[{'id':1,'name':'1','root':None},{'id':2,'name':'2','root':{'client':{'className':'Ghostty'}}}]}]})
        if args[:2]==['bspc','config']:
            _,kind,low,high=SCHEMA[args[2]]
            return '10' if kind=='int' else '.5' if kind=='float' else '#aabbcc' if kind=='color' else 'false' if kind=='bool' else low[0]
        return ''

class DisplayTests(Fixture):
    def test_realistic_inventory_and_exact_argv(self):
        outputs=parse_xrandr(XRANDR);plan=display_plan(outputs);self.assertEqual(len(plan),2);self.assertEqual(outputs[0]['modes'][0]['rates'],['60.00','59.94']);command=display_command(plan,outputs);self.assertIn('800x0',command);self.assertEqual(command.count('--primary'),1)
        portrait=parse_xrandr(XRANDR.replace('800x600+800+0 (','600x800+800+0 left ('));self.assertEqual(portrait[1]['rotation'],'left');self.assertEqual(portrait[1]['mode'],'800x600')
    def test_invalid_or_hotplugged_layout_never_gets_command(self):
        outputs=parse_xrandr(XRANDR);plan=display_plan(outputs)
        for modify in (lambda p:[r.update(enabled=False) for r in p],lambda p:p[0].update(primary=True),lambda p:p[0].update(mode='9999x9999'),lambda p:p.pop()):
            draft=copy.deepcopy(plan);modify(draft)
            with self.assertRaises(ValueError):display_command(draft,outputs)
    def test_guard_recovers_after_app_crash_and_accepted_is_untouched(self):
        folder=self.home/'trial';folder.mkdir();plan=display_plan(parse_xrandr(XRANDR));(folder/'trial.json').write_text(json.dumps({'deadline':time.time()-1,'old':plan}));guard(folder,self.runner);self.assertTrue((folder/'reverted').exists());self.assertTrue(any(a[0]=='xrandr' and a[1]!='--query' for a in self.calls))
        self.calls.clear();(folder/'reverted').unlink();(folder/'accepted').write_text('ok');guard(folder,self.runner);self.assertFalse(self.calls)
    def test_trial_only_persists_on_confirmation_and_can_reject(self):
        plan=display_plan(parse_xrandr(XRANDR));plan[1]['x']=640
        with patch('environment_settings.subprocess.Popen'):
            trial=DisplayTrial(self.env,plan);self.assertFalse(self.env.section('displays'));trial.reject();self.assertFalse(self.env.section('displays'));self.assertTrue((trial.folder/'reverted').exists())
            trial=DisplayTrial(self.env,plan);trial.accept();self.assertEqual(self.env.section('displays')['profiles']['DP-1|eDP-1'][1]['x'],640);self.assertTrue((trial.folder/'accepted').exists())
    def test_expired_confirmation_does_not_save(self):
        with patch('environment_settings.subprocess.Popen'):trial=DisplayTrial(self.env,display_plan(parse_xrandr(XRANDR)))
        path=trial.folder/'trial.json';data=json.loads(path.read_text());data['deadline']=time.time()-1;path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):trial.accept()
        trial.reject();self.assertFalse(self.env.section('displays'))
    def test_restore_after_unplug_keeps_remaining_screen_on(self):
        old=display_plan(parse_xrandr(XRANDR));old[0]['enabled']=False
        reduced=XRANDR.replace('DP-1 connected primary 800x600+800+0','DP-1 disconnected')
        calls=[]
        restore_display(old,lambda args:(calls.append(args) or reduced) if args[1]=='--query' else calls.append(args));self.assertIn('--primary',calls[-1]);self.assertNotIn('--off',calls[-1])

class ConfigTests(Fixture):
    def test_workspace_restore_removes_only_empty_extras(self):
        self.env.save_section('workspaces',{'eDP-1':['Trabajo']})
        restore_workspaces(self.env)
        self.assertIn(['bspc','desktop','0x00000001','-n','Trabajo'],self.calls)
        self.assertNotIn(['bspc','desktop','0x00000002','-r'],self.calls)
    def test_autostart_runs_only_explicit_entries_once_per_session(self):
        self.env.add_autostart('Test app','true')
        with patch.dict(os.environ,{'XDG_RUNTIME_DIR':str(self.home),'XDG_SESSION_ID':'settings-test-session','XDG_CONFIG_DIRS':str(self.home/'no-system')}),patch('settings_runtime.subprocess.run') as launch:
            start_applications(self.env);start_applications(self.env)
            self.assertEqual(launch.call_count,1);self.assertEqual(launch.call_args.args[0][:2],['gio','launch'])
    def test_sections_merge_but_stale_same_section_is_rejected(self):
        other=EnvironmentSettings(self.home,self.runner);self.env.save_section('bar',{'a':1});other.save_section('wallpaper',{'default':'x'});self.assertEqual(json.loads(self.env.path.read_text())['bar'],{'a':1})
        with self.assertRaises(ValueError):other.save_section('bar',{'a':2})
    def test_bar_preferences_enable_laptop_and_tray_follows_selection(self):
        values=self.env.bar_values();values.update(monitors={'eDP-1':True,'DP-1':False,'DP-2':True},tray_monitor='eDP-1',opacity=75);self.env.apply_bar(values);self.assertEqual(configured_bar_monitors(['DP-1','DP-2'],['eDP-1','DP-1','DP-2'],self.home),['eDP-1','DP-2']);text=(self.home/'.config/bspwm/polybar/config').read_text();self.assertIn('enable-ipc = true',text);self.assertIn('#BF101118',text)
    def test_failed_bar_apply_restores_preferences_and_config(self):
        values=self.env.bar_values();values['height']=42;self.env.runner=lambda _:(_ for _ in ()).throw(RuntimeError('activation failed'))
        with self.assertRaises(RuntimeError):self.env.apply_bar(values)
        self.assertEqual((self.home/'.config/bspwm/polybar/config').read_text(),BAR);self.assertFalse(self.env.section('bar'))
    def test_terminal_and_notifications_preserve_unrelated_fields(self):
        values=self.env.component_values('terminal');values.update({'font-size':18,'background':'#123456','foreground':'#ABCDEF'});self.env.apply_component('terminal',values);text=(self.home/'.config/ghostty/config').read_text();self.assertIn('shell-integration = none',text);self.assertIn('keybind = ctrl+shift+a=select_all',text);self.assertIn('font-size = 18.0',text)
        values=self.env.component_values('notifications');values.update(origin='bottom-right',timeout=8);self.env.apply_component('notifications',values);self.assertIn('[urgency_critical]\ntimeout = 0',(self.home/'.config/bspwm/dunstrc').read_text())
    def test_effects_keep_fullscreen_rule_and_no_shell_injection(self):
        values=self.env.component_values('effects');values.update(duration=100,shadow=True,fading=True,vsync=True,**{'blur-background':True})
        with patch('environment_settings.subprocess.run') as process:
            process.return_value.returncode=1;self.env.apply_component('effects',values)
        text=(self.home/'.config/bspwm/picom.conf').read_text();self.assertIn('{ match = "fullscreen"; corner-radius = 0; shadow = false; blur-background = false; }',text);self.assertIn('duration = 0.1;',text)
        values['duration']='100;touch /tmp/nope'
        with self.assertRaises(ValueError):self.env.apply_component('effects',values)
    def test_nonempty_or_last_workspace_cannot_be_deleted(self):
        with self.assertRaises(ValueError):self.env.workspace_action('remove','0x00000002')
        self.assertFalse(any(args[:2]==['bspc','desktop'] for args in self.calls))
    def test_autostart_override_preserves_original_and_tracks_opt_in(self):
        root=self.home/'system';folder=root/'autostart';folder.mkdir(parents=True);source=folder/'example.desktop';source.write_text('[Desktop Entry]\nName=Example\nType=Application\nExec=true\nHidden=false\n')
        with patch.dict(os.environ,{'XDG_CONFIG_DIRS':str(root)}):
            entry=self.env.autostart_entries()[0];self.assertFalse(entry['managed']);self.env.set_autostart(entry,False);new=self.env.autostart_entries()[0];self.assertFalse(new['enabled']);self.assertTrue(new['managed']);self.assertIn('Hidden=false',source.read_text())

class ContentTests(Fixture):
    def test_edit_one_group_member_preserves_other_shortcuts(self):
        model=ShortcutFile(self.home/'.config/sxhkd/sxhkdrc');change_binding(model,0,1,'super + alt + 2','bspc desktop -f ^2','Second');rows=expanded_rows(model);self.assertEqual([r['key'] for r in rows],['super + 1','super + alt + 2','super + 3','super + n']);self.assertIn('# Leave this preamble',model.original)
        change_binding(model,1,0);self.assertEqual([r['key'] for r in expanded_rows(model)],['super + 1','super + 3','super + n'])
    def test_group_edit_conflict_and_external_edit_are_rejected(self):
        model=ShortcutFile(self.home/'.config/sxhkd/sxhkdrc')
        for key in ('super + 3','super + n'):
            with self.assertRaises(ValueError):change_binding(model,0,1,key,'true','Duplicated')
        model.path.write_text(model.original+'\n# external change\n')
        with self.assertRaises(ValueError):change_binding(model,0,1,'super + alt + 2','true','Edited')
    def test_wallpaper_composes_separate_outputs_and_preserves_sources(self):
        red=self.home/'red.png';blue=self.home/'blue.png';image=QImage(30,20,QImage.Format_RGB32);image.fill(QColor('red'));image.save(str(red));image.fill(QColor('blue'));image.save(str(blue));before=red.read_bytes()
        values={'default':str(red),'mode':'fill','monitors':{'DP-1':{'path':str(blue),'mode':'fill'}}};path=render_wallpaper(values,parse_xrandr(XRANDR),self.home,self.runner);result=QImage(str(path));self.assertEqual(result.pixelColor(400,300),QColor('red'));self.assertEqual(result.pixelColor(1200,300),QColor('blue'));self.assertEqual(red.read_bytes(),before);self.assertIn('--no-xinerama',(self.home/'.fehbg').read_text())
    def test_failed_wallpaper_keeps_preferences(self):
        self.env.save_section('wallpaper',{'default':'old.png'})
        with self.assertRaises(ValueError):self.env.apply_wallpaper({'default':'missing.png'})
        self.assertEqual(self.env.section('wallpaper'),{'default':'old.png'})

class UITests(Fixture):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_standalone_ipc_handles_fragmented_messages_and_disconnect(self):
        from settings_app import LocalSettingsServer
        endpoint=self.home/'settings.sock';server=LocalSettingsServer(endpoint);routes=[];server.requested.connect(routes.append)
        connection=socket.socket(socket.AF_UNIX);connection.connect(str(endpoint));connection.sendall(b'short');self.app.processEvents();self.assertEqual(routes,[])
        connection.sendall(b'cuts\n');self.app.processEvents();self.app.processEvents();self.assertEqual(routes,['shortcuts']);connection.close()
        connection=socket.socket(socket.AF_UNIX);connection.connect(str(endpoint));connection.close();self.app.processEvents();self.assertFalse(server.clients)
        self.assertEqual(endpoint.stat().st_mode&0o777,0o600);server.close();self.assertFalse(endpoint.exists());server.deleteLater();self.app.sendPostedEvents(None,QEvent.DeferredDelete)
    def test_all_sections_and_live_catalog_without_configuration_writes(self):
        with patch('settings_hub.EnvironmentSettings',lambda home:EnvironmentSettings(home,self.runner)),patch('settings_data.checked',self.runner):
            # The legacy backend's default argument is bound at import time.
            from settings_data import DesktopSettings
            with patch('settings_hub.DesktopSettings',lambda home:DesktopSettings(home,self.runner)):window=SettingsHub(test=True,home=self.home)
        window.show();self.app.processEvents()
        for job in list(window.jobs):job.wait(15000)
        self.app.processEvents();self.assertEqual(window.pages.count(),14);self.assertEqual(window.table.rowCount(),4);self.assertEqual(len(window.inventory),3)
        for route in window.routes:window.go(route);self.app.processEvents()
        for job in list(window.jobs):job.wait(15000)
        self.app.processEvents();self.assertGreater(len(window.extra_shortcuts),20);window.shortcut_scope.setCurrentText('Global');self.assertEqual(window.table.rowCount(),4);window.shortcut_search.setText('super + n');self.assertEqual(window.table.rowCount(),1)
        self.assertFalse(self.env.path.exists());self.assertEqual((self.home/'.config/sxhkd/sxhkdrc').read_text(),SHORTCUTS)
        for route in ('home','displays','bar','shortcuts','wallpaper'):
            window.go(route);self.app.processEvents();window.grab().save('/tmp/orbit-settings-'+route+'.png')
        for job in list(window.jobs):job.wait(15000)
        window.hide();window.deleteLater();self.app.sendPostedEvents(None,QEvent.DeferredDelete)

if __name__=='__main__':unittest.main(verbosity=2)
