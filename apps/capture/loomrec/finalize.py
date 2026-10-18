"""Durable automatic MP4 finalization, independent of the GUI.

One inherited flock spans request, detached render and atomic publication. A
request contains an immutable project snapshot; originals are never rewritten.
"""
from pathlib import Path
from contextlib import contextmanager
import fcntl,hashlib,json,os,signal,subprocess,sys,tempfile,time,uuid
from datetime import datetime
from .schema import atomic_json,project_from_dict,validate

ACTIVE={'pending','running'}

def _path(project_path):
    path=Path(project_path).absolute()
    return path/'project.json' if path.is_dir() else path

def _read(path):
    try:return json.loads(path.read_text())
    except FileNotFoundError:return {}

def _locked(root):
    try:fd=os.open(root/'finalization.lock',os.O_RDWR|os.O_NOFOLLOW)
    except FileNotFoundError:return False
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);return False
        except BlockingIOError:return True
    finally:os.close(fd)

def status(project_path):
    """Read durable state; only ready returns an existing output path."""
    path=_path(project_path);data=_read(path.parent/'finalization.json')
    if not data:return dict(state='none',output=None,project_sha256=None,progress=0.,phase='',error=None)
    result=dict(data)
    if result.get('state') in ACTIVE and not _locked(path.parent):
        result.update(state='error',phase='Preparación interrumpida',error='La preparación del MP4 se interrumpió. Puedes reintentar.')
    if result.get('state')=='ready' and not Path(result.get('output') or '').is_file():
        result.update(state='error',phase='MP4 no disponible',error='No se encuentra el MP4 preparado. Puedes reintentar.')
    if result.get('state')!='ready':result['output']=None
    try:result['matches_project']=hashlib.sha256(path.read_bytes()).hexdigest()==result.get('project_sha256')
    except OSError:result['matches_project']=False
    return result

@contextmanager
def _directory(path):
    """Pin every directory component; never follow replacement symlinks."""
    path=Path(path)
    if not path.is_absolute():raise ValueError('La carpeta de salida debe ser absoluta')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if part in ('.','..'):raise ValueError('Carpeta de salida inválida')
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        yield fd
    finally:os.close(fd)

