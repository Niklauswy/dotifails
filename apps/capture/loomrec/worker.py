"""Independent recorder process; one FFmpeg clock per segment, pause closes files."""
from pathlib import Path
from dataclasses import replace
import fcntl
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import time
from .capture import CaptureConfig, append_segment, trim_tail
from .schema import Project, atomic_json, save_project


def capture_command(config, root, stem, origin=None):
    from .devices import resolve_system_audio
    from .cursor import effect_settings
    system_audio = resolve_system_audio(config.system_audio)
    origin = time.time() if origin is None else origin
    x,y,w,h = config.rect
    cmd = ['ffmpeg', '-hide_banner', '-y', '-loglevel', 'warning', '-thread_queue_size', '512',
           '-f', 'x11grab', '-draw_mouse', '1' if config.cursor and not effect_settings(config.cursor_effects) else '0',
           '-framerate', str(config.fps), '-video_size', f'{w}x{h}', '-i', f'{config.display}+{x},{y}']
    audio_indices = []
    next_input = 1
    for device in [config.mic, system_audio]:
        if device:
            cmd += ['-thread_queue_size', '512', '-f', 'pulse', '-fragment_size', '1920', '-i', device]
            audio_indices.append(next_input)
            next_input += 1
    if config.camera:
        cmd += ['-thread_queue_size', '512', '-use_wallclock_as_timestamps', '1', '-f', 'v4l2', '-i', config.camera]
    cmd += ['-copyts', '-map', '0:v:0']
    for index in audio_indices:
        cmd += ['-map', f'{index}:a:0']
    cmd += ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', str({'compact':28,'standard':20,'high':16}[config.quality]), '-pix_fmt', 'yuv420p',
            '-threads', '2', '-vf', f'setpts=PTS-{origin}/TB,fps=fps={config.fps}',
            '-c:a', 'pcm_s16le', '-af', f'asetpts=PTS-{origin}/TB,aresample=async=1',
            '-f', 'matroska', str(root/(stem+'.mkv'))]
    if config.camera:
        cmd += ['-map', f'{next_input}:v:0', '-c:v', 'libx264', '-preset', 'ultrafast',
                '-threads', '1', '-vf', f'setpts=PTS-{origin}/TB,fps=fps={config.fps}', '-pix_fmt', 'yuv420p', '-f', 'matroska', str(root/(stem+'-camera.mkv'))]
    return cmd


def child_parent_guard():
    # Finalize Matroska when the supervising recorder is killed unexpectedly.
    import ctypes
    libc = ctypes.CDLL(None)
    libc.prctl(1, signal.SIGINT)
    if os.getppid() == 1:
        os.kill(os.getpid(), signal.SIGINT)


