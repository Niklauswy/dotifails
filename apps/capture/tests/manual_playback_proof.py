"""Run with QT_QPA_PLATFORM=xcb: synthetic video only, no device capture."""
import os
import tempfile
import time
import subprocess
import json
from dataclasses import asdict
from unittest.mock import patch
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QEvent,QPointF,Qt,QTimer
from PySide6.QtGui import QMouseEvent
from loomrec.capture import CaptureConfig
from loomrec.library import Library
from loomrec.schema import Project,Source,Clip,save_project
from loomrec.ui.main import Window,apply_theme


def main():
    with tempfile.TemporaryDirectory(prefix='loom-playback-proof-') as directory:
        os.environ['XDG_STATE_HOME']=directory
        os.environ['XDG_CONFIG_HOME']=directory
        library=Library(directory);root=library.new_directory();path=root/'project.json'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=30',
                        '-t','4','-c:v','libx264','-threads','1',str(root/'synthetic.mkv')],check=True)
        save_project(Project(title='Prueba de reproducción',sources=[Source('s','synthetic.mkv',duration=4)],clips=[Clip('s',0,4)]),path)
        (root/'capture.json').write_text(json.dumps(asdict(CaptureConfig(str(root),':0',[0,0,640,360],auto_finalize=False))))
        def status(state):
            (root/'status.json').write_text(json.dumps({'state':state,'heartbeat':time.time(),'project_path':str(path),'error':None}))
        status('paused')
        app=QApplication([]);apply_theme(app);window=Window(library,False)
        errors=[];window.error=lambda text:errors.append(str(text));window.show()

        def wait(predicate):
            deadline=time.monotonic()+40
            while time.monotonic()<deadline:
                app.processEvents()
                if errors:raise AssertionError(errors)
                result=predicate()
                if result:return result
                time.sleep(.05)
            raise TimeoutError(window.preview_label.text())

        def double_click_recording():
            viewport=window.items.viewport();point=window.items.visualItemRect(window.items.item(0)).center()
            globalpoint=viewport.mapToGlobal(point)
            for event in (QEvent.MouseButtonPress,QEvent.MouseButtonRelease,QEvent.MouseButtonDblClick,QEvent.MouseButtonRelease):
                app.sendEvent(viewport,QMouseEvent(event,QPointF(point),QPointF(globalpoint),Qt.LeftButton,
                              Qt.NoButton if event==QEvent.MouseButtonRelease else Qt.LeftButton,Qt.NoModifier))

        def focused_visible():
            if not window.isVisible():return False
            info=subprocess.check_output(['xwininfo','-id',str(int(window.winId()))],text=True)
            focused=subprocess.check_output(['bspc','query','-N','-n','focused'],text=True).strip()
            return 'Map State: IsViewable' in info and int(focused,16)==int(window.winId())

        try:
            app.processEvents();before=path.read_bytes()
            with patch.object(window,'ensure_keys'):
                double_click_recording();wait(focused_visible)
                assert window.stack.currentWidget()==window.setup_page and window.record.text()=='Reanudar'
                assert window.job is None and window.editor is None
                assert not list(root.glob('command-*.json'))
                status('recording');window.back_library();double_click_recording()
                assert not window.isVisible() and window.show_paused
                commands=list(root.glob('command-*.json'));assert len(commands)==1
                assert json.loads(commands[0].read_text())['command']=='pause'
                status('paused');wait(focused_visible)
            # Only synthetic metadata changes; no worker, device or real capture is used.
            window.session=None;status('stopped');window.back_library();app.processEvents();double_click_recording()
            wait(focused_visible)
            assert window.viewing and not window.inspector.isVisible()
            duration=wait(lambda:window.job is None and window.player.command('get_property','duration'))
            assert abs(duration-4)<.2
            window.play_button.click();wait(lambda:window.position>.4)
            window.play_button.click();window.player.seek(2)
            wait(lambda:abs(window.position-2)<.2)
            assert path.read_bytes()==before
            window.edit_video.click();assert window.inspector.isVisible()
            window.edit(lambda:window.editor.trim(0,1,3));window.watch_video.click()
            duration=wait(lambda:window.job is None and window.player.command('get_property','duration'))
            assert abs(duration-2)<.2
            assert window.viewing and not window.editor_timeline.isVisible()
            cached=window.playback_path();window.back_library();window.open_project(path)
            assert window.job is None and window.playback_path()==cached
            wait(lambda:window.player.command('get_property','duration'))
            assert window.activate_instance('quick')['quick'];window.quick.hide_all();window.quick_mode=False
            window.show();wait(focused_visible)
            # Exercise actual message boxes without leaving a blocking dialog behind.
            messages=[]
            window.error=lambda message:Window.error(window,message)
            def dismiss_error():
                box=app.activeModalWidget()
                if isinstance(box,QMessageBox):messages.append(box.text());box.accept()
            dismiss=QTimer();dismiss.timeout.connect(dismiss_error);dismiss.start(50)
            window.player.load(root/'missing.mp4');assert messages and 'archivo' in messages[-1]
            start=window.player.process.start
            with patch.object(window.player.process,'start',side_effect=lambda _,args:start('loom-missing-mpv-executable',args)):
                window.player.load(cached)
            wait(lambda:len(messages)==2);assert 'mpv' in messages[-1]
            dismiss.stop();assert window.isVisible()
            # An absent source is reported in the persistent job strip, not a crash.
            window.enter_editor();window.edit(lambda:window.editor.apply(lambda project:setattr(project,'title','Missing source')))
            (root/'synthetic.mkv').rename(root/'source-preserved.mkv');window.watch_video.click()
            wait(lambda:window.job is None)
            assert 'Falló' in window.job_panel.title.text() and window.isVisible()
            assert path.read_bytes()!=before
            print('PASS: native double-click paused visible without commands; recording hidden until pause ACK; terminal player visible+focused; mpv play/pause/seek; Edit and return; cache; quick IPC; missing file/mpv dialogs; missing source job error',flush=True)
        finally:
            window.session=None
            if window.job:
                window.job.cancel()
                deadline=time.monotonic()+10
                while window.job and time.monotonic()<deadline:
                    app.processEvents();time.sleep(.05)
            window.close();window.deleteLater();app.processEvents()


if __name__=='__main__':main()
