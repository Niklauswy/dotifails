"""Local video catalogue. Viewing is read-only; editing takes a private snapshot."""
import json,os,hashlib,subprocess,shutil,uuid,time,threading
from pathlib import Path
from .library import Library,Entry,default_root
from .schema import atomic_json,Project,Source,Clip,save_project

EXTENSIONS={'.mp4','.mkv','.mov','.webm','.avi','.m4v','.mpeg','.mpg','.mts','.ts','.ogv'}
def absolute_video_path(path):
    """Resolve a selected public video, never an editable project's internals."""
    path=Path(path)
    if path.name=='project.json':raise ValueError('Exporta el video para copiar su ruta')
    try:resolved=path.resolve(strict=True)
    except FileNotFoundError:raise FileNotFoundError('El video ya no existe. Actualiza la biblioteca o restaura el archivo.') from None
    if not resolved.is_file() or resolved.suffix.lower() not in EXTENSIONS:raise ValueError('Selecciona un archivo de video existente')
    if any(parent.name in ('.preview','.wybie') or (parent/'project.json').is_file() for parent in resolved.parents):
        raise ValueError('Exporta el video para copiar su ruta')
    return resolved

def finalization_status(path):
    from .finalize import status
    return status(Path(path))

def recording_video(path):
    """Return only a durable published video and whether edits have changed."""
    path=Path(path);state=finalization_status(path)
    if state.get('state')!='ready' or not state.get('output'):return None,False
    try:output=absolute_video_path(state['output'])
    except (OSError,ValueError,RuntimeError):return None,False
    changed=hashlib.sha256(path.read_bytes()).hexdigest()!=state.get('project_sha256')
    return output,changed

def preferences_path():return Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'loomrec/preferences.json'
def preferences():
    try:return json.loads(preferences_path().read_text())
    except (OSError,ValueError):return {}
def save_preferences(**values):
    current=preferences();current.update(values);atomic_json(preferences_path(),current)
def videos_root():return Path(preferences().get('videos_folder',str(Path.home()/'Videos'))).expanduser()
_MEDIA_LOCK=threading.Lock()
def media_command(arguments,timeout,cancel=None):
    while not _MEDIA_LOCK.acquire(timeout=.1):
        if cancel and cancel.is_set():raise InterruptedError('Lectura cancelada')
    try:
        if cancel and cancel.is_set():raise InterruptedError('Lectura cancelada')
        with subprocess.Popen(arguments,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as process:
            deadline=time.monotonic()+timeout
            try:
                while True:
                    if cancel and cancel.is_set():raise InterruptedError('Lectura cancelada')
                    if time.monotonic()>deadline:raise TimeoutError('El video tarda demasiado en responder')
                    try:
                        stdout,stderr=process.communicate(timeout=.1)
                        return subprocess.CompletedProcess(arguments,process.returncode,stdout,stderr)
                    except subprocess.TimeoutExpired:pass
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=.5)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
    finally:_MEDIA_LOCK.release()
def probe(path,cancel=None):
    result=media_command(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],timeout=12,cancel=cancel)
    if result.returncode:raise ValueError('No se pudo leer el video: '+Path(path).name)
    data=json.loads(result.stdout);streams=data.get('streams',[])
    if not any(s.get('codec_type')=='video' for s in streams):raise ValueError('El archivo no contiene video')
    duration=float(data.get('format',{}).get('duration') or next((s.get('duration') for s in streams if s.get('duration')),0))
    return duration,any(s.get('codec_type')=='audio' for s in streams)

