"""Worker-owned live cursor child; never owns the recording engine or user UI."""
import json,os,selectors,subprocess,sys,time
from pathlib import Path

class LiveCursor:
    def __init__(self,display,rect,effects):
        self.display=display;self.rect=list(rect);self.effects=dict(effects);self.process=None;self.error=None
    def prepare(self,timeout=3):
        environment=os.environ.copy();package=str(Path(__file__).resolve().parent.parent)
        environment['PYTHONPATH']=package+(os.pathsep+environment['PYTHONPATH'] if environment.get('PYTHONPATH') else '')
        try:
            self.process=subprocess.Popen([sys.executable,'-P','-m','loomrec.ui.live_cursor','--display',self.display,'--rect',json.dumps(self.rect),'--effects',json.dumps(self.effects),'--parent-pid',str(os.getpid())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=environment,start_new_session=True)
            deadline=time.monotonic()+timeout;data=b''
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdout,selectors.EVENT_READ)
                while time.monotonic()<deadline:
                    if self.process.poll() is not None:raise RuntimeError('El cursor en vivo no pudo iniciarse')
                    if not selector.select(min(.1,max(0,deadline-time.monotonic()))):continue
                    part=os.read(self.process.stdout.fileno(),4096)
                    if not part:raise RuntimeError('El cursor en vivo cerró su conexión')
                    data+=part
                    if len(data)>16384:raise RuntimeError('Respuesta de cursor inválida')
                    while b'\n' in data:
                        line,data=data.split(b'\n',1)
                        try:message=json.loads(line)
                        except ValueError:continue
                        if message.get('ready') is True:return self
                        if message.get('error'):raise RuntimeError(str(message['error']))
            raise RuntimeError('El cursor en vivo no respondió a tiempo')
        except Exception as exc:
            self.error=str(exc);self.stop();raise
    def start(self,origin):
        """Ready means already mapped; encoder shares its own unchanged epoch."""
    def alive(self):return self.process is not None and self.process.poll() is None
    def stop(self):
        p=self.process
        if not p:return
        if p.stdin:
            try:p.stdin.close()
            except OSError:pass
        try:p.wait(timeout=.8)
        except subprocess.TimeoutExpired:
            p.terminate()
            try:p.wait(timeout=.8)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=2)
        if p.stdout:p.stdout.close()
        self.process=None
