import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QImage,QColor,QIcon
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
from settings_data import ShortcutFile,DesktopSettings,expand_sequence,canonical
from connections_data import ssh_hosts,SSHProfiles,ssh_args,ConnectionScan
from desktop_common import vim_args,is_text_file
from desktop_v3 import OrbitV3
from data_v2 import StoreV2
from media import png_bytes
from orbit import STYLE

def wait(ms):
    until=time.monotonic()+ms/1000
    while time.monotonic()<until:QApplication.processEvents();time.sleep(.005)

class ConfigTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def model(self,text):
        p=self.root/'sxhkdrc';p.write_text(text);return ShortcutFile(p)
    def test_shortcut_group_expansion_and_preservation(self):
        text='# inicio\nsuper + Return\n    terminal\n\n# direcciones\nsuper + {_,shift + }{Left,Right}\n    bspc node -{f,s} {west,east}\n\n# fin\n';m=self.model(text)
        self.assertEqual(len(expand_sequence(m.rows[1]['key'])),4)
        with patch('settings_data.backup_file') as backup:m.save('super + alt + Return','terminal --title test',0)
        self.assertIn(text[text.index('# direcciones'):],m.path.read_text());self.assertTrue(backup.called);self.assertIn('# inicio',m.path.read_text())
    def test_conflicts_rejected_without_write(self):
        m=self.model('super + {a,b}\n    app\n');before=m.path.read_bytes()
        with self.assertRaises(ValueError):m.save('mod4 + a','echo test')
        self.assertEqual(m.path.read_bytes(),before)
    def test_malformed_and_stale_never_overwrite(self):
        m=self.model('super + a\n    app\n');before=m.path.read_bytes()
        for key,cmd in [('super + b\nsuper + c','app'),('super + Nosuchkeysym','app'),('super + b',"echo '"),('super + {b,c}','echo {1,2,3}')]:
            with self.assertRaises(ValueError):m.save(key,cmd)
        self.assertEqual(before,m.path.read_bytes());m.path.write_text('# external\n'+m.original)
        with self.assertRaises(ValueError):m.save('super + c','app')
        self.assertTrue(m.path.read_text().startswith('# external'))
    def test_duplicate_report_from_expansion(self):
        m=self.model('super + c\n    calc\nsuper + {_,shift + }c\n    bspc node -f {next,prev}.local\n');self.assertEqual(len(m.conflicts()),1)
    def test_bspwm_persistence_and_no_restart(self):
        values={'window_gap':'12'};calls=[]
        def run(args):
            calls.append(args)
            if len(args)==3:return values.get(args[2],'false')
            if args[1]=='config':values[args[2]]=args[3]
            return ''
        m=DesktopSettings(self.root,run)
        with patch('settings_data.backup_file'):m.apply({'window_gap':'17'},[])
        self.assertEqual(values['window_gap'],'17');self.assertIn('bspc config window_gap 17',m.script.read_text());self.assertEqual(json.loads(m.path.read_text())['values']['window_gap'],'17');self.assertFalse(any('wm' in c for c in calls))
    def test_bspwm_failure_rolls_back_runtime_and_files(self):
        values={'window_gap':'12','border_width':'1'}
        def run(args):
            if len(args)==3:return values.get(args[2],'false')
            if args[2:] == ['border_width','3']:raise subprocess.CalledProcessError(1,args)
            if args[1]=='config':values[args[2]]=args[3]
            return ''
        m=DesktopSettings(self.root,run)
        with self.assertRaises(subprocess.CalledProcessError):m.apply({'window_gap':'22','border_width':'3'},[])
        self.assertEqual(values['window_gap'],'12');self.assertFalse(m.path.exists());self.assertFalse(m.script.exists())
    def test_bspwm_invalid_color_and_rule_blocked(self):
        m=DesktopSettings(self.root,lambda _: '0')
        for values,rules in [({'window_gap':'999'},[]),({'focused_border_color':'$(touch /tmp/unsafe)'},[]),({},[dict(__class='Code',**{'class':'Code;exit','state':'floating'})])]:
            with self.assertRaises(ValueError):m.apply(values,rules)
        self.assertFalse(m.path.exists())

