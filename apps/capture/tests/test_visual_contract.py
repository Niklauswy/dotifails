"""Presentation contracts independent of device discovery and media processes."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QAbstractAnimation,QEvent,QPointF,Qt
from PySide6.QtGui import QEnterEvent,QKeyEvent
from PySide6.QtWidgets import QApplication
from loomrec.ui.tokens import TOKENS,apply_theme
from loomrec.ui.motion import reduced_motion
from loomrec.ui.components import SoftButton


def luminance(color):
    values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))


class VisualContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def test_readable_text_and_focus_contrast(self):
        for foreground in ('text','muted'):
            for background in ('canvas','surface','well'):
                values=sorted([luminance(TOKENS[foreground]),luminance(TOKENS[background])])
                self.assertGreaterEqual((values[1]+.05)/(values[0]+.05),4.5,(foreground,background))
        for background in ('canvas','surface','well'):
            values=sorted([luminance(TOKENS['blue']),luminance(TOKENS[background])])
            self.assertGreaterEqual((values[1]+.05)/(values[0]+.05),3,background)

    def test_reduced_motion_environment_and_local_preference(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d,'LOOMREC_REDUCED_MOTION':'','ORBIT_REDUCED_MOTION':''}):
            for key in ('LOOMREC_REDUCED_MOTION','ORBIT_REDUCED_MOTION'):
                with patch.dict(os.environ,{key:'true'}):self.assertTrue(reduced_motion(),key)
            path=Path(d)/'loomrec/appearance.json';path.parent.mkdir();path.write_text(json.dumps({'reduced_motion':True}))
            self.assertTrue(reduced_motion())

    def test_reduced_motion_does_not_start_hover_animation(self):
        with patch.dict(os.environ,{'LOOMREC_REDUCED_MOTION':'1'}):
            button=SoftButton('Grabar')
            button.enterEvent(QEnterEvent(QPointF(2,2),QPointF(2,2),QPointF(2,2)))
            self.assertEqual(button.anim.state(),QAbstractAnimation.Stopped)
            button.leaveEvent(QEvent(QEvent.Leave))
            self.assertEqual(button.anim.state(),QAbstractAnimation.Stopped)
            button.deleteLater()

    def press_space(self,button):
        for event in (QEvent.KeyPress,QEvent.KeyRelease):
            self.app.sendEvent(button,QKeyEvent(event,Qt.Key_Space,Qt.NoModifier))

    def test_button_keyboard_activation_and_disabled_guard(self):
        button=SoftButton('Grabar');calls=[];button.clicked.connect(lambda:calls.append(True));button.show();button.setFocus();self.app.processEvents()
        self.assertTrue(button.focusPolicy() & Qt.TabFocus)
        self.assertTrue(button.accessibleName())
        self.press_space(button);self.assertEqual(len(calls),1)
        button.setEnabled(False);self.press_space(button);self.assertEqual(len(calls),1)
        button.close();button.deleteLater();self.app.processEvents()

    def test_library_actions_follow_available_selection(self):
        from loomrec.ui.main import Window
        from loomrec.library import Library
        from loomrec.schema import Project,save_project
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_STATE_HOME':d}):
            library=Library(d);window=Window(library,False)
            try:
                self.assertFalse(window.library_open.isEnabled());self.assertFalse(window.library_more.isEnabled())
                save_project(Project(title='Synthetic item'),library.new_directory()/'project.json');window.refresh_library()
                window.items.setCurrentRow(0);self.app.processEvents()
                self.assertTrue(window.library_open.isEnabled());self.assertTrue(window.library_more.isEnabled())
                window.search.setText('no matching project');self.app.processEvents()
                self.assertFalse(window.library_open.isEnabled());self.assertFalse(window.library_more.isEnabled())
            finally:window.timer.stop();window.close();window.deleteLater();self.app.processEvents()

    def test_advanced_setup_and_inspector_fit_and_accept_keyboard(self):
        from loomrec.ui.main import Window
        from loomrec.library import Library
        from PySide6.QtWidgets import QScrollArea
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_STATE_HOME':d}):
            window=Window(Library(d),False)
            try:
                window.show()
                for width,height in ((940,1054),(1280,800)):
                    window.resize(width,height);window.stack.setCurrentWidget(window.setup_page)
                    window.setup_advanced.trigger.setChecked(True);self.app.processEvents()
                    self.assertTrue(window.setup_advanced.body.isVisible())
                    self.assertEqual((window.width(),window.height()),(width,height))
                    for scroll in window.setup_page.findChildren(QScrollArea):self.assertEqual(scroll.horizontalScrollBar().maximum(),0)
                    window.stack.setCurrentWidget(window.editor_page);self.app.processEvents()
                    tabs=window.inspector.tabBar();tabs.setCurrentIndex(0);tabs.setFocus()
                    self.app.sendEvent(tabs,QKeyEvent(QEvent.KeyPress,Qt.Key_Right,Qt.NoModifier))
                    self.assertEqual(window.inspector.currentIndex(),1)
                    for i in range(window.inspector.count()):
                        window.inspector.setCurrentIndex(i);self.app.processEvents()
                        self.assertEqual(window.inspector.widget(i).horizontalScrollBar().maximum(),0,i)
                    self.assertEqual((window.width(),window.height()),(width,height))
            finally:window.timer.stop();window.close();window.deleteLater();self.app.processEvents()

    def test_localized_annotation_dialog_preserves_schema_values(self):
        from loomrec.ui.main import Window
        from loomrec.library import Library
        from loomrec.schema import Project,Source,Clip,save_project
        from PySide6.QtWidgets import QDialog,QComboBox,QDialogButtonBox,QLineEdit,QScrollArea
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_STATE_HOME':d}):
            library=Library(d);path=library.new_directory()/'project.json'
            save_project(Project(sources=[Source('s','synthetic.mkv',duration=5)],clips=[Clip('s',0,5)]),path)
            window=Window(library,False);window.open_project(path,edit=True);window.resize(1280,800);window.show();self.app.processEvents()
            expected_kinds=['text','arrow','highlight','mask','blur','subtitle'];expected_colors=['yellow','white','black','red','green','blue']
            try:
                for index,key in enumerate(expected_kinds):
                    def interact(dialog):
                        dialog.show();self.app.processEvents()
                        combos=dialog.findChildren(QComboBox);kind=next(c for c in combos if c.findData('text')>=0);color=next(c for c in combos if c.findData('yellow')>=0)
                        self.assertEqual([kind.itemData(i) for i in range(kind.count())],expected_kinds)
                        self.assertEqual([color.itemData(i) for i in range(color.count())],expected_colors)
                        self.assertEqual(color.itemText(0),'Amarillo');self.assertEqual(kind.itemText(0),'Texto')
                        kind.setCurrentIndex(index);color.setCurrentIndex(index);dialog.findChild(QLineEdit).setText('Fixture')
                        box=dialog.findChild(QDialogButtonBox);save=box.button(QDialogButtonBox.Save)
                        self.assertTrue(save.isVisible());self.assertTrue(dialog.rect().contains(save.mapTo(dialog,save.rect().bottomRight())))
                        self.assertFalse(any(scroll.isAncestorOf(box) for scroll in dialog.findChildren(QScrollArea)))
                        save.click();dialog.hide();return QDialog.Accepted
                    with patch.object(QDialog,'exec',interact):window.annotation_dialog()
                    if key=='subtitle':self.assertEqual(window.editor.project.subtitles[-1].text,'Fixture')
                    else:
                        annotation=window.editor.project.annotations[-1]
                        self.assertEqual((annotation.kind,annotation.color),(key,expected_colors[index]))
                window.inspector.setCurrentIndex(0);self.app.processEvents()
                from PySide6.QtWidgets import QPushButton
                apply=next(b for b in window.inspector.findChildren(QPushButton) if b.text()=='Aplicar recorte')
                viewport=window.inspector.widget(0).viewport()
                self.assertTrue(viewport.rect().contains(apply.mapTo(viewport,apply.rect().bottomRight())))
            finally:window.timer.stop();window.close();window.deleteLater();self.app.processEvents()

    def test_paused_controls_hide_before_deferred_resume(self):
        from loomrec.ui.main import Window
        from loomrec.library import Library
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_STATE_HOME':d}):
            window=Window(Library(d),False);window.timer.stop();window.stack.setCurrentWidget(window.setup_page);window.show()
            session=Mock();session.status.return_value={'state':'paused'};window.session=session
            try:
                window.capture_presentation('paused');self.app.processEvents()
                for control in (window.monitor,window.mic,window.system,window.camera,*window.rect):self.assertFalse(control.isEnabled())
                self.assertTrue(window.stop_record.isVisible());self.assertTrue(window.record.isEnabled());self.assertEqual(window.record.text(),'Reanudar')
                with patch('loomrec.ui.main.QTimer.singleShot') as schedule:
                    window.record.click();self.assertFalse(window.isVisible());self.assertFalse(window.tray.isVisible());session.resume.assert_not_called()
                    self.assertEqual(schedule.call_args.args[0],500);schedule.call_args.args[1]();session.resume.assert_called_once()
                window.stop_record.click();session.stop.assert_called_once()
                window.session=None;window.capture_presentation('stopped');self.assertTrue(window.mic.isEnabled());self.assertEqual(window.record.text(),'Grabar')
            finally:window.session=None;window.close();window.deleteLater();self.app.processEvents()
