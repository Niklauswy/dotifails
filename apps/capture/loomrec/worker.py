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


def capture_command(config, root, stem, origin=None, pipewire=None):
    from .devices import resolve_system_audio
    from .cursor import effect_settings
    system_audio = resolve_system_audio(config.system_audio)
    origin = time.time() if origin is None else origin
    x,y,w,h = config.rect
    cmd = ['ffmpeg', '-hide_banner', '-y', '-loglevel', 'warning', '-thread_queue_size', '512']
    if pipewire is not None:
        fd,w,h=pipewire
        cmd += ['-probesize','32','-analyzeduration','1','-fpsprobesize','0',
                '-use_wallclock_as_timestamps','1','-f','rawvideo','-pixel_format','bgra',
                '-framerate',str(config.fps),'-video_size',f'{w}x{h}','-i',f'pipe:{fd}']
    else:
        if config.selected_backend()!='x11':raise RuntimeError('Falta la fuente PipeWire autorizada')
        cmd += ['-f','x11grab','-draw_mouse','1' if config.cursor and not effect_settings(config.cursor_effects) else '0',
                '-framerate',str(config.fps),'-video_size',f'{w}x{h}','-i',f'{config.display}+{x},{y}']
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


def end_portal_segment(process,producer,on_wait=None,live_inputs=False):
    """EOF stops raw video; SIGINT also finalizes still-live Pulse/V4L2 inputs."""
    try:
        producer.finish()
    finally:
        # This PIPE is FFmpeg's interactive command input, not the raw-video
        # input. The portal route stops via producer EOF/SIGINT, never q.
        # Release our writer explicitly even if producer teardown fails.
        if process.stdin is not None:process.stdin.close()
    interrupted=False
    if live_inputs and process.poll() is None:
        process.send_signal(signal.SIGINT);interrupted=True
    deadline=time.monotonic()+10
    while process.poll() is None:
        if on_wait:on_wait()
        if time.monotonic()>=deadline:raise subprocess.TimeoutExpired(process.args,10)
        time.sleep(.1)
    return interrupted


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
    native_live_failed = False
    segment_config = config
    wayland_capture = None
    mouse_effects = None
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
        nonlocal process, stem, logfile, state,cursor_recorder,cursor_helper,cursor_warning,live_failed,segment_config,mouse_effects
        from .devices import clamp_rect, display_bounds
        if config.selected_backend()=='x11' and clamp_rect(config.rect, display_bounds(config.display)) != config.rect:
            raise RuntimeError('Display geometry changed; start a new recording with a valid area')
        if shutil.disk_usage(root).free < 256*1024*1024:
            raise RuntimeError('Insufficient free space: keep at least 256 MiB available')
        stem = f'segment-{time.time_ns()}'
        from .cursor import CursorRecorder,effect_settings
        segment_config=config
        if config.selected_backend()=='x11' and config.cursor and effect_settings(config.cursor_effects):
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
        live_options=None
        if wayland_capture and mouse_effects and config.cursor_live and not native_live_failed:
            live_options=dict(cursor_trace_path=str(root/(stem+'.cursor.jsonl')),cursor_effects=config.cursor_effects,cursor_marker=str(root/(stem+'.cursor-live.json')))
        pipewire=wayland_capture.begin(logfile,live_effects=live_options) if wayland_capture else None
        origin=time.time()
        process = subprocess.Popen(capture_command(segment_config, root, stem,origin=origin,pipewire=pipewire), stdin=subprocess.PIPE,
                                   pass_fds=(pipewire[0],) if pipewire else (),
                                   stdout=subprocess.DEVNULL, stderr=logfile, preexec_fn=child_parent_guard)
        if wayland_capture and mouse_effects:
            try:
                from .wayland_pointer import NativePointerReader
                from .pipewire_bridge import pixel_crop
                size=wayland_capture.source_size;metadata=wayland_capture.metadata
                crop=pixel_crop(*size,metadata,config.rect if config.source_type=='region' else None)
                reader=NativePointerReader(mouse_effects,metadata,size,crop)
                mouse_effects.run()
                cursor_recorder=CursorRecorder(root/(stem+'.cursor.jsonl'),'',(0,0,crop[2],crop[3]),config.cursor_effects,reader=reader,native_cursor=True)
                cursor_warning='Wayland: halo y traza'+(', clics autorizados' if mouse_effects.buttons_available else ' sin lectura de botones')+(' incluidos en el vídeo; no son una capa del escritorio.' if live_options else ' al exportar; la grabación conserva el cursor nativo.')
            except Exception as exc:
                cursor_warning='Se conserva el cursor nativo; efectos de ratón no disponibles. '+str(exc)
                mouse_effects.close();mouse_effects=None
        if cursor_recorder:
            try:cursor_recorder.start(origin)
            except Exception as exc:
                if not wayland_capture:raise
                cursor_warning='El cursor nativo permanece; efectos de ratón no disponibles. '+str(exc)
                cursor_recorder.stop();cursor_recorder=None
        state = 'recording'
    def finish():
        nonlocal process, logfile,cursor_recorder,cursor_warning,cursor_helper
        if cursor_recorder:
            cursor_recorder.stop()
            if cursor_recorder.error:cursor_warning=cursor_recorder.error
            cursor_recorder=None
        if process is None:
            if cursor_helper:cursor_helper.stop();cursor_helper=None
            return
        interrupted_by_us=False
        try:
            if process.poll() is None:
                try:
                    if wayland_capture:
                        interrupted_by_us=end_portal_segment(process,wayland_capture,status,bool(config.mic or config.system_audio or config.camera))
                    else:process.communicate(b'q\n', timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
        finally:
            # Also covers an already exited child and timeout/error cleanup.
            if process.stdin is not None:process.stdin.close()
        if cursor_helper:cursor_helper.stop();cursor_helper=None
        if wayland_capture:wayland_capture.finish()
        rc = process.returncode
        process = None
        logfile.close()
        if rc != 0 and not (interrupted_by_us and rc==255):
            raise RuntimeError('Capture failed: '+(root/(stem+'.log')).read_text(errors='replace')[-1500:])
        # append_segment probes outputs; rc255 is accepted only after our own
        # intentional SIGINT and never skips media validation.
        append_segment(project, root, stem, segment_config)
        save_project(project, root/'project.json')
    try:
        save_project(project, root/'project.json')
        status()
        if config.selected_backend()=='portal':
            from .wayland_capture import PipeWireCapture
            def waiting():
                status()
                if mouse_effects:mouse_effects.ping()
                if stop_requested or any(json.loads(p.read_text()).get('command')=='stop' for p in root.glob('command-*.json')):
                    raise RuntimeError('Selección del portal cancelada')
            from .cursor import effect_settings
            if config.cursor and effect_settings(config.cursor_effects) and config.source_type in ('monitor','region'):
                from .wayland_pointer import MouseEffects,PositionEffects
                try:
                    mouse_effects=MouseEffects(on_wait=waiting) if effect_settings(config.cursor_effects).get('clicks') else PositionEffects();mouse_effects.prepare()
                except Exception as exc:
                    if mouse_effects:mouse_effects.close();mouse_effects=None
                    cursor_warning='Cursor nativo; clics sin autorización o helper. '+str(exc)
                    if effect_settings(config.cursor_effects).get('halo') or effect_settings(config.cursor_effects).get('trail'):mouse_effects=PositionEffects()
            wayland_capture=PipeWireCapture(config,on_wait=waiting)
            if config.cursor and effect_settings(config.cursor_effects) and not mouse_effects and not cursor_warning:cursor_warning='Wayland: cursor nativo; efectos de ratón requieren monitor/región y autorización explícita por grabación.'
        begin()
        while not stop_requested:
            if mouse_effects:
                try:mouse_effects.ping()
                except (OSError,RuntimeError) as exc:
                    cursor_warning='Se revocaron los efectos del ratón; el cursor nativo permanece. '+str(exc)
                    mouse_effects.close();mouse_effects=None
            if wayland_capture:
                wayland_capture.check()
                marker=root/(stem+'.cursor-live.json')
                if state=='recording' and not native_live_failed and marker.is_file():
                    live_error=json.loads(marker.read_text()).get('error') or (cursor_recorder.error if cursor_recorder else None)
                    if live_error:
                        native_live_failed=True;finish();begin()
                        cursor_warning='Efectos en vivo interrumpidos; nuevos segmentos con efectos al exportar. '+str(live_error)
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
        if mouse_effects:mouse_effects.close()
        if wayland_capture:wayland_capture.close()
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
