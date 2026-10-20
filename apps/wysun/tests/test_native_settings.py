import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QMimeData,QUrl,QObject,QByteArray
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from hypr_settings import inventory,display_command,HyprShortcutFile,script,lua
from clipboard_mime import from_packet,encode,restore

APP=QApplication.instance() or QApplication([])

class NativeSettingsTests(unittest.TestCase):
    def test_display_scale_negative_and_hotplug_modes(self):
        monitors=[dict(name='DP-1',width=1920,height=1080,x=-1280,y=0,scale=1.5,refreshRate=60,availableModes=['1920x1080@60.00Hz'],focused=True)]
        rows=inventory(lambda _:json.dumps(monitors));self.assertEqual(rows[0]['width'],1280)
        from environment_settings import display_plan
        plan=display_plan(rows);self.assertEqual(plan[0]['scale'],1.5)
        cmd=display_command(plan,rows);self.assertEqual(cmd[:2],['hyprctl','eval']);self.assertIn('-1280x0',cmd[-1]);self.assertIn('1.5',cmd[-1])
        with self.assertRaises(ValueError):display_command(plan,[])
    def test_display_trial_reject_restores_native_plan(self):
        from environment_settings import EnvironmentSettings,DisplayTrial
        monitors=[dict(name='DP-1',width=800,height=600,x=0,y=0,scale=1,refreshRate=60,availableModes=['800x600@60.00Hz'],focused=True),
                  dict(name='DP-2',width=800,height=600,x=800,y=0,scale=1,refreshRate=60,availableModes=['800x600@60.00Hz'],focused=False)]
        calls=[]
        def runner(args):
            calls.append(args)
            return json.dumps(monitors) if args[:3]==['hyprctl','-j','monitors'] else 'ok'
        with tempfile.TemporaryDirectory() as home,patch.dict(os.environ,{'WAYLAND_DISPLAY':'unit','HYPRLAND_INSTANCE_SIGNATURE':'unit'}),patch('environment_settings.subprocess.Popen'):
            backend=EnvironmentSettings(home,runner=runner)
            from environment_settings import display_plan
            # Swapped order (DP-2 dragged to the left, overlapping): applied edge to edge.
            old=display_plan(inventory(runner));changed=[dict(old[0],x=400),dict(old[1],x=-100)]
            trial=DisplayTrial(backend,changed);trial.reject()
            cmds=[c for c in calls if c[:2]==['hyprctl','eval'] and 'hl.monitor(' in c[-1]]
            self.assertTrue(any(c[:2]==['hyprctl','eval'] and 'hl.workspace_rule' in c[-1] for c in calls))  # re-pinned after revert
            self.assertIn('["output"] = "DP-1", ["mode"] = "800x600@60.00", ["position"] = "800x0"',cmds[0][-1])
            self.assertIn('["output"] = "DP-1", ["mode"] = "800x600@60.00", ["position"] = "0x0"',cmds[-1][-1]);self.assertTrue((trial.folder/'reverted').exists())
    def test_bindings_preserve_user_config_and_reject_foreign_conflict(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home);(root/'.config/hypr').mkdir(parents=True);user=root/'.config/hypr/hyprland.lua';user.write_text('-- user unchanged\n')
            runner=Mock(side_effect=lambda a:json.dumps([dict(modmask=64,key='Return')]) if a[-1]=='binds' else 'ok')
            model=HyprShortcutFile(root,runner)
            with self.assertRaisesRegex(ValueError,'compositor'):model.save('super + Return','true')
            model.save('super + alt + j','printf test',title='Own')
            self.assertIn('hl.bind',model.script.read_text());self.assertEqual(user.read_text(),'-- user unchanged\n')
            model.delete(0);self.assertEqual(json.loads(model.path.read_text()),[])
    def test_lua_string_escaping_and_only_owned_rule_handles(self):
        value='x" .. os.execute("bad") .. "'
        self.assertEqual(lua(value),json.dumps(value))
        with self.assertRaises(ValueError):lua('line\nexec')
        text=script({'border_width':'2'},[{'class':'test','state':'floating','border':False}])
        self.assertIn('wysun_window_rules',text);self.assertIn('set_enabled(false)',text);self.assertNotIn('bspc',text)
    def test_clipboard_rich_text_and_uri_roundtrip(self):
        packet={'formats':{'text/plain':base64.b64encode('Prueba'.encode()).decode(),'text/html':base64.b64encode(b'<b>Prueba</b>').decode(),'text/uri-list':base64.b64encode(b'file:///tmp/own%20file.txt\r\n').decode(),'x-special/gnome-copied-files':base64.b64encode(b'cut\nfile:///tmp/own%20file.txt').decode()}}
        mime=from_packet(packet);saved=encode(mime);copied=restore(saved)
        self.assertEqual(copied.html(),'<b>Prueba</b>');self.assertEqual(copied.urls()[0].toLocalFile(),'/tmp/own file.txt')
        self.assertTrue(bytes(copied.data('x-special/gnome-copied-files')).startswith(b'copy\n'))
    def test_clipboard_png_bounds_and_sensitive_mime(self):
        from PySide6.QtCore import QBuffer,QIODevice
        image=QImage(32,20,QImage.Format_ARGB32);image.fill(QColor('red'));data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG')
        mime=from_packet({'formats':{'image/png':base64.b64encode(bytes(data)).decode()}})
        self.assertTrue(mime.hasImage());self.assertEqual(mime.imageData().pixelColor(0,0),QColor('red'))
        with self.assertRaises(ValueError):from_packet({'formats':{'password-manager':base64.b64encode(b'x').decode()}})
        with self.assertRaises(ValueError):from_packet({'formats':{'text/plain':base64.b64encode(b'api_key=synthetic').decode()}})
    def test_wl_paste_slow_offer_is_killed_at_deadline(self):
        import wayland_clipboard as clip
        real_popen=subprocess.Popen;processes=[]
        def owned(*args,**kwargs):
            proc=real_popen([sys.executable,'-c','import time; time.sleep(5)'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);processes.append(proc);return proc
        with patch.object(clip.subprocess,'Popen',side_effect=owned):
            with self.assertRaises(TimeoutError):clip.read_offer('text/plain',timeout=.03)
        self.assertIsNotNone(processes[0].poll())
    def test_split_ratio_uses_actual_default_split_ratio(self):
        from hypr_settings import config,HyprDesktopSettings
        self.assertEqual(config({'split_ratio':'.5'}),{'dwindle':{'default_split_ratio':1.0}})
        with tempfile.TemporaryDirectory() as home:
            model=HyprDesktopSettings(home,lambda _:json.dumps({'float':1.2}))
            self.assertEqual(float(model.values['split_ratio']),.6)
    def test_rule_only_save_does_not_override_live_theme_or_spacing(self):
        from hypr_settings import HyprDesktopSettings
        with tempfile.TemporaryDirectory() as home:
            calls=[]
            def runner(args):
                calls.append(args)
                if args[:3]==['hyprctl','-j','getoption']:
                    if 'col.' in args[-1]:return json.dumps({'gradient':'rgb(123456) 0deg'})
                    if args[-1]=='general:gaps_in':return json.dumps({'css':'7 7 7 7'})
                    if args[-1]=='dwindle:default_split_ratio':return json.dumps({'float':1.0})
                    return json.dumps({'int':2})
                return 'ok'
            model=HyprDesktopSettings(home,runner);self.assertEqual(model.values['window_gap'],'7');self.assertEqual(model.values['focused_border_color'],'#123456')
            model.apply(dict(model.values),[dict(**{'class':'own'},state='floating',border=True)])
            generated=model.script.read_text();self.assertNotIn('active_border',generated);self.assertNotIn('gaps_in',generated);self.assertNotIn('border_size',generated)
            self.assertEqual(json.loads(model.path.read_text())['overrides'],{})
    def test_native_bar_and_theme_with_xdg_outside_home(self):
        from environment_settings import EnvironmentSettings
        from theme_runtime import apply_theme
        from theme_tokens import theme_id,invalidate
        from ui_appearance import save_appearance,read_appearance
        with tempfile.TemporaryDirectory() as home,tempfile.TemporaryDirectory() as xdg,patch.dict(os.environ,{'HOME':home,'XDG_CONFIG_HOME':xdg,'WAYLAND_DISPLAY':'fixture','ORBIT_THEME':''}):
            native=Path(xdg)/'orbit/hypr-bar.json';native.parent.mkdir(parents=True);native.write_text(json.dumps({'height':40,'background':'#101118','opacity':65}))
            calls=[]
            def runner(args):
                calls.append(args)
                if args[:3]==['hyprctl','-j','getoption']:return json.dumps({'gradient':'rgb(112233)'})
                if args[:3]==['hyprctl','-j','monitors']:return json.dumps([dict(name='FIXTURE',width=800,height=600,scale=1,refreshRate=60,availableModes=['800x600@60.00Hz'])])
                return 'ok'
            model=EnvironmentSettings(runner=runner);values=model.bar_values();self.assertEqual(values['height'],40)
            values.update(left=['orbit'],center=['title'],right=['date','tray'],monitors={'DP-1':True},tray_monitor='DP-1')
            model.apply_bar(values);native=Path(xdg)/'orbit/hypr-bar.json'
            self.assertEqual(json.loads(native.read_text())['height'],40)
            wallpaper=Path(home)/'.local/share/backgrounds/tokyo.png';wallpaper.parent.mkdir(parents=True);image=QImage(32,20,QImage.Format_ARGB32);image.fill(QColor('red'));image.save(str(wallpaper),'PNG')
            result=apply_theme(Path.home(),'tokyo',runner)
            self.assertTrue(Path(result['backup']).is_dir())
            # Theme colours are no longer copied into the bar file: the bar follows the theme.
            saved=json.loads(native.read_text());self.assertNotIn('background',saved);self.assertEqual(saved['monitors'],{'DP-1':True})
            self.assertTrue((Path(xdg)/'orbit/environment.json').exists());self.assertFalse((Path(home)/'.config').exists())
            invalidate();self.assertEqual(theme_id(Path.home()),'space-black:tokyo')
            save_appearance({'opacity':77,'reduced_motion':True},Path.home());self.assertEqual(read_appearance()['opacity'],77)
            self.assertIn(['wysun','shell','reload-preferences'],calls);self.assertFalse(any('bspc' in c or 'desktop-bar' in str(c) for c in calls))
    def test_first_fragment_runtime_error_rolls_back_files_and_partial_bindings(self):
        with tempfile.TemporaryDirectory() as home:
            calls=[]
            def runner(args):
                calls.append(args)
                if args[-1]=='binds':return '[]'
                if 'hl.bind' in args[-1]:return 'fixture Lua error after bind'
                return 'ok'
            model=HyprShortcutFile(home,runner)
            with self.assertRaisesRegex(RuntimeError,'fixture Lua error'):model.save('super + j','true')
            self.assertFalse(model.script.exists());self.assertFalse(model.path.exists())
            self.assertIn('bind:remove()',calls[-1][-1])
    def test_fragment_write_error_never_changes_runtime(self):
        from hypr_settings import apply_fragment
        with tempfile.TemporaryDirectory() as home:
            root=Path(home);one=root/'one';two=root/'two';one.write_text('before')
            import settings_data
            real=settings_data.atomic_write
            def write(path,text):
                if path==two:raise OSError('fixture full disk')
                real(path,text)
            runner=Mock()
            with patch.object(settings_data,'atomic_write',side_effect=write):
                with self.assertRaises(OSError):apply_fragment(runner,{one:'after',two:'new'},'new runtime','old runtime')
            runner.assert_not_called();self.assertEqual(one.read_text(),'before');self.assertFalse(two.exists())
    def test_effects_observe_live_state_and_prepare_rollback(self):
        from hypr_settings import effects_state
        options={'decoration:rounding':10,'decoration:shadow.enabled':True,'decoration:shadow.range':16,'decoration:shadow.color':'rgba(00000080)','decoration:blur.enabled':False,'decoration:blur.size':3}
        animation=[dict(name=n,enabled=True,speed=2.5,bezier='default',style='') for n in ('windows','fade','windowsIn')]
        def runner(args):return json.dumps([animation,[]]) if args[-1]=='animations' else json.dumps({'str':options[args[-1]]})
        state,rollback=effects_state(runner)
        self.assertFalse(state['blur-background']);self.assertEqual(state['corner-radius'],10);self.assertEqual(state['duration'],250)
        self.assertIn('windowsIn',rollback);self.assertIn('false',rollback)
    def test_theme_watcher_observes_atomic_replace_and_late_creation(self):
        from PySide6.QtCore import QEventLoop,QTimer
        def wait(ms):
            loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
        import theme_tokens
        with tempfile.TemporaryDirectory() as home,patch.dict(os.environ,{'HOME':home,'XDG_CONFIG_HOME':home+'/config','ORBIT_THEME':''}),patch.object(theme_tokens,'refresh_widgets') as refresh:
            previous=getattr(APP,'orbitThemeWatcher',None)
            if previous is not None:del APP.orbitThemeWatcher
            theme_tokens.invalidate();theme_tokens.watch_theme();watcher=APP.orbitThemeWatcher
            try:
                path=Path(home)/'config/orbit/theme.json';path.parent.mkdir(parents=True);path.write_text('{"id":"tokyo"}')
                wait(120);self.assertEqual(watcher.key,'space-black:tokyo');self.assertEqual(refresh.call_count,1)
                alternate=path.with_suffix('.new');alternate.write_text('{"id":"space-black"}');alternate.replace(path)
                wait(120);self.assertEqual(watcher.key,'space-black:space-black');self.assertEqual(refresh.call_count,2)
                wait(100);self.assertEqual(refresh.call_count,2);self.assertFalse(watcher.timer.isActive())
            finally:
                watcher.deleteLater();del APP.orbitThemeWatcher
                if previous is not None:APP.orbitThemeWatcher=previous
                theme_tokens.invalidate()
    def test_large_watch_offer_is_drained_before_rereading_formats(self):
        import threading
        import wayland_clipboard as clip
        read,write=os.pipe();data=b'x'*(256*1024);done=[]
        def source():
            try:
                remaining=memoryview(data)
                while remaining:remaining=remaining[os.write(write,remaining):]
                done.append(True)
            finally:os.close(write)
        thread=threading.Thread(target=source,daemon=True);thread.start()
        try:clip.drain_watch_offer(read,timeout=1);thread.join(timeout=1);self.assertEqual(done,[True])
        finally:os.close(read)
        with patch.object(clip,'drain_watch_offer') as drain,patch.object(clip.subprocess,'check_output',return_value='text/plain'),patch.object(clip,'read_offer',return_value=b'own fixture'),patch('builtins.print'):
            clip.snapshot();drain.assert_called_once()
    def test_libmpv_distribution_copies_are_identical(self):
        root=Path(__file__).resolve().parents[3]
        self.assertEqual((root/'apps/wysun/mpv_embed.py').read_bytes(),(root/'apps/capture/loomrec/ui/mpv_embed.py').read_bytes())

if __name__=='__main__':unittest.main()
