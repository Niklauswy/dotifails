"""Cancellable, atomic MP4 rendering of a non-destructive project snapshot."""
from pathlib import Path
from dataclasses import replace
import os
import json
import shutil
import subprocess
import tempfile
import threading
from .schema import load_project, media_path, project_from_dict
from copy import deepcopy

PIPELINE_VERSION='native-fps-live-cursor-v2'
PROFILES={'preview':{'cap':None,'crf':None},'compact':{'cap':(1280,720),'crf':26},
          'standard':{'cap':None,'crf':20},'high':{'cap':None,'crf':16}}

def render_profile_signature(preset='preview'):
    return {'pipeline':PIPELINE_VERSION,'preset':preset,**PROFILES[preset],
            'fps':'source-timestamps','upscale':False,'encoder':'libx264-veryfast-bf0','pixel_format':'yuv420p'}

def native_canvas(sizes,crop=None,cap=None):
    """Uniform concat canvas; preserve native pixels, pad smaller clips, never upscale."""
    cropped=[(max(2,int(w*(crop[2] if crop else 1))//2*2),max(2,int(h*(crop[3] if crop else 1))//2*2)) for w,h in sizes]
    width=max(w for w,h in cropped);height=max(h for w,h in cropped)
    factor=min(1,cap[0]/width,cap[1]/height) if cap else 1
    return max(2,int(width*factor)//2*2),max(2,int(height*factor)//2*2)



def camera_overlay(camera,width,height):
    """Filter chain and position for the camera bubble: centre crop, never stretched.

    Circle: a square crop with a circular alpha mask. Rounded: a 4:3 crop with
    rounded corners. Size is relative to the video height; a margin keeps the
    bubble off the edges in the chosen corner.
    """
    from .schema import CAMERA_SIZES
    tall=max(2,int(height*CAMERA_SIZES.get(getattr(camera,'size','medium'),.28))//2*2)
    circle=getattr(camera,'shape','circle')=='circle'
    w,h=(tall,tall) if circle else (max(2,int(tall*4/3)//2*2),tall)
    if circle:
        crop="crop='min(iw,ih)':'min(iw,ih)'"
        alpha="if(lte(hypot(X-W/2,Y-H/2),W/2-1),255,0)"
    else:
        crop="crop='min(iw,ih*4/3)':'min(ih,iw*3/4)'"
        r=max(4,h//8)
        alpha=f"if(lte(pow(max(max({r}-X,X-(W-1-{r})),0),2)+pow(max(max({r}-Y,Y-(H-1-{r})),0),2),{r*r}),255,0)"
    chain=f"{crop},scale={w}:{h},format=yuva420p,geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='{alpha}'"
    margin=max(8,int(height*.035))
    corner=getattr(camera,'corner','bottom-right')
    x=width-w-margin if corner.endswith('right') else margin
    y=height-h-margin if corner.startswith('bottom') else margin
    return chain,max(0,x),max(0,y)

class RenderJob:
    def __init__(self, project_path, output, preset="standard", *, snapshot=None):
        self._snapshot=deepcopy(snapshot)
        if preset not in PROFILES: raise ValueError("Unknown export preset")
        self.preset=preset;self.width=self.height=None;self.crf=PROFILES[preset]['crf']
        self.project_path = Path(project_path).resolve()
        self.output = Path(output).resolve()
        self._cancel = threading.Event()
        self._state = 'idle'
        self._progress = 0.0
        self._error = None
        self._process = None
        self._thread = None
        self._phase = 'Preparando'
        self._step_base=0.;self._step_span=0.;self._step_duration=None

    def poll(self):
        return dict(state=self._state, progress=self._progress, error=self._error, output=str(self.output), phase=self._phase)

    def start(self):
        if self._state != 'idle':
            raise RuntimeError('RenderJob can only start once')
        self.project = project_from_dict(self._snapshot) if self._snapshot is not None else load_project(self.project_path)
        if not self.project.clips: raise ValueError('Project contains no clips')
        protected = {media_path(self.project_path, s) for s in self.project.sources} | {self.project_path}
        protected.update(media_path(self.project_path,replace(s,path=s.cursor_path)) for s in self.project.sources if s.cursor_path)
        if self.output in protected: raise ValueError('Export cannot overwrite project or source media')
        if self.output.exists(): raise FileExistsError('Choose a new export filename')
        if self.output.suffix.lower() != '.mp4': raise ValueError('Export filename must end with .mp4')
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self._state = 'running'
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def cancel(self):
        self._cancel.set()

    def _read_progress(self,path):
        if not self._step_duration:return
        try:
            with open(path,'rb') as stream:
                stream.seek(0,2);stream.seek(max(0,stream.tell()-4096));lines=stream.read().decode(errors='replace').splitlines()
            values=[int(line.split('=',1)[1]) for line in lines if line.startswith('out_time_us=') and line.split('=',1)[1].lstrip('-').isdigit()]
            if values:
                fraction=max(0,min(1,values[-1]/1_000_000/self._step_duration))
                self._progress=max(self._progress,self._step_base+self._step_span*fraction)
        except OSError:pass

    def _execute(self, command, logpath):
        if self._cancel.is_set(): raise InterruptedError('Export cancelled')
        progress_path=Path(logpath).with_name('render-progress.txt')
        if Path(command[0]).name=='ffmpeg':command=[command[0],'-progress',str(progress_path),'-stats_period','0.25',*command[1:]]
        with open(logpath, 'wb') as log:
            self._process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log, stdin=subprocess.DEVNULL, cwd=Path(logpath).parent)
            while self._process.poll() is None:
                self._read_progress(progress_path)
                if self._cancel.wait(0.1):
                    self._process.terminate()
                    try: self._process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self._process.kill(); self._process.wait()
                    raise InterruptedError('Export cancelled')
            if self._process.returncode:
                raise RuntimeError(Path(logpath).read_text(errors='replace')[-3000:])
        self._process = None

    def _run(self):
        try:
            if self._cancel.is_set():raise InterruptedError('Export cancelled')
            self._prepare_geometry()
            with tempfile.TemporaryDirectory(prefix='.loom-export-', dir=self.output.parent) as temporary:
                temp = Path(temporary)
                offset = 0
                for i, clip in enumerate(self.project.clips):
                    self._phase=f'Renderizando clip {i+1} de {len(self.project.clips)}'
                    self._step_duration=clip.out_s-clip.in_s;self._step_base=.9*offset/self.project.duration;self._step_span=.9*self._step_duration/self.project.duration
                    command = self._clip_command(clip, offset, temp, i)
                    self._execute(command, temp/'ffmpeg.log')
                    offset += clip.out_s - clip.in_s
                    self._progress = 0.9 * offset / self.project.duration
                # Names are generated internally, never interpolated source paths.
                self._phase='Uniendo clips y finalizando MP4';self._step_duration=None
                (temp/'concat.txt').write_text(''.join(f"file 'clip-{i}.mp4'\nduration {clip.out_s-clip.in_s:.9f}\n" for i,clip in enumerate(self.project.clips)))
                self._execute(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '1', '-i',
                    str(temp/'concat.txt'), '-c', 'copy', '-movflags', '+faststart', str(temp/'result.mp4')], temp/'ffmpeg.log')
                if self._cancel.is_set(): raise InterruptedError('Export cancelled')
                with (temp/'result.mp4').open('rb') as f: os.fsync(f.fileno())
                os.link(temp/'result.mp4', self.output)
                self._progress = 1.0
                self._state = 'done'
        except InterruptedError:
            self._state = 'cancelled'
        except Exception as exc:
            self._error = str(exc)
            self._state = 'error'

    def _prepare_geometry(self):
        from .capture import probe
        selected={clip.source_id for clip in self.project.clips};sources=[s for s in self.project.sources if s.id in selected]
        sizes=[]
        for source in sources:
            if self._cancel.is_set():raise InterruptedError('Export cancelled')
            if source.width and source.height:sizes.append((source.width,source.height))
            else:
                streams=[s for s in probe(media_path(self.project_path,source))['streams'] if s['codec_type']=='video']
                stream=streams[source.stream];sizes.append((stream['width'],stream['height']))
        self.width,self.height=native_canvas(sizes,self.project.crop,PROFILES[self.preset]['cap'])
        if self.preset=='preview':
            qualities=[s.quality for s in sources]
            # Old projects lack per-source quality but retain their capture intent.
            try:
                previous=json.loads((self.project_path.parent/'capture.json').read_text()).get('quality')
                if previous in {'compact','standard','high'}:qualities.append(previous)
            except (OSError,ValueError):pass
            self.crf=min({'compact':26,'standard':20,'high':16}[q] for q in qualities)

    def _clip_command(self, clip, offset, temp, index):
        if self.width is None:self._prepare_geometry()
        project = self.project
        source = next(s for s in project.sources if s.id == clip.source_id)
        duration = clip.out_s - clip.in_s
        linked = [s for s in project.sources if s.group and s.group == source.group and s.kind != 'screen']
        cmd = ['ffmpeg', '-hide_banner', '-v', 'error', '-y', '-copyts', '-filter_complex_threads', '1']
        inputs = [source] + [s for s in linked if s.kind in {'mic', 'system'} or project.camera.enabled]
        for s in inputs:
            cmd += ['-i', str(media_path(self.project_path, s))]
        filters = [f'[0:v:{source.stream}]trim=start={clip.in_s}:end={clip.out_s},setpts=PTS-{clip.in_s}/TB[v0]']
        current = 'v0'
        counter = 0
        def apply(filt):
            nonlocal counter, current
            counter += 1
            label = f'v{counter}'
            filters.append(f'[{current}]{filt}[{label}]')
            current = label
        if source.cursor_path and not source.cursor_baked:
            from .cursor import write_ass
            trace=media_path(self.project_path,replace(source,path=source.cursor_path))
            script=temp/f'cursor-{index}.ass'
            if write_ass(trace,script,clip.in_s,clip.out_s,source.cursor_effects,self._cancel):
                apply(f'ass={script.name}')
        if project.crop:
            x,y,w,h = project.crop
            apply(f'crop=w=trunc(iw*{w}/2)*2:h=trunc(ih*{h}/2)*2:x=iw*{x}:y=ih*{y}')
        # Native-size canvas for same-size sources; pad differing clips instead of
        # enlarging them. Preserve input timestamps, including non-30fps sources.
        apply(f"scale=w='min(iw,{self.width})':h='min(ih,{self.height})':force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,setsar=1")
        audio = []
        for i, s in enumerate(inputs[1:], 1):
            if s.kind in {'mic','system'}:
                label = f'a{i}'
                filters.append(f'[{i}:a:{s.stream}]atrim=start={clip.in_s}:end={clip.out_s},asetpts=PTS-{clip.in_s}/TB,aresample=48000,volume={s.gain},apad,atrim=duration={duration}[{label}]')
                audio.append(label)
            elif s.kind == 'camera':
                chain,x,y = camera_overlay(project.camera,self.width,self.height)
                filters.append(f'[{i}:v:{s.stream}]trim=start={clip.in_s}:end={clip.out_s},setpts=PTS-{clip.in_s}/TB,{chain}[cam{i}]')
                counter += 1
                filters.append(f'[{current}][cam{i}]overlay=x={x}:y={y}:eof_action=pass[v{counter}]')
                current = f'v{counter}'
        # Redaction is composited after cursor, camera, and other annotations.
        for j, a in enumerate(sorted(project.annotations,key=lambda a:a.kind in {'mask','blur'})):
            start, end = max(0,a.start-offset), min(duration,a.end-offset)
            if end <= start: continue
            x,y,w,h = a.rect
            x,y,w,h = int(x*self.width),int(y*self.height),max(2,int(w*self.width)),max(2,int(h*self.height))
            enable = f"between(t,{start},{end})"
            if a.kind == 'text':
                textfile = temp/f'text-{index}-{j}.txt'; textfile.write_text(a.text)
                apply(f"drawtext=textfile='{textfile.name}':expansion=none:fontcolor={a.color}:fontsize=32:x={x}:y={y}:enable='{enable}'")
            elif a.kind in {'mask','highlight'}:
                color = 'black' if a.kind == 'mask' else a.color+'@0.35'
                apply(f"drawbox=x={x}:y={y}:w={w}:h={h}:color={color}:t=fill:enable='{enable}'")
            elif a.kind == 'arrow':
                # Horizontal arrow in the selected rectangle: shaft plus two diagonals.
                apply(f"drawbox=x={x}:y={y+h//2}:w={w}:h=4:color={a.color}:t=fill:enable='{enable}'")
                for n in range(12):
                    ax = x+w-4-n*3
                    for ay in [y+h//2-n*2, y+h//2+n*2]:
                        apply(f"drawbox=x={ax}:y={ay}:w=4:h=4:color={a.color}:t=fill:enable='{enable}'")
            elif a.kind == 'blur':
                counter += 1
                filters.append(f'[{current}]split[base{counter}][region{counter}]')
                filters.append(f'[region{counter}]crop={w}:{h}:{x}:{y},boxblur=luma_radius={min(10,w//2,h//2)}:luma_power=2:chroma_radius=0[blur{counter}]')
                filters.append(f"[base{counter}][blur{counter}]overlay={x}:{y}:enable='{enable}'[v{counter}]")
                current = f'v{counter}'
        for j,s in enumerate(project.subtitles):
            start,end = max(0,s.start-offset),min(duration,s.end-offset)
            if end <= start: continue
            textfile = temp/f'sub-{index}-{j}.txt'; textfile.write_text(s.text)
            apply(f"drawtext=textfile='{textfile.name}':expansion=none:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.8:x=(w-tw)/2:y=h-th-40:enable='between(t,{start},{end})'")
        if audio:
            filters.append(''.join(f'[{a}]' for a in audio)+f'amix=inputs={len(audio)}:normalize=0,alimiter=limit=0.95:latency=1[aout]')
        else:
            filters.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={duration}[aout]')
        cmd += ['-filter_complex', ';'.join(filters), '-map', f'[{current}]', '-map', '[aout]',
                '-t', str(duration), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(self.crf),
                '-threads', '2', '-bf', '0', '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', '-enc_time_base:v', '1:90000', '-video_track_timescale', '90000', '-c:a', 'aac', '-ar', '48000', '-ac', '2',
                '-movflags', '+faststart', str(temp/f'clip-{index}.mp4')]
        return cmd
