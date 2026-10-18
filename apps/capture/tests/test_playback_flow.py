"""Library playback is read-only; editing is an explicit navigation choice."""
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
        self.render_patch=patch('loomrec.ui.main.RenderJob',return_value=Mock(start=Mock(return_value=self.job)))
        self.render=self.render_patch.start()
        self.load_patch=patch.object(self.window.player,'load');self.load=self.load_patch.start()

    def tearDown(self):
        self.window.job=None;self.window.close();self.window.deleteLater();self.app.processEvents()
        self.load_patch.stop();self.render_patch.stop();self.env.stop();self.temp.cleanup()

    def complete(self):
        output=self.window.playback_path();output.touch()
        self.job.poll.return_value={'state':'done','progress':1,'output':str(output)}
        with patch.object(self.window.wave_process,'start'):self.window.poll_job()

    def test_library_opens_player_and_editor_is_explicit(self):
        w=self.window;before=self.path.read_bytes();w.items.setCurrentRow(0);w.library_open.click()
        self.assertTrue(w.viewing);self.assertEqual(w.title.text(),'Video de prueba')
        self.assertTrue(w.edit_video.isVisible());self.assertFalse(w.edit_video.isEnabled())
        for widget in (w.inspector,w.editor_timeline,w.editor_toolbar,*w.edit_actions):self.assertFalse(widget.isVisible())
        self.render.assert_called_once_with(self.path,w.playback_path(),preset='preview')
        self.complete();self.assertTrue(w.play_button.isEnabled());self.load.assert_called_once()
        with patch.object(w.player,'toggle') as toggle:w.play_button.click();toggle.assert_called_once()
        editor=w.editor;w.edit_video.click();self.assertFalse(w.viewing);self.assertIs(w.editor,editor)
        self.assertTrue(w.inspector.isVisible());self.assertTrue(w.editor_timeline.isVisible())
        w.watch_video.click();self.assertTrue(w.viewing);self.assertEqual(self.render.call_count,1)
        self.assertEqual(self.path.read_bytes(),before)

    def test_reopen_reuses_video_and_edits_invalidate_it(self):
        w=self.window;w.open_project(self.path);self.complete();cached=w.playback_path()
        w.back_library();w.open_project(self.path);self.assertEqual(self.render.call_count,1)
        self.load.assert_called_with(cached)
        w.edit_video.click();w.edit(lambda:w.editor.trim(0,1,3));w.watch_video.click()
        self.assertNotEqual(w.playback_path(),cached);self.assertEqual(self.render.call_count,2)
        self.assertEqual(w.seek.maximum(),2000);self.assertEqual(w.position,0)

    def test_viewing_shortcuts_cannot_undo_saved_edits(self):
        w=self.window;w.open_project(self.path,edit=True);w.edit(lambda:w.editor.trim(0,1,3))
        w.show_playback();self.complete();before=self.path.read_bytes();w.undo();w.redo()
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(w.editor.project.duration,2)

    def test_leaving_during_preparation_does_not_start_hidden_player(self):
        w=self.window;w.open_project(self.path);w.back_library();self.complete()
        self.load.assert_not_called();self.assertEqual(w.stack.currentWidget(),w.library_page)
        w.open_project(self.path);self.load.assert_called_once()

    def test_cancelled_preparation_can_be_retried_from_play(self):
        w=self.window;w.open_project(self.path)
        self.job.poll.return_value={'state':'cancelled','progress':0};w.poll_job()
        self.assertTrue(w.edit_video.isEnabled());self.assertTrue(w.play_button.isEnabled())
        self.job.poll.return_value={'state':'running','progress':0};w.play_button.click()
        self.assertEqual(self.render.call_count,2)

    def test_empty_project_still_offers_editor(self):
        save_project(Project(title='Vacía'),self.path);self.window.open_project(self.path)
        self.render.assert_not_called();self.assertIn('no tiene clips',self.window.preview_label.text())
        self.window.edit_video.click();self.assertFalse(self.window.viewing)

    def test_old_capture_without_status_opens_player_instead_of_hiding(self):
        import json,time
        from dataclasses import asdict
        from loomrec.capture import CaptureConfig
        config=self.path.parent/'capture.json'
        config.write_text(json.dumps(asdict(CaptureConfig(str(self.path.parent),':0',[0,0,640,360]))))
        os.utime(config,(time.time()-60,time.time()-60))
        self.window.open_project(self.path)
        self.assertTrue(self.window.isVisible());self.assertTrue(self.window.viewing)
        self.assertIsNone(self.window.session);self.render.assert_called_once()

    def test_plain_video_view_never_constructs_editor_or_renderer(self):
        path=self.library.root/'ordinary.mp4';path.write_bytes(b'owned fixture')
        with patch('loomrec.ui.main.Editor') as editor:
            self.window.open_media(path);editor.assert_not_called();self.render.assert_not_called();self.load.assert_called_once_with(path)
        self.assertTrue(self.window.viewing);self.assertIsNone(self.window.editor)

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
