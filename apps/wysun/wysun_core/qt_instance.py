"""Serves a claimed :class:`~wysun_core.instance.SingleInstance` from the Qt event loop."""
from PySide6.QtCore import QObject, QSocketNotifier, QTimer


class InstanceNotifier(QObject):
    def __init__(self, instance, handler, parent=None):
        super().__init__(parent)
        self._instance = instance
        self._handler = handler
        self._notifier = QSocketNotifier(instance.fileno(), QSocketNotifier.Read, self)
        self._notifier.activated.connect(self._poll)
        # Clients already accepted are not on the listening socket: keep polling while any is pending.
        self._timer = QTimer(self, interval=50)
        self._timer.timeout.connect(self._poll)

    def _poll(self, *_):
        self._instance.poll(self._handler)
        if self._instance.pending:
            self._timer.start()
        else:
            self._timer.stop()

    def close(self):
        self._timer.stop()
        self._notifier.setEnabled(False)
