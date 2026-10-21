import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QImage,QColor,QIcon,QKeyEvent
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
from connections_data import ssh_hosts,SSHProfiles,ssh_args,ConnectionScan
from desktop_common import vim_args,is_text_file
from desktop_v3 import OrbitV3
from data_v2 import StoreV2
from media import png_bytes
from orbit import STYLE

def wait(ms):
    until=time.monotonic()+ms/1000
    while time.monotonic()<until:QApplication.processEvents();time.sleep(.005)

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
    def test_window_selector_keeps_other_wysun_apps(self):
        import os
        from unittest.mock import patch
        rows=[
            dict(id='0xabc',title='Wysun',app='Orbit',workspace='1',focused=True,fullscreen=False,rect=[0,0,100,100],pid=os.getpid(),xwayland=False),
            dict(id='0xdef',title='Wysun Music',app='Orbit',workspace='1',focused=False,fullscreen=False,rect=[0,0,200,200],pid=os.getpid()+1,xwayland=False),
        ]
        with patch('desktop_backend.Desktop.windows',return_value=rows):
            self.w.set_mode('windows');self.w.render()
        values=[self.w.results.item(i).data(Qt.UserRole) for i in range(self.w.results.count())]
        self.assertEqual([(row['title'],row['wid']) for row in values],[('Wysun Music','0xdef')])
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
        image=QImage(40,40,QImage.Format_RGB32);image.fill(QColor('red'));ident=self.store.clip('image','Imagen',png_bytes(image));self.store.save_media(ident,'FACTURA',{},None);self.w.set_mode('clipboard');self.w.actions()
        ui=self.w.clipboard_ui;menu=ui.active_menu;titles=[action.text() for action in menu.actions() if not action.isSeparator()]
        self.assertIn('Volver a reconocer texto',titles);self.assertIn('Copiar como',titles);self.assertIn('Añadir a colección…',titles)
        self.assertFalse(any('historial' in title.casefold() or 'snippet' in title.casefold() for title in titles))
        menu.close()
        self.w.search.setText('FACTURA');wait(90);self.assertEqual(self.w.results.count(),1)
    def test_copy_color_rgb_and_text_vim_action(self):
        self.store.clip('color','F54927');self.w.set_mode('clipboard');self.w.actions()
        menu=self.w.clipboard_ui.active_menu;copy_menu=next(action.menu() for action in menu.actions() if action.text()=='Copiar como')
        next(action for action in copy_menu.actions() if action.data()=='RGB').trigger();wait(30);self.assertEqual(self.app.clipboard().text(),'rgb(245, 73, 39)')
        menu.close()
        self.store.clip('text','print("hello")');self.w.show();self.w.set_mode('clipboard');self.w.search.setText('print');wait(90)
        with patch('desktop_v3.edit_text') as edit:self.w.edit_in_vim();edit.assert_called_once_with('print("hello")')
    def test_power_independent_fits_screen_cancel_safe(self):
        self.w.show_mode('power');power=self.w.utilities['power'];self.assertFalse(self.w.isVisible());self.assertLessEqual(power.width(),power.screen().availableGeometry().width());self.assertLessEqual(power.height(),power.screen().availableGeometry().height());self.assertEqual(len(power.action_buttons),5)
        QTimer.singleShot(20,lambda:QApplication.activeModalWidget().reject())
        with patch('enhanced.run') as execute:power.trigger({'action':'shutdown','title':'Apagar'});execute.assert_not_called()
    def test_power_enter_confirmation_dispatch_and_cancel(self):
        self.w.show_mode('power');power=self.w.utilities['power'];button=power.action_buttons[-1]
        for answer in (QMessageBox.Cancel,QMessageBox.Yes):
            button.setFocus()
            QTimer.singleShot(20,lambda result=answer:QApplication.activeModalWidget().button(result).click())
            with patch('enhanced.run') as execute:
                self.app.sendEvent(button,QKeyEvent(QEvent.KeyPress,Qt.Key_Return,Qt.NoModifier))
                if answer==QMessageBox.Yes:execute.assert_called_once_with(['systemctl','poweroff']);self.assertFalse(power.isVisible())
                else:execute.assert_not_called();self.assertTrue(power.isVisible())
    def test_connections_readonly_all_tabs(self):
        for mode in ('wifi','bluetooth','vpn','saved','ssh'):
            output=[];scan=ConnectionScan(mode);scan.ready.connect(lambda m,rows,meta:output.append((m,rows,meta)));scan.run();self.assertEqual(output[0][0],mode);self.assertIsInstance(output[0][1],list)
    def test_real_app_icons_available(self):
        for name in ('system-file-manager','utilities-terminal','brave-browser'):self.assertFalse(QIcon.fromTheme(name).isNull())

if __name__=='__main__':unittest.main(verbosity=2)