class IntegrationDataTests(unittest.TestCase):
    def test_ssh_includes_profiles_and_option_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'more').write_text('Host staging\n HostName staging.local\n User deploy\n Port 2222\n');(root/'config').write_text('Include more\nHost prod\n HostName prod.local\nMatch exec "touch /tmp/never-execute-orbit"\n User wrong\nHost *\n User shared\n')
            rows=ssh_hosts(root/'config');self.assertEqual([r['alias'] for r in rows],['staging','prod']);self.assertEqual(rows[0]['user'],'deploy');self.assertEqual(rows[1]['user'],'');self.assertNotIn('wrong',str(rows))
            store=SSHProfiles(root/'ssh.json');store.save({'name':'Local','host':'localhost','user':'nicolas','port':2222});self.assertEqual(store.saved()[0]['port'],2222);self.assertEqual((root/'ssh.json').stat().st_mode&0o777,0o600)
            with self.assertRaises(ValueError):store.save({'name':'Bad','host':'-oProxyCommand=bad','port':22})
            with patch('connections_data.terminal_args',side_effect=lambda args,title:args):args=ssh_args(store.saved()[0]);self.assertEqual(args,['ssh','-p','2222','-l','nicolas','--','localhost'])
    def test_vim_paths_are_separate_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'space $(unsafe).py';path.write_text('print("hello")');args=vim_args(path);self.assertEqual(args[-2:],['--',str(path)]);self.assertTrue(is_text_file(path));binary=Path(tmp)/'binary';binary.write_bytes(b'a\0b');self.assertFalse(is_text_file(binary))

class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion');cls.app.setStyleSheet(STYLE);QIcon.setThemeSearchPaths([str(Path.home()/'.local/share/icons'),'/usr/share/icons']);QIcon.setThemeName('Win11-Dark');QIcon.setFallbackThemeName('Adwaita')
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=StoreV2(self.tmp.name);self.w=OrbitV3(self.store,test=True);self.w.show();self.app.processEvents()
    def tearDown(self):
        self.w.status_timer.stop();self.w.debounce.stop();self.w.prune_timer.stop()
        for window in self.w.utilities.values():
            for job in list(getattr(window,'jobs',[])):job.wait(15000)
            if hasattr(window,'periodic'):window.periodic.stop()
            if getattr(window,'scan',None):window.scan.wait(6000)
            window.hide();window.deleteLater()
        for job in self.w.jobs:
            job.wait(6000)
        if getattr(self.w,'popup',None):self.w.popup.hide()
        self.w.hide();self.w.deleteLater();self.app.sendPostedEvents(None,QEvent.DeferredDelete);self.store.db.close();self.tmp.cleanup()
    def test_image_actions_are_only_contextual(self):
        image=QImage(40,40,QImage.Format_RGB32);image.fill(QColor('red'));ident=self.store.clip('image','Imagen',png_bytes(image));self.store.save_media(ident,'FACTURA',{},None);self.w.set_mode('clipboard');self.w.actions();titles=[self.w.popup.list.item(i).data(Qt.UserRole)['title'] for i in range(self.w.popup.list.count())];self.assertEqual(len(titles),7);self.assertFalse(any('reconocido' in x or 'snippet' in x or 'historial' in x for x in titles));self.assertLess(self.w.popup.height(),285)
        self.w.popup.hide();self.w.search.setText('FACTURA');wait(90);self.assertEqual(self.w.results.count(),1)
    def test_copy_color_rgb_and_text_vim_action(self):
        self.store.clip('color','F54927');self.w.set_mode('clipboard');self.w.actions();self.w.popup.search.setText('RGB');self.w.popup.choose();wait(30);self.assertEqual(self.app.clipboard().text(),'rgb(245, 73, 39)')
        self.store.clip('text','print("hello")');self.w.show();self.w.set_mode('clipboard');self.w.search.setText('print');wait(90)
        with patch('desktop_v3.edit_text') as edit:self.w.edit_in_vim();edit.assert_called_once_with('print("hello")')
    def test_power_independent_compact_cancel_safe(self):
        self.w.show_mode('power');power=self.w.utilities['power'];self.assertFalse(self.w.isVisible());self.assertLess(power.width(),500);self.assertLess(power.height(),380)
        QTimer.singleShot(20,lambda:QApplication.activeModalWidget().reject())
        with patch('enhanced.run') as execute:power.trigger({'action':'shutdown','title':'Apagar'});execute.assert_not_called()
    def test_settings_reads_real_bindings_without_applying(self):
        before=(Path.home()/'.config/sxhkd/sxhkdrc').read_bytes();self.w.show_mode('settings');settings=self.w.utilities['settings'];self.assertGreater(len(settings.shortcuts.rows),40);settings.go('shortcuts');settings.shortcut_search.setText('super + n');self.assertGreater(settings.table.rowCount(),0);self.assertEqual(before,(Path.home()/'.config/sxhkd/sxhkdrc').read_bytes());self.assertFalse(self.w.isVisible())
    def test_connections_readonly_all_tabs(self):
        for mode in ('wifi','bluetooth','vpn','saved','ssh'):
            output=[];scan=ConnectionScan(mode);scan.ready.connect(lambda m,rows,meta:output.append((m,rows,meta)));scan.run();self.assertEqual(output[0][0],mode);self.assertIsInstance(output[0][1],list)
    def test_real_app_icons_available(self):
        for name in ('system-file-manager','utilities-terminal','brave-browser'):self.assertFalse(QIcon.fromTheme(name).isNull())

if __name__=='__main__':unittest.main(verbosity=2)
