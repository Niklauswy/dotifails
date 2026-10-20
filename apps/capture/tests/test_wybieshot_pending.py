"""Region cancellation through real private D-Bus + QApplication.exec.

Only the consent transport is real. PipeWire begin/bytes are owned pipes and
synthetic QImages; no compositor, host bus, inputs or media are used.
"""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def private_client():
    import time
    import dbus
    from PySide6.QtCore import QTimer,QEvent
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage,QColor,QKeyEvent
    from PySide6.QtWidgets import QApplication
    from wybieshot.ui.main import Window
    from wybieshot.actions import ActionWindow,CaptureActions
    from wybieshot.capture import CaptureEngine,CaptureResult
    from wybieshot.schema import Rect
    from wybieshot.instance import CaptureLease
    from wybieshot.storage import Storage
    from loomrec.portal import Portal
    from loomrec.wayland_capture import PipeWireCapture
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    service=subprocess.Popen([sys.executable,str(ROOT/'tests/portal_fixture_service.py')],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    bus=None;window=None;results=[];portals=[];pipes=[]
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(service.stdout,selectors.EVENT_READ)
            if not selector.select(3) or service.stdout.readline()!=b'READY\n':
                raise RuntimeError('Private synthetic portal did not start')
        bus=dbus.SessionBus(private=True);bus.set_exit_on_disconnect(False)
        control=dbus.Interface(bus.get_object(str(bus.get_name_owner('org.freedesktop.portal.Desktop')),
            '/org/freedesktop/portal/desktop'),'org.wysun.Test')
        original_init=Portal.__init__;original_request=Portal.request
        state={}
        def portal_init(self,**kwargs):
            original_init(self,**kwargs)
            if state.get('case','').startswith('strict-'):self.close_timeout=.08
            portals.append(self)
        def request(self,*args,**kwargs):
            if state.get('case')=='timeout':kwargs['timeout']=1
            return original_request(self,*args,**kwargs)
        def begin(self,log,even=True):
            # report(frame) must have hidden the status dialog before any
            # consumer starts, so its pixels cannot enter the frozen image.
            assert state.get('hidden'), 'GUI did not hide status before connecting the consumer'
            state['begin']=True
            if state['case']=='begin-cancel':
                while True:
                    self.portal.on_wait();time.sleep(.01)
            read,write=os.pipe();pipes.append(read)
            if state['case']!='read-cancel':
                image=QImage(32,24,QImage.Format_ARGB32);image.fill(QColor('#315787'))
                os.write(write,bytes(image.constBits()))
            os.close(write) if state['case']!='read-cancel' else pipes.append(write)
            return read,32,24
        cases=('quick-cancel-retry','quick-escape','direct-cancel','close-pending','portal-cancel',
               'portal-error','timeout','begin-cancel','read-cancel')
        if len(sys.argv)>2:cases=(sys.argv[2],)
        with patch.object(Portal,'__init__',portal_init),patch.object(Portal,'request',request),patch.object(PipeWireCapture,'begin',begin):
            for index,case in enumerate(cases):
                strict=case.startswith('strict-')
                desktop=case.startswith('desktop-')
                control.Configure(case if strict else 'strict-ack' if case=='desktop-cancel-ack' else 'hold-select-close' if case=='select-close-hold' else 'hold-start' if case in ('quick-cancel-retry','quick-escape','direct-cancel','close-pending','timeout') else
                    'cancel-start' if case=='portal-cancel' else 'fail-start' if case=='portal-error' else 'success')
                state.clear();state.update(case=case,phase='wait',begin=False)
                root=Path.home()/case;root.mkdir()
                store=Storage(root/'library');store.update_settings(delay=0,include_cursor=True)
                # The real ScreenCast pending/cancel transport is now reached
                # through the cursor branch: non-cursor region freezes use the
                # Screenshot portal and expose no provider picker to hold.
                cls=ActionWindow if case in ('direct-cancel','portal-cancel','portal-error') else Window
                window=cls(CaptureActions(delay=0),store,CaptureEngine()) if cls is ActionWindow else cls(store,CaptureEngine())
                if desktop:
                    class DesktopEngine:
                        def capture(self,request,*,progress,on_wait):
                            assert request.mode=='desktop' and request.include_cursor
                            portal=Portal(strict_close=True);portal.on_wait=on_wait
                            try:
                                portal.screencast('monitor',False)
                                image=QImage(32,24,QImage.Format_ARGB32);image.fill(QColor('#315787'))
                                return CaptureResult(image,Rect(0,0,32,24),'desktop','owned desktop fixture')
                            finally:portal.close()
                        def freeze(self,*args,**kwargs):raise AssertionError('Desktop must not freeze REGION')
                    window.engine=DesktopEngine();window.capture_mode='desktop';store.update_settings(include_cursor=True)
                window._capture_lease=CaptureLease(root/'lease');assert window._capture_lease.claim()
                competing=CaptureLease(root/'lease');assert not competing.claim()
                # This harness owns app termination, while exercising the same
                # Window/ActionWindow cancellation and closeEvent paths.
                app._wybieshot_window=None
                errors=[];beats=[];before=time.monotonic();start_portals=len(portals)
                def fail(exc):
                    errors.append(str(exc));app.exit(1)
                def poll():
                    try:
                        beats.append(1)
                        feedback=window._capture_feedback
                        if feedback:
                            state['feedback']=feedback
                            if feedback.dialog:state['hidden']=not feedback.dialog.isVisible()
                        stats=json.loads(control.Stats())
                        if not stats['selected' if strict or case in ('select-close-hold','desktop-cancel-ack') else 'started']:return
                        if state['phase']=='wait':
                            trigger=(stats['selected']==1 if strict or case in ('select-close-hold','desktop-cancel-ack') else stats['started']==1 if case in ('quick-cancel-retry','quick-escape','direct-cancel','close-pending') else state['begin'] if case in ('begin-cancel','read-cancel') else False)
                            if case=='strict-initial-error':trigger=False
                            if trigger:
                                assert feedback is not None
                                assert not competing.claim()
                                if strict:
                                    portal=portals[-1];original_wait=portal.on_wait;state['wait_calls']=0
                                    def counted_wait():
                                        state['wait_calls']+=1;return original_wait()
                                    portal.on_wait=counted_wait
                                if case=='close-pending':window.close()
                                elif case=='desktop-cancel-ack':window.cancel_capture()
                                elif case=='quick-escape':app.sendEvent(feedback.dialog,QKeyEvent(QEvent.KeyPress,Qt.Key_Escape,Qt.NoModifier))
                                else:feedback.cancel_button.click()
                                # Cancel requests teardown, never steals/releases
                                # a still-running worker's lease.
                                assert window.busy and window.jobs
                                assert not competing.claim()
                                state['phase']='cancelled'
                        if strict and state['phase']=='cancelled':
                            portal=portals[-1];assert portal.strict_close
                            target='request-close-unconfirmed' if case.startswith('strict-response-') else 'session-close-unconfirmed'
                            if portal.cancel_state==target:
                                assert window.jobs and window.busy and not competing.claim()
                                assert feedback.dialog.isVisible() and feedback.cancelled.is_set()
                                assert stats['started']==stats['remotes']==stats['sessions_closed']==0
                                if 'unconfirmed' not in state:
                                    state['unconfirmed']=time.monotonic();state['calls_after_cancel']=state['wait_calls']
                                assert state['wait_calls']==state['calls_after_cancel'], 'on_wait repeated after cancellation'
                                if time.monotonic()-state['unconfirmed']>=.35:
                                    if case=='strict-response-closed':control.CompleteSelection(1,True)
                                    elif case=='strict-response-success':control.CompleteSelection(0,False)
                                    elif case=='strict-session-error':control.Revoke({})
                                    elif case=='strict-owner-loss':control.ReplaceOwner()
                                    state['phase']='await-close'
                        if case=='select-close-hold' and state['phase']=='cancelled' and stats['requests_closed']:
                            assert window.jobs and window.busy and not competing.claim()
                            assert feedback.dialog.isVisible() and feedback.cancelled.is_set()
                            assert stats['sessions_closed']==stats['remotes']==0
                            assert 'selector del portal' in feedback.text.text()
                            if 'close_sent' not in state:state['close_sent']=time.monotonic()
                            if time.monotonic()-state['close_sent']>=.15:
                                control.ReleaseClose();state['phase']='await-close'
                        if window.jobs:return
                        if case=='quick-cancel-retry' and state['phase']=='cancelled':
                            assert window.quick.isVisible() and not window.busy
                            assert stats['requests_closed']==stats['sessions_closed']==1,stats
                            assert competing.claim();competing.release()
                            assert store.list_sessions()==[]
                            control.Configure('success');state.update(phase='retry',begin=False)
                            window._capture_lease=CaptureLease(root/'lease')
                            window.begin_capture();return
                        if desktop:
                            if case=='desktop-success':
                                assert window.document is not None
                                assert window.document.render().pixelColor(0,0).name()=='#315787'
                                assert 'owned desktop fixture' in window.statusBar().currentMessage()
                            else:assert window.document is None and window.quick.isVisible()
                            assert not window.busy
                        elif strict:
                            if case=='strict-initial-error':
                                assert window.isVisible() and 'NoReply' in window.statusBar().currentMessage()
                            else:assert window.quick.isVisible()
                            assert not window.busy
                            assert stats['requests_closed']==1 and stats['session_close_calls']<=1,stats
                            assert stats['started']==stats['remotes']==0,stats
                            if case not in ('strict-ack','strict-initial-error'):assert 'unconfirmed' in state
                        elif case=='quick-cancel-retry' and state['phase']=='retry':
                            if window.overlay is None:return
                            assert window.frozen.image.pixelColor(0,0).name()=='#315787'
                            assert window._capture_feedback is None
                            assert not competing.claim();window.cancel_capture()
                        elif case in ('direct-cancel','portal-cancel'):
                            assert not window.quick.isVisible() and not window.isVisible()
                            assert not window.busy
                        elif case=='close-pending':
                            if window._capture_lease is not None:return
                            assert window._closing and not window.quick.isVisible()
                        elif case in ('portal-error','timeout'):
                            assert window.isVisible() and not window._closing
                            assert ('rechazó' if case=='portal-error' else 'no respondió') in window.statusBar().currentMessage()
                        elif case in ('quick-escape','begin-cancel','read-cancel','select-close-hold'):
                            assert state['phase']==('await-close' if case=='select-close-hold' else 'cancelled')
                            assert window.quick.isVisible() and not window.busy
                        elif state['phase']=='wait':return
                        assert window.overlay is None
                        if case!='desktop-success':assert window.document is None
                        assert store.list_sessions()==[]
                        assert competing.claim();competing.release()
                        for portal in portals[start_portals:]:assert portal.disposed and portal.fd is None and portal.session is None
                        stats=json.loads(control.Stats())
                        assert stats['created']==1,stats
                        assert stats['sessions_closed']==(0 if case=='strict-owner-loss' else 1),stats
                        if case in ('quick-escape','direct-cancel','close-pending','timeout','select-close-hold'):assert stats['requests_closed']==1,stats
                        assert len(beats)>1
                        results.append(dict(case=case,elapsed=round(time.monotonic()-before,3),qt_ticks=len(beats),
                            lease_free=True,portal_closed=True,requests_closed=stats['requests_closed']))
                        app.quit()
                    except Exception:
                        import traceback
                        fail(traceback.format_exc())
                timer=QTimer();timer.setInterval(10);timer.timeout.connect(poll)
                guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(lambda:fail('Private QApplication case timed out: '+case));guard.start(6000)
                timer.start();window.begin_capture();app.exec()
                timer.stop();guard.stop()
                if window.jobs:
                    if window._capture_feedback:window._capture_feedback.cancel()
                    # Only private fixture processes are involved in this failure.
                    service.terminate();service.wait(timeout=2)
                    print(json.dumps(dict(case=case,errors=errors,unfinished=True)),flush=True);os._exit(4)
                if errors:raise AssertionError(errors)
                window.close();window.quick.close();window.quick.deleteLater();window.deleteLater()
                app.sendPostedEvents(None,QEvent.DeferredDelete);window=None
                for fd in pipes:os.close(fd)
                pipes.clear()
        control.Quit();service.wait(timeout=2)
        print(json.dumps(dict(cases=results,loop='QApplication.exec',manual_process_events=False,
            media=False,bus='synthetic-private',frames='owned QImage pipes')),flush=True)
    finally:
        if bus:bus.close()
        if service.poll() is None:service.terminate();service.wait(timeout=2)
        service.stdout.close();service.stderr.close()
        for fd in pipes:os.close(fd)


class PendingTests(unittest.TestCase):
    def test_wait_dialog_escape_stays_visible_until_worker_ack(self):
        from PySide6.QtCore import QObject,QTimer,QEvent,Qt
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtWidgets import QApplication
        from wybieshot.ui.capture_feedback import CaptureWaitFeedback
        app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False)
        class Owner(QObject):
            def __init__(self):super().__init__();self.calls=0
            def cancel_capture(self):self.calls+=1;self.feedback.cancel()
        owner=Owner();owner.feedback=feedback=CaptureWaitFeedback(owner)
        result={}
        def escape():
            app.sendEvent(feedback.dialog,QKeyEvent(QEvent.KeyPress,Qt.Key_Escape,Qt.NoModifier))
            result.update(cancelled=feedback.cancelled.is_set(),visible=feedback.dialog.isVisible(),calls=owner.calls,
                message=feedback.text.text(),button_enabled=feedback.cancel_button.isEnabled())
            # A WM close request is also cancellation, never teardown ACK.
            feedback.dialog.close();result['visible_after_close']=feedback.dialog.isVisible()
            feedback.close()  # Owned fixture supplies the simulated teardown ACK.
            app.quit()
        QTimer.singleShot(0,escape);guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(app.quit);guard.start(1000)
        app.exec();guard.stop()
        try:
            self.assertTrue(result.get('cancelled'));self.assertTrue(result.get('visible'))
            self.assertTrue(result.get('visible_after_close'));self.assertFalse(result.get('button_enabled'))
            self.assertIn('selector del portal',result.get('message',''))
            self.assertGreaterEqual(result.get('calls',0),1)
        finally:
            if feedback.dialog is not None:feedback.close()
            owner.deleteLater();app.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_callbacks_cover_consent_before_begin_and_always_close(self):
        from loomrec.portal_image import capture_frame
        calls=[]
        def check():calls.append('check')
        def progress(state):calls.append(state['stage'])
        class Owned:
            def __init__(self,config,on_wait=None):
                assert config.strict_close is True
                self.on_wait=on_wait;on_wait();calls.append('consent')
            def close(self):calls.append('closed')
        with patch('loomrec.portal_image.PipeWireCapture',Owned),patch('loomrec.portal_image.read_frame',side_effect=lambda capture,on_wait:calls.append('read') or 42):
            self.assertEqual(capture_frame('monitor',False,progress=progress,on_wait=check),42)
        self.assertEqual(calls,['check','consent','check','frame','read','closed'])
        calls.clear()
        with patch('loomrec.portal_image.PipeWireCapture',Owned),patch('loomrec.portal_image.read_frame') as read:
            with self.assertRaisesRegex(RuntimeError,'owned cancel'):
                capture_frame('monitor',progress=lambda state:(_ for _ in ()).throw(RuntimeError('owned cancel')),on_wait=check)
            read.assert_not_called();self.assertEqual(calls[-1],'closed')

    def test_pipewire_strict_flag_is_explicit_and_recorder_defaults_legacy(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from loomrec.wayland_capture import PipeWireCapture
        for flag in (None,False,True):
            config=SimpleNamespace(source_type='monitor',cursor=False)
            if flag is not None:config.strict_close=flag
            portal=Mock();portal.screencast.return_value=(47,{})
            with patch('loomrec.wayland_capture.Portal',return_value=portal) as factory:
                capture=PipeWireCapture(config,on_wait=lambda:None)
                factory.assert_called_once_with(**({'strict_close':True} if flag else {}))
                capture.cancel()
                if flag:self.assertIs(portal.cancel_requested,True)

    def run_private_cases(self,cases):
        if not shutil.which('dbus-run-session'):self.skipTest('dbus-run-session unavailable')
        try:import dbus;from gi.repository import GLib
        except ImportError:self.skipTest('Private D-Bus/GLib unavailable')
        with tempfile.TemporaryDirectory(prefix='wysun-region-pending-') as home:
            env=dict(os.environ,HOME=home,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1',
                XDG_SESSION_TYPE='wayland',WAYLAND_DISPLAY='synthetic-not-connected',QT_QPA_PLATFORM='offscreen',PYTHONFAULTHANDLER='1')
            for key in ('DISPLAY','DBUS_SESSION_BUS_ADDRESS','DBUS_STARTER_ADDRESS','DBUS_STARTER_BUS_TYPE',
                        'HYPRLAND_INSTANCE_SIGNATURE','QT_NO_GLIB','APPIMAGE','APPDIR','ARGV0'):
                env.pop(key,None)
            # Isolate cancellation from the separate offscreen Qt/GLib default
            # context race. This fixture setting is not a product bootstrap
            # change; the integrator tests the public native path separately.
            env['QT_NO_GLIB']='1'
            for key in ('XDG_RUNTIME_DIR','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_STATE_HOME'):
                path=Path(home)/key;path.mkdir(mode=0o700);env[key]=str(path)
            for case in cases:
                # Direct commands have separate Qt lifetimes in production.
                # The quick retry remains within one exec() in its own case.
                result=subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),
                    '--private-client',case],env=env,capture_output=True,text=True,timeout=10)
                if result.returncode==127 and 'Operation not permitted' in result.stderr:self.skipTest('Sandbox blocks private D-Bus sockets')
                self.assertEqual(result.returncode,0,case+'\n'+result.stdout+'\n'+result.stderr)
                data=json.loads(result.stdout);self.assertEqual(len(data['cases']),1)
                self.assertFalse(data['media']);self.assertFalse(data['manual_process_events'])

    def test_region_pending_exec_cancel_close_timeout_error_and_reopen(self):
        self.run_private_cases(('quick-cancel-retry','quick-escape','direct-cancel','close-pending','portal-cancel',
                                'portal-error','timeout','begin-cancel','read-cancel'))

    def test_select_sources_close_hold_keeps_lease_until_reply(self):
        self.run_private_cases(('select-close-hold',))

    def test_strict_close_no_reply_terminal_evidence_and_original_owner(self):
        self.run_private_cases(('strict-ack','strict-response-closed','strict-response-success',
                                'strict-session-error','strict-owner-loss','strict-initial-error'))

    def test_desktop_feedback_success_and_cancel_ack_hold_lease_until_finished(self):
        self.run_private_cases(('desktop-success','desktop-cancel-ack'))


if __name__=='__main__':
    if sys.argv[1:2]==['--private-client']:private_client()
    else:unittest.main()
