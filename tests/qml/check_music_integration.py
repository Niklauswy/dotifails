"""Desktop integration of the QML Music window: MPRIS on a private session bus (playerctl), Raise presents the
hidden window, and --background starts without showing it."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

SCRIPT = textwrap.dedent('''
    import subprocess, sys
    from wysun_qml import bootstrap
    bootstrap.preload_qt()
    from qml import support, music_fixture
    h = support.Harness.get()
    music_fixture.setup()
    from wysun_music.app import build
    music = build(test=True, publish=True, ui='qml')
    assert music.mpris is not None, 'MPRIS was not published'
    keys = music_fixture.keys_by_title()

    def ctl(*args):
        process = subprocess.Popen(['playerctl', '-p', 'wysun_music', *args], stdout=subprocess.PIPE, text=True)
        h.wait_for(lambda: process.poll() is not None, 5000)
        return process.stdout.read().strip()

    music.player.play(keys['first'], list(keys.values()), 'all')
    h.wait_for(lambda: music.player.playing, 5000)
    print('STATUS', ctl('status'))
    ctl('pause')
    h.wait_for(lambda: music.player.paused, 3000)
    print('PAUSED', music.player.paused)
    print('TITLE', ctl('metadata', 'xesam:title'))
    ctl('next')
    h.wait_for(lambda: music.player.current == keys['second'], 3000)
    print('NEXT', music.player.current == keys['second'])
    music.window.hide()
    raise_ = subprocess.Popen(['gdbus', 'call', '--session', '--dest', 'org.mpris.MediaPlayer2.wysun_music',
                               '--object-path', '/org/mpris/MediaPlayer2', '--method', 'org.mpris.MediaPlayer2.Raise'],
                              stdout=subprocess.DEVNULL)
    h.wait_for(lambda: raise_.poll() is not None, 5000)      # the service answers from this process' event loop
    h.wait_for(lambda: music.window.isVisible(), 3000)
    print('RAISED', music.window.isVisible())
    music.player.engine.quit()
''')


@unittest.skipUnless(shutil.which('dbus-run-session') and shutil.which('playerctl') and shutil.which('gdbus'),
                     'needs dbus-run-session, playerctl and gdbus')
class MprisTests(unittest.TestCase):
    def test_mpris_on_a_private_bus(self):
        python = support.venv_python()
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', WYSUN_QML_LIB=str(ROOT / 'apps/qml'),
                   WYSUN_QML_RUNTIME=str(python.parent.parent),
                   PYTHONPATH=os.pathsep.join([str(ROOT / 'apps/python'), str(ROOT / 'apps/python/vendor'), str(ROOT / 'tests')]),
                   TMPDIR=str(Path.home() / '.cache/wysun-fase1/tmp'))
        env.pop('WYSUN_MUSIC_HOME', None)
        env.pop('WYSUN_MUSIC_LIBRARY', None)
        result = subprocess.run(['dbus-run-session', '--', str(python), '-c', SCRIPT], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        out = result.stdout
        self.assertIn('STATUS Playing', out, out + result.stderr[-2000:])
        self.assertIn('PAUSED True', out)
        self.assertIn('TITLE first', out)
        self.assertIn('NEXT True', out)
        self.assertIn('RAISED True', out)


class BackgroundTests(unittest.TestCase):
    def test_background_route_does_not_show_the_window(self):
        from qml import music_fixture
        support.Harness.get()
        music_fixture.setup()
        music = music_fixture.app()
        music.window.hide()
        music.present('background')
        self.assertFalse(music.window.isVisible())
        music.present('present')
        self.assertTrue(music.window.isVisible())


if __name__ == '__main__':
    unittest.main()
