"""Explicit native screenshot proof using only an owned opaque fixture.

Run serially with the desktop capture slot reserved. No screenshot is retained.
QT_QPA_PLATFORM=xcb python3 tests/manual_screenshot_proof.py --owned-fixture
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owned-fixture',action='store_true',required=True)
    parser.parse_args()
    # Refuse media workers before opening a fixture; never inspect user media.
    for process in Path('/proc').glob('[0-9]*'):
        try:
            if int(process.name)==__import__('os').getpid():continue
            args=(process/'cmdline').read_bytes().split(b'\0')
            if b'loomrec.worker' in args or (args and Path(args[0].decode(errors='replace')).name=='ffmpeg' and (b'x11grab' in args or b'pulse' in args)):
                raise RuntimeError('A desktop/media capture is active; reserve a separate native slot')
        except (OSError,PermissionError):continue
    from PySide6.QtWidgets import QApplication,QWidget
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor,QPainter,QImage
    from Xlib import display,X
    from wybieshot.capture import CaptureEngine
    from wybieshot.schema import CaptureRequest,Rect
    from wybieshot.document import Document
    from wybieshot.storage import Storage
    app=QApplication([])
    class Fixture(QWidget):
        def paintEvent(self,event):
            painter=QPainter(self);painter.fillRect(self.rect(),QColor('#23a6bf'))
            painter.fillRect(32,32,90,60,QColor('#ed354a'));painter.end()
    window=Fixture(None,Qt.Window|Qt.FramelessWindowHint|Qt.X11BypassWindowManagerHint|Qt.WindowStaysOnTopHint)
    connection=display.Display()
    try:
        window.resize(320,240);window.move(80,80);window.show();window.raise_()
        for _ in range(15):app.processEvents();time.sleep(.03)
        root=connection.screen().root;native=connection.create_resource_object('window',int(window.winId()))
        attrs=native.get_attributes();geometry=native.get_geometry();point=root.translate_coords(native,0,0)
        assert attrs.map_state==X.IsViewable and attrs.override_redirect
        assert root.query_tree().children[-1].id==native.id,'Fixture must be topmost'
        region=Rect(point.x+8,point.y+8,geometry.width-16,geometry.height-16)
        result=CaptureEngine().capture(CaptureRequest(region=region))
        assert result.image.pixelColor(0,0).name()=='#23a6bf'
        assert result.image.pixelColor(40,40).name()=='#ed354a'
        with tempfile.TemporaryDirectory(prefix='wybie-owned-proof-') as directory:
            store=Storage(Path(directory)/'private');doc=Document(result.image,'Owned synthetic capture')
            output=store.export(doc,Path(directory)/'proof.png')
            assert QImage(str(output))==result.image
            store.copy(doc);app.processEvents();assert app.clipboard().image()==result.image
            print(json.dumps({'geometry':[region.x,region.y,region.width,region.height],
                              'viewable':True,'override_redirect':True,'topmost':True,
                              'pixels':'two exact RGB colors','PNG':'exact roundtrip',
                              'clipboard':'exact QImage equality','retained_images':0}))
    finally:
        window.close();app.processEvents();connection.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
