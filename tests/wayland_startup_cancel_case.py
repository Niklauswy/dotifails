"""Stop the real installed worker while its first bridge is still starting."""
import fcntl
import json
from pathlib import Path
import time


def run_case(run_dir,env,command,start,wait_for):
    from loomrec.capture import CaptureConfig,CaptureSession
    recording=CaptureSession(CaptureConfig(str(run_dir/'startup-cancel'),'portal',[0,0,1280,800],
        fps=12,cursor=False,auto_finalize=False,backend='portal',source_type='monitor'))
    def bridge():
        pid=recording.status().get('pid')
        if not pid:return None
        children=Path(f'/proc/{pid}/task/{pid}/children')
        try:rows=children.read_text().split()
        except FileNotFoundError:return None
        for child in rows:
            try:args=Path(f'/proc/{child}/cmdline').read_bytes().split(b'\0')
            except FileNotFoundError:continue
            if b'loomrec.pipewire_bridge' in args:return int(child)
        return None
    def finished(pid):
        try:return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1][0]=='Z'
        except FileNotFoundError:return True
    try:
        recording.start();child=wait_for(bridge,'actual bridge child during startup')
        worker=recording.status()['pid'];time.sleep(.25)
        assert recording.status()['state']=='starting','Missed startup cancellation interval'
        before=time.monotonic();recording.stop()
        wait_for(lambda:recording.status()['state'] in ('stopped','error'),'startup stop response',timeout=8)
        elapsed=time.monotonic()-before;status=recording.status()
        wait_for(lambda:finished(child) and finished(worker),'own cancelled processes finished',timeout=8)
        with (recording.root/'capture.lock').open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        project=json.loads((recording.root/'project.json').read_text());assert project['sources']==[],project
        assert status['state']=='stopped' or 'cancelad' in (status.get('error') or '').lower(),status
        result=dict(result='WYSUN_NATIVE_STARTUP_CANCEL_FINISHED',state=status['state'],message=status.get('error'),
            stop_response_s=elapsed,bridge_and_worker_finished=True,capture_lock_released=True,source_count=0,
            scope='actual installed worker, no startup instrumentation, own source only')
        (run_dir/'native-startup-cancel-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
        return result
    finally:recording.stop()
