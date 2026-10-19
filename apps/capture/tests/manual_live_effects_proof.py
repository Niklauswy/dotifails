"""Serial synthetic-only bridge/FFmpeg comparison; run with the media slot.

No portal, compositor, helper, input devices, microphone, camera or audio output.
Run from any cwd with the same Python/GStreamer environment as the app launcher.
"""
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]


def run_case(root,live):
    trace=root/'cursor.jsonl';marker=root/'cursor-live.json';output=root/('live.mkv' if live else 'base.mkv')
    values=dict(fd=-1,node=0,metadata={},fps=12,synthetic=True)
    origin=time.time();stop=threading.Event()
    if live:
        values.update(cursor_trace_path=str(trace),cursor_marker=str(marker),cursor_effects=dict(preset='trail'))
        def write_trace():
            with trace.open('w',buffering=1) as stream:
                stream.write(json.dumps(dict(version=1,width=320,height=240,origin=origin,native_cursor_embedded=True))+'\n')
                while not stop.is_set():
                    t=time.time()-origin
                    stream.write(json.dumps([t,160+int(25*(t%1)),120,0])+'\n')
                    if .4<t<.46:stream.write(json.dumps([t,160,120,1])+'\n')
                    stop.wait(.025)
        thread=threading.Thread(target=write_trace);thread.start()
    env=dict(os.environ,PYTHONPATH=str(ROOT),QT_QPA_PLATFORM='offscreen')
    before=resource.getrusage(resource.RUSAGE_CHILDREN);started=time.monotonic()
    producer=encoder=None
    try:
        producer=subprocess.Popen([sys.executable,'-P','-m','loomrec.pipewire_bridge',json.dumps(values)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        # The bridge itself enforces first-frame timeout; parent has a hard cap too.
        import selectors
        with selectors.DefaultSelector() as selector:
            selector.register(producer.stdout,selectors.EVENT_READ)
            if not selector.select(15):raise TimeoutError('No synthetic header')
        header=json.loads(producer.stdout.readline())
        if (header['width'],header['height'])!=(320,240):raise ValueError(header)
        encoder=subprocess.Popen(['ffmpeg','-hide_banner','-y','-loglevel','error','-f','rawvideo','-pixel_format','bgra','-video_size','320x240','-framerate','12','-i','pipe:0','-an','-c:v','libx264','-threads','1','-preset','ultrafast',str(output)],stdin=producer.stdout,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        producer.stdout.close()
        stderr=producer.communicate(timeout=20)[1]
        if producer.returncode:raise RuntimeError(stderr.decode(errors='replace'))
        _,stderr=encoder.communicate(timeout=10)
        if encoder.returncode:raise RuntimeError(stderr.decode(errors='replace'))
        decoded=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'],capture_output=True,timeout=10)
        if decoded.returncode:raise RuntimeError(decoded.stderr.decode(errors='replace'))
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(output)],timeout=10))
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        return dict(live=live,frames=int(info['streams'][0]['nb_read_frames']),duration=float(info['format']['duration']),elapsed_s=round(time.monotonic()-started,4),child_cpu_s=round(after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,4),child_peak_rss_kib=after.ru_maxrss,marker=json.loads(marker.read_text()) if live else None)
    finally:
        stop.set()
        if live:thread.join(timeout=1)
        for process in (encoder,producer):
            if process and process.poll() is None:process.terminate();process.wait(timeout=3)


def main():
    with tempfile.TemporaryDirectory(prefix='wysun-live-proof-') as folder:
        root=Path(folder)
        results=[run_case(root,False),run_case(root,True)]
        if any(result['frames']<10 for result in results):raise RuntimeError(results)
        if not results[1]['marker'].get('baked') or results[1]['marker'].get('error'):raise RuntimeError(results)
        print(json.dumps(dict(synthetic=True,portal=False,notes='Two sequential 320x240@12 clips; CPU includes bridge/encoder/decode/probe. Peak RSS is cumulative child maximum, not incremental renderer memory.',results=results),indent=2))

if __name__=='__main__':main()
