"""Blocking Qt exec + real private D-Bus transport; no GUI, pixels or media."""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def private_client():
    import time
    import dbus
    # Exercise the same bootstrap before constructing a real Qt event loop.
    from wybieshot.__main__ import prepare_event_loop
    prepare_event_loop()
    from PySide6.QtCore import QCoreApplication,QTimer
    from wybieshot.ui.main import Work
    from wybieshot.instance import CaptureLease
    from loomrec.portal import Portal
    assert os.environ['QT_NO_GLIB']=='1'
    app=QCoreApplication([])
    service=subprocess.Popen([sys.executable,str(ROOT/'tests/portal_fixture_service.py')],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    bus=None;job=None;results=[]
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(service.stdout,selectors.EVENT_READ)
            if not selector.select(3) or service.stdout.readline()!=b'READY\n':
                raise RuntimeError('Private synthetic portal did not start')
        bus=dbus.SessionBus(private=True);bus.set_exit_on_disconnect(False)
        test=dbus.Interface(bus.get_object('org.freedesktop.portal.Desktop',
            '/org/freedesktop/portal/desktop'),'org.wysun.Test')
        for mode in ('success','cancel-start','fail-start','hold-start','success'):
            test.Configure(mode)
            lease=CaptureLease(Path.home()/'owned-lease');assert lease.claim()
            competing=CaptureLease(Path.home()/'owned-lease');assert not competing.claim()
            outcome={};cleanup={};ticks=[]
            def task():
                portal=Portal()
                request=portal.request
                def bounded(*args,**kwargs):
                    kwargs['timeout']=1
                    return request(*args,**kwargs)
                portal.request=bounded
                try:
                    node,_=portal.screencast('monitor',False)
                    assert node==47
                    return node
                finally:
                    portal.close();cleanup.update(disposed=portal.disposed,fd_closed=portal.fd is None)
            job=Work(task,app)
            job.ready.connect(lambda node:outcome.update(node=node))
            job.failed.connect(lambda message:outcome.update(error=message))
            job.finished.connect(app.quit)
            heartbeat=QTimer();heartbeat.setInterval(10);heartbeat.timeout.connect(lambda:ticks.append(1));heartbeat.start()
            guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(app.quit);guard.start(5000)
            before=time.monotonic();job.start()
            try:app.exec()  # Never pump processEvents() manually.
            finally:lease.release();heartbeat.stop();guard.stop()
            if not job.wait(300):
                # Only this owned process/service; avoid destructing a live QThread.
                service.terminate();service.wait(timeout=2)
                print(json.dumps({'blocked':True,'mode':mode}),flush=True);os._exit(4)
            assert cleanup==dict(disposed=True,fd_closed=True),cleanup
            assert competing.claim();competing.release()  # Next direct invocation can claim.
            stats=json.loads(test.Stats())
            assert stats['created']==stats['sessions_closed']==1,stats
            assert stats['remotes']==(1 if mode=='success' else 0),stats
            if mode=='success':assert outcome==dict(node=47),outcome
            elif mode=='cancel-start':assert 'cancelada' in outcome.get('error',''),outcome
            elif mode=='fail-start':assert 'rechazó' in outcome.get('error',''),outcome
            else:
                assert 'no respondió' in outcome.get('error',''),outcome
                assert stats['requests_closed']==1,stats
            if mode=='hold-start':assert ticks,'Qt timers stopped during portal wait'
            results.append(dict(mode=mode,elapsed=round(time.monotonic()-before,3),
                qt_timer_ticks=len(ticks),session_closed=True,fd_closed=True,lease_reclaim=True))
            job.deleteLater();job=None
        test.Quit();service.wait(timeout=2)
        print(json.dumps(dict(cases=results,loop='QCoreApplication.exec',manual_process_events=False,
            media=False,graphics=False,bus='synthetic-private')),flush=True)
    finally:
        if bus:bus.close()
        if service.poll() is None:service.terminate();service.wait(timeout=2)
        service.stdout.close();service.stderr.close()


class EventLoopTests(unittest.TestCase):
    def test_bootstrap_scoped_to_wayland_and_does_not_select_xcb(self):
        from unittest.mock import patch
        from wybieshot.__main__ import prepare_event_loop
        for env in ({'XDG_SESSION_TYPE':'wayland'},{'WAYLAND_DISPLAY':'own-wayland'}):
            with self.subTest(env=env),patch.dict(os.environ,env,clear=True):
                prepare_event_loop();self.assertEqual(os.environ['QT_NO_GLIB'],'1')
                self.assertNotIn('QT_QPA_PLATFORM',os.environ)
        with patch.dict(os.environ,{'XDG_SESSION_TYPE':'x11'},clear=True):
            prepare_event_loop();self.assertNotIn('QT_NO_GLIB',os.environ)
        with patch.dict(os.environ,{'XDG_SESSION_TYPE':'x11','QT_NO_GLIB':'keep'},clear=True):
            prepare_event_loop();self.assertEqual(os.environ['QT_NO_GLIB'],'keep')

    def test_real_exec_private_portal_teardown_cancel_error_timeout_and_reopen(self):
        if not shutil.which('dbus-run-session'):self.skipTest('dbus-run-session unavailable')
        try:import dbus;from gi.repository import GLib
        except ImportError:self.skipTest('Private D-Bus/GLib unavailable')
        previous=os.environ.get('QT_NO_GLIB')
        with tempfile.TemporaryDirectory(prefix='wysun-exec-regression-') as home:
            env=dict(os.environ,HOME=home,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1',
                XDG_SESSION_TYPE='wayland',WAYLAND_DISPLAY='synthetic-not-connected')
            for key in ('DISPLAY','DBUS_SESSION_BUS_ADDRESS','DBUS_STARTER_ADDRESS','DBUS_STARTER_BUS_TYPE',
                        'HYPRLAND_INSTANCE_SIGNATURE','QT_NO_GLIB','APPIMAGE','APPDIR','ARGV0'):
                env.pop(key,None)
            for key in ('XDG_RUNTIME_DIR','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_STATE_HOME'):
                path=Path(home)/key;path.mkdir(mode=0o700);env[key]=str(path)
            result=subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),
                '--private-client'],env=env,capture_output=True,text=True,timeout=15)
        if result.returncode==127 and 'Failed to bind socket' in result.stderr and 'Operation not permitted' in result.stderr:
            self.skipTest('Sandbox blocks private D-Bus sockets')
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        data=json.loads(result.stdout);self.assertEqual(len(data['cases']),5)
        self.assertFalse(data['media']);self.assertFalse(data['graphics']);self.assertFalse(data['manual_process_events'])
        self.assertEqual(os.environ.get('QT_NO_GLIB'),previous)  # No session/Recorder-parent mutation.


if __name__=='__main__':
    if sys.argv[1:]==['--private-client']:private_client()
    else:unittest.main()
