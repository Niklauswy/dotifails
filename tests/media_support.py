"""Shared setup for the wysun_media tests: offscreen Qt, the Wysun host, generated fixtures, a private D-Bus, an event pump."""
import atexit
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
sys.path.insert(0, str(ROOT / 'tests'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('ORBIT_REDUCED_MOTION', '1')


class SessionBus:
    """A throw-away D-Bus session daemon; ``address`` is what clients put in DBUS_SESSION_BUS_ADDRESS."""

    def __init__(self):
        self.process = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'], stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True)
        self.address = self.process.stdout.readline().strip()
        atexit.register(self.stop)                   # never leave a daemon behind, whatever happens to the test run

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)
        if not self.process.stdout.closed:
            self.process.stdout.close()


# libdbus resolves the session bus address once per process, so the whole test process shares one throw-away
# daemon, started before anything can connect: tests never reach the user's real session bus.
try:
    bus = SessionBus()
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = bus.address
except OSError:
    bus = None
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=/nonexistent/wysun-test-bus'

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_app = None
_fixtures = None


def app():
    """One QApplication per process, with the Wysun theme palette and the player host installed."""
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv[:1])
        _app.setStyle('Fusion')
        import media_host
        import theme_tokens
        theme_tokens.apply_palette(_app)
        media_host.install()
    return _app


def fixtures():
    """Path of the synthetic media set, generated once per process (a few seconds)."""
    global _fixtures
    if _fixtures is None:
        import media_fixtures
        app()
        _fixtures = Path(tempfile.mkdtemp(prefix='wysun-media-fixtures-'))
        media_fixtures.build(_fixtures)
    return _fixtures


def pump(predicate=None, timeout=8.0, step=0.01):
    """Process events until ``predicate()`` is true (or for ``timeout`` seconds when none is given)."""
    qt = app()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qt.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)     # a real event loop would run deleteLater()
        if predicate is not None and predicate():
            return True
        time.sleep(step)
    return predicate is None or bool(predicate())


def settle(seconds=0.1):
    pump(timeout=seconds)
