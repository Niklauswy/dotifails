"""Native halo/trail and telemetry-failure proof on our sole synthetic output.

No button observation, helper, pkexec, audio, physical input or private surface.
Only the guarded portal runner may call this function.
"""
import json
import time
import threading
from pathlib import Path


def run_case(run_dir, env, command, start, wait_for, *, movement_during_recovery=True):
    from loomrec.capture import CaptureConfig,CaptureSession
    from wayland_test_pointer import SyntheticPointer
    pointer=SyntheticPointer(env)
    moving=threading.Event();motion_errors=[]
    def continuous_motion():
        began=time.monotonic()
        try:
            while not moving.wait(.04):pointer.move(450+int(((time.monotonic()-began)%1)*150),350)
        except Exception as error:motion_errors.append(str(error))
    motion_thread=None
    project=run_dir/'native-live-effects'
    recording=CaptureSession(CaptureConfig(str(project),'portal',[0,0,1280,800],fps=12,cursor=True,
        cursor_effects=dict(preset='trail',halo=True,trail=True,clicks=False),
        cursor_live=True,auto_finalize=False,backend='portal',source_type='monitor'))
    def state(wanted):
        status=recording.status()
        if status['state'] in ('error','interrupted'):raise RuntimeError(status)
        return status['state']==wanted
    def motion(seconds):
        began=time.monotonic()
        while time.monotonic()-began<seconds:
            t=time.monotonic()-began
            pointer.move(450+int((t%1)*150),350)
            time.sleep(.04)
    try:
        pointer.move(450,350)
        motion_thread=threading.Thread(target=continuous_motion,daemon=True);motion_thread.start()
        started_at=time.monotonic();recording.start()
        wait_for(lambda:state('recording'),'native LIVE recording',timeout=35)
        initial_start_s=time.monotonic()-started_at
        wait_for(lambda:list(project.glob('*.cursor-live.json')),'native LIVE marker')
        time.sleep(2.5)
        if not movement_during_recovery:
            moving.set();motion_thread.join(4)
        trace=next(project.glob('*.cursor.jsonl'))
        events=[json.loads(line) for line in trace.read_text().splitlines()]
        assert len(events)>5 and all(event[3]==0 for event in events[1:]),'Unexpected button data'
        # Corrupt only our disposable telemetry, exercising the product's actual
        # follower error -> finalized baked interval -> deferred new interval.
        with trace.open('a') as stream:stream.write('{"owned-test-invalid-event":true}\n');stream.flush()
        marker=next(project.glob('*.cursor-live.json'))
        wait_for(lambda:json.loads(marker.read_text()).get('error'),'follower detects invalid own telemetry')
        def fallback():
            data=json.loads((project/'project.json').read_text())
            return len(data['sources'])>=1 and state('recording') and 'interrumpidos' in (recording.status().get('cursor_warning') or '')
        wait_for(fallback,'finalize LIVE and continue deferred',timeout=25)
        fd_counts=[];fd_samples=[];latencies=[]
        for cycle in range(3):
            time.sleep(1)
            before=time.monotonic();recording.pause();wait_for(lambda:state('paused'),'native effects pause')
            paused_at=time.monotonic();worker=recording.status()['pid']
            samples=[]
            for _ in range(7):
                samples.append(len(list(Path(f'/proc/{worker}/fd').iterdir())));time.sleep(.02)
            fd_samples.append(samples);fd_counts.append(min(samples))
            recording.resume();wait_for(lambda:state('recording'),'native effects resume',timeout=25)
            latencies.append(dict(pause_s=paused_at-before,resume_s=time.monotonic()-paused_at))
        time.sleep(1)
        before=time.monotonic();recording.stop();wait_for(lambda:state('stopped'),'native effects stop',timeout=25)
        stop_s=time.monotonic()-before
        assert max(fd_counts)==min(fd_counts),fd_counts
        assert not motion_errors,motion_errors
        data=json.loads((project/'project.json').read_text())
        sources=[s for s in data['sources'] if s['kind']=='screen']
        assert len(sources)==5,sources
        assert sources[0]['cursor_baked'] is True and sources[0]['cursor_path'] is None,sources[0]
        assert all(not s['cursor_baked'] and s['cursor_path'] for s in sources[1:]),sources
        files=sorted(project.glob('segment-*.mkv'));assert len(files)==5,files
        clips=[]
        for path in files:
            info=json.loads(command(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',path]))
            video=info['streams'][0];assert len(info['streams'])==1 and int(video['nb_read_frames'])>5,info
            command(['ffmpeg','-v','error','-i',path,'-f','null','-'])
            frames=json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_frames',
                '-show_entries','frame=best_effort_timestamp_time','-of','json',path]))['frames']
            pts=[float(frame['best_effort_timestamp_time']) for frame in frames]
            assert all(b>a for a,b in zip(pts,pts[1:])),pts
            clips.append(dict(file=path.name,frames=int(video['nb_read_frames']),duration_s=float(info['format']['duration']),
                first_pts_s=pts[0],last_pts_s=pts[-1]))
        import subprocess
        pixels=subprocess.check_output(['ffmpeg','-v','error','-i',str(files[0]),'-vf',r'select=eq(n\,12),crop=400:120:350:300',
            '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],env=env)
        assert len(pixels)==400*120*3
        # The halo/trail is translucent blue; the embedded arrow is white/dark.
        # On our uniformly blue fixture these pixels distinguish actual effects.
        accent=sum(pixels[i]<60 and pixels[i+1]<115 and pixels[i+2]>142 for i in range(0,len(pixels),3))
        assert accent>600,accent
        result=dict(result='WYSUN_NATIVE_LIVE_EFFECTS_OK',backend='real native portal/BGRA/FFmpeg',
            effects='halo/trail; clicks=false, no privileged helper',decoded_accent_pixels=accent,
            clips=clips,telemetry_failure=json.loads(marker.read_text())['error'],
            baked_source_has_no_export_trace=True,deferred_sources=len(sources)-1,pause_resume_stop=True,
            movement_during_recovery=movement_during_recovery,paused_worker_fd_counts=fd_counts,paused_fd_samples=fd_samples,
            initial_start_s=initial_start_s,pause_resume_latencies=latencies,stop_s=stop_s,
            limits=['no physical input/buttons','no WINDOW mapping or embedded cursor shape/size claim',
                    'baked provenance prevents a second export overlay; no physical desktop cost claim'])
        (run_dir/'native-live-effects-results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2),flush=True)
        return result
    except Exception:
        partial=dict(result='INCOMPLETE',movement_during_recovery=movement_during_recovery,
            status=recording.status(),project=json.loads((project/'project.json').read_text()) if (project/'project.json').exists() else None)
        (run_dir/'native-live-effects-failure.json').write_text(json.dumps(partial,indent=2)+'\n')
        raise
    finally:
        recording.stop();moving.set()
        if motion_thread:motion_thread.join(4)
        pointer.close()
