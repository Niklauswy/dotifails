"""Lifecycle adapter keeping portal consent alive across finalized pause segments."""
import json
import selectors
import os
import time
import subprocess
import sys
from .portal import Portal


def wait_remote_quiescence(finished_at,on_wait=None,*,clock=time.monotonic,pause=time.sleep):
    """Credit time already elapsed after releasing the previous client socket.

    Hyprland 0.55 reuses a managed screenshare session with a 500 ms sharing
    latch; XDPH copy_with_damage otherwise can await damage on reconnect.
    This finite barrier never changes desktop content or reuses an old frame.
    """
    if finished_at is None:return
    deadline=finished_at+.65
    while clock()<deadline:
        if on_wait:on_wait()
        remaining=deadline-clock()
        if remaining>0:pause(min(.05,remaining))


def diagnostic_tail(log):
    """Bounded stderr from our own helper, including anonymous temporary logs."""
    try:
        log.flush();size=os.fstat(log.fileno()).st_size
        data=os.pread(log.fileno(),4096,max(0,size-4096))
    except (OSError,ValueError,AttributeError):
        try:
            with open(log.name,'rb') as stream:
                stream.seek(0,os.SEEK_END);stream.seek(max(0,stream.tell()-4096));data=stream.read(4096)
        except (OSError,TypeError,ValueError,AttributeError):return ''
    return ''.join(c for c in data.decode('utf8',errors='replace') if c in '\n\t' or ord(c)>=32).strip()


class PipeWireCapture:
    def __init__(self,config,on_wait=None):
        self.config=config;self._remote_used=False;self._remote_finished_at=None;self.portal=Portal();self.portal.on_wait=on_wait;self.process=None;self._coordinate_topology=None
        try:
            self.node,self.metadata=self.portal.screencast(config.source_type,config.cursor,multiple=config.source_type=='desktop')
            needs_coordinates=config.source_type=='region' or (config.source_type=='monitor' and config.cursor and bool(getattr(config,'cursor_effects',{})))
            if needs_coordinates and getattr(config,'normalize_coordinates',True) and os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
                from .desktop_capture import read_topology,coordinate_metadata
                self._coordinate_topology=read_topology();self.metadata=coordinate_metadata(self.metadata,self._coordinate_topology)
        except BaseException:self.portal.close();raise
    def begin(self,log,even=True,live_effects=None):
        if self._remote_used and os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            def waiting():
                self.portal.dispatch()
                if self.portal.on_wait:self.portal.on_wait()
            wait_remote_quiescence(self._remote_finished_at,waiting)
        if self._coordinate_topology is not None:
            from .desktop_capture import read_topology
            if read_topology()!=self._coordinate_topology:raise RuntimeError('Cambió la topología del monitor autorizado; inicia una nueva selección. Los segmentos anteriores se conservan.')
        self.portal.dispatch()
        if self._remote_used or self.portal.fd is None:self.portal.open_remote()
        self._remote_used=True
        values=dict(fd=self.portal.fd,node=self.node,metadata=self.metadata,fps=self.config.fps,
                    rect=self.config.rect if self.config.source_type=='region' else None,even=even)
        if live_effects:values.update(live_effects)
        try:
            self.process=subprocess.Popen([sys.executable,'-P','-m','loomrec.pipewire_bridge',json.dumps(values)],
                stdout=subprocess.PIPE,stderr=log,pass_fds=(self.portal.fd,),bufsize=0)
            # Never block startup forever if the portal source disappears.
            header=bytearray();deadline=time.monotonic()+15
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdout,selectors.EVENT_READ)
                while not header.endswith(b'\n') and len(header)<2048:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError('PipeWire no inició el vídeo')
                    if self.portal.on_wait:self.portal.on_wait()
                    if not selector.select(min(.25,remaining)):continue
                    chunk=os.read(self.process.stdout.fileno(),1)
                    if not chunk:raise RuntimeError('No se pudo leer PipeWire. Revisa el registro del segmento.')
                    header.extend(chunk)
            if not header.endswith(b'\n'):raise RuntimeError('Cabecera PipeWire demasiado grande')
            info=json.loads(header)
            if not all(type(info[k]) is int and 16<=info[k]<=32768 for k in ('width','height')):raise RuntimeError('Dimensiones PipeWire inválidas')
            self.source_size=info.get('source_size',[info['width'],info['height']])
            return self.process.stdout.fileno(),info['width'],info['height']
        except BaseException as error:
            self.finish()
            if isinstance(error,Exception):
                detail=diagnostic_tail(log)
                if detail:raise RuntimeError(str(error)+'\nPuente PipeWire: '+detail) from error
            raise
    def check(self):
        self.portal.dispatch()
        if self.process and self.process.poll() is not None:raise RuntimeError('La fuente PipeWire se cerró; los segmentos finalizados se conservan')
    def finish(self):
        process,self.process=self.process,None
        try:
            if process:
                try:
                    if process.poll() is None:
                        process.terminate()
                        try:process.wait(timeout=3)
                        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
                except BaseException:
                    # A failing wait/terminate still gets a bounded reap attempt.
                    try:
                        if process.poll() is None:process.kill();process.wait(timeout=3)
                    except Exception:pass
                    raise
                finally:process.stdout.close()
        finally:
            # pass_fds duplicates this same socket into the bridge. Keeping the
            # parent copy alive can retain the old client/link after child exit.
            # Release before quiescence/new OpenPipeWireRemote, even on failure.
            if self.portal.fd is not None:
                try:self.portal.release_remote()
                finally:self._remote_finished_at=time.monotonic()
    def close(self):
        try:self.finish()
        finally:self.portal.close()