@contextmanager
def _publication_lock(root):
    fd=os.open(root/'finalization-publish.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:fcntl.flock(fd,fcntl.LOCK_EX);yield
    finally:os.close(fd)

def _state(root,data,**values):
    data.update(values,heartbeat=time.time());atomic_json(root/'finalization.json',data)

def request(project_path,output_dir=None,*,retry=False):
    """Queue once and return immediately. retry=True explicitly snapshots new edits."""
    path=_path(project_path);root=path.parent
    if path.is_symlink():raise ValueError('El proyecto no puede ser un enlace simbólico')
    lock=os.open(root/'finalization.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return status(path)
        previous=status(path)
        if previous['state'] in ACTIVE:
            previous.update(state='error',error='La preparación se interrumpió. Puedes reintentar.',output=None)
            atomic_json(root/'finalization.json',previous)
        if (root/'discard.json').exists():return dict(state='cancelled',output=None,progress=0.,phase='Captura descartada',error=None,project_sha256=None)
        if previous['state']=='ready' and (not retry or previous.get('matches_project')):return previous
        if previous['state'] in {'error','cancelled'} and not retry:return previous
        capture=_read(root/'status.json')
        if capture.get('state') in {'starting','recording','paused','stopping'}:raise RuntimeError('Termina la captura antes de preparar el MP4')
        raw=path.read_bytes();snapshot=json.loads(raw);project=project_from_dict(snapshot);validate(project)
        if not project.clips:raise ValueError('La grabación no tiene clips para preparar')
        config=_read(root/'capture.json')
        if output_dir is None:output_dir=config.get('output_dir')
        if output_dir is None:
            from .videolibrary import videos_root
            output_dir=str(videos_root().resolve())
        destination=str(Path(output_dir).expanduser().absolute())
        token=uuid.uuid4().hex;work=root/'.finalize'
        if work.is_symlink():raise ValueError('Directorio temporal inválido')
        work.mkdir(mode=0o700,exist_ok=True)
        sha=hashlib.sha256(raw).hexdigest();filename=datetime.now().strftime('Grabacion-%Y%m%d-%H%M%S-')+token[:12]+'.mp4'
        data=dict(version=1,state='pending',output=None,project_sha256=sha,progress=0.,phase='Preparando MP4',error=None,pid=None,token=token,destination=destination,filename=filename)
        atomic_json(work/(token+'.json'),dict(project=snapshot,state=data))
        _state(root,data)
        environment=os.environ.copy();package=str(Path(__file__).resolve().parent.parent)
        environment['PYTHONPATH']=package+(os.pathsep+environment['PYTHONPATH'] if environment.get('PYTHONPATH') else '')
        try:
            with (work/'finalizer.log').open('ab') as log:
                subprocess.Popen([sys.executable,'-P','-m','loomrec.finalize',str(path),'--token',token,'--lock-fd',str(lock)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,pass_fds=(lock,),env=environment)
        except Exception as exc:_state(root,data,state='error',error=str(exc),phase='No se pudo preparar el MP4')
        return dict(data)
    finally:os.close(lock)

def retry(project_path,output_dir=None):return request(project_path,output_dir,retry=True)

def cancel(project_path,*,discard=False):
    """Cancel this attempt; publication and cancellation have one commit gate."""
    path=_path(project_path);root=path.parent
    with _publication_lock(root):
        if discard:atomic_json(root/'discard.json',{'discard':True})
        data=_read(root/'finalization.json')
        if data.get('state') in ACTIVE and data.get('token'):
            atomic_json(root/'.finalize'/('cancel-'+data['token']+'.json'),{'cancel':True})
    return status(path)

def _publish(source,destination,filename,cancelled,*,root=None,commit=None):
    """Copy into a private temporary file, then publish with no-overwrite link."""
    with _directory(destination) as fd:
        temporary='.wybie-finalize-'+uuid.uuid4().hex+'.tmp'
        target=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=fd)
        try:
            with os.fdopen(target,'wb') as output,open(source,'rb') as input:
                while block:=input.read(1024*1024):
                    if cancelled():raise InterruptedError('Preparación cancelada')
                    output.write(block)
                output.flush();os.fsync(output.fileno())
            with _publication_lock(root or Path(source).parent):
                if cancelled():raise InterruptedError('Preparación cancelada')
                # A last-moment destination replacement must not redirect publication.
                with _directory(destination) as current:
                    if (os.fstat(fd).st_dev,os.fstat(fd).st_ino)!=(os.fstat(current).st_dev,os.fstat(current).st_ino):raise RuntimeError('La carpeta de salida cambió durante la preparación')
                os.link(temporary,filename,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
                os.fsync(fd)
                if commit:commit(str(Path(destination)/filename))
        finally:
            try:os.unlink(temporary,dir_fd=fd)
            except FileNotFoundError:pass
    return str(Path(destination)/filename)

def run(project_path,token,lock_fd):
    from .render import RenderJob
    path=_path(project_path);root=path.parent;work=root/'.finalize';request_data=_read(work/(token+'.json'));data=request_data['state'];job=None;stop=False
    def signal_cancel(*_):
        nonlocal stop
        stop=True
    def cancelled():return stop or (root/'discard.json').exists() or (work/('cancel-'+token+'.json')).exists()
    for signum in (signal.SIGTERM,signal.SIGINT):signal.signal(signum,signal_cancel)
    try:
        _state(root,data,state='running',pid=os.getpid())
        if cancelled():raise InterruptedError('Preparación cancelada')
        with _directory(data['destination']) as fd:
            if os.fstatvfs(fd).f_bavail*os.fstatvfs(fd).f_frsize<128*1024*1024:raise OSError('Espacio insuficiente en la carpeta de salida')
        with tempfile.TemporaryDirectory(prefix='render-',dir=work) as temporary:
            output=Path(temporary)/'result.mp4'
            job=RenderJob(path,output,preset='preview',snapshot=request_data['project']).start()
            while job.poll()['state']=='running':
                if cancelled():job.cancel()
                progress=job.poll();_state(root,data,progress=progress['progress']*.97,phase=progress['phase']);time.sleep(.15)
            progress=job.poll()
            if progress['state']=='cancelled' or cancelled():raise InterruptedError('Preparación cancelada')
            if progress['state']!='done':raise RuntimeError(progress.get('error') or 'No se pudo preparar el MP4')
            _state(root,data,progress=.98,phase='Guardando MP4')
            _publish(output,data['destination'],data['filename'],cancelled,root=root,commit=lambda published:_state(root,data,state='ready',output=published,progress=1.,phase='MP4 listo',error=None))
    except InterruptedError as exc:_state(root,data,state='cancelled',output=None,phase='Preparación cancelada',error=str(exc))
    except Exception as exc:_state(root,data,state='error',output=None,phase='No se pudo preparar el MP4',error=str(exc))
    finally:
        if job and job.poll()['state']=='running':job.cancel();job._thread.join(10)
        (work/('cancel-'+token+'.json')).unlink(missing_ok=True)
        (work/(token+'.json')).unlink(missing_ok=True)
        os.close(lock_fd)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('project_path');parser.add_argument('--token',required=True);parser.add_argument('--lock-fd',required=True,type=int);args=parser.parse_args()
    run(args.project_path,args.token,args.lock_fd)
