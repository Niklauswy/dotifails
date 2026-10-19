"""Real D-Bus transport with a synthetic service, distinct from real capture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]


def private_client():
    import selectors
    import socket
    import stat
    import time
    import dbus
    from loomrec.portal import Portal,PortalCancelled
    service=subprocess.Popen([sys.executable,str(ROOT/'tests/portal_fixture_service.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    bus=None;portal=None;cases=[]
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(service.stdout,selectors.EVENT_READ)
            if not selector.select(5):raise TimeoutError('Private service not ready')
        if service.stdout.readline()!=b'READY\n':raise RuntimeError(service.stderr.read().decode())
        bus=dbus.SessionBus(private=True);bus.set_exit_on_disconnect(False)
        test=dbus.Interface(bus.get_object('org.freedesktop.portal.Desktop','/org/freedesktop/portal/desktop'),'org.wysun.Test')
        for mode in ('success','legacy'):
            test.Configure(mode);portal=Portal()
            node,metadata=portal.screencast('monitor',cursor=True)
            assert node==47 and int(metadata['size'][0])==100 and int(metadata['position'][0])==-100
            assert ('pipewire-serial' in metadata)==(mode=='success')
            if mode=='success':assert int(metadata['pipewire-serial'])==987654321001
            baseline=len(os.listdir('/proc/self/fd'));previous=portal.fd
            assert stat.S_ISSOCK(os.fstat(previous).st_mode)
            duplicate=socket.socket(fileno=os.dup(previous));assert duplicate.getsockopt(socket.SOL_SOCKET,socket.SO_TYPE)==socket.SOCK_STREAM;duplicate.close()
            for _ in range(3):
                current=portal.open_remote();assert current!=previous
                try:os.fstat(previous)
                except OSError:pass
                else:raise AssertionError('Previous remote FD leaked')
                assert len(os.listdir('/proc/self/fd'))==baseline;previous=current
            stats=json.loads(test.Stats());assert stats['remotes']==4 and stats['sessions_closed']==0
            assert not portal.disposed and portal.bus.get_is_connected() # connection lives across pauses
            portal.close();portal.close();portal=None
            stats=json.loads(test.Stats());assert stats['sessions_closed']==1
            cases.append(mode+'-3-remotes-and-close')
        for mode in ('cancel-create','cancel-select','cancel-start','fail-start','no-window','no-cursor'):
            test.Configure(mode);portal=Portal()
            try:portal.screencast('window',cursor=True)
            except (PortalCancelled,RuntimeError):pass
            else:raise AssertionError('Failure fixture accepted: '+mode)
            portal.close();portal=None;stats=json.loads(test.Stats())
            expected=0 if mode in ('cancel-create','no-window','no-cursor') else 1
            assert stats['created']==expected and stats['sessions_closed']==expected and stats['remotes']==0,(mode,stats)
            cases.append(mode+'-closed')
        test.Configure('success');portal=Portal();portal.screencast('monitor')
        dbus.Interface(portal.bus.get_object('org.freedesktop.portal.Desktop',portal.session),'org.freedesktop.portal.Session').Close()
        deadline=time.monotonic()+.1
        while time.monotonic()<deadline:portal.dispatch();time.sleep(.005)
        assert not portal.closed,'Own Close must not manufacture a backend Closed signal'
        portal.close();assert portal.disposed and portal.fd is None;portal=None
        assert json.loads(test.Stats())['sessions_closed']==1
        cases.append('own-close-without-closed-signal')
        for details in ({},{'reason':dbus.String('synthetic-backend-revocation')}):
            test.Configure('success');portal=Portal();portal.screencast('window',cursor=False)
            stats=json.loads(test.Stats());assert stats['types']==2 and stats['cursor']==1
            test.Revoke(dbus.Dictionary(details,signature='sv'));deadline=time.monotonic()+2
            while not portal.closed and time.monotonic()<deadline:
                try:portal.dispatch()
                except RuntimeError:break
                time.sleep(.005)
            assert portal.closed,'Closed(a{sv}) was not dispatched'
            try:portal.dispatch()
            except RuntimeError:pass
            else:raise AssertionError('Revocation did not interrupt capture')
            try:portal.open_remote()
            except RuntimeError:pass
            else:raise AssertionError('Remote opened after revocation')
            remote=portal.fd;portal.close();portal.close();assert portal.disposed and portal.fd is None;portal=None
            try:os.fstat(remote)
            except OSError:pass
            else:raise AssertionError('Remote FD leaked after revocation')
            cases.append('window-hidden-cursor-revocation-'+('details' if details else 'empty'))
        test.Quit();service.wait(timeout=3)
        print(json.dumps(dict(service='synthetic-private-dbus',media=False,cases=cases)))
    finally:
        if portal:portal.close()
        if bus:bus.close()
        if service.poll() is None:service.terminate();service.wait(timeout=3)
        service.stdout.close();service.stderr.close()


class PortalBusTests(unittest.TestCase):
    def test_serial_target_never_sets_reusable_node_path(self):
        from unittest.mock import Mock
        from loomrec.pipewire_bridge import configure_pipewire_source
        source=Mock();configure_pipewire_source(source,13,47,{'pipewire-serial':987654321001})
        values=dict(call.args for call in source.set_property.call_args_list)
        self.assertEqual(values,{'fd':13,'do-timestamp':True,'target-object':'987654321001'})
        source=Mock();configure_pipewire_source(source,13,47,{})
        values=dict(call.args for call in source.set_property.call_args_list)
        self.assertEqual(values,{'fd':13,'do-timestamp':True,'path':'47'});source.find_property.assert_not_called()
        source=Mock();source.find_property.return_value=None
        with self.assertRaisesRegex(RuntimeError,'object.serial'):configure_pipewire_source(source,13,47,{'pipewire-serial':12})
        for serial in (-1,2**64,True,1.5,'12'):
            with self.assertRaises(ValueError):configure_pipewire_source(Mock(),13,47,{'pipewire-serial':serial})

    def test_private_service_lifecycle_capabilities_cancel_and_revocation(self):
        if not shutil.which('dbus-run-session'):self.skipTest('dbus-run-session unavailable')
        try:import dbus;from gi.repository import GLib
        except ImportError:self.skipTest('dbus-python/GLib unavailable')
        env=dict(os.environ,PYTHONPATH=str(ROOT));env.pop('DBUS_STARTER_ADDRESS',None);env.pop('DBUS_STARTER_BUS_TYPE',None)
        result=subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),'--private-client'],env=env,capture_output=True,text=True,timeout=30)
        if result.returncode==127 and 'Failed to bind socket' in result.stderr and 'Operation not permitted' in result.stderr:
            self.skipTest('Sandbox blocks creation of the private D-Bus socket')
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        data=json.loads(result.stdout);self.assertFalse(data['media']);self.assertEqual(len(data['cases']),11)

if __name__=='__main__':
    if sys.argv[1:]==['--private-client']:private_client()
    else:unittest.main()
