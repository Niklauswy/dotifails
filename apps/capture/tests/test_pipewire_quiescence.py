"""Clock-only regression for the compositor's sharing latch; no runtime/media."""
import unittest


class Clock:
    def __init__(self,now=100.):self.now=now;self.sleeps=[]
    def monotonic(self):return self.now
    def pause(self,seconds):self.sleeps.append(seconds);self.now+=seconds


class QuiescenceTests(unittest.TestCase):
    def wait(self,finished,clock,heartbeat=None):
        from loomrec.wayland_capture import wait_remote_quiescence
        return wait_remote_quiescence(finished,heartbeat,clock=clock.monotonic,pause=clock.pause)
    def test_first_connection_does_not_wait(self):
        clock=Clock();heartbeats=[];self.wait(None,clock,lambda:heartbeats.append(clock.now))
        self.assertEqual(clock.sleeps,[]);self.assertEqual(heartbeats,[])
    def test_immediate_reconnect_waits_only_until_close_plus_650ms(self):
        clock=Clock();heartbeats=[];self.wait(100.,clock,lambda:heartbeats.append(clock.now))
        self.assertAlmostEqual(clock.now,100.65);self.assertAlmostEqual(sum(clock.sleeps),.65)
        self.assertTrue(heartbeats);self.assertTrue(all(0<s<=.05 for s in clock.sleeps))
    def test_long_pause_has_no_additional_delay(self):
        clock=Clock(104.);self.wait(100.,clock)
        self.assertEqual(clock.sleeps,[]);self.assertEqual(clock.now,104.)
    def test_elapsed_finalization_time_is_credited(self):
        clock=Clock(100.4);self.wait(100.,clock)
        self.assertAlmostEqual(sum(clock.sleeps),.25);self.assertAlmostEqual(clock.now,100.65)
    def test_heartbeat_can_cancel_before_opening_remote(self):
        from loomrec.portal import PortalCancelled
        clock=Clock();heartbeats=[]
        def heartbeat():
            heartbeats.append(clock.now)
            if len(heartbeats)==3:raise PortalCancelled('synthetic stop')
        with self.assertRaises(PortalCancelled):self.wait(100.,clock,heartbeat)
        self.assertEqual(len(heartbeats),3);self.assertLessEqual(sum(clock.sleeps),.1)
    def test_heartbeat_execution_time_does_not_extend_the_barrier(self):
        clock=Clock()
        def heartbeat():clock.now+=.2
        self.wait(100.,clock,heartbeat)
        self.assertAlmostEqual(clock.now,100.7);self.assertAlmostEqual(sum(clock.sleeps),.1)



