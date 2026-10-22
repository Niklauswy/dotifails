"""Three focused native desktop tools sharing Wysun's visual language."""
import os
from pathlib import Path
from PySide6.QtCore import QTimer,QThread
from PySide6.QtGui import QKeySequence,QShortcut
from PySide6.QtWidgets import (QApplication,QHBoxLayout,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem,
    QPlainTextEdit,QTextBrowser,QSplitter,QComboBox,QMessageBox,QFileDialog)
from desktop_common import Surface,button,text_label,open_vim
from utility_data import Notes,Colors,Processes,digest


def shortcut(window,key,fn):QShortcut(QKeySequence(key),window).activated.connect(fn)







from color_window import ColorWindow