def main(root):
    root = Path(root)
    lock = (root/'capture.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    data=json.loads((root/'capture.json').read_text());data.setdefault('auto_finalize',False)
    config = CaptureConfig(**data)
    config.validate()
    project = Project(title=config.title or root.name)
    process = None
    logfile = None
    stem = None
    state = 'starting'
    error = None
    stop_requested = False
    explicit_stop=False
    discard=False
    cursor_recorder = None
    cursor_warning = None
    cursor_helper = None
    live_failed = False
    segment_config = config
    def stop_signal(*_):
        nonlocal stop_requested
        stop_requested = True
    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)
    def status():
        usage=resource.getrusage(resource.RUSAGE_CHILDREN)
        atomic_json(root/'status.json', dict(state=state, error=error, pid=os.getpid(),
                    heartbeat=time.time(), auto_finalize=config.auto_finalize, finalization_expected=bool(config.auto_finalize and explicit_stop and not discard and not (root/'discard.json').exists()), project_path=str(root/'project.json'), duration=project.duration, cursor_warning=cursor_warning, child_cpu_s=round(usage.ru_utime+usage.ru_stime,3), child_peak_rss_kib=usage.ru_maxrss))
    def begin():
        nonlocal process, stem, logfile, state,cursor_recorder,cursor_helper,cursor_warning,live_failed,segment_config
        from .devices import clamp_rect, display_bounds
        if clamp_rect(config.rect, display_bounds(config.display)) != config.rect:
            raise RuntimeError('Display geometry changed; start a new recording with a valid area')
        if shutil.disk_usage(root).free < 256*1024*1024:
            raise RuntimeError('Insufficient free space: keep at least 256 MiB available')
        stem = f'segment-{time.time_ns()}'
        from .cursor import CursorRecorder,effect_settings
        segment_config=config
        if config.cursor and effect_settings(config.cursor_effects):
            if config.cursor_live:
                if not live_failed:
                    try:
                        from .live_cursor import LiveCursor
                        cursor_helper=LiveCursor(config.display,config.rect,config.cursor_effects).prepare()
                        atomic_json(root/(stem+'.cursor-live.json'),{'baked':True,'effects':config.cursor_effects})
                    except Exception as exc:
                        if cursor_helper:cursor_helper.stop();cursor_helper=None
                        live_failed=True;cursor_warning='Cursor en vivo no disponible; se usa el puntero nativo. '+str(exc)
                if live_failed:segment_config=replace(config,cursor_effects={})
            else:cursor_recorder=CursorRecorder(root/(stem+'.cursor.jsonl'),config.display,config.rect,config.cursor_effects)
        logfile = (root/(stem+'.log')).open('wb')
        origin=time.time()
        process = subprocess.Popen(capture_command(segment_config, root, stem,origin=origin), stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=logfile, preexec_fn=child_parent_guard)
        if cursor_recorder:cursor_recorder.start(origin)
        state = 'recording'
    def finish():
        nonlocal process, logfile,cursor_recorder,cursor_warning,cursor_helper
        if cursor_recorder:
            cursor_recorder.stop();cursor_warning=cursor_recorder.error;cursor_recorder=None
        if process is None:
            if cursor_helper:cursor_helper.stop();cursor_helper=None
            return
        if process.poll() is None:
            try:
                process.communicate(b'q\n', timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
        if cursor_helper:cursor_helper.stop();cursor_helper=None
        rc = process.returncode
        process = None
        logfile.close()
        if rc != 0:
            raise RuntimeError('Capture failed: '+(root/(stem+'.log')).read_text(errors='replace')[-1500:])
        append_segment(project, root, stem, segment_config)
        save_project(project, root/'project.json')
    try:
        save_project(project, root/'project.json')
        begin()
        while not stop_requested:
            if cursor_recorder and cursor_recorder.error:cursor_warning=cursor_recorder.error
            if cursor_helper and not cursor_helper.alive():
                # Finalize the already-baked interval before native fallback. Never
                # rewrite originals, double-render effects or loop helper restarts.
                cursor_warning='El cursor en vivo se cerró; la grabación continúa con el puntero nativo.'
                live_failed=True;finish();begin()
            status()
            if process is not None and process.poll() is not None:
                finish()
                raise RuntimeError('Capture device stopped unexpectedly')
            if process is not None and shutil.disk_usage(root).free < 128*1024*1024:
                raise RuntimeError('Recording stopped: storage reserve reached')
            for command in sorted(root.glob('command-*.json')):
                payload = json.loads(command.read_text())
                action = payload['command']
                command.unlink()
                if action == 'stop':
                    explicit_stop=True;discard=bool(payload.get('discard'));stop_requested=True;break
                if action == 'pause' and state == 'recording':
                    finish(); state = 'paused'
                if action == 'resume' and state == 'paused': begin()
                if action == 'rewind' and state in {'recording','paused'}:
                    seconds = payload.get('seconds', 10)
                    if not isinstance(seconds,(int,float)) or not 0 < seconds <= 600:
                        continue
                    was_recording = state == 'recording'
                    finish()
                    trim_tail(project, seconds)
                    save_project(project, root/'project.json')
                    if was_recording: begin()
            time.sleep(0.15)
        state = 'stopping'; status()
        finish()
        state = 'stopped'
    except Exception as exc:
        error = str(exc)
        try: finish()
        except Exception as final_exc: error += '\n'+str(final_exc)
        state = 'error'
    finally:
        if logfile is not None and not logfile.closed: logfile.close()
        if state!='stopped':status()
        lock.close()
    if state=='stopped' and explicit_stop and not discard and not (root/'discard.json').exists() and config.auto_finalize and project.clips:
        from .finalize import request
        try:
            # Mark capture complete for request validation; UI uses finalization_expected.
            status()
            request(root/'project.json',config.output_dir)
        except Exception as exc:
            atomic_json(root/'finalization.json',dict(state='error',output=None,project_sha256=None,progress=0.,phase='No se pudo preparar el MP4',error=str(exc)))

    status()

if __name__ == '__main__':
    main(sys.argv[1])
