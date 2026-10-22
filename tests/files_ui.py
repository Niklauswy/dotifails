"""Wysun Files window: navigation, operations, sheets, inspector and players, on disposable files."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
if not (root/'apps/wysun').is_dir():root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'apps/wysun'))
from PySide6.QtCore import QItemSelectionModel, QUrl, QCoreApplication, QEvent, QSettings, Qt
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
        QSettings('Orbita','Files').clear()        # preferences (hidden files, details panel) must not leak between tests
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        (self.base/'alpha.txt').write_text('unchanged source')
        (self.base/'destination').mkdir();(self.base/'.hidden').write_text('hidden')
        self.w=FilesWindow([str(self.base)]);self.w.resize(1320,800);self.w.show()
        wait_for(lambda:self.w.current().model.rowCount(self.w.current().model.index(str(self.base)))>=2)
    def tearDown(self):
        wait_for(lambda:not self.w.jobs and self.w.inline_preview.job is None and not self.w.inline_preview.timer.isActive())
        self.w.close();self.w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);QApplication.processEvents();self.temp.cleanup()
    def select(self,path):
        tab=self.w.current();index=tab.model.index(str(path))
        tab.view().selectionModel().select(index,QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)
    def rows(self,tab=None):
        tab=tab or self.w.current();root_index=tab.model.index(tab.path)
        return [tab.model.fileName(tab.model.index(row,0,root_index)) for row in range(tab.model.rowCount(root_index))]

    # ------------------------------------------------------------ navigation
    def test_navigation_tabs_and_history(self):
        self.w.navigate(str(self.base/'destination'));self.assertEqual(self.w.current().path,str(self.base/'destination'))
        self.w.current().go(-1);self.assertEqual(self.w.current().path,str(self.base))
        self.w.new_tab(str(self.base/'destination'));self.assertEqual(self.w.tabs.count(),2)
        self.assertTrue(self.w.tabs.strip.isVisible())
        self.w.close_tab(1);self.assertEqual(self.w.current().path,str(self.base))
        self.assertFalse(self.w.tabs.strip.isVisible())
    def test_pathbar_edit_and_segments(self):
        self.w.focus_path();self.assertTrue(self.w.pathbar.edit.isVisible())
        self.w.pathbar.edit.setText(str(self.base/'destination'));self.w.pathbar.edit.returnPressed.emit()
        self.assertEqual(self.w.current().path,str(self.base/'destination'))
        self.assertFalse(self.w.pathbar.edit.isVisible())
        self.assertEqual(self.w.pathbar.segments[-1][1],str(self.base/'destination'))
        self.w.navigate(str(self.base/'missing'))
        self.assertTrue(self.w.sheet.isVisible());self.w.sheet.dismiss()
    def test_pathbar_copy_does_not_navigate(self):
        self.w.copy_current_path();self.assertEqual(self.app.clipboard().text(),str(self.base));self.assertEqual(self.w.current().path,str(self.base))
    def test_sidebar_marks_containing_place(self):
        self.w.sidebar.set_current(str(Path.home()));active=[item.label for item in self.w.sidebar.items if item.active]
        self.assertEqual(active,['Inicio'])
    def test_file_url_and_remote_rejection(self):
        self.assertEqual(local_paths([QUrl.fromLocalFile(str(self.base)).toString()]),[str(self.base)])
        with self.assertRaises(ValueError):local_paths(['https://example.com'])

    # ------------------------------------------------------------ operations
    def test_copy_paste_and_move(self):
        self.select(self.base/'alpha.txt');self.w.copy()
        self.w.navigate(str(self.base/'destination'));self.w.paste()
        wait_for(lambda:not self.w.jobs)
        self.assertEqual((self.base/'destination/alpha.txt').read_text(),'unchanged source')
        self.assertTrue((self.base/'alpha.txt').exists())
        self.w.operation('rename',[str(self.base/'destination/alpha.txt')],str(self.base/'destination/beta.txt'))
        wait_for(lambda:not self.w.jobs)
        self.assertTrue((self.base/'destination/beta.txt').exists())
    def test_cut_marks_files_until_pasted(self):
        self.select(self.base/'alpha.txt');self.w.copy(cut=True)
        self.assertIn(str(self.base/'alpha.txt'),self.w.current().view().cut)
        self.app.clipboard().clear();self.assertFalse(self.w.current().view().cut)
    def test_mkdir_worker(self):
        self.w.operation('mkdir',[],str(self.base/'new'));wait_for(lambda:not self.w.jobs)
        self.assertTrue((self.base/'new').is_dir())
    def test_new_folder_sheet_validates_and_creates(self):
        self.w.new_folder();sheet=self.w.sheet;self.assertTrue(sheet.isVisible())
        sheet.edit.setText('a/b');sheet.accept_callback();self.assertTrue(sheet.error.isVisible());self.assertTrue(sheet.isVisible())
        sheet.edit.setText('Docs');sheet.accept_callback();self.assertFalse(sheet.isVisible())
        wait_for(lambda:not self.w.jobs);self.assertTrue((self.base/'Docs').is_dir())
    def test_rename_sheet_selects_stem_and_renames(self):
        self.select(self.base/'alpha.txt');self.w.rename();sheet=self.w.sheet
        self.assertEqual(sheet.edit.selectedText(),'alpha')
        sheet.edit.setText('gamma.txt');sheet.accept_callback();wait_for(lambda:not self.w.jobs)
        self.assertTrue((self.base/'gamma.txt').exists());self.assertFalse((self.base/'alpha.txt').exists())
    def test_trash_asks_first_and_keeps_files_on_cancel(self):
        self.select(self.base/'alpha.txt');self.w.trash();self.assertTrue(self.w.sheet.isVisible())
        self.w.sheet.dismiss();self.assertTrue((self.base/'alpha.txt').exists())
    def test_selection_bar_follows_selection(self):
        bar=self.w.selection_bar;self.assertFalse(bar.isVisible())
        self.select(self.base/'alpha.txt');wait_for(bar.isVisible);self.assertTrue(bar.buttons['rename'].isEnabled());self.assertNotIn('cut',bar.buttons)
        self.w.bar_action('clear');wait_for(lambda:not bar.isVisible())
    def test_alt_k_menu_and_keyboard_shortcuts(self):
        self.select(self.base/'alpha.txt');menu=self.w.build_menu()
        titles={e['text']:e for e in menu.entries if not e['separator']};self.assertIn('Cambiar nombre',titles);self.assertTrue(titles['Enviar a la papelera']['danger'])
        self.assertEqual(titles['Cambiar nombre']['keys'],'F2');self.assertTrue(titles['Abrir']['enabled'])
        menu.popup(self.w.mapToGlobal(self.w.rect().center()));wait_for(lambda:menu.progress>=.99);menu.grab()
        menu.keyPressEvent(type('K',(),{'key':lambda s:Qt.Key_Down,'text':lambda s:''})());self.assertGreater(menu.index,0)
        picked=[];entry=titles['Copiar ruta'];entry['callback']=lambda:picked.append(1);menu._activate(menu.entries.index(entry));wait_for(lambda:picked)
        self.assertTrue(any(s.key().toString()=='Alt+K' for s in self.w.shortcuts))
        view=self.w.current().view();view.type_requested.emit('a');self.assertEqual(self.w.filter_edit.text(),'a')
        self.w.escape();self.assertEqual(self.w.filter_edit.text(),'')
    def test_going_up_reselects_the_folder_we_left(self):
        self.w.navigate(str(self.base/'destination'));wait_for(lambda:str(self.base/'destination') in self.w.current().loaded_paths)
        self.w.up();wait_for(lambda:self.w.current().selected_paths()==[str(self.base/'destination')])
    def test_kind_chips_filter_files_but_keep_folders(self):
        (self.base/'pic.png').write_bytes(b'x');(self.base/'song.mp3').write_bytes(b'x')
        wait_for(lambda:'song.mp3' in self.rows())
        self.w.hero.chips['images'].click();wait_for(lambda:'song.mp3' not in self.rows());self.assertIn('pic.png',self.rows());self.assertIn('destination',self.rows())
        self.w.hero.chips['folders'].click();wait_for(lambda:self.rows()==['destination'])
        self.w.navigate(str(self.base/'destination'));self.assertEqual(self.w.current().kind,'all')       # a new folder starts unfiltered
        self.w.navigate(str(self.base));self.w.hero.chips['all'].click();wait_for(lambda:'song.mp3' in self.rows())
    def test_segmented_switch_and_selection_pop(self):
        self.w.view_toggle.mouseReleaseEvent(type('E',(),{'button':lambda s:Qt.LeftButton,'position':lambda s:__import__('PySide6.QtCore',fromlist=['QPointF']).QPointF(60,10)})())
        self.assertEqual(self.w.current().view().mode,'list');self.assertEqual(self.w.view_toggle.index,1)
        view=self.w.current().view();self.assertEqual(view.pop_scale('/nowhere'),1.0)
        self.select(self.base/'alpha.txt');self.assertIn(str(self.base/'alpha.txt'),view.pops)
        self.assertGreater(view.pop_scale(str(self.base/'alpha.txt')),.9)
    def test_sidebar_indicator_follows_active_place(self):
        self.w.sidebar.set_current(str(Path.home()));wait_for(lambda:not self.w.sidebar.rail.pill.isNull())
        self.assertEqual(self.w.sidebar.active_item.label,'Inicio')
    def test_large_folder_stays_responsive(self):
        big=self.base/'big';big.mkdir()
        for number in range(3000):(big/f'file{number:04d}.txt').write_text('x')
        start=time.monotonic();self.w.navigate(str(big));wait_for(lambda:self.w.current().model.rowCount(self.w.current().model.index(str(big)))>=3000,20)
        view=self.w.current().view();view.grab();self.assertLess(time.monotonic()-start,8)
    def test_grid_layout_settles_without_a_resize_loop(self):
        view=self.w.current().view();self.w.set_grid(True);calls=[0];original=view._fit
        view._fit=lambda:(calls.__setitem__(0,calls[0]+1),original())[1]
        for width in (1320,1180,1320,1250):                     # tiling resizes the window a lot
            self.w.resize(width,800);wait_for(lambda:True)
        end=time.monotonic()+.6
        while time.monotonic()<end:QApplication.processEvents();time.sleep(.01)
        settled=calls[0];end=time.monotonic()+.6
        while time.monotonic()<end:QApplication.processEvents();time.sleep(.01)
        self.assertEqual(calls[0],settled);self.assertLess(settled,60)
    def test_properties_sheet(self):
        self.select(self.base/'alpha.txt');self.w.properties();self.assertTrue(self.w.sheet.isVisible());self.w.sheet.dismiss()

    # ---------------------------------------------------------- presentation
    def test_filter_hidden_grid(self):
        self.w.set_grid(True);self.assertEqual(self.w.current().view().mode,'grid')
        self.w.filter_edit.setText('alpha')
        wait_for(lambda:sorted(self.rows())==['alpha.txt','destination'])      # folders stay navigable under a name filter
        self.w.filter_edit.clear();wait_for(lambda:'destination' in self.rows())
        self.assertNotIn('.hidden',self.rows());self.w.toggle_hidden();wait_for(lambda:'.hidden' in self.rows())
    def test_empty_and_filter_messages(self):
        tab=self.w.current();(self.base/'only').mkdir();(self.base/'only/x.txt').write_text('x')
        self.w.navigate(str(self.base/'only'));wait_for(lambda:self.rows()==['x.txt'])
        self.w.filter_edit.setText('zzzz');wait_for(lambda:not self.rows());self.assertIn('filtro',tab.view().message)
        (self.base/'empty').mkdir();self.w.navigate(str(self.base/'empty'));wait_for(lambda:str(self.base/'empty') in tab.loaded_paths)
        self.assertIn('vacía',tab.view().message)
    def test_view_switch_preserves_selection(self):
        self.select(self.base/'alpha.txt');tab=self.w.current();view=tab.view()
        self.w.set_grid(True);self.assertEqual(view.mode,'grid');self.assertFalse(tab.header.isVisible())
        self.assertEqual(tab.model.fileName(view.selectionModel().selectedRows()[0]),'alpha.txt')
        self.w.set_grid(False);self.assertEqual(view.mode,'list');self.assertEqual(len(view.selectionModel().selectedRows()),1)
        self.assertTrue(tab.header.isVisible())
    def test_sort_both_directions(self):
        (self.base/'zeta.txt').write_text('z')
        tab=self.w.current();wait_for(lambda:'zeta.txt' in self.rows())
        for order in (Qt.AscendingOrder,Qt.DescendingOrder):
            self.w.apply_sort(0,order)
            pick=lambda:[n for n in self.rows() if n in ('alpha.txt','zeta.txt')]
            wait_for(lambda:pick()==sorted(pick(),reverse=order==Qt.DescendingOrder))
            self.assertEqual(tab.header.order,order)
    def test_header_click_toggles_sort_direction(self):
        tab=self.w.current();self.w.set_grid(False)
        tab.header.sort_requested.emit(2,Qt.DescendingOrder);self.assertEqual((tab.header.column,tab.header.order),(2,Qt.DescendingOrder))
    def test_image_thumbnail_worker(self):
        from PySide6.QtGui import QImage, QColor
        image=QImage(64,48,QImage.Format_RGB32);image.fill(QColor('#1266bb'))  # theme-exception: imagen de prueba
        path=self.base/'preview.png';image.save(str(path))
        cache=self.w.current().model.thumbnails
        cache.get(str(path));wait_for(lambda:cache.get(str(path)) is not None)
        self.assertFalse(cache.get(str(path)).isNull())
    def test_kind_symbols_come_from_extension(self):
        from wysun_files.kinds import describe,preview_kind
        self.assertEqual(describe('a.png')[0],'image');self.assertEqual(describe('a.md')[2],'Markdown')
        self.assertEqual(describe('x',True)[0],'folder');self.assertEqual(preview_kind('a.py'),'code');self.assertEqual(preview_kind('a.bin'),'')
    def test_reduced_motion_applies_hover_immediately(self):
        view=self.w.current().view()
        with patch.dict(os.environ,{'ORBIT_REDUCED_MOTION':'1'}):
            view.hover.point('x',1.0);self.assertEqual(view.hover.amount('x'),1.0)
            view.start_entrance();self.assertEqual(view.entrance(0),(1.0,0.0,0.0))
    def test_inspector_opens_only_for_files_with_a_preview(self):
        self.assertFalse(self.w.inspector.isVisible())                       # nothing selected
        self.select(self.base/'alpha.txt');wait_for(lambda:self.w.inspector.isVisible() and self.w.inspector.width()>=self.w.inspector_target()-2)
        self.assertGreaterEqual(self.w.inspector.width(),372);self.assertLessEqual(self.w.inspector.width(),860)
        self.select(self.base/'destination');wait_for(lambda:not self.w.inspector.isVisible())      # folders have no preview
        self.select(self.base/'alpha.txt');wait_for(self.w.inspector.isVisible)
        self.w.resize(900,700);wait_for(lambda:not self.w.inspector.isVisible())
        self.w.resize(1320,800);wait_for(self.w.inspector.isVisible)
        self.w.details_button.setChecked(False);self.w.toggle_inspector();wait_for(lambda:not self.w.inspector.isVisible())
        self.assertFalse(self.w.wants_inspector())

    # -------------------------------------------------------------- inspector
    def test_image_preview_and_stale_selection(self):
        from PySide6.QtGui import QImage,QColor
        image=QImage(120,80,QImage.Format_RGB32);image.fill(QColor('#286acc'))  # theme-exception: imagen de prueba
        path=self.base/'photo.png';image.save(str(path))
        wait_for(lambda:self.w.current().model.index(str(path)).isValid())
        self.select(path);preview=self.w.inline_preview
        wait_for(lambda:preview.image.image is not None and not preview.image.image.isNull())
        self.assertEqual(preview.image.image.width(),120)
        self.select(self.base/'alpha.txt')
        self.assertEqual(preview.path,str(self.base/'alpha.txt'))
        wait_for(lambda:preview.job is None and not preview.timer.isActive())
        self.assertIsNone(preview.image.image)
    def test_text_preview_is_literal_with_gutter(self):
        path=self.base/'alpha.txt';path.write_text('<script>literal text</script>\nsecond')
        self.select(path);preview=self.w.inline_preview
        wait_for(lambda:preview.kind=='text' and preview.holder.layout().count()==1 and preview.job is None)
        from wysun_files.textview import CodeView
        view=preview.holder.layout().itemAt(0).widget();self.assertIsInstance(view,CodeView)
        self.assertTrue(view.edit.isReadOnly());self.assertEqual(view.edit.toPlainText(),'<script>literal text</script>\nsecond')
    def test_markdown_renders_and_toggles_to_source(self):
        path=self.base/'note.md';path.write_text('# Title\n\nSome **bold** text.\n\n- one\n- two\n')
        wait_for(lambda:self.w.current().model.index(str(path)).isValid());self.select(path);preview=self.w.inline_preview
        from wysun_files.textview import MarkdownView,CodeView
        wait_for(lambda:preview.holder.layout().count() and isinstance(preview.holder.layout().itemAt(0).widget(),MarkdownView))
        preview._markdown_mode(False)
        self.assertIsInstance(preview.holder.layout().itemAt(0).widget(),CodeView)
    def test_folder_and_multiple_selection_summaries(self):
        preview=self.w.inline_preview
        preview.set_selection([],str(self.base));self.assertEqual(preview.details.name.text(),self.base.name)
        preview.set_selection([str(self.base/'destination')],str(self.base));self.assertEqual(preview.kind,'folder')
        preview.set_selection([str(self.base/'alpha.txt'),str(self.base/'destination')],str(self.base))
        self.assertEqual(preview.kind,'multiple');self.assertEqual(preview.details.name.text(),'2 elementos')
    def test_support_rules(self):
        from wysun_files.preview import SelectionPreview
        self.assertFalse(SelectionPreview.supported(str(self.base/'missing.png')))
        (self.base/'broken.png').symlink_to(self.base/'missing.png');self.assertFalse(SelectionPreview.supported(str(self.base/'broken.png')))
        self.assertTrue(SelectionPreview.supported(str(self.base/'alpha.txt')));self.assertFalse(SelectionPreview.supported(str(self.base/'destination')))
    def test_expand_and_collapse_preview(self):
        self.w.preview();self.assertFalse(self.w.expanded)         # a folder is not expandable
        self.w.sheet.dismiss()
        path=self.base/'note.md';path.write_text('# hi');wait_for(lambda:self.w.current().model.index(str(path)).isValid())
        self.select(path);self.w.set_expanded(True);wait_for(lambda:not self.w.files_surface.isVisible())
        self.assertTrue(self.w.expanded);self.w.escape();wait_for(self.w.files_surface.isVisible);self.assertFalse(self.w.expanded)
    def test_zoom_wheel_and_reset(self):
        from wysun_files.preview import ImageStage
        from PySide6.QtGui import QImage,QWheelEvent
        from PySide6.QtCore import QPoint,QPointF
        canvas=ImageStage();canvas.resize(300,200)
        canvas.set_image(QImage(200,100,QImage.Format_RGB32))
        event=QWheelEvent(QPointF(100,80),QPointF(100,80),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
        canvas.wheelEvent(event);self.assertGreater(canvas.zoom,1.)
        canvas.zoom_at(1000,QPointF(100,80));self.assertEqual(canvas.zoom,12.)
        canvas.reset_zoom();self.assertEqual(canvas.zoom,1.);self.assertTrue(canvas.offset.isNull())
        canvas.grab()
    def test_pdf_uses_browser_not_mime_handler(self):
        pdf=self.base/'document with spaces.pdf';pdf.write_bytes(b'%PDF-1.4')
        with patch('files_browser.open_pdf') as browser,patch('files_window.QDesktopServices.openUrl') as desktop,patch('wysun_files.window.QDesktopServices.openUrl') as other:
            self.w.open_path(str(pdf));browser.assert_called_once_with(str(pdf));desktop.assert_not_called();other.assert_not_called()

    # ----------------------------------------------------------------- media
    def test_media_lifecycle(self):
        path=self.base/'test.mp4';path.write_bytes(b'fixture')
        wait_for(lambda:self.w.current().model.index(str(path)).isValid())
        self.select(path);preview=self.w.inline_preview
        wait_for(lambda:preview.player is not None);player=preview.player
        self.select(self.base/'destination')
        wait_for(lambda:player.core.stopped);self.assertIsNone(preview.player)
    def test_audio_has_controls_without_video_surface(self):
        path=self.base/'test.wav';path.write_bytes(b'fixture')
        wait_for(lambda:self.w.current().model.index(str(path)).isValid())
        self.select(path);wait_for(lambda:self.w.inline_preview.player is not None);player=self.w.inline_preview.player
        self.assertTrue(player.surface.isHidden());self.assertTrue(player.full.isHidden())
        self.w.current().view().clearSelection();wait_for(lambda:player.core.stopped)
        wait_for(lambda:player.job is None or not player.job.isRunning())
    def test_transport_actions_and_states(self):
        from wysun_files.player import MediaPlayer
        player=MediaPlayer(str(self.base/'test.mp4'));self.addCleanup(player.deleteLater);self.addCleanup(player.stop)
        player.core.sock=object();player.core.props={'pause':True,'mute':False,'duration':100.0,'time-pos':10.0}
        with patch.object(player.core,'send') as send,patch.object(player.core,'poll',return_value=True):
            player._tick();self.assertEqual(player.play.symbol,'play_arrow');self.assertIn('Reproducir',player.play.accessibleName())
            player.play.click();send.assert_called_with(['cycle','pause'])
            player.mute.click();send.assert_called_with(['cycle','mute'])
            player.ahead.click();send.assert_called_with(['seek',10,'relative+exact'])
            player.progress.released.emit(.5);send.assert_called_with(['seek',50.0,'absolute-percent+exact'])
            player.core.props.update(pause=False,mute=True);player._tick()
            self.assertEqual(player.play.symbol,'pause');self.assertEqual(player.mute.symbol,'volume_off')
        player.core.sock=None
    def test_audio_fullscreen_guard(self):
        from wysun_files.player import MediaPlayer
        player=MediaPlayer(str(self.base/'test.wav'),audio=True);self.addCleanup(player.deleteLater);self.addCleanup(player.stop)
        emitted=[];player.fullscreen_requested.connect(emitted.append);player.set_fullscreen(True)
        self.assertEqual(emitted,[]);self.assertFalse(player.fullscreen)


if __name__=='__main__':unittest.main()