class VideoLibrary(Library):
    def __init__(self,folder=None,legacy=None,include_previous=True):
        self.videos=Path(folder) if folder else videos_root();self.videos.mkdir(parents=True,exist_ok=True)
        super().__init__(self.videos/'.wybie/recordings')
        self.legacy=Path(legacy) if legacy else default_root()
        self.previous=[Path(p) for p in preferences().get('previous_video_folders',[]) if Path(p).exists() and Path(p).resolve()!=self.videos.resolve()] if include_previous else []
        self.cache=self.videos/'.wybie/catalogue';self.cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    def _key(self,path):return hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()
    def _metadata(self,path):
        target=self.cache/(self._key(path)+'.json')
        try:return json.loads(target.read_text())
        except (OSError,ValueError):return {}
    def _write_metadata(self,path,**changes):
        data=self._metadata(path);data.update(changes);atomic_json(self.cache/(self._key(path)+'.json'),data)
    def entries(self,query='',trash=False):
        result=super().entries(query,trash)
        if self.legacy.exists() and self.legacy.resolve()!=self.root.resolve():result+=Library(self.legacy).entries(query,trash)
        if trash:
            for record in (self.videos/'.wybie/trash').glob('*/entry.json'):
                try:
                    data=json.loads(record.read_text());path=record.parent/data['name'];result.append(Entry(path,data['title'],data.get('duration',0),path.stat().st_mtime))
                except (OSError,ValueError,KeyError):continue
        else:
            for base,dirs,files in os.walk(self.videos,followlinks=False):
                dirs[:]=[d for d in dirs if not d.startswith('.')]
                if 'project.json' in files:dirs[:]=[];continue
                for name in files:
                    path=Path(base)/name
                    if path.suffix.lower() not in EXTENSIONS or path.is_symlink():continue
                    data=self._metadata(path)
                    try:stat=path.stat()
                    except OSError:continue
                    result.append(Entry(path,data.get('title',path.stem),data.get('duration',0),stat.st_mtime,data.get('collection','')))
        for previous in self.previous:
            result+=VideoLibrary(previous,legacy=previous/'.wybie/no-legacy',include_previous=False).entries(query,trash)
        published={}
        for entry in result:
            if entry.path.name=='project.json':
                try:output,_=recording_video(entry.path)
                except (OSError,ValueError):output=None
                if output:published[str(output.resolve())]=str(entry.path.resolve())
        # Keep the editable recording as the single catalogue row, pointing to its MP4.
        result=[entry for entry in result if str(entry.path.resolve()) not in published]
        associated=set()
        for entry in result:
            if entry.path.name!='project.json':
                metadata=self._catalogue(entry.path)._metadata(entry.path)
                if metadata.get('edit_project') and str(Path(metadata['edit_project']).resolve()) not in published.values():associated.add(str(Path(metadata['edit_project']).resolve()))
        result=list({str(e.path.resolve()):e for e in result if str(e.path.resolve()) not in associated}.values())
        return sorted((e for e in result if query.casefold() in (e.title+' '+e.collection).casefold()),key=lambda e:e.modified,reverse=True)
    def _catalogue(self,path):
        for previous in self.previous:
            if Path(path).resolve().is_relative_to(previous.resolve()):return VideoLibrary(previous,legacy=previous/'.wybie/no-legacy',include_previous=False)
        return self
    def enrich(self,entry,cancel=None):
        owner=self._catalogue(entry.path)
        if owner is not self:return owner.enrich(entry,cancel)
        if entry.path.name=='project.json':return entry
        stat=entry.path.stat();data=self._metadata(entry.path);stamp=[stat.st_size,stat.st_mtime_ns]
        if data.get('stamp')!=stamp:
            duration,_=probe(entry.path,cancel);self._write_metadata(entry.path,duration=duration,stamp=stamp);entry.duration=duration
        return entry
    def thumbnail_path(self,path):return self._catalogue(path).cache/(self._key(path)+'.jpg')
    def thumbnail(self,path,cancel=None):
        output=self.thumbnail_path(path)
        if not output.exists():
            media_command(['ffmpeg','-v','error','-nostdin','-n','-i',str(path),'-frames:v','1','-vf','scale=288:-2',str(output)],timeout=15,cancel=cancel)
        return output
    def _owner(self,path,trash=False):
        for root in (self.root,self.legacy,*[p/'.wybie/recordings' for p in self.previous]):
            base=root/'.trash' if trash else root
            if Path(path).resolve().parent.parent==base.resolve():return Library(root)
        raise ValueError('Grabación fuera de la biblioteca')
    def rename(self,path,title):
        if Path(path).name=='project.json':return self._owner(path).rename(path,title)
        if not title.strip():raise ValueError('Escribe un título')
        self._catalogue(path)._write_metadata(path,title=title.strip())
    def organize(self,path,collection):
        if Path(path).name=='project.json':return self._owner(path).organize(path,collection)
        self._catalogue(path)._write_metadata(path,collection=collection.strip())
    def delete(self,path):
        path=Path(path)
        if path.name=='project.json':return self._owner(path).delete(path)
        owner=self._catalogue(path)
        if owner is not self:return owner.delete(path)
        if not path.resolve().is_relative_to(self.videos.resolve()) or path.is_symlink():raise ValueError('Video fuera de la biblioteca')
        dest=self.videos/'.wybie/trash'/uuid.uuid4().hex;dest.mkdir(parents=True,mode=0o700)
        data=self._metadata(path);atomic_json(dest/'entry.json',dict(original=str(path.resolve()),name=path.name,title=data.get('title',path.stem),duration=data.get('duration',0)))
        path.rename(dest/path.name);return dest/path.name
    def restore(self,path):
        path=Path(path)
        if path.name=='project.json':return self._owner(path,True).restore(path)
        owner=self._catalogue(path)
        if owner is not self:return owner.restore(path)
        if path.parent.parent.resolve()!=(self.videos/'.wybie/trash').resolve():raise ValueError('Video fuera de la papelera')
        data=json.loads((path.parent/'entry.json').read_text());target=Path(data['original'])
        if not target.resolve().is_relative_to(self.videos.resolve()):raise ValueError('Destino inválido')
        if target.exists():raise FileExistsError('Ya existe un video con ese nombre; no se sobrescribirá')
        target.parent.mkdir(parents=True,exist_ok=True);path.rename(target);(path.parent/'entry.json').unlink();path.parent.rmdir();return target
    def create_edit(self,path,cancel=None):
        path=Path(path);owner=self._catalogue(path);existing=owner._metadata(path).get('edit_project')
        if existing and Path(existing).is_file():return Path(existing)
        duration,audio=probe(path,cancel)
        if duration<=0:raise ValueError('No se pudo determinar la duración')
        folder=self.new_directory()
        try:
            source=folder/('original'+path.suffix.lower())
            with path.open('rb') as original,source.open('xb') as target:
                while chunk:=original.read(1024*1024):
                    if cancel and cancel.is_set():raise ValueError('Preparación cancelada; original conservado')
                    target.write(chunk)
            if cancel and cancel.is_set():raise ValueError('Preparación cancelada; original conservado')
            sources=[Source('video',source.name,duration=duration,group='original')]
            if audio:sources.append(Source('audio',source.name,'system',duration=duration,group='original'))
            project=Project(title=self._metadata(path).get('title',path.stem),sources=sources,clips=[Clip('video',0,duration)])
            save_project(project,folder/'project.json');owner._write_metadata(path,edit_project=str(folder/'project.json'));return folder/'project.json'
        except Exception:shutil.rmtree(folder);raise
