"""Library playback is watch-only: an MP4 plays, a recording without one is prepared."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from loomrec.library import Library
from loomrec.schema import Project,Source,Clip,save_project
from loomrec.ui.main import Window


class PlaybackFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'XDG_STATE_HOME':self.temp.name,'XDG_CONFIG_HOME':self.temp.name});self.env.start()
        self.library=Library(self.temp.name);self.path=self.library.new_directory()/'project.json'
        save_project(Project(title='Video de prueba',sources=[Source('s','synthetic.mkv',duration=4)],clips=[Clip('s',0,4)]),self.path)
        self.window=Window(self.library,False);self.window.timer.stop();self.window.show()
        self.job=Mock();self.job.poll.return_value={'state':'running','progress':0}
        self.render_patch=patch('loomrec.render.RenderJob',return_value=Mock(start=Mock(return_value=self.job)))
        self.render=self.render_patch.start()
        self.load_patch=patch.object(self.window.player,'load');self.load=self.load_patch.start()

    def tearDown(self):
        self.window.job=None;self.window.close();self.window.deleteLater();self.app.processEvents()
        self.load_patch.stop();self.render_patch.stop();self.env.stop();self.temp.cleanup()

    def test_plain_video_plays_without_renderer(self):
        path=self.library.root/'ordinary.mp4';path.write_bytes(b'owned fixture')
        self.window.open_media(path);self.render.assert_not_called();self.load.assert_called_once_with(path)
        self.assertIs(self.window.stack.currentWidget(),self.window.editor_page);self.assertEqual(self.window.title.text(),'ordinary')

    def test_old_capture_without_mp4_prepares_it_instead_of_editing(self):
        import json,time
        from dataclasses import asdict
        from loomrec.capture import CaptureConfig
        config=self.path.parent/'capture.json'
        config.write_text(json.dumps(asdict(CaptureConfig(str(self.path.parent),':0',[0,0,640,360]))))
        os.utime(config,(time.time()-60,time.time()-60))
        with patch.object(self.window,'retry_finalization') as retry:self.window.open_project(self.path)
        retry.assert_called_once();self.render.assert_not_called();self.load.assert_not_called()
        self.assertIs(self.window.stack.currentWidget(),self.window.library_page);self.assertIsNone(self.window.session)

    def test_project_that_is_not_a_recording_reports_missing_mp4(self):
        with patch.object(self.window,'error') as error:
            self.window.items.setCurrentRow(0);self.window.open_selected()
        self.assertIn('MP4',error.call_args.args[0]);self.render.assert_not_called();self.load.assert_not_called()

    def test_new_recording_buttons_route_to_quickbar(self):
        from loomrec.ui.components import SoftButton
        w=self.window
        with patch.object(w,'activate_instance') as activate:
            for page in [w.library_page,w.settings_page]:
                button=next(b for b in page.findChildren(SoftButton) if b.text()=='Nueva grabación');button.click()
            self.assertEqual([c.args for c in activate.call_args_list],[('quick',),('quick',)])

    def test_library_search_keeps_space_and_arrows_for_text(self):
        from PySide6.QtCore import Qt,QEvent
        from PySide6.QtGui import QKeyEvent
        w=self.window;w.stack.setCurrentWidget(w.library_page);w.search.setFocus();self.app.processEvents()
        with patch.object(w.player,'toggle') as toggle:
            self.app.sendEvent(w.search,QKeyEvent(QEvent.KeyPress,Qt.Key_Space,Qt.NoModifier,' '))
            self.assertEqual(w.search.text(),' ');toggle.assert_not_called()

    def test_capture_waits_for_background_media_release(self):
        w=self.window;w.active_metadata=1;w.capture_pending=True;callbacks=[]
        with patch('loomrec.ui.main.QTimer.singleShot',side_effect=lambda _,fn:callbacks.append(fn)),patch('loomrec.ui.main.CaptureSession') as capture:
            w.start_capture();capture.assert_not_called();self.assertEqual(len(callbacks),1)
        w.capture_pending=False;w.active_metadata=0

    def test_manual_region_updates_are_coalesced(self):
        w=self.window;w.stack.setCurrentWidget(w.setup_page);w.capture_modes.buttons()[1].setChecked(True)
        with patch.object(w.recording_indicator,'select') as selected:
            w.rect[0].setValue(10);w.rect[1].setValue(20);w.rect[2].setValue(320);w.rect[3].setValue(180)
            self.app.processEvents();self.assertEqual(selected.call_count,1);self.assertEqual(selected.call_args.args[0],[10,20,320,180])


    def test_idle_region_indicator_mode_dismiss_and_reopen(self):
        w=self.window;w.stack.setCurrentWidget(w.setup_page)
        for spin,value in zip(w.rect,[10,20,320,180]):spin.setValue(value)
        w.capture_modes.buttons()[1].setChecked(True);self.app.processEvents()
        self.assertEqual(w.recording_indicator.state,'selected')
        w.monitor.addItem('Synthetic',[0,0,640,480]);w.monitor_changed();self.app.processEvents()
        self.assertNotEqual(w.recording_indicator.state,'selected');self.assertFalse(w.recording_indicator.windows)
        w.capture_modes.buttons()[1].setChecked(True);self.app.processEvents();self.assertEqual(w.recording_indicator.state,'selected')
        w.selection_timer.start();w.hide();self.app.processEvents()
        self.assertFalse(w.recording_indicator.windows)
        w.show();self.app.processEvents();self.assertEqual(w.recording_indicator.state,'selected')
        w.stack.setCurrentWidget(w.library_page);self.app.processEvents();self.assertFalse(w.recording_indicator.windows)
        w.quick.present();self.app.processEvents();self.assertEqual(w.recording_indicator.state,'selected')
        w.selection_timer.start();w.quick.hide_all();self.app.processEvents();self.assertFalse(w.recording_indicator.windows)
        w.capture_pending=True
        with patch.object(w.recording_indicator,'hide') as hide:w.selection_feedback();hide.assert_not_called()
        w.capture_pending=False
