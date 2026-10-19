"""Negative-position, fractional/rotated region on a second owned output."""
import hashlib
import json
import time
from types import SimpleNamespace


def run_case(run_dir,env,command,start,wait_for):
    from loomrec.desktop_capture import read_topology
    from loomrec.portal_image import read_frame
    from loomrec.wayland_capture import PipeWireCapture
    from loomrec.wayland_pointer import NativePointerReader,PositionEffects
    from loomrec.capture import CaptureConfig,CaptureSession
    from wayland_portal_cases import prepare_picker
    choice=prepare_picker(run_dir)
    command(['hyprctl','eval','hl.monitor({output="WYSUN-TEST-1",mode="1280x800@60",position="0x0",scale=1})'])
    command(['hyprctl','eval','hl.monitor({output="WYSUN-TEST-2",mode="640x480@60",position="-384x0",scale=1.25,transform=1})'])
    command(['hyprctl','output','create','headless','WYSUN-TEST-2'])
    wait_for(lambda:len(read_topology())==2,'second owned fractional/rotated output')
    fixture=run_dir/'region-second-output.py'
    fixture.write_text('from PySide6.QtWidgets import QApplication,QWidget\n'
        'a=QApplication([]);w=QWidget();w.setWindowTitle("Wysun region output fixture")\n'
        'w.setStyleSheet("background:#af2b32");w.showFullScreen();a.exec()\n')
    process=start('region-second-output',['/usr/bin/python3',fixture]);recording=None
    def clients():return json.loads(command(['hyprctl','-j','clients']))
    try:
        window=wait_for(lambda:next((c for c in clients() if c.get('title')=='Wysun region output fixture'),None),'own region window')
        target=next(m for m in json.loads(command(['hyprctl','-j','monitors'])) if m['name']=='WYSUN-TEST-2')
        command(['hyprctl','dispatch','hl.dsp.window.move({window="address:'+window['address']+'",monitor="WYSUN-TEST-2",follow=true})'])
        wait_for(lambda:any(c.get('title')=='Wysun region output fixture' and c['monitor']==target['id'] for c in clients()),'own window on fractional output')
        time.sleep(.3);choice.write_text('screen:WYSUN-TEST-2')
        rect=[-364,20,320,240]
        capture=PipeWireCapture(SimpleNamespace(rect=rect,fps=12,source_type='region',cursor=False))
        try:
            image=read_frame(capture)
            assert (image.width(),image.height())==(400,300),image.size()
            meta=capture.metadata
            assert tuple(meta['position'])==(-384,0) and tuple(meta['size'])==(384,512),meta
            assert tuple(meta['portal_position'])==(0,0) and tuple(meta['portal_size'])==(640,480),meta
            assert capture.source_size==[480,640],capture.source_size
            command(['hyprctl','dispatch','hl.dsp.cursor.move({x=-224,y=120})'])
            reader=NativePointerReader(PositionEffects(),meta,capture.source_size,[25,25,400,300])
            point=reader.position();assert point==(175,125),point
            p=image.pixelColor(100,100);rgb=[p.red(),p.green(),p.blue()]
            assert all(abs(a-b)<=4 for a,b in zip(rgb,[175,43,50])),rgb
        finally:capture.close()
        project=run_dir/'region-coordinates-recording'
        recording=CaptureSession(CaptureConfig(str(project),'portal',rect,fps=12,cursor=False,
            auto_finalize=False,backend='portal',source_type='region'));recording.start()
        def state(wanted):
            status=recording.status()
            if status['state'] in ('error','interrupted'):raise RuntimeError(status)
            return status['state']==wanted
        wait_for(lambda:state('recording'),'fractional region recording',timeout=35)
        time.sleep(2);recording.pause();wait_for(lambda:state('paused'),'fractional region pause')
        recording.resume();wait_for(lambda:state('recording'),'fractional region resume')
        time.sleep(1);recording.pause();wait_for(lambda:state('paused'),'second fractional region pause')
        clips=[];before={}
        for path in sorted(project.glob('segment-*.mkv')):
            info=json.loads(command(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',path]))
            video=info['streams'][0];assert (video['width'],video['height'])==(400,300) and len(info['streams'])==1,info
            assert int(video['nb_read_frames'])>8,video
            command(['ffmpeg','-v','error','-i',path,'-f','null','-'])
            before[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            clips.append(dict(frames=int(video['nb_read_frames']),duration_s=float(info['format']['duration'])))
        assert len(clips)==2,clips
        command(['hyprctl','eval','hl.monitor({output="WYSUN-TEST-2",mode="640x480@60",position="-400x0",scale=1.25,transform=1})'])
        wait_for(lambda:any(o.name=='WYSUN-TEST-2' and o.position==(-400,0) for o in read_topology()),'owned topology change')
        recording.resume();wait_for(lambda:recording.status()['state']=='error','topology change rejected on resume')
        assert 'topología' in recording.status()['error'],recording.status()
        assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in project.glob('segment-*.mkv')}==before
        result=dict(result='WYSUN_NATIVE_REGION_COORDINATES_OK',output=dict(position=[-384,0],pixels=[640,480],scale=1.25,transform=1),
            logical_rect=rect,encoded_size=[400,300],rgb=rgb,actual_native_pointer_in_crop=list(point),
            portal_raw_metadata_retained=True,clips=clips,topology_change='resume rejected, both finalized source hashes preserved',
            limits=['synthetic outputs/picker, no physical monitor or user data','no mid-frame topology guarantee'])
        (run_dir/'region-coordinate-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
        return result
    finally:
        if recording:recording.stop()
        process.terminate();process.wait(timeout=3)
        command(['hyprctl','output','destroy','WYSUN-TEST-2'])
