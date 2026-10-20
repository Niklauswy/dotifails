#!/usr/bin/env python3
"""Probe a real portal on an already isolated, synthetic nested Hyprland.

Run ONLY through apps/shell/tests/nested_runtime.py --probe. The picker is
a declared fixture selecting the sole nested output; this does not test human
consent. No host buses, audio devices, microphone, camera or physical output.
"""
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PORTAL_ROOT = Path('/tmp/wysun-portal-tools/root')


def wait_for(function, description, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = function()
        if value:return value
        time.sleep(.1)
    raise RuntimeError('Timeout: ' + description)


def verify_gtk(run_dir, env, command, start):
    sys.path.insert(0, str(ROOT / 'apps/wysun/tests'))
    from manual_gtk_filechooser_probe import run_cases as gtk_cases
    from wayland_test_pointer import SyntheticPointer
    pointer = SyntheticPointer(env);pointer.keyboard()
    def gtk_command(argv,*args,**kwargs):
        # GTK mnemonics use a standard keymap. One-shot custom wtype keymaps
        # can deliver a key while failing the mnemonic lookup; retain a real
        # virtual seat/keymap for these shortcuts, as for the shell bind proof.
        keys={('wtype','-M','alt','-k','c','-m','alt'):(46,8),
              ('wtype','-M','alt','-k','a','-m','alt'):(30,8),
              ('wtype','-M','ctrl','-k','a','-m','ctrl'):(30,4),
              ('wtype','-M','ctrl','-k','l','-m','ctrl'):(38,4),
              ('wtype','-k','Return'):(28,0)}
        if tuple(argv) in keys:
            pointer.press(*keys[tuple(argv)]);return ''
        return command(argv,*args,**kwargs)
    try:chooser = gtk_cases(run_dir, env, gtk_command, start, wait_for)
    finally:pointer.close()
    protocol = (run_dir / 'private-gtk.log').read_text(errors='replace')
    imported = protocol.count('import_toplevel(') >= len(chooser)
    parented = protocol.count('set_parent_of(') >= len(chooser)
    assert imported and parented, 'GTK did not import and parent every exported native handle'
    for result in chooser.values():result['parent_import_verified'] = True
    (run_dir / 'gtk-filechooser-results.json').write_text(json.dumps(chooser, indent=2))
    print(json.dumps({'result':'WYSUN_GTK_FILECHOOSER_OK','cases':chooser}, indent=2), flush=True)


def main(serial_diagnostic=False, stream_diagnostic=False, case_selector='all'):
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/nonexistent')).resolve()
    run_dir = runtime.parent
    display = os.environ.get('WAYLAND_DISPLAY', '')
    assert str(runtime).startswith('/tmp/ws-') and runtime.name == 'r'
    assert '/' not in display and display and (runtime / display).is_socket()
    assert 'no-system-bus' in os.environ.get('DBUS_SYSTEM_BUS_ADDRESS', '')
    # Confirm the peer is the extracted test compositor, not a desktop socket.
    with socket.socket(socket.AF_UNIX) as connection:
        connection.connect(str(runtime / display))
        pid, uid, gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    executable = Path(f'/proc/{pid}/exe').resolve()
    assert executable.name == 'Hyprland' and str(executable).startswith('/tmp/'), executable
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = str(PORTAL_ROOT / 'usr/lib/x86_64-linux-gnu') + ':' + env.get('LD_LIBRARY_PATH', '')
    env['PATH'] = str(PORTAL_ROOT / 'usr/bin') + ':' + env['PATH']
    env['GST_PLUGIN_PATH'] = str(PORTAL_ROOT / 'usr/lib/x86_64-linux-gnu/gstreamer-1.0')
    env['GST_REGISTRY'] = str(run_dir / 'portal-gst-registry.bin')
    env['XDG_DATA_DIRS'] = str(PORTAL_ROOT / 'usr/share') + ':' + env.get('XDG_DATA_DIRS', '/usr/share')
    env['XDG_CURRENT_DESKTOP'] = 'Wysun:Hyprland'
    env['XDG_SESSION_DESKTOP'] = 'wysun'
    env['PIPEWIRE_RUNTIME_DIR'] = str(runtime)
    env['PIPEWIRE_REMOTE'] = 'pipewire-0'
    env['PULSE_SERVER'] = 'unix:' + str(runtime / 'no-pulse-server')
    if stream_diagnostic or case_selector.startswith('live-static'):
        env['GST_DEBUG'] = 'pipewiresrc:6'
    os.environ.update(env)
    # Quickshell/Qt may have activated a portal with the runner's earlier env.
    # This updates ONLY the fresh private bus, never the host user manager.
    subprocess.run(['dbus-update-activation-environment', '--all'], env=env, check=True)
    processes, streams = [], []
    recording = None

    def command(argv, timeout=20):
        return subprocess.run(list(map(str, argv)), env=env, cwd='/', text=True,
                              capture_output=True, timeout=timeout, check=True).stdout

    def start(name, argv, extra_env=None):
        log = (run_dir / (name + '.log')).open('w'); streams.append(log)
        process = subprocess.Popen(list(map(str, argv)), env=dict(env, **(extra_env or {})), cwd='/', stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        return process

    try:
        monitors = json.loads(command(['hyprctl', '-j', 'monitors']))
        assert len(monitors) == 1 and monitors[0]['name'] == 'WYSUN-TEST-1', monitors
        monitor = monitors[0]['name']
        config = Path(env['XDG_CONFIG_HOME'])
        picker = run_dir / 'fixture-picker'
        picker.write_text('#!/usr/bin/python3\nprint(' + repr('[SELECTION]/screen:' + monitor) + ')\n')
        if case_selector=='screenshot-route':
            # The real picker has its own /tmp/hypr settings path. The route
            # case requires a private tmpfs there before starting the process.
            mounts=Path('/proc/self/mountinfo').read_text().splitlines()
            assert any(' /tmp/hypr ' in line and ' - tmpfs ' in line for line in mounts)
            picker.write_text('#!/bin/sh\nexec /usr/bin/hyprland-share-picker "$@"\n')
        picker.chmod(0o700)
        (config / 'hypr').mkdir(parents=True, exist_ok=True)
        (config / 'hypr/xdph.conf').write_text('screencopy {\n  custom_picker_binary = ' + str(picker) + '\n}\n')
        (config / 'xdg-desktop-portal').mkdir(parents=True, exist_ok=True)
        (config / 'xdg-desktop-portal/wysun-portals.conf').write_text(
            '[preferred]\ndefault=hyprland;gtk;\norg.freedesktop.impl.portal.ScreenCast=hyprland;\n')
        start('private-pipewire', ['/usr/bin/pipewire'])
        wait_for(lambda: (runtime / 'pipewire-0').is_socket(), 'private PipeWire')
        # Stock policy profile has no ALSA/BlueZ/V4L2/libcamera monitors.
        start('private-wireplumber-policy', ['/usr/bin/wireplumber', '--profile', 'policy'],
              {'WIREPLUMBER_DEBUG':'4'} if stream_diagnostic or case_selector.startswith('live-static') else None)
        objects = json.loads(command(['/usr/bin/pw-dump']))
        assert not any(o.get('type', '').endswith(':Device') for o in objects), 'Unexpected hardware device'
        if case_selector=='color':
            tools=run_dir/'color-picker-bin';tools.mkdir()
            wrapper=tools/'slurp'
            wrapper.write_text('#!/usr/bin/python3\nimport subprocess,sys\nfrom pathlib import Path\np=subprocess.run(["/tmp/wysun-portal-tools/root/usr/bin/slurp",*sys.argv[1:]],stdout=subprocess.PIPE)\nPath('+repr(str(run_dir/'selected-point.txt'))+').write_bytes(p.stdout)\nsys.stdout.buffer.write(p.stdout)\nraise SystemExit(p.returncode)\n')
            wrapper.chmod(0o700);env['PATH']=str(tools)+':'+env['PATH'];os.environ['PATH']=env['PATH']
        start('private-xdph', [PORTAL_ROOT / 'usr/libexec/xdg-desktop-portal-hyprland'])
        start('private-gtk', ['/usr/libexec/xdg-desktop-portal-gtk', '--replace', '--verbose'],
              {'GDK_BACKEND':'wayland', 'WAYLAND_DEBUG':'client'})
        start('private-portal', ['/usr/libexec/xdg-desktop-portal', '--replace', '--verbose'])
        wait_for(lambda: 'org.freedesktop.portal.Desktop' in command(
            ['dbus-send', '--session', '--print-reply', '--dest=org.freedesktop.DBus',
             '/org/freedesktop/DBus', 'org.freedesktop.DBus.ListNames']), 'private desktop portal')
        def screencast_ready():
            try:
                owner = command(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus',
                    '--object-path', '/org/freedesktop/DBus', '--method',
                    'org.freedesktop.DBus.GetNameOwner', 'org.freedesktop.portal.Desktop'])
                unique = owner.split("'")[1]
                owner_pid = command(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus',
                    '--object-path', '/org/freedesktop/DBus', '--method',
                    'org.freedesktop.DBus.GetConnectionUnixProcessID', unique])
                interfaces = command(['gdbus', 'introspect', '--session', '--dest', unique,
                    '--object-path', '/org/freedesktop/portal/desktop'])
                (run_dir / 'portal-owner.txt').write_text(owner + owner_pid + interfaces)
                result = command(['dbus-send', '--session', '--print-reply',
                    '--dest=org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop',
                    'org.freedesktop.DBus.Properties.Get', 'string:org.freedesktop.portal.ScreenCast',
                    'string:AvailableSourceTypes'])
                (run_dir / 'portal-readiness.txt').write_text(result)
                return 'uint32' in result and 'interface org.freedesktop.portal.ScreenCast' in interfaces
            except subprocess.CalledProcessError as error:
                (run_dir / 'portal-readiness.txt').write_text((error.stdout or '') + (error.stderr or ''))
                return False
        wait_for(screencast_ready, 'ScreenCast interface registration')
        print('PORTAL_READY: owner/PID, ScreenCast introspection and capabilities verified', flush=True)
        # Install genuine distribution files, then exercise public commands from /.
        command(['/usr/bin/python3', ROOT / 'installer/main.py', 'install', '--source', ROOT,
                 '--target-home', env['HOME'], '--components', 'wayland', '--config-only'], timeout=60)
        public = Path(env['HOME']) / '.local/bin/wysun'
        assert 'Wysun Recorder' in command([public, 'recorder', '--version'])
        assert 'Wysun Screenshot' in command([public, 'screenshot', '--version'])
        releases = Path(env['HOME']) / '.local/share/wysun/capture/releases'
        release = next(releases.iterdir())
        # Match the public installed launcher's module search environment;
        # subprocess bridges intentionally use python -P -m.
        env['PYTHONPATH'] = str(release)
        os.environ['PYTHONPATH'] = str(release)
        sys.path.insert(0, str(release))
        fixture = run_dir / 'opaque-window.py'
        fixture.write_text('from PySide6.QtWidgets import QApplication,QWidget\n'
                           'a=QApplication([]);a.setApplicationName("wysun-synthetic")\n'
                           'w=QWidget();w.setWindowTitle("Wysun synthetic opaque fixture")\n'
                           'w.setStyleSheet("background:#315787");w.showFullScreen();a.exec()\n')
        start('opaque-fixture', ['/usr/bin/python3', fixture])
        wait_for(lambda: any(w.get('title') == 'Wysun synthetic opaque fixture'
                             for w in json.loads(command(['hyprctl', '-j', 'clients']))), 'opaque native fixture')
        time.sleep(.4)
        from loomrec.portal import Portal
        original_screencast=Portal.screencast
        branch_observations=[]
        def observed_screencast(portal,*args,**kwargs):
            result=original_screencast(portal,*args,**kwargs)
            properties=portal.dbus.Interface(portal.object,'org.freedesktop.DBus.Properties')
            branch_observations.append(dict(source=args[0] if args else kwargs.get('source','monitor'),
                interface_version=int(properties.Get('org.freedesktop.portal.ScreenCast','version')),
                serial_present=result[1].get('pipewire-serial') is not None,
                node_id=result[0],pipewire_serial=result[1].get('pipewire-serial')))
            if os.environ.get('WYSUN_DIAGNOSTIC_SERIAL')=='1':
                print('SYNTHETIC_PORTAL_NODE: '+json.dumps(branch_observations[-1]),flush=True)
            objects=json.loads(command(['/usr/bin/pw-dump']))
            granted=next((obj for obj in objects if obj.get('id')==result[0]),{})
            branch_observations[-1]['private_registry_serial']=granted.get('info',{}).get('props',{}).get('object.serial')
            (run_dir/'portal-actual-branches.json').write_text(json.dumps(branch_observations,indent=2))
            if serial_diagnostic:
                print('SYNTHETIC_SERIAL_DIAGNOSTIC: '+json.dumps(branch_observations[-1]),flush=True)
                raise SystemExit(0)
            return result
        Portal.screencast=observed_screencast
        if case_selector == 'gtk':
            verify_gtk(run_dir, env, command, start)
            return
        if case_selector in ('live','live-static'):
            from wayland_live_case import run_case
            run_case(run_dir,env,command,start,wait_for,movement_during_recovery=case_selector=='live')
            return
        if case_selector == 'desktop':
            from wayland_desktop_case import run_case
            run_case(run_dir,env,command,start,wait_for)
            return
        if case_selector == 'region-coordinates':
            from wayland_region_coordinates_case import run_case
            run_case(run_dir,env,command,start,wait_for)
            return
        if case_selector in ('externals','external-konsole','external-firefox','external-obs'):
            sys.path.insert(0,str(ROOT/'apps/shell/tests'))
            from native_external_apps_probe import run_cases
            from wayland_test_pointer import SyntheticPointer
            pointer=SyntheticPointer(env);pointer.keyboard()
            def key(*args):
                if args==('-k','Return'):pointer.press(28);return
                command(['wtype','-s','200',*args])
            cases=('konsole','firefox','obs') if case_selector=='externals' else (case_selector.removeprefix('external-'),)
            try:result=run_cases(run_dir,dict(env,WYSUN_TEST_OBS_DBUS_DEBUG='1') if cases==('obs',) else env,command,start,wait_for,key=key,cases=cases,obs_audio='silent',obs_creation='collection')
            finally:pointer.close()
            print(json.dumps(result,indent=2),flush=True)
            return
        if case_selector == 'startup-cancel':
            from wayland_startup_cancel_case import run_case
            run_case(run_dir,env,command,start,wait_for)
            return
        if case_selector == 'color':
            from wayland_color_case import run_case
            run_case(run_dir,env,command,start,wait_for)
            return
        if case_selector == 'screenshot-route':
            from wayland_screenshot_route_case import run_case
            run_case(run_dir,env,command,start,wait_for)
            return
        if case_selector == 'screenshot-gui':
            from wayland_screenshot_gui_case import run_case
            run_case(run_dir,env,command,start,wait_for)
            return
        if case_selector == 'previews':
            from wayland_preview_case import run_case
            run_case(run_dir,env,command,start,wait_for)
            return
        if case_selector == 'music':
            pulse=runtime/'pulse/native'
            env['PULSE_SERVER']='unix:'+str(pulse);os.environ['PULSE_SERVER']=env['PULSE_SERVER']
            start('private-pipewire-pulse',['/usr/bin/pipewire-pulse'])
            wait_for(pulse.is_socket,'private pulse socket')
            from wayland_music_case import run_case
            run_case(run_dir,env,command,start,wait_for)
            return
        if case_selector == 'sync':
            from wayland_portal_cases import prepare_picker
            prepare_picker(run_dir)
            pulse=runtime/'pulse/native'
            env['PULSE_SERVER']='unix:'+str(pulse);os.environ['PULSE_SERVER']=env['PULSE_SERVER']
            start('private-pipewire-pulse',['/usr/bin/pipewire-pulse'])
            wait_for(pulse.is_socket,'private pulse socket')
            from wayland_sync_case import run_case
            run_case(run_dir,env,command,start,wait_for)
            return
        from loomrec.portal_image import capture_frame
        if stream_diagnostic:
            # Observe our installed producer without editing its immutable release.
            # Every queried server and log belongs to this guarded synthetic run.
            import threading
            original_popen = subprocess.Popen
            bridge_debug = (run_dir / 'bridge-debug.log').open('w'); streams.append(bridge_debug)
            bootstrap = '''import json,sys,gi
gi.require_version('Gst','1.0')
from gi.repository import Gst
from loomrec import pipewire_bridge as bridge
original=bridge.configure_pipewire_source
def observed(source,*args):
 original(source,*args)
 plugin=Gst.Registry.get().find_plugin('pipewire')
 print('SOURCE_READBACK: '+json.dumps(dict(properties={key:source.get_property(key) for key in ('fd','path','target-object','autoconnect')},plugin=plugin.get_filename(),version=plugin.get_version())),file=sys.stderr,flush=True)
bridge.configure_pipewire_source=observed
bridge.stream(**json.loads(sys.argv[1]))
'''
            if stream_diagnostic == 'drop-only':
                bootstrap = bootstrap.replace('bridge.stream(**', '''factory=Gst.ElementFactory.make
def make(name,*args):
 item=factory(name,*args)
 if name=='videorate':item.set_property('drop-only',True)
 return item
Gst.ElementFactory.make=make
print('DIAGNOSTIC_ONLY: videorate drop-only=True',file=sys.stderr,flush=True)
bridge.stream(**''')
            def diagnostic_popen(argv, *args, **kwargs):
                if isinstance(argv, list) and argv[1:4] == ['-P','-m','loomrec.pipewire_bridge']:
                    argv = [argv[0], '-P', '-c', bootstrap, argv[4]]
                    kwargs['stderr'] = bridge_debug
                return original_popen(argv, *args, **kwargs)
            subprocess.Popen = diagnostic_popen
            stop_observer = threading.Event()
            def observe_nodes():
                with (run_dir / 'private-pipewire-objects.jsonl').open('w') as log:
                    while not stop_observer.wait(.25):
                        try:
                            objects = json.loads(command(['/usr/bin/pw-dump'], timeout=3))
                            log.write(json.dumps({'time':time.monotonic(), 'objects':objects})+'\n'); log.flush()
                        except Exception as error:
                            log.write(json.dumps({'error':str(error)})+'\n'); log.flush()
            observer = threading.Thread(target=observe_nodes, daemon=True); observer.start()
            try:
                image = capture_frame('monitor', False)
                print('STREAM_DIAGNOSTIC_FRAME: '+str(image.size()), flush=True)
            finally:
                stop_observer.set(); observer.join(4)
                subprocess.Popen = original_popen
            return
        began = time.monotonic()
        image = capture_frame('monitor', False)
        pixel = image.pixelColor(image.width() // 2, image.height() // 2)
        rgb = [pixel.red(), pixel.green(), pixel.blue()]
        assert all(abs(a-b) <= 3 for a,b in zip(rgb, [49,87,135])), rgb
        screenshot_ms = round((time.monotonic() - began) * 1000, 1)
        print(json.dumps({'phase':'SCREENSHOT_FRAME_OK', 'rgb':rgb, 'width':image.width(),
                          'height':image.height(), 'screenshot_ms':screenshot_ms}), flush=True)
        from loomrec.capture import CaptureConfig, CaptureSession
        project = run_dir / 'synthetic-recording'
        recording = CaptureSession(CaptureConfig(str(project), 'portal', [0,0,320,240],
            fps=12, cursor=False, auto_finalize=False, backend='portal', source_type='monitor'))
        recording.start()
        def state(wanted):
            current = recording.status()
            if current['state'] in ('error', 'interrupted'):raise RuntimeError(current)
            return current['state'] == wanted
        wait_for(lambda: state('recording'), 'portal recording', timeout=35)
        print('RECORDER_STARTED', flush=True)
        # Keep the opaque scene static: a damage-driven source may emit exactly
        # one buffer. The producer must still sustain the recording cadence.
        static_began = time.monotonic()
        time.sleep(4.2)
        recording.pause(); wait_for(lambda: state('paused'), 'pause finalizes segment')
        static_elapsed = time.monotonic() - static_began
        recording.resume(); wait_for(lambda: state('recording'), 'resume same portal consent')
        time.sleep(1)
        recording.stop(); wait_for(lambda: state('stopped'), 'stop recording', timeout=30)
        segments = sorted(project.glob('segment-*.mkv'))
        assert len(segments) == 2, segments
        media = []
        for segment in segments:
            info = json.loads(command(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', segment]))
            assert not any(s['codec_type'] == 'audio' for s in info['streams'])
            video = next(s for s in info['streams'] if s['codec_type'] == 'video')
            assert video['width'] == image.width() // 2 * 2 and video['height'] == image.height() // 2 * 2
            assert int(video['nb_read_frames']) > 8
            command(['ffmpeg', '-v', 'error', '-i', segment, '-f', 'null', '-'])
            frames = json.loads(command(['ffprobe','-v','error','-select_streams','v:0',
                '-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',segment]))['frames']
            pts = [float(frame['best_effort_timestamp_time']) for frame in frames]
            assert all(b>a for a,b in zip(pts,pts[1:])), pts
            media.append({'width':video['width'], 'height':video['height'], 'decoded_frames':int(video['nb_read_frames']),
                          'duration_s':float(info['format']['duration']), 'first_pts_s':pts[0], 'last_pts_s':pts[-1]})
        assert media[0]['last_pts_s'] >= 3 and media[0]['decoded_frames'] >= 36, media[0]
        print(json.dumps({'result':'WYSUN_REAL_PORTAL_SYNTHETIC_OK', 'picker':'declared fixture, not human consent',
            'backend':'private native Hyprland/XDPH/PipeWire/GStreamer/FFmpeg', 'rgb':rgb,
            'screenshot_ms':screenshot_ms, 'segments':media, 'static_wait_including_finalize_s':static_elapsed,
            'pause_resume_stop':True,
            'hardware_audio_camera':False}, indent=2), flush=True)
        sys.path.insert(0, str(ROOT / 'tests'))
        from wayland_portal_cases import run_cases
        run_cases(run_dir, env, command, start, wait_for)
        verify_gtk(run_dir, env, command, start)
    finally:
        if recording:
            try:
                recording.stop()
                current = recording.status()
                pid = current.get('pid')
                if pid and current['state'] not in ('stopped', 'error'):
                    # This PID comes only from the just-created private project.
                    os.killpg(pid, signal.SIGTERM)
            except (OSError, ValueError):pass
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL);process.wait()
        for stream in streams:stream.close()


if __name__ == '__main__':
    main()
