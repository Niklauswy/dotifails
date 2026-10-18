"""Transactional non-destructive edits with bounded history and atomic autosave."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from .schema import Clip, Annotation, Subtitle, validate, save_project, load_project


class Editor:
    def __init__(self, path):
        self.path = Path(path)
        self.project = load_project(path)
        self.undo_stack = []
        self.redo_stack = []
        self.revision = 0

    def apply(self, change):
        candidate = deepcopy(self.project)
        change(candidate)
        validate(candidate)
        save_project(candidate, self.path)
        self.undo_stack.append(deepcopy(self.project))
        self.undo_stack = self.undo_stack[-100:]
        self.redo_stack.clear()
        self.project = candidate
        self.revision += 1

    def _restore(self, source, target):
        if not source:
            return False
        candidate = deepcopy(source[-1])
        save_project(candidate, self.path)
        target.append(self.project)
        self.project = candidate
        source.pop()
        self.revision += 1
        return True

    def undo(self): return self._restore(self.undo_stack, self.redo_stack)
    def redo(self): return self._restore(self.redo_stack, self.undo_stack)

    @staticmethod
    def _timeline(p, segments):
        """Remap timed overlays through kept/reordered old timeline intervals."""
        for field in ('annotations', 'subtitles'):
            result, offset = [], 0.0
            for start, end in segments:
                for item in getattr(p, field):
                    left, right = max(start, item.start), min(end, item.end)
                    if right > left:
                        result.append(replace(item, start=offset+left-start, end=offset+right-start))
                offset += end-start
            setattr(p, field, result)

    def _ranges(self):
        result, pos = [], 0.0
        for c in self.project.clips:
            end = pos+c.out_s-c.in_s
            result.append((pos, end))
            pos = end
        return result

    def trim(self, index, start, end):
        clip = self.project.clips[index]
        if not clip.in_s <= start < end <= clip.out_s:
            raise ValueError('El recorte debe estar dentro del clip seleccionado')
        ranges = self._ranges()
        left, _ = ranges[index]
        ranges[index] = (left+start-clip.in_s, left+end-clip.in_s)
        def edit(p):
            self._timeline(p, ranges)
            p.clips[index] = Clip(clip.source_id, start, end)
        self.apply(edit)

    def split(self, index, at):
        clip = self.project.clips[index]
        if not clip.in_s < at < clip.out_s:
            raise ValueError('Coloca el cursor dentro del clip para dividir')
        self.apply(lambda p: p.clips.__setitem__(slice(index,index+1),
            [Clip(clip.source_id, clip.in_s, at), Clip(clip.source_id, at, clip.out_s)]))

    def delete(self, index):
        ranges = self._ranges(); ranges.pop(index)
        def edit(p):
            self._timeline(p, ranges)
            p.clips.pop(index)
        self.apply(edit)

    def move(self, index, target):
        if not 0 <= target < len(self.project.clips): return
        order = list(range(len(self.project.clips)))
        order.insert(target, order.pop(index))
        ranges = self._ranges()
        def edit(p):
            self._timeline(p, [ranges[i] for i in order])
            p.clips = [p.clips[i] for i in order]
        self.apply(edit)

    def join(self, index):
        if index+1 >= len(self.project.clips):
            raise ValueError('Selecciona un clip con un siguiente clip')
        a,b = self.project.clips[index:index+2]
        if a.source_id != b.source_id or abs(a.out_s-b.in_s) > 1e-6:
            raise ValueError('Solo se unen cortes contiguos de la misma fuente; la exportación concatena todos los clips')
        self.apply(lambda p: p.clips.__setitem__(slice(index,index+2), [Clip(a.source_id,a.in_s,b.out_s)]))

    def gain(self, source_id, gain):
        self.apply(lambda p: setattr(next(s for s in p.sources if s.id == source_id), 'gain', gain))

    def add_annotation(self, kind, start, end, rect, text='', color='yellow'):
        if end > self.project.duration: raise ValueError('La anotación excede la duración')
        self.apply(lambda p: p.annotations.append(Annotation(kind,start,end,rect,text,color)))

    def subtitle(self, start, end, text, index=None):
        if end > self.project.duration: raise ValueError('El subtítulo excede la duración')
        def edit(p):
            item = Subtitle(start,end,text)
            if index is None: p.subtitles.append(item)
            else: p.subtitles[index] = item
        self.apply(edit)

    def export_srt(self, destination):
        def stamp(t):
            ms = round(t*1000)
            return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
        with Path(destination).open('x', encoding='utf-8') as f:
            for i,s in enumerate(sorted(self.project.subtitles,key=lambda s:s.start),1):
                f.write(f'{i}\n{stamp(s.start)} --> {stamp(s.end)}\n{s.text}\n\n')

    def remove_ranges(self, intervals):
        """Apply only reviewed timeline removals, preserving original media."""
        duration=self.project.duration
        merged=[]
        for start,end in sorted(intervals):
            if not 0 <= start < end <= duration: raise ValueError('Intervalo fuera de la línea de tiempo')
            if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
            else:merged.append((start,end))
        kept=[]; pos=0
        for start,end in merged:
            if start>pos:kept.append((pos,start))
            pos=end
        if pos<duration:kept.append((pos,duration))
        ranges=self._ranges()
        def change(p):
            clips=[]
            for start,end in kept:
                for clip,(left,right) in zip(p.clips,ranges):
                    a,b=max(start,left),min(end,right)
                    if b>a:clips.append(Clip(clip.source_id,clip.in_s+a-left,clip.in_s+b-left))
            self._timeline(p,kept); p.clips=clips
        self.apply(change)
