import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,unittest,socket,threading,time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock,patch
from loomrec.ui.instance import Instance

class InstanceTests(unittest.TestCase):
 def test_one_owner_under_concurrent_claims(self):
  with tempfile.TemporaryDirectory() as directory:
   peers=[Instance(directory) for _ in range(6)]
   try:
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(lambda p:p.claim(),peers))
    self.assertEqual(sum(results),1)
   finally:
    for peer in peers:peer.close()
 def test_stale_socket_recovered_and_requests_share_owner(self):
  with tempfile.TemporaryDirectory() as directory:
   owner=Instance(directory);stale=socket.socket(socket.AF_UNIX);stale.bind(str(owner.path));stale.close()
   self.assertTrue(owner.claim());peer=Instance(directory);self.assertFalse(peer.claim());results=[]
   try:
    for action in ('setup','status','focus'):
     thread=threading.Thread(target=lambda:results.append(peer.request(action)));thread.start()
     deadline=time.monotonic()+2
     while thread.is_alive() and time.monotonic()<deadline:owner.poll(lambda a:{'action':a,'pid':123});time.sleep(.005)
     thread.join(.1);self.assertFalse(thread.is_alive())
    self.assertEqual([r['action'] for r in results],['setup','status','focus'])
   finally:owner.close();peer.close()
   next_owner=Instance(directory);self.assertTrue(next_owner.claim());next_owner.close()

class ActivationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from PySide6.QtWidgets import QApplication
  cls.app=QApplication.instance() or QApplication([])
