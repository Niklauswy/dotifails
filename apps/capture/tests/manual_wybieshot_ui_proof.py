"""Native UI integration proof. All root pixels are covered by an owned fixture.
Run serially: QT_QPA_PLATFORM=xcb python tests/manual_wybieshot_ui_proof.py --owned-fixture OUTPUT_DIRECTORY
"""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--owned-fixture',action='store_true',required=True);parser.add_argument('--surfaces-only',action='store_true',help='Reuse synthetic pixels; do not repeat desktop capture proof');parser.add_argument('output',type=Path);args=parser.parse_args()
    for process in Path('/proc').glob('[0-9]*'):
        try:
            command=(process/'cmdline').read_bytes().split(b'\0')
            if b'loomrec.worker' in command or (command and Path(command[0].decode(errors='replace')).name=='ffmpeg' and (b'x11grab' in command or b'pulse' in command)):raise RuntimeError('Active media capture; refusing native test')
        except (OSError,PermissionError):continue
    from PySide6.QtCore import Qt,QRect,QPointF,QEvent
    from PySide6.QtGui import QColor,QPainter,QFont,QMouseEvent,QImage
    from PySide6.QtWidgets import QApplication,QWidget
    from Xlib import display,X
    from wybieshot.ui.main import Window
    from wybieshot.ui.components import apply_theme
    from wybieshot.storage import Storage
    from wybieshot.schema import Layer
    app=QApplication([]);app.setQuitOnLastWindowClosed(False);apply_theme(app)
    connection=display.Display();root=connection.screen().root
    def settle():
        for _ in range(10):app.processEvents();time.sleep(.025)
    def assert_native(widget,topmost=True):
        app.sync();connection.sync()
        native=connection.create_resource_object('window',int(widget.winId()));attributes=native.get_attributes();g=native.get_geometry();point=root.translate_coords(native,0,0)
        assert attributes.map_state==X.IsViewable and attributes.override_redirect
        if topmost:
            visible=[w for w in root.query_tree().children if w.get_attributes().map_state==X.IsViewable and w.get_attributes().win_class==X.InputOutput]
            assert visible[-1].id==native.id,'Owned surface must be topmost visible surface'
        return QRect(point.x,point.y,g.width,g.height)
    def click_drag(widget,start,end):
        for kind,pos,button,buttons in ((QEvent.MouseButtonPress,start,Qt.LeftButton,Qt.LeftButton),(QEvent.MouseMove,end,Qt.NoButton,Qt.LeftButton),(QEvent.MouseButtonRelease,end,Qt.LeftButton,Qt.NoButton)):
            app.sendEvent(widget,QMouseEvent(kind,QPointF(pos),QPointF(widget.mapToGlobal(pos)),button,buttons,Qt.NoModifier))
    class Fixture(QWidget):
        def paintEvent(self,event):
            p=QPainter(self);p.fillRect(self.rect(),QColor('#EDF3FA'))
            p.fillRect(QRect(80,80,880,460),QColor('#FCFDFF'))
            font=QFont();font.setPixelSize(16);p.setFont(font);p.setPen(QColor('#596A80'));p.drawText(120,133,'WYBIE / OWNED TEST FIXTURE')
            font.setPixelSize(34);font.setBold(True);p.setFont(font);p.setPen(QColor('#1C2A3B'));p.drawText(120,195,'Una idea, más clara.')
            font.setPixelSize(19);font.setBold(False);p.setFont(font);p.setPen(QColor('#596A80'));p.drawText(120,235,'Captura. Anota. Comparte el contexto.')
            for x,height,title in ((140,90,'Capturar'),(380,145,'Explicar'),(620,190,'Continuar')):
                p.fillRect(x,460-height,160,height,QColor('#DCE9FC'));p.setPen(QColor('#2165D5'));p.drawText(x,490,title)
            p.end()
    geometry=QApplication.primaryScreen().virtualGeometry()
    fixture=Fixture(None,Qt.Window|Qt.FramelessWindowHint|Qt.X11BypassWindowManagerHint|Qt.WindowStaysOnTopHint);fixture.setAttribute(Qt.WA_OpaquePaintEvent);fixture.setGeometry(geometry)
    window=None
    try:
        fixture.show();fixture.raise_();settle();actual=assert_native(fixture);assert actual.contains(geometry),'Fixture must cover entire desktop before freeze'
        with tempfile.TemporaryDirectory(prefix='wybieshot-ui-proof-') as temp:
            store=Storage(Path(temp)/'private');store.set_output(Path(temp)/'output');window=Window(store);window.setWindowFlags(Qt.Window|Qt.FramelessWindowHint|Qt.X11BypassWindowManagerHint|Qt.WindowStaysOnTopHint)
            if args.surfaces_only:
                from wybieshot.document import Document
                window.set_document(Document(fixture.grab(QRect(80,80,880,460)).toImage(),'Fixture propio'))
            else:
                window.pending_request=__import__('wybieshot.schema',fromlist=['CaptureRequest']).CaptureRequest();window.busy=True
                window.capture_tick();settle();assert window.overlay is not None
                click_drag(window.overlay,__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(80-geometry.x(),80-geometry.y()),__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(959-geometry.x(),539-geometry.y()))
                from PySide6.QtGui import QKeyEvent
                app.sendEvent(window.overlay,QKeyEvent(QEvent.KeyPress,Qt.Key_Return,Qt.NoModifier));settle()
                assert window.document is not None and window.document.size.width()==880
            window.resize(1120,760);window.move(40,40);window.show();window.raise_();settle()
            doc=window.document;doc.title='Una idea, más clara';window.title.setText(doc.title)
            window.choose_tool('arrow');r=window.canvas.image_rect()
            from PySide6.QtCore import QPoint
            def at(x,y):return QPoint(round(r.x()+x*r.width()/880),round(r.y()+y*r.height()/460))
            click_drag(window.canvas,at(520,100),at(570,225));assert doc.layers[-1].tool=='arrow'
            doc.add_layer(Layer('number',((300,280),),number=1));doc.add_layer(Layer('text',((470,75),),text='El siguiente paso',font_size=22));window.changed();window.save_document();window.copy();export=window.export();assert QImage(str(export))==doc.render();assert app.clipboard().image()==doc.render()
            previous=len(doc.layers);window.undo();assert len(doc.layers)==previous-1;window.redo();assert len(doc.layers)==previous
            session=doc.session_id;window.set_document(store.load(session));assert len(window.document.layers)==previous
            window.canvas.selected_id=window.document.layers[0].id;window.choose_tool('select');settle()
            args.output.mkdir(parents=True,exist_ok=True)
            def screenshot(widget,name):
                region=assert_native(widget);assert geometry.contains(region)
                # Validate the background is still ours before any composited root crop.
                assert assert_native(fixture,False).contains(region)
                pixels=app.primaryScreen().grabWindow(0,region.x(),region.y(),region.width(),region.height()).toImage();assert pixels.save(str(args.output/name))
            screenshot(window,'editor.png')
            window.hide();window.quick.setWindowFlag(Qt.X11BypassWindowManagerHint,True);window.quick.present();settle();screenshot(window.quick,'quick.png')
            window.quick.hide()
            from wybieshot.document import Document
            before=Document(doc.original,'Antes · idea inicial');before_id=store.save(before)
            after=Document(doc.original,'Después · contexto añadido')
            for layer in doc.layers:after.add_layer(layer)
            after_id=store.save(after)
            window.show_library();window.resize(960,650);window.move(40,40);window.show();window.raise_();settle()
            for _ in range(20):
                settle()
                if not window.jobs and not window.thumbnail_pending:break
            assert window.thumbnail_cache and len(window.thumbnail_cache)<=32
            window.items.setCurrentRow(0);screenshot(window,'library.png')
            def select_originals():
                window.show_library()
                for n in range(window.items.count()):
                    item=window.items.item(n);item.setSelected(item.data(Qt.UserRole) in (before_id,after_id))
                assert len(window.selected_ids())==2
            from PySide6.QtWidgets import QDialog,QSlider,QPushButton,QComboBox,QSpinBox,QCheckBox,QDialogButtonBox
            from PySide6.QtCore import QTimer
            from unittest.mock import patch
            original_exec=QDialog.exec;errors=[]
            def execute(dialog,kind):
                dialog.setWindowFlags(Qt.Dialog|Qt.FramelessWindowHint|Qt.X11BypassWindowManagerHint|Qt.WindowStaysOnTopHint);dialog.move(100,70)
                def interact():
                    try:
                        dialog.raise_();settle()
                        if kind=='composition':
                            dialog.findChild(QComboBox).setCurrentIndex(0);dialog.findChild(QSpinBox).setValue(24);dialog.findChild(QCheckBox).setChecked(True)
                            screenshot(dialog,'composition-options.png');dialog.accept()
                        elif kind=='comparison':
                            dialog.findChild(QSlider).setValue(40);settle();screenshot(dialog,'comparison.png')
                            next(b for b in dialog.findChildren(QPushButton) if b.text()=='Guardar vista').click()
                        else:
                            combos=dialog.findChildren(QComboBox);combos[0].setCurrentText('JPEG');combos[1].setCurrentIndex(1)
                            for check in dialog.findChildren(QCheckBox):check.setChecked(True)
                            screenshot(dialog,'settings.png');dialog.accept()
                    except Exception as exc:errors.append(exc);dialog.reject()
                QTimer.singleShot(180,interact);result=original_exec(dialog)
                if errors:raise errors[0]
                return result
            select_originals()
            with patch.object(QDialog,'exec',lambda dialog:execute(dialog,'composition')):window.compose()
            assert window.document.size.width()==1784 and window.document.size.height()==508
            window.resize(1120,760);window.move(40,40);window.raise_();settle();screenshot(window,'composition.png')
            select_originals()
            with patch.object(QDialog,'exec',lambda dialog:execute(dialog,'comparison')):window.compare()
            assert window.document.title=='Antes y después'
            with patch.object(QDialog,'exec',lambda dialog:execute(dialog,'settings')):window.show_settings()
            assert Storage(store.root).settings['format']=='JPEG' and store.settings['delay']==3
            print('PASS native surfaces: topmost owned frame crops; editor; bounded real thumbnails; composition dialog+result; comparison slider+saved view; settings persisted JPEG/delay/cursor/reduced motion',flush=True)
    finally:
        if window:
            for job in list(window.jobs):job.wait(5000)
            app.processEvents();window.quick.close();window.close();window.quick.deleteLater();window.deleteLater()
        fixture.close();fixture.deleteLater();app.processEvents();app.sendPostedEvents(None,QEvent.DeferredDelete);connection.close()
        import gc
        gc.collect();app.processEvents()
    return 0

if __name__=='__main__':raise SystemExit(main())
