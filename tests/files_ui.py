"""Real model/worker integration checks using disposable files only."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
if not (root/'apps/orbit').is_dir():root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'apps/orbit'))
from PySide6.QtCore import QItemSelectionModel, QUrl, QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication
from files_window import FilesWindow
from files_app import local_paths


def wait_for(predicate, timeout=4):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        QApplication.processEvents()
        if predicate():return
        time.sleep(.01)
    raise AssertionError('Timeout waiting for Qt model or worker')


class FilesUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=tempfile.TemporaryDirectory()
        cls.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':cls.config.name})
        cls.env.start();cls.app=QApplication.instance() or QApplication([])
    @classmethod
    def tearDownClass(cls):
        cls.app.clipboard().clear();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);cls.env.stop();cls.config.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        (self.base/'alpha.txt').write_text('unchanged source')
        (self.base/'destination').mkdir();(self.base/'.hidden').write_text('hidden')
        self.w=FilesWindow([str(self.base)]);self.w.show()
        wait_for(lambda:self.w.current().model.rowCount(self.w.current().model.index(str(self.base)))>=2)
    def tearDown(self):
        wait_for(lambda:not self.w.jobs and self.w.inline_preview.job is None and not self.w.inline_preview.timer.isActive())
        self.w.close();self.w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);QApplication.processEvents();self.temp.cleanup()
    def select(self,path):
        tab=self.w.current();index=tab.model.index(str(path))
        tab.view().selectionModel().select(index,QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)
    def test_navigation_tabs_and_history(self):
        self.w.navigate(str(self.base/'destination'));self.assertEqual(self.w.current().path,str(self.base/'destination'))
        self.w.current().go(-1);self.assertEqual(self.w.current().path,str(self.base))
        self.w.new_tab(str(self.base/'destination'));self.assertEqual(self.w.tabs.count(),2)
        self.w.close_tab(1);self.assertEqual(self.w.current().path,str(self.base))
    def test_copy_paste_and_move(self):
        self.select(self.base/'alpha.txt');self.w.copy()
        self.w.navigate(str(self.base/'destination'));self.w.paste()
        wait_for(lambda:not self.w.jobs)
        self.assertEqual((self.base/'destination/alpha.txt').read_text(),'unchanged source')
        self.assertTrue((self.base/'alpha.txt').exists())
        self.w.operation('rename',[str(self.base/'destination/alpha.txt')],str(self.base/'destination/beta.txt'))
        wait_for(lambda:not self.w.jobs)
        self.assertTrue((self.base/'destination/beta.txt').exists())
    def test_filter_hidden_grid(self):
        self.w.set_grid(True);self.assertIs(self.w.current().view(),self.w.current().grid)
        self.w.filter_edit.setText('alpha')
        wait_for(lambda:self.w.current().model.rowCount(self.w.current().model.index(str(self.base)))<=2)
        self.w.filter_edit.clear();self.w.toggle_hidden()
        self.assertEqual(self.w.hidden_button.isChecked(),self.w.hidden)
    def test_mkdir_worker(self):
        self.w.operation('mkdir',[],str(self.base/'new'));wait_for(lambda:not self.w.jobs)
        self.assertTrue((self.base/'new').is_dir())
    def test_finder_navigation_and_optional_inspector(self):
        self.assertFalse(self.w.inspector.isVisible())
        self.assertFalse(self.w.tabs.tabBar().isVisible())
        self.w.focus_path();self.assertTrue(self.w.path_edit.isVisible())
        self.w.path_edit.setText(str(self.base/'destination'));self.w.enter_path()
        self.assertEqual(self.w.current().path,str(self.base/'destination'))
        self.assertFalse(self.w.path_edit.isVisible())
        self.w.new_tab(str(self.base));self.assertTrue(self.w.tabs.tabBar().isVisible())
        self.w.details_button.setChecked(True);self.w.toggle_inspector()
        self.assertFalse(self.w.inspector.isVisible())
    def test_image_thumbnail_worker(self):
        from PySide6.QtGui import QImage, QColor
        image=QImage(64,48,QImage.Format_RGB32);image.fill(QColor('#1266bb'))
        path=self.base/'preview.png';image.save(str(path))
        cache=self.w.current().model.thumbnails
        cache.get(str(path));wait_for(lambda:cache.get(str(path)) is not None)
        self.assertFalse(cache.get(str(path)).isNull())
    def test_view_switch_preserves_selection(self):
        self.select(self.base/'alpha.txt')
        self.w.set_grid(True)
        tab=self.w.current()
        self.assertIs(tab.grid.selectionModel(),tab.tree.selectionModel())
        self.assertEqual(tab.model.fileName(tab.grid.selectionModel().selectedRows()[0]),'alpha.txt')
        self.w.set_grid(False)
        self.assertEqual(len(tab.tree.selectionModel().selectedRows()),1)
    def test_fluent_text_contrast(self):
        from files_visuals import COLORS
        def luminance(value):
            channels=[int(value[i:i+2],16)/255 for i in (1,3,5)]
            linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in channels]
            return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
        for foreground,background in [('text','surface'),('muted','mica'),('selected_text','selected'),('paper','accent')]:
            values=sorted([luminance(COLORS[foreground]),luminance(COLORS[background])])
            self.assertGreaterEqual((values[1]+.05)/(values[0]+.05),4.5)
    def test_reduced_motion_feedback(self):
        from files_motion import SoftButton
        button=SoftButton('Test')
        with patch.dict(os.environ,{'ORBIT_REDUCED_MOTION':'1'}):
            button._tween(button._hover_animation,'_soft_hover',1.0,180)
            self.assertEqual(button._soft_hover,1.0)
            self.assertEqual(button._hover_animation.state().name,'Stopped')
        button.deleteLater()
    def test_automatic_preview_and_stale_selection(self):
        from PySide6.QtGui import QImage,QColor
        image=QImage(120,80,QImage.Format_RGB32);image.fill(QColor('#286acc'))
        path=self.base/'photo.png';image.save(str(path))
        wait_for(lambda:self.w.current().model.index(str(path)).isValid())
        self.select(path)
        self.assertTrue(self.w.inspector.isVisible())
        wait_for(lambda:self.w.inline_preview.image is not None)
        self.assertEqual(self.w.inline_preview.image.width(),120)
        self.select(self.base/'alpha.txt')
        self.assertEqual(self.w.inline_preview.path,str(self.base/'alpha.txt'))
        wait_for(lambda:self.w.inline_preview.job is None)
        self.assertIsNone(self.w.inline_preview.image)
    def test_breadcrumb_double_click_copies_without_navigation(self):
        from files_inspector import BreadcrumbButton
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QPointF
        control=self.w.pathbar.findChildren(BreadcrumbButton)[0]
        control.click()
        event=QMouseEvent(QEvent.MouseButtonDblClick,QPointF(5,5),QPointF(5,5),Qt.LeftButton,Qt.LeftButton,Qt.NoModifier)
        control.mouseDoubleClickEvent(event)
        self.assertFalse(control.timer.isActive())
        self.assertEqual(self.app.clipboard().text(),str(self.base))
        self.assertEqual(self.w.current().path,str(self.base))
    def test_panel_hides_for_unhelpful_selections(self):
        from files_inspector import SelectionPreview
        for name in ('destination','.hidden'):
            self.select(self.base/name)
            self.assertFalse(self.w.inspector.isVisible())
        self.w.current().view().clearSelection()
        self.assertFalse(self.w.inspector.isVisible())
        self.assertFalse(SelectionPreview.supported(str(self.base/'missing.png')))
        (self.base/'broken.png').symlink_to(self.base/'missing.png')
        self.assertFalse(SelectionPreview.supported(str(self.base/'broken.png')))
    def test_zoom_wheel_and_reset(self):
        from files_zoom import ZoomCanvas
        from PySide6.QtGui import QImage,QWheelEvent
        from PySide6.QtCore import QPoint,QPointF
        canvas=ZoomCanvas();canvas.resize(300,200)
        canvas.set_image(QImage(200,100,QImage.Format_RGB32))
        event=QWheelEvent(QPointF(100,80),QPointF(100,80),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
        canvas.wheelEvent(event);self.assertGreater(canvas.zoom,1.)
        canvas.zoom_at(1000,QPointF(100,80));self.assertEqual(canvas.zoom,12.)
        canvas.reset_zoom();self.assertEqual(canvas.zoom,1.);self.assertTrue(canvas.offset.isNull())
    def test_sort_grid_both_directions(self):
        (self.base/'zeta.txt').write_text('z')
        tab=self.w.current();wait_for(lambda:tab.model.index(str(self.base/'zeta.txt')).isValid())
        self.w.set_grid(True)
        for order in (Qt.AscendingOrder,Qt.DescendingOrder):
            self.w.apply_sort(0,order)
            root=tab.model.index(str(self.base))
            def names():return [tab.model.fileName(tab.model.index(row,0,root)) for row in range(tab.model.rowCount(root)) if tab.model.fileName(tab.model.index(row,0,root)) in ('alpha.txt','zeta.txt')]
            wait_for(lambda:names()==sorted(names(),reverse=order==Qt.DescendingOrder))
            self.assertEqual(names(),sorted(names(),reverse=order==Qt.DescendingOrder))
            self.assertEqual(tab.tree.header().sortIndicatorOrder(),order)
    def test_pdf_uses_browser_not_mime_handler(self):
        pdf=self.base/'document with spaces.pdf';pdf.write_bytes(b'%PDF-1.4')
        with patch('files_browser.open_pdf') as browser,patch('files_window.QDesktopServices.openUrl') as desktop:
            self.w.open_path(str(pdf));browser.assert_called_once_with(str(pdf));desktop.assert_not_called()

    def test_text_preview_is_readonly_and_literal(self):
        path=self.base/'alpha.txt';path.write_text('<script>literal text</script>')
        self.select(path)
        preview=self.w.inline_preview
        wait_for(lambda:preview.text.isVisible() and preview.job is None)
        self.assertTrue(preview.text.isReadOnly())
        self.assertEqual(preview.text.toPlainText(),'<script>literal text</script>')
        self.assertFalse(preview.canvas.isVisible())
    def test_media_lifecycle_and_fullscreen(self):
        path=self.base/'test.mp4';path.write_bytes(b'fixture')
        wait_for(lambda:self.w.current().model.index(str(path)).isValid())
        self.select(path);preview=self.w.inline_preview;player=preview.player
        self.assertIsNotNone(player)
        player.set_fullscreen(True);QApplication.processEvents()
        self.assertTrue(self.w.isFullScreen());self.assertFalse(self.w.toolbar.isVisible())
        self.w.cancel_path();QApplication.processEvents()
        self.assertFalse(player.fullscreen);self.assertTrue(self.w.toolbar.isVisible())
        self.select(self.base/'destination')
        self.assertTrue(player.stopped);self.assertIsNone(preview.player)
        self.assertFalse(self.w.inspector.isVisible())
    def test_audio_has_controls_without_video_surface(self):
        path=self.base/'test.wav';path.write_bytes(b'fixture')
        wait_for(lambda:self.w.current().model.index(str(path)).isValid())
        self.select(path);player=self.w.inline_preview.player
        self.assertIsNotNone(player);self.assertTrue(player.surface.isHidden());self.assertTrue(player.full_button.isHidden())
        self.w.close_inspector();self.assertTrue(player.stopped)

    def test_transport_actions_and_accessible_icon_states(self):
        from files_player import InlinePlayer
        from PySide6.QtWidgets import QSlider
        player=InlinePlayer(str(self.base/'test.mp4'))
        self.addCleanup(player.stop)
        self.addCleanup(player.deleteLater)
        player.sock=object();player.props={'pause':True,'mute':False}
        with patch.object(player,'send') as send:
            player.refresh_controls()
            self.assertEqual(player.play_button.text(),'')
            self.assertIn('Reproducir',player.play_button.accessibleName())
            self.assertFalse(player.play_button.icon().isNull())
            self.assertTrue(player.play_button.isEnabled())
            player.play_button.click();send.assert_called_with(['cycle','pause'])
            player.mute.click();send.assert_called_with(['cycle','mute'])
            player.volume.setValue(42);send.assert_called_with(['set_property','volume',42])
            player.position.triggerAction(QSlider.SliderSingleStepAdd)
            self.assertEqual(send.call_args.args[0][0],'seek')
            player.props.update(pause=False,mute=True);player.refresh_controls()
            self.assertIn('Pausar',player.play_button.accessibleName())
            self.assertIn('Activar audio',player.mute.accessibleName())
        player.sock=None

    def test_transport_reduced_motion_and_audio_fullscreen_guard(self):
        from files_player import InlinePlayer
        player=InlinePlayer(str(self.base/'test.wav'),audio=True)
        self.addCleanup(player.stop)
        self.addCleanup(player.deleteLater)
        player.show();QApplication.processEvents()
        self.app.setProperty('orbitReducedMotion',True)
        try:
            player.props['pause']=False;player.refresh_controls()
            self.assertEqual(player.play_button._fade.state().name,'Stopped')
            self.assertEqual(player.play_button._symbol,'pause')
        finally:self.app.setProperty('orbitReducedMotion',False)
        emitted=[];player.fullscreenRequested.connect(emitted.append)
        player.set_fullscreen(True)
        self.assertEqual(emitted,[]);self.assertFalse(player.fullscreen)
        player.close()

    def test_file_url_and_remote_rejection(self):
        self.assertEqual(local_paths([QUrl.fromLocalFile(str(self.base)).toString()]),[str(self.base)])
        with self.assertRaises(ValueError):local_paths(['https://example.com'])


if __name__=='__main__':unittest.main()
