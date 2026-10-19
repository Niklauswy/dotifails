"""Correlated flash/tone measurement; only the guarded private portal runner."""
import array
import json
import math
from pathlib import Path
import socket
import statistics
import time


def run_case(run_dir, env, command, start, wait_for):
    from loomrec.capture import CaptureConfig,CaptureSession
    sink='wysun-sync-only'
    command(['pactl','load-module','module-null-sink','sink_name='+sink,'channels=1','rate=48000'])
    clip=run_dir/'common-clock-flash-pulse.mkv'
    command(['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=640x360:r=30:d=16',
        '-f','lavfi','-i',r'aevalsrc=if(lt(mod(t\,1)\,0.15)\,0.4*sin(2*PI*880*t)\,0):s=48000:d=16',
        '-vf',"drawbox=color=white:t=fill:enable='lt(mod(t,1),0.15)'",'-c:v','libx264','-preset','ultrafast',
        '-threads','1','-c:a','pcm_s16le','-shortest',clip])
    ipc=run_dir/'sync-mpv.sock'
    player=start('synthetic-sync-player',['/usr/bin/mpv','--no-config','--load-scripts=no','--ytdl=no',
        '--vo=gpu-next','--gpu-context=wayland','--ao=pulse','--audio-device=pulse/'+sink,
        '--volume=80','--pause','--keep-open=yes','--fullscreen','--title=Wysun sync fixture',
        '--input-ipc-server='+str(ipc),clip])
    wait_for(lambda:ipc.is_socket() and any(c.get('title')=='Wysun sync fixture'
        for c in json.loads(command(['hyprctl','-j','clients']))),'synthetic sync player')
    def mpv(*args):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(3);connection.connect(str(ipc))
            connection.sendall((json.dumps({'command':args,'request_id':381})+'\n').encode())
            data=b''
            while True:
                data+=connection.recv(65536)
                while b'\n' in data:
                    line,data=data.split(b'\n',1);response=json.loads(line)
                    if response.get('request_id')==381:
                        assert response.get('error')=='success',response
                        return response
    (run_dir/'picker-choice').write_text('window-sync')
    project=run_dir/'correlated-sync-recording'
    recording=CaptureSession(CaptureConfig(str(project),'portal',[0,0,640,360],fps=30,cursor=False,
        auto_finalize=False,backend='portal',source_type='window',system_audio=sink+'.monitor'))
    recording.start();fd_counts=[]
    def state(wanted):
        value=recording.status()
        if value['state'] in ('error','interrupted'):raise RuntimeError(value)
        return value['state']==wanted
    try:
        wait_for(lambda:state('recording'),'sync recording',timeout=35)
        mpv('set_property','pause',False)
        for cycle in range(4):
            time.sleep(2.2)
            if cycle<3:
                recording.pause();wait_for(lambda:state('paused'),'sync pause')
                worker=recording.status()['pid'];fd_counts.append(len(list(Path(f'/proc/{worker}/fd').iterdir())))
                time.sleep(.2)
                recording.resume();wait_for(lambda:state('recording'),'sync resume',timeout=25)
        recording.stop();wait_for(lambda:state('stopped'),'sync stop',timeout=30)
        assert max(fd_counts)-min(fd_counts)<=1,fd_counts
        reports=[]
        for path in sorted(project.glob('segment-*.mkv')):
            frames=json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_frames',
                '-show_entries','frame=best_effort_timestamp_time','-of','json',path]))['frames']
            import subprocess
            gray=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf','crop=iw/2:ih/2:iw/4:ih/4,scale=1:1',
                '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','gray','-'],env=env)
            samples=array.array('f',subprocess.check_output(['ffmpeg','-v','error','-copyts','-i',str(path),'-map','0:a:0',
                '-af','aresample=async=1:first_pts=0','-ac','1','-ar','48000','-f','f32le','-'],env=env))
            assert len(gray)==len(frames),(len(gray),len(frames))
            rms=[math.sqrt(sum(x*x for x in samples[i:i+480])/480) for i in range(0,len(samples)-480,480)]
            assert rms and max(rms)>.05,'No synthetic pulse decoded'
            vt=[(float(frames[i]['best_effort_timestamp_time']),gray[i]>128)
                for i in range(1,len(gray)) if (gray[i]>128)!=(gray[i-1]>128)]
            at=[(i/100,rms[i]>.05) for i in range(1,len(rms)) if (rms[i]>.05)!=(rms[i-1]>.05)]
            pairs=[]
            for video,state_after in vt:
                candidates=[audio for audio,state in at if state==state_after and abs(audio-video)<.45]
                if candidates:
                    audio=min(candidates,key=lambda a:abs(a-video));pairs.append(dict(video_s=video,audio_s=audio,delta_ms=round((video-audio)*1000,2)))
            assert len(pairs)>=2,(path,vt,at)
            delta=[p['delta_ms'] for p in pairs]
            reports.append(dict(segment=path.name,decoded_frames=len(frames),video_range=[min(gray),max(gray)],
                matched_edges=pairs,median_video_minus_audio_ms=round(statistics.median(delta),2),
                max_abs_delta_ms=max(map(abs,delta)),edge_delta_change_ms=round(delta[-1]-delta[0],2)))
        assert len(reports)==4,reports
        result=dict(result='WYSUN_CORRELATED_AV_MEASUREMENT',stimulus='one encoded file: 30fps white flashes and 880Hz 150ms pulses at each second',
            playback='native mpv to private null sink, then native window portal',
            scope='measured encoded signal offsets, includes player/compositor/buffering latency; no physical device or acceptance threshold inferred',
            paused_worker_fd_counts=fd_counts,permission='one ScreenCast session, three resumes',segments=reports)
        (run_dir/'correlated-av-results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2),flush=True)
        return result
    finally:
        recording.stop()
        player.terminate();player.wait(timeout=3)
