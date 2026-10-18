"""Optional local-only audio analysis. Never downloads models or modifies projects."""
from pathlib import Path
import re
import shutil
import tempfile
import threading
from .schema import Subtitle, load_project, media_path
from .render import RenderJob


def import_srt(path):
    text = Path(path).read_text(encoding='utf-8-sig').replace('\r\n','\n')
    result = []
    pattern = re.compile(r'(\d+):(\d{2}):(\d{2})[,.](\d{3})\s+-->\s+(\d+):(\d{2}):(\d{2})[,.](\d{3})')
    for block in re.split(r'\n\s*\n', text.strip()):
        match = pattern.search(block)
        if not match: raise ValueError('Invalid SRT cue')
        fields = [int(v) for v in match.groups()]
        def stamp(f): return f[0]*3600+f[1]*60+f[2]+f[3]/1000
        start,end = stamp(fields[:4]),stamp(fields[4:])
        body = block[match.end():].strip()
        if end <= start or not body: raise ValueError('Invalid SRT cue interval or text')
        result.append(Subtitle(start,end,body))
    return result


def parse_silence(log, duration):
    intervals = []
    start = None
    for kind,value in re.findall(r'silence_(start|end):\s*([\d.eE+-]+)',log):
        value = max(0,min(duration,float(value)))
        if kind == 'start': start = value
        elif start is not None:
            if value > start: intervals.append({'start':start,'end':value})
            start = None
    if start is not None and duration > start: intervals.append({'start':start,'end':duration})
    return intervals


class AnalysisJob(RenderJob):
    """kind=silence or transcription; poll result is intervals or Subtitle objects."""
    def __init__(self, project_path, kind='silence', *, executable=None, model_path=None,
                 threshold_db=-35, min_s=.5):
        super().__init__(project_path, Path(project_path).parent/'analysis-unused.mp4')
        if kind not in {'silence','transcription'}: raise ValueError('Unknown analysis kind')
        if not -90 <= threshold_db <= -5 or not .1 <= min_s <= 30:
            raise ValueError('Invalid silence detection settings')
        self.kind,self.executable,self.model_path = kind,executable,model_path
        self.threshold_db,self.min_s = threshold_db,min_s
        self.result = None

    def poll(self):
        data = super().poll()
        data.pop('output')
        data['result'] = self.result
        return data

    def start(self):
        if self._state != 'idle': raise RuntimeError('AnalysisJob can only start once')
        self.project = load_project(self.project_path)
        if not self.project.clips: raise ValueError('No clips to analyze')
        if not any(s.kind in {'mic','system'} and s.gain > 0 for s in self.project.sources):
            raise ValueError('No enabled audio source to analyze')
        if self.kind == 'transcription':
            executable = shutil.which(self.executable or 'whisper-cli')
            if not executable: raise FileNotFoundError('Install whisper.cpp locally and select its whisper-cli executable')
            if not self.model_path or not Path(self.model_path).is_file():
                raise FileNotFoundError('Select an existing local whisper.cpp model file; no model is downloaded')
            self.executable = str(Path(executable).resolve())
        self._state = 'running'
        self._thread = threading.Thread(target=self._run,daemon=True)
        self._thread.start()
        return self

    def _run(self):
        try:
            with tempfile.TemporaryDirectory(prefix='loom-analysis-') as directory:
                temp=Path(directory)
                for i,clip in enumerate(self.project.clips):
                    screen=next(s for s in self.project.sources if s.id==clip.source_id)
                    sources=[s for s in self.project.sources if s.group and s.group==screen.group and s.kind in {'mic','system'}]
                    duration=clip.out_s-clip.in_s
                    command=['ffmpeg','-v','error','-y','-copyts','-filter_complex_threads','1']
                    filters=[];labels=[]
                    for j,source in enumerate(sources):
                        command+=['-i',str(media_path(self.project_path,source))]
                        filters.append(f'[{j}:a:{source.stream}]atrim=start={clip.in_s}:end={clip.out_s},asetpts=PTS-{clip.in_s}/TB,volume={source.gain},apad,atrim=duration={duration}[a{j}]')
                        labels.append(f'[a{j}]')
                    if labels: filters.append(''.join(labels)+f'amix=inputs={len(labels)}:normalize=0[out]')
                    else: filters.append(f'anullsrc=r=16000:cl=mono,atrim=duration={duration}[out]')
                    command+=['-filter_complex',';'.join(filters),'-map','[out]','-ar','16000','-ac','1','-c:a','pcm_s16le',str(temp/f'a{i}.wav')]
                    self._execute(command,temp/'process.log')
                    self._progress=.6*(i+1)/len(self.project.clips)
                (temp/'concat.txt').write_text(''.join(f"file 'a{i}.wav'\n" for i in range(len(self.project.clips))))
                wav=temp/'audio.wav'
                self._execute(['ffmpeg','-v','error','-y','-f','concat','-safe','1','-i',str(temp/'concat.txt'),'-c','copy',str(wav)],temp/'process.log')
                if self.kind=='silence':
                    self._execute(['ffmpeg','-hide_banner','-i',str(wav),'-af',f'silencedetect=noise={self.threshold_db}dB:d={self.min_s}','-f','null','-'],temp/'silence.log')
                    self.result=parse_silence((temp/'silence.log').read_text(),self.project.duration)
                else:
                    self._execute([self.executable,'-m',str(Path(self.model_path).resolve()),'-f',str(wav),'-osrt','-of',str(temp/'transcript'),'-l','auto','-t','2'],temp/'asr.log')
                    self.result=import_srt(temp/'transcript.srt')
                if self._cancel.is_set(): raise InterruptedError()
                self._progress=1
                self._state='done'
        except InterruptedError:
            self._state='cancelled'
        except Exception as exc:
            self._error=str(exc);self._state='error'