class RemoteOwnershipTests(unittest.TestCase):
    def adapter(self):
        import socket
        from types import SimpleNamespace
        from unittest.mock import Mock
        from loomrec.portal import Portal
        from loomrec.wayland_capture import PipeWireCapture
        left,peer=socket.socketpair();portal=Portal.__new__(Portal)
        portal.fd=left.detach();portal.disposed=False;portal.closed=False;portal.session='/own/session';portal._match=None
        portal.bus=Mock();portal.object=object();portal.on_wait=None;portal.dispatch=Mock()
        portal.dbus=Mock();portal.dbus.DBusException=RuntimeError
        api=portal.dbus.Interface.return_value
        capture=PipeWireCapture.__new__(PipeWireCapture)
        capture.portal=portal;capture.process=None;capture._remote_used=False;capture._remote_finished_at=None;capture._coordinate_topology=None
        capture.node=47;capture.metadata={};capture.config=SimpleNamespace(source_type='monitor',fps=15,rect=[0,0,32,24])
        return capture,portal,api,peer
    def test_parent_copy_retains_socket_after_child_duplicate_is_closed(self):
        import os,socket
        left,peer=socket.socketpair();child=os.dup(left.fileno());peer.setblocking(False)
        try:
            os.close(child)
            with self.assertRaises(BlockingIOError):peer.recv(1)
            left.close();self.assertEqual(peer.recv(1),b'')
        finally:left.close();peer.close()
    def test_finish_waits_for_child_then_releases_remote_once_without_session_close(self):
        import os,tempfile
        from unittest.mock import Mock,patch
        capture,portal,api,peer=self.adapter();events=[];fd=portal.fd
        process=Mock();process.poll.return_value=None
        process.terminate.side_effect=lambda:events.append('terminate')
        def waited(**kwargs):os.fstat(fd);events.append('waited')
        process.wait.side_effect=waited;process.stdout.close.side_effect=lambda:events.append('stdout-closed');capture.process=process
        real_close=os.close
        def close(which):
            if which==fd:events.append('parent-fd-closed')
            real_close(which)
        try:
            with patch('loomrec.wayland_capture.time.monotonic',return_value=100.),patch('loomrec.portal.os.close',side_effect=close):capture.finish()
            self.assertEqual(events,['terminate','waited','stdout-closed','parent-fd-closed'])
            self.assertIsNone(portal.fd);self.assertIsNone(capture.process);self.assertEqual(capture._remote_finished_at,100.)
            self.assertEqual(portal.session,'/own/session');self.assertFalse(portal.disposed);api.Close.assert_not_called()
            with self.assertRaises(OSError):os.fstat(fd)
            # An unrelated file may reuse the closed descriptor number.
            with tempfile.TemporaryFile() as unrelated:
                capture.finish();capture.close();capture.close();os.fstat(unrelated.fileno())
            self.assertEqual(capture._remote_finished_at,100.);api.Close.assert_called_once()
        finally:capture.close();peer.close()
    def test_failed_begin_releases_parent_fd_and_final_close_cannot_close_it_twice(self):
        import os,tempfile
        from unittest.mock import Mock,patch
        capture,portal,api,peer=self.adapter();original=portal.fd;read,write=os.pipe();os.close(write)
        process=Mock();process.stdout=os.fdopen(read,'rb');process.poll.return_value=None
        try:
            with tempfile.TemporaryFile() as log,patch.dict('os.environ',{'HYPRLAND_INSTANCE_SIGNATURE':'own-fixture'}),patch('loomrec.wayland_capture.wait_remote_quiescence') as barrier,patch('loomrec.wayland_capture.subprocess.Popen',return_value=process):
                with self.assertRaisesRegex(RuntimeError,'leer PipeWire'):capture.begin(log)
                barrier.assert_not_called()
            self.assertIsNone(portal.fd);self.assertIsNone(capture.process);self.assertIsNotNone(capture._remote_finished_at)
            self.assertEqual(peer.recv(1),b'')
            with self.assertRaises(OSError):os.fstat(original)
            capture.close();capture.close();api.Close.assert_called_once()
        finally:capture.close();peer.close()
    def test_cancellation_during_quiescence_cannot_acquire_a_new_remote(self):
        from unittest.mock import Mock,patch
        from loomrec.portal import PortalCancelled
        capture,portal,api,peer=self.adapter();capture.finish();capture._remote_used=True
        try:
            with patch.dict('os.environ',{'HYPRLAND_INSTANCE_SIGNATURE':'own-fixture'}),patch('loomrec.wayland_capture.wait_remote_quiescence',side_effect=PortalCancelled('own stop')),patch('loomrec.wayland_capture.subprocess.Popen') as spawn:
                with self.assertRaises(PortalCancelled):capture.begin(Mock())
                api.OpenPipeWireRemote.assert_not_called();spawn.assert_not_called()
            self.assertIsNone(portal.fd);self.assertFalse(portal.disposed)
        finally:capture.close();peer.close()


    def test_reconnect_barrier_precedes_remote_and_spawn_then_failed_start_releases_new_fd(self):
        import os,socket,tempfile
        from unittest.mock import Mock,patch
        capture,portal,api,peer=self.adapter();capture.finish();capture._remote_used=True
        new_left,new_peer=socket.socketpair();fresh=new_left.detach();events=[]
        def acquired():events.append('open-remote');return fresh
        api.OpenPipeWireRemote.return_value.take.side_effect=acquired
        read,write=os.pipe();os.close(write);process=Mock();process.stdout=os.fdopen(read,'rb');process.poll.return_value=None
        def spawn(*args,**kwargs):events.append('spawn');self.assertEqual(kwargs['pass_fds'],(fresh,));return process
        try:
            with tempfile.TemporaryFile() as log,patch.dict('os.environ',{'HYPRLAND_INSTANCE_SIGNATURE':'own-fixture'}),patch('loomrec.wayland_capture.wait_remote_quiescence',side_effect=lambda *args:events.append('quiescence')),patch('loomrec.wayland_capture.subprocess.Popen',side_effect=spawn):
                with self.assertRaisesRegex(RuntimeError,'leer PipeWire'):capture.begin(log)
            self.assertEqual(events,['quiescence','open-remote','spawn']);self.assertIsNone(portal.fd)
            self.assertEqual(new_peer.recv(1),b'');self.assertEqual(portal.session,'/own/session')
            api.Close.assert_not_called();capture.close();api.Close.assert_called_once()
        finally:capture.close();peer.close();new_peer.close()


    def test_popen_error_releases_remote_without_requiring_external_close(self):
        import os,tempfile
        from unittest.mock import patch
        capture,portal,api,peer=self.adapter();original=portal.fd
        try:
            with tempfile.TemporaryFile() as log,patch('loomrec.wayland_capture.subprocess.Popen',side_effect=OSError('own spawn fixture')):
                with self.assertRaisesRegex(OSError,'own spawn fixture'):capture.begin(log)
            self.assertIsNone(capture.process);self.assertIsNone(portal.fd);self.assertIsNotNone(capture._remote_finished_at)
            with self.assertRaises(OSError):os.fstat(original)
            self.assertEqual(peer.recv(1),b'');api.Close.assert_not_called();capture.close();capture.close();api.Close.assert_called_once()
        finally:capture.close();peer.close()
    def test_stdout_close_error_still_releases_fd_and_final_close_disposes_session(self):
        import os
        from unittest.mock import Mock
        capture,portal,api,peer=self.adapter();original=portal.fd
        process=Mock();process.poll.return_value=0;process.stdout.close.side_effect=OSError('own stdout close fixture');capture.process=process
        try:
            with self.assertRaisesRegex(OSError,'own stdout close fixture'):capture.close()
            self.assertIsNone(capture.process);self.assertIsNone(portal.fd);self.assertTrue(portal.disposed)
            self.assertIsNotNone(capture._remote_finished_at);self.assertEqual(peer.recv(1),b'')
            with self.assertRaises(OSError):os.fstat(original)
            capture.close();capture.close();api.Close.assert_called_once();portal.bus.close.assert_called_once()
        finally:capture.close();peer.close()
    def test_wait_error_attempts_kill_and_reap_then_releases_remote(self):
        import os
        from unittest.mock import Mock
        capture,portal,api,peer=self.adapter();original=portal.fd
        process=Mock();process.poll.return_value=None;process.wait.side_effect=[OSError('own wait fixture'),0];capture.process=process
        try:
            with self.assertRaisesRegex(OSError,'own wait fixture'):capture.finish()
            process.kill.assert_called_once();self.assertEqual(process.wait.call_count,2);process.stdout.close.assert_called_once()
            self.assertIsNone(capture.process);self.assertIsNone(portal.fd);self.assertEqual(peer.recv(1),b'')
            with self.assertRaises(OSError):os.fstat(original)
            capture.close();capture.close();api.Close.assert_called_once()
        finally:capture.close();peer.close()

if __name__=='__main__':unittest.main()
