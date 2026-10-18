import hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from dataclasses import asdict
from loomrec import finalize
from loomrec.schema import Source,Project,Clip,atomic_json,save_project
from loomrec.capture import CaptureConfig,CaptureSession,append_segment

class FinalizeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'project.json';self.dest=self.root/'Videos';self.dest.mkdir()
  self.project=Project(sources=[Source('s','source.mkv',duration=1,width=64,height=64)],clips=[Clip('s',0,1)]);save_project(self.project,self.path)
 def tearDown(self):self.temp.cleanup()
 def test_legacy_is_none_and_old_attach_never_enables_automatic(self):
  self.assertEqual(finalize.status(self.path)['state'],'none')
  config=asdict(CaptureConfig(str(self.root),':0',[0,0,64,64]));config.pop('auto_finalize');atomic_json(self.root/'capture.json',config)
  self.assertFalse(CaptureSession.attach(self.root).config.auto_finalize)
 def test_gains_are_persisted_on_every_segment_not_applied_to_originals(self):
  info={'format':{'duration':'2'},'streams':[{'codec_type':'video','start_time':'.1'},{'codec_type':'audio','start_time':'.1'},{'codec_type':'audio','start_time':'.1'}]}
  c=CaptureConfig(str(self.root),':0',[0,0,64,64],mic='owned1',system_audio='owned2',mic_gain=.25,system_gain=1.75)
  p=Project()
  with patch('loomrec.capture.probe',return_value=info):
   for stem in ['a','b']:append_segment(p,self.root,stem,c)
  self.assertEqual([s.gain for s in p.sources if s.kind=='mic'],[.25,.25]);self.assertEqual([s.gain for s in p.sources if s.kind=='system'],[1.75,1.75])
  for gain in [-1,9,float('nan')]:
   c.mic_gain=gain
   with self.assertRaises(ValueError):c.validate()
 def test_snapshot_and_inherited_lock_deduplicate_requests(self):
  leases=[]
  def spawn(*args,**kwargs):leases.append(os.dup(kwargs['pass_fds'][0]));return Mock()
  before=self.path.read_bytes()
  try:
   with patch('loomrec.finalize.subprocess.Popen',side_effect=spawn) as process:
    first=finalize.request(self.path,self.dest);second=finalize.request(self.path,self.dest)
   self.assertEqual(first['token'],second['token']);process.assert_called_once()
   request=json.loads((self.root/'.finalize'/(first['token']+'.json')).read_text());self.assertEqual(request['state']['project_sha256'],hashlib.sha256(before).hexdigest());self.assertEqual(request['project']['sources'][0]['path'],'source.mkv')
   finalize.cancel(self.path);self.assertTrue((self.root/'.finalize'/('cancel-'+first['token']+'.json')).exists());self.assertEqual(self.path.read_bytes(),before)
  finally:
   for fd in leases:os.close(fd)
  self.assertEqual(finalize.status(self.path)['state'],'error')
 def test_ready_retry_idempotent_stale_revision_visible_and_missing_output(self):
  output=self.dest/'ready.mp4';output.write_bytes(b'owned');data=dict(state='ready',output=str(output),project_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),progress=1.,error=None)
  atomic_json(self.root/'finalization.json',data)
  with patch('loomrec.finalize.subprocess.Popen') as spawn:
   self.assertEqual(finalize.retry(self.path)['output'],str(output));spawn.assert_not_called()
  self.project.title='changed';save_project(self.project,self.path);self.assertFalse(finalize.status(self.path)['matches_project']);self.assertEqual(finalize.status(self.path)['state'],'ready')
  output.unlink();self.assertEqual(finalize.status(self.path)['state'],'error');self.assertIsNone(finalize.status(self.path)['output'])
 def test_publish_no_overwrite_no_symlink_and_cancel_cleanup(self):
  source=self.root/'render.mp4';source.write_bytes(b'owned-source');target=self.dest/'final.mp4';target.write_bytes(b'existing')
  with self.assertRaises(FileExistsError):finalize._publish(source,self.dest,target.name,lambda:False)
  self.assertEqual(target.read_bytes(),b'existing');self.assertEqual(source.read_bytes(),b'owned-source');self.assertFalse(list(self.dest.glob('.*.tmp')))
  link=self.root/'alias';link.symlink_to(self.dest,target_is_directory=True)
  with self.assertRaises(OSError):finalize._publish(source,link,'other.mp4',lambda:False)
  with self.assertRaises(InterruptedError):finalize._publish(source,self.dest,'cancel.mp4',lambda:True)
  self.assertFalse((self.dest/'cancel.mp4').exists());self.assertFalse(list(self.dest.glob('.*.tmp')))
 def test_discard_cancels_pending_without_deleting_ready_output(self):
  work=self.root/'.finalize';work.mkdir();atomic_json(self.root/'finalization.json',{'state':'pending','token':'owned'})
  CaptureSession(CaptureConfig(str(self.root),':0',[0,0,64,64])).stop(discard=True)
  self.assertTrue((self.root/'discard.json').exists());self.assertTrue((work/'cancel-owned.json').exists())
  output=self.dest/'existing.mp4';output.write_bytes(b'keep');atomic_json(self.root/'finalization.json',{'state':'ready','output':str(output)})
  finalize.cancel(self.path,discard=True);self.assertEqual(output.read_bytes(),b'keep')
 def test_missing_destination_durable_error_and_retry_preserves_sources(self):
  leases=[]
  def spawn(*args,**kwargs):leases.append(os.dup(kwargs['pass_fds'][0]));return Mock()
  with patch('loomrec.finalize.subprocess.Popen',side_effect=spawn):data=finalize.request(self.path,self.root/'missing')
  with patch('loomrec.finalize.signal.signal'):finalize.run(self.path,data['token'],leases.pop())
  result=finalize.status(self.path);self.assertEqual(result['state'],'error');self.assertIsNone(result['output']);self.assertEqual(finalize.request(self.path,self.dest)['state'],'error')
  with patch('loomrec.finalize.subprocess.Popen',side_effect=spawn):new=finalize.retry(self.path,self.dest)
  self.assertNotEqual(new['token'],data['token']);self.assertEqual(new['project_sha256'],data['project_sha256'])
  for fd in leases:os.close(fd)
 def test_renderer_uses_snapshot_even_if_project_changes_before_start(self):
  from loomrec.render import RenderJob
  snapshot=json.loads(self.path.read_bytes());job=RenderJob(self.path,self.root/'out.mp4',snapshot=snapshot)
  self.project.clips=[];save_project(self.project,self.path);snapshot['clips']=[]
  with patch('loomrec.render.threading.Thread') as thread:job.start()
  self.assertEqual(len(job.project.clips),1);thread.return_value.start.assert_called_once()
 def test_renderer_exit_failure_and_cancel_are_durable_and_clean(self):
  for ending in ('error','cancelled'):
   leases=[]
   def spawn(*args,**kwargs):leases.append(os.dup(kwargs['pass_fds'][0]));return Mock()
   with patch('loomrec.finalize.subprocess.Popen',side_effect=spawn):data=finalize.request(self.path,self.dest,retry=True)
   job=Mock();job.poll.return_value={'state':ending,'error':'synthetic encoder exit','progress':.2,'phase':'Renderizando'}
   before=self.path.read_bytes()
   with patch('loomrec.finalize.signal.signal'),patch('loomrec.render.RenderJob') as render:
    render.return_value.start.return_value=job;finalize.run(self.path,data['token'],leases.pop())
   self.assertEqual(finalize.status(self.path)['state'],ending);self.assertIsNone(finalize.status(self.path)['output']);self.assertEqual(self.path.read_bytes(),before);self.assertFalse(list((self.root/'.finalize').glob('render-*')))
 def test_worker_only_explicit_successful_stop_requests_finalization(self):
  from loomrec.worker import main
  for action in ('stop','discard','signal','error'):
   with tempfile.TemporaryDirectory() as td:
    root=Path(td);atomic_json(root/'capture.json',asdict(CaptureConfig(td,':0',[0,0,64,64],cursor=False,output_dir=str(self.dest),title='Captured title',mic_gain=.3,system_gain=1.4)))
    if action in ('stop','discard'):atomic_json(root/'command-stop.json',{'command':'stop','discard':action=='discard'})
    handlers={}
    def spawn(*args,**kwargs):
     if action=='error':raise OSError('synthetic encoder failure')
     if action=='signal':handlers[__import__('signal').SIGTERM]()
     process=Mock();process.poll.return_value=None;process.returncode=0;return process
    def append(project,*_):project.sources.append(Source('s','s.mkv',duration=1));project.clips.append(Clip('s',0,1))
    with patch('loomrec.worker.signal.signal',side_effect=lambda signum,handler:handlers.__setitem__(signum,handler)),patch('loomrec.devices.display_bounds',return_value=[1920,1080]),patch('loomrec.worker.shutil.disk_usage') as disk,patch('loomrec.worker.subprocess.Popen',side_effect=spawn),patch('loomrec.worker.append_segment',side_effect=append),patch('loomrec.worker.time.sleep'),patch('loomrec.finalize.request') as request:
     disk.return_value.free=10**10;main(root)
    self.assertEqual(request.call_count,1 if action=='stop' else 0,action)
    saved=json.loads((root/'project.json').read_text());self.assertEqual(saved['title'],'Captured title')
