"""Additional capture contracts on the guarded synthetic portal probe only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def prepare_picker(run_dir):
    picker = run_dir / 'fixture-picker'
    choice = run_dir / 'picker-choice'
    choice.write_text('screen:WYSUN-TEST-1')
    picker.write_text('''#!/usr/bin/python3
import os
from pathlib import Path
mode=Path(__file__).with_name('picker-choice').read_text()
if mode=='cancel':raise SystemExit(0)
if mode in ('window','window-sync'):
    entries=os.environ.get('XDPH_WINDOW_SHARING_LIST','').split('[HA>]')
    title='Wysun sync fixture' if mode=='window-sync' else 'Wysun synthetic opaque fixture'
    match=[e.split('[HC>]')[0] for e in entries if '[HT>]'+title+'[HE>]' in e]
    if len(match)!=1:raise RuntimeError('Expected one owned fixture window')
    mode='window:'+match[0]
print('[SELECTION]/'+mode)
''')
    picker.chmod(0o700)
    return choice


def run_cases(run_dir, env, command, start, wait_for):
    from loomrec.portal import Portal, PortalCancelled
    from loomrec.portal_image import capture_frame
    from loomrec.capture import CaptureConfig, CaptureSession
    choice = prepare_picker(run_dir)
    results = {}
    def phase(name):
        (run_dir/'portal-extra-results.json').write_text(json.dumps(results,indent=2))
        print('PORTAL_CASE: '+name,flush=True)
    def rgb(image):
        p=image.pixelColor(image.width()//2,image.height()//2)
        return [p.red(),p.green(),p.blue()]
    def check_color(image, expected):
        actual=rgb(image);assert all(abs(a-b)<=3 for a,b in zip(actual,expected)),actual
        return dict(rgb=actual,width=image.width(),height=image.height())
    choice.write_text('window')
    phase('window-visible')
    results['window_visible']=check_color(capture_frame('window',False),[49,87,135])
    cover=run_dir/'opaque-cover.py'
    cover.write_text('from PySide6.QtWidgets import QApplication,QWidget\n'
        'a=QApplication([]);w=QWidget();w.setWindowTitle("Wysun synthetic cover")\n'
        'w.setStyleSheet("background:#af2b32");w.showFullScreen();a.exec()\n')
    cover_process=start('opaque-cover',['/usr/bin/python3',cover])
    wait_for(lambda:any(c.get('title')=='Wysun synthetic cover' for c in json.loads(command(['hyprctl','-j','clients']))),'cover fixture')
    time.sleep(.3)
    choice.write_text('screen:WYSUN-TEST-1')
    check_color(capture_frame('monitor',False),[175,43,50])
    choice.write_text('window')
    phase('window-occluded')
    try:results['window_occluded']=check_color(capture_frame('window',False),[49,87,135])
    except RuntimeError as exc:results['window_occluded']={'unsupported':str(exc)}
    cover_process.terminate();cover_process.wait(timeout=3)
    choice.write_text('cancel')
    phase('cancel')
    portal=Portal()
    try:
        try:portal.screencast('monitor',False)
        except PortalCancelled:results['cancel']='PortalCancelled, no capture process'
        else:raise AssertionError('Cancellation unexpectedly granted a source')
    finally:portal.close()
    choice.write_text('screen:WYSUN-TEST-1')
    phase('region-two-private-audio-tracks')
    # The policy-only PipeWire has no hardware monitors. Add only explicit null
    # sinks and play generated tones to their monitors; never use default audio.
    pulse=Path(env['XDG_RUNTIME_DIR'])/'pulse/native'
    env['PULSE_SERVER']='unix:'+str(pulse);os.environ['PULSE_SERVER']=env['PULSE_SERVER']
    start('private-pipewire-pulse',['/usr/bin/pipewire-pulse'])
    wait_for(lambda:pulse.is_socket(),'private pulse socket')
    for name in ('wysun-synthetic-mic','wysun-synthetic-system'):
        command(['pactl','load-module','module-null-sink','sink_name='+name,'channels=1','rate=48000'])
    for name,hz in [('wysun-synthetic-mic',440),('wysun-synthetic-system',880)]:
        start(name,['ffmpeg','-v','error','-re','-f','lavfi','-i',f'sine=frequency={hz}:sample_rate=48000',
                    '-f','pulse','-device',name,'Wysun synthetic tone'])
    time.sleep(.4)
    assert not any(o.get('type','').endswith(':Device') for o in json.loads(command(['pw-dump'])))
    project=run_dir/'synthetic-region-audio'
    config=CaptureConfig(str(project),'portal',[20,30,320,240],fps=12,cursor=False,
        auto_finalize=False,backend='portal',source_type='region',
        mic='wysun-synthetic-mic.monitor',system_audio='wysun-synthetic-system.monitor')
    controller=run_dir/'detached-controller.py'
    controller.write_text('from loomrec.capture import CaptureConfig,CaptureSession\n'
        'import json\nCaptureSession(CaptureConfig(**json.loads('+repr(json.dumps(config.__dict__))+'))).start()\n')
    command(['/usr/bin/python3',controller])  # Exit the GUI/controller equivalent.
    recording=CaptureSession.attach(project)
    def state(wanted):
        value=recording.status()
        if value['state'] in ('error','interrupted'):raise RuntimeError(value)
        return value['state']==wanted
    try:
        wait_for(lambda:state('recording'),'detached region/audio recording',timeout=35)
        time.sleep(2)
        recording.pause();wait_for(lambda:state('paused'),'region/audio pause')
        recording.resume();wait_for(lambda:state('recording'),'region/audio resume')
        time.sleep(1)
        recording.stop();wait_for(lambda:state('stopped'),'region/audio stop',timeout=30)
        segments=[]
        for path in sorted(project.glob('segment-*.mkv')):
            info=json.loads(command(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',path]))
            videos=[s for s in info['streams'] if s['codec_type']=='video'];audios=[s for s in info['streams'] if s['codec_type']=='audio']
            assert len(videos)==1 and len(audios)==2,info
            video=videos[0];assert video['width']==320 and video['height']==240 and int(video['nb_read_frames'])>5,video
            # Complete decode validates both audio tracks and every video packet.
            command(['ffmpeg','-v','error','-i',path,'-map','0','-f','null','-'])
            segments.append(dict(frames=int(video['nb_read_frames']),duration_s=float(info['format']['duration']),
                starts_s=[float(s.get('start_time',0)) for s in info['streams']],audio_tracks=2))
        assert len(segments)==2,segments
        results['region_detached_two_synthetic_audio_tracks']=segments
    finally:
        recording.stop()
    phase('two-output-desktop')
    # A fresh portal has no Screenshot permission. Seed only this disposable
    # bus/store for the backend test; human consent is a separate test level.
    import dbus
    private_bus=dbus.SessionBus(private=True)
    private_bus.set_exit_on_disconnect(False)
    try:
        store=dbus.Interface(private_bus.get_object('org.freedesktop.impl.portal.PermissionStore',
            '/org/freedesktop/impl/portal/PermissionStore'),'org.freedesktop.impl.portal.PermissionStore')
        store.SetPermission('screenshot',True,'screenshot','',dbus.Array(['yes'],signature='s'))
    finally:private_bus.close()
    results['screenshot_permission']='explicit fixture in disposable private PermissionStore, not human consent'
    command(['hyprctl','eval','hl.monitor({output="WYSUN-TEST-2",mode="640x480@60",position="1280x0",scale=1})'])
    command(['hyprctl','output','create','headless','WYSUN-TEST-2'])
    wait_for(lambda:len(json.loads(command(['hyprctl','-j','monitors'])))==2,'two synthetic outputs')
    desktop=capture_frame('desktop',False)
    assert desktop.width()==1920 and desktop.height()==800,(desktop.width(),desktop.height())
    results['desktop_two_outputs_no_cursor']={'width':desktop.width(),'height':desktop.height(),'backend':'real Screenshot portal'}
    selections=[]
    def choose_remaining(state):
        if state['stage']=='select':
            selections.append(state['remaining'][0]);choice.write_text('screen:'+state['remaining'][0])
    with_cursor=capture_frame('desktop',True,progress=choose_remaining)
    assert (with_cursor.width(),with_cursor.height())==(1920,800)
    assert sorted(selections)==['WYSUN-TEST-1','WYSUN-TEST-2'],selections
    results['desktop_two_outputs_cursor']={'size':[1920,800],'selections':selections,
        'contract':'two explicit fixture permissions, sequential composition; not a multi-stream grant'}
    command(['hyprctl','output','destroy','WYSUN-TEST-2'])
    phase('explicit-client-close')
    # Core 1.20.3 deliberately does not send Closed for the client's own Close.
    # This proves explicit cleanup, not backend-initiated revocation.
    portal=Portal()
    try:
        portal.screencast('monitor',False)
        portal.dbus.Interface(portal.bus.get_object('org.freedesktop.portal.Desktop',portal.session),'org.freedesktop.portal.Session').Close()
        results['explicit_client_close']='own Close returned; no Closed signal expected and no revocation claim'
    finally:portal.close()
    phase('correlated-flash-audio-and-fd-lifecycle')
    from wayland_sync_case import run_case
    results['correlated_av']=run_case(run_dir,env,command,start,wait_for)
    print(json.dumps({'result':'WYSUN_PORTAL_EXTRA_CASES','cases':results,
                     'audio_scope':'private null sinks and a separate common-file flash/pulse measurement; no physical audio'},indent=2),flush=True)
    return results
