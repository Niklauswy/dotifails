"""Short, interruptible state transitions; no repeating recording animations."""
from PySide6.QtWidgets import QApplication,QStyle

from wysun_core import appearance


def reduced_motion():
    if appearance.reduced_motion():
        return True
    app=QApplication.instance()
    return bool(app and app.style().styleHint(QStyle.SH_Widget_Animation_Duration)==0)
