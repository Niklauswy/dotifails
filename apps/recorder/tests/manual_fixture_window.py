import sys,os
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QPalette,QColor
app=QApplication(sys.argv);w=QWidget();w.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.X11BypassWindowManagerHint);full=os.environ.get('MODE')=='monitor';w.setGeometry(0 if full else 100,0 if full else 100,1920 if full else 640,1080 if full else 360);w.setAttribute(Qt.WA_OpaquePaintEvent);w.setAutoFillBackground(True);pal=w.palette();pal.setColor(QPalette.Window,QColor('black'));w.setPalette(pal);w.showFullScreen() if full else w.show();w.raise_();app.processEvents();print(int(w.winId()),flush=True);QTimer.singleShot(90000,app.quit);app.exec()
