"""Wysun Player process: single instance, request protocol, window lifecycle, launching from other apps."""
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import media_support as support

support.app()
from PySide6.QtWidgets import QFileDialog  # noqa: E402
import player_client  # noqa: E402
import player_window  # noqa: E402
from wysun_media import mpv  # noqa: E402

APP = support.ROOT / 'apps/wysun/player_app.py'


class Environment(unittest.TestCase):
    """Private runtime and state directories: tests never touch the user's player or its remembered positions."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='wysun-player-test-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.run_dir = self.root / 'run'
        self.run_dir.mkdir(mode=0o700)
        patch = mock.patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(self.run_dir), 'XDG_STATE_HOME': str(self.root / 'state'),
                                             'WYSUN_MPV_OPTIONS': 'ao=null'})
        patch.start()
        self.addCleanup(patch.stop)
        self.files = support.fixtures()


class ClientTests(Environment):
    def test_request_makes_paths_absolute_and_carries_options(self):
        payload = player_client.request(['a.png', Path('/x/b.mp4')], paused=True, fullscreen=True, start=12)
        self.assertEqual(payload['files'], [os.path.abspath('a.png'), '/x/b.mp4'])
        self.assertEqual((payload['paused'], payload['fullscreen'], payload['start']), (True, True, 12.0))
        self.assertIsNone(player_client.request(['a.png'])['start'])

    def test_command_line_keeps_every_name_after_the_separator(self):
        payload = player_client.request(['-rf.png', '--quit.mp4'], paused=True, start=3)
        argv = player_client.command(payload)
        self.assertEqual(argv[argv.index('--') + 1:], payload['files'])
        self.assertIn('--paused', argv)
        self.assertEqual(argv[argv.index('--start') + 1], '3.0')

    def test_nothing_listening_means_not_forwarded(self):
        self.assertFalse(player_client.forward(player_client.request([self.files / 'plain.png']), timeout=.3))

    def test_launch_starts_a_process_only_when_no_player_answers(self):
        with mock.patch.object(subprocess, 'Popen') as popen:
            player_client.launch([self.files / 'plain.png'], paused=True)
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0][-1], str(self.files / 'plain.png'))
        self.assertTrue(popen.call_args.kwargs['start_new_session'])

    def test_launch_uses_the_running_player(self):
        server = player_window.RequestServer()
        self.addCleanup(server.close)
        received = []
        server.received.connect(received.append)
        with mock.patch.object(subprocess, 'Popen') as popen:
            outcome = []
            worker = threading.Thread(target=lambda: outcome.append(player_client.forward(player_client.request([self.files / 'plain.png']))))
            worker.start()
            self.assertTrue(support.pump(lambda: received))
            worker.join(3)
        popen.assert_not_called()
        self.assertEqual(outcome, [True])
        self.assertEqual(received[0]['files'], [str(self.files / 'plain.png')])


class ServerTests(Environment):
    def server(self):
        server = player_window.RequestServer()
        self.addCleanup(server.close)
        server.got = []
        server.received.connect(server.got.append)
        return server

    def talk(self, server, data, wait=True):
        reply = []

        def client():
            with socket.socket(socket.AF_UNIX) as connection:
                connection.settimeout(3)
                connection.connect(str(player_client.endpoint()))
                connection.sendall(data)
                try:
                    reply.append(connection.recv(16))
                except OSError:
                    reply.append(b'')
        worker = threading.Thread(target=client)
        worker.start()
        support.pump(lambda: not worker.is_alive(), 4)
        worker.join(4)
        return reply[0] if reply else None

    def test_valid_request_is_acknowledged_and_emitted(self):
        server = self.server()
        self.assertEqual(self.talk(server, b'{"files": ["/a/b.png"], "paused": true}\n'), b'ok\n')
        support.settle(.05)
        self.assertEqual(server.got, [{'files': ['/a/b.png'], 'paused': True}])

    def test_garbage_is_refused_and_never_reaches_the_player(self):
        server = self.server()
        for data in (b'not json\n', b'[1, 2]\n', b'{"files": "x"}\n', b'\n'):
            self.assertEqual(self.talk(server, data), b'no\n', data)
        support.settle(.05)
        self.assertEqual(server.got, [])

    def test_a_request_without_a_newline_is_dropped_after_a_timeout(self):
        server = self.server()
        self.assertIn(self.talk(server, b'{"files": []}'), (b'', None))
        self.assertEqual(server.got, [])

    def test_oversized_requests_are_dropped(self):
        server = self.server()
        self.assertIn(self.talk(server, b'x' * (player_client.LIMIT + 10)), (b'', None))
        self.assertEqual(server.got, [])

    def test_socket_is_private_and_removed_on_close(self):
        server = player_window.RequestServer()
        path = player_client.endpoint()
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        server.close()
        self.assertFalse(path.exists())

    def test_a_stale_socket_is_replaced_but_a_regular_file_is_never_deleted(self):
        stale = socket.socket(socket.AF_UNIX)
        stale.bind(str(player_client.endpoint()))
        stale.close()                                       # leaves the socket file behind, like a crash
        player_window.RequestServer().close()
        player_client.endpoint().write_text('precious')
        with self.assertRaises(RuntimeError):
            player_window.RequestServer()
        self.assertEqual(player_client.endpoint().read_text(), 'precious')


class ProcessTests(Environment):
    def process(self):
        quits = []
        process = player_window.Process(lambda: quits.append(1))
        process.quits = quits
        self.addCleanup(self.stop, process)
        return process

    def stop(self, process):
        process.shutdown()
        for window in list(process.windows):
            window.close()
        support.settle(.1)
        mpv.wait_closed()

    def test_a_request_opens_a_window_on_its_files(self):
        process = self.process()
        window = process.show({'files': [str(self.files / 'tone.mp3')], 'paused': True})
        self.assertEqual(len(process.windows), 1)
        self.assertEqual(window.player.source.name, 'tone.mp3')
        self.assertTrue(support.pump(lambda: window.player.session.state == 'paused'))
        self.assertEqual(window.windowTitle(), 'tone.mp3 · Wysun Player')

    def test_one_file_browses_its_folder_and_several_keep_their_order(self):
        process = self.process()
        single = process.show({'files': [str(self.files / 'plain.png')]})
        self.assertTrue(support.pump(lambda: len(single.player.collection) > 2))
        several = process.show({'files': [str(self.files / 'plain.png'), str(self.files / 'alpha.png')]})
        self.assertEqual([Path(p).name for p in several.player.collection.paths], ['plain.png', 'alpha.png'])

    def test_each_request_gets_its_own_window_and_session(self):
        process = self.process()
        first = process.show({'files': [str(self.files / 'tone.mp3')], 'paused': True})
        second = process.show({'files': [str(self.files / 'tone.flac')], 'paused': True})
        self.assertIsNot(first.player.session, second.player.session)
        self.assertEqual(len(process.windows), 2)

    def test_start_position_and_fullscreen_requests(self):
        process = self.process()
        window = process.show({'files': [str(self.files / 'tone.wav')], 'paused': True, 'start': 1.5, 'fullscreen': True})
        self.assertTrue(support.pump(lambda: window.player.session.state == 'paused' and window.player.session.duration > 0))
        self.assertAlmostEqual(window.player.session.position, 1.5, delta=.15)
        self.assertEqual(window.player.fullscreen, False, 'audio has no fullscreen')
        video = process.show({'files': [str(self.files / 'h264.mp4')], 'paused': True, 'fullscreen': True})
        self.assertTrue(video.player.fullscreen)

    def test_an_unplayable_file_still_opens_a_window_that_explains_it(self):
        process = self.process()
        window = process.show({'files': [str(self.files / 'list.m3u')]})
        self.assertTrue(window.player.note.isVisible())

    def test_closing_the_last_window_quits_after_a_grace_period(self):
        process = self.process()
        process.grace.setInterval(40)
        window = process.show({'files': [str(self.files / 'plain.png')]})
        window.close()
        self.assertTrue(support.pump(lambda: process.quits, 3))
        self.assertEqual(process.quits, [1])

    def test_a_request_during_the_grace_period_keeps_the_process_alive(self):
        process = self.process()
        process.grace.setInterval(120)
        process.show({'files': [str(self.files / 'plain.png')]}).close()
        support.settle(.03)
        process.show({'files': [str(self.files / 'alpha.png')]})
        support.settle(.4)
        self.assertEqual(process.quits, [])
        self.assertEqual(len(process.windows), 1)

    def test_a_request_without_files_asks_which_to_open_and_cancelling_exits(self):
        process = self.process()
        process.grace.setInterval(40)
        with mock.patch.object(QFileDialog, 'getOpenFileNames', return_value=([], '')):
            self.assertIsNone(process.show({'files': []}))
        self.assertTrue(support.pump(lambda: process.quits, 3))
        with mock.patch.object(QFileDialog, 'getOpenFileNames', return_value=([str(self.files / 'plain.png')], '')):
            self.assertIsNotNone(process.show({'files': []}))

    def test_windows_are_bounded(self):
        process = self.process()
        for _ in range(player_window.WINDOW_LIMIT + 3):
            process.show({'files': [str(self.files / 'plain.png')]})
        self.assertEqual(len(process.windows), player_window.WINDOW_LIMIT)

    def test_closing_a_window_releases_its_player(self):
        process = self.process()
        window = process.show({'files': [str(self.files / 'tone.mp3')]})
        support.pump(lambda: window.player.session.state == 'playing')
        session = window.player.session
        window.close()
        self.assertIsNone(session.core)


class SingleInstanceTests(Environment):
    """Real processes: the second launch must hand over its files and exit, whatever the timing."""

    def env(self):
        env = dict(os.environ, HOME=str(self.root), QT_QPA_PLATFORM='offscreen', ORBIT_REDUCED_MOTION='1',
                   XDG_CONFIG_HOME=str(self.root / 'config'), XDG_DATA_HOME=str(self.root / 'data'), XDG_CACHE_HOME=str(self.root / 'cache'))
        for variable in ('WAYLAND_DISPLAY', 'DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE'):
            env.pop(variable, None)
        return env

    def spawn(self, *files):
        process = subprocess.Popen([sys.executable, str(APP), '--', *map(str, files)], env=self.env(), cwd=str(self.root),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.reap, process)
        return process

    def reap(self, process):
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
        try:
            process.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()

    def serving(self):
        return [pid for pid in os.listdir('/proc') if pid.isdigit() and self.is_player(pid)]

    def is_player(self, pid):
        try:
            command = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
            environment = Path(f'/proc/{pid}/environ').read_bytes()
        except OSError:
            return False
        return str(APP).encode() in command and str(self.run_dir).encode() in environment

    def test_second_launch_hands_over_and_exits_quickly(self):
        first = self.spawn(self.files / 'tone.mp3')
        self.assertTrue(support.pump(lambda: player_client.endpoint().exists(), 15), 'the first launch serves a socket')
        started = time.monotonic()
        second = self.spawn(self.files / 'tone.flac')
        self.assertEqual(second.wait(timeout=10), 0)
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertIsNone(first.poll(), 'the first player keeps running')
        self.assertEqual(len(self.serving()), 1)

    def test_simultaneous_first_launches_still_make_one_player(self):
        launches = [self.spawn(self.files / name) for name in ('tone.mp3', 'tone.flac', 'tone.ogg', 'tone.opus')]
        support.pump(lambda: sum(p.poll() == 0 for p in launches) >= 3, 25)
        self.assertEqual(len(self.serving()), 1)
        self.assertEqual(sum(p.poll() is None for p in launches), 1)

    def test_terminating_the_player_cleans_the_socket(self):
        first = self.spawn(self.files / 'tone.mp3')
        support.pump(lambda: player_client.endpoint().exists(), 15)
        first.send_signal(signal.SIGTERM)
        first.wait(timeout=10)
        self.assertFalse(player_client.endpoint().exists())
        self.assertEqual(self.serving(), [])

    def test_a_crashed_player_does_not_block_the_next_launch(self):
        first = self.spawn(self.files / 'tone.mp3')
        support.pump(lambda: player_client.endpoint().exists(), 15)
        first.kill()
        first.wait()
        second = self.spawn(self.files / 'tone.flac')
        self.assertTrue(support.pump(lambda: player_client.endpoint().exists() and second.poll() is None, 15))
        self.assertEqual(len(self.serving()), 1)

    def test_help_does_not_start_a_player(self):
        done = subprocess.run([sys.executable, str(APP), '--help'], env=self.env(), capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0)
        self.assertIn('wysun player', done.stdout)
        self.assertFalse(player_client.endpoint().exists())


if __name__ == '__main__':
    unittest.main()
