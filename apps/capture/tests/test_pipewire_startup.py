"""Negotiation/uncork state machine; no compositor, PipeWire or media devices."""
from types import SimpleNamespace
import unittest
from loomrec.pipewire_bridge import start_hyprland_pipeline

Gst=SimpleNamespace(SECOND=1000000000,
    State=SimpleNamespace(PAUSED='paused',PLAYING='playing',NULL='null',READY='ready',VOID_PENDING='void'),
    StateChangeReturn=SimpleNamespace(FAILURE='failure',SUCCESS='success',NO_PREROLL='live',ASYNC='async'))


class Pipeline:
    def __init__(self,states=None):
        self.now=100.;self.events=[];self.sleeps=[];self.states=iter(states or [('live','paused','void')]);self.fail=None
    def set_state(self,state):
        self.events.append((state,self.now))
        return 'failure' if state==self.fail else 'live'
    def get_state(self,timeout):
        self.now+=timeout/Gst.SECOND
        self.events.append(('read-state',self.now))
        return next(self.states,('async','ready','paused'))
    def pause(self,seconds):self.sleeps.append(seconds);self.now+=seconds
    def start(self,stopping=lambda:False):
        start_hyprland_pipeline(self,Gst,stopping,clock=lambda:self.now,pause=self.pause)


class PipeWireStartupTests(unittest.TestCase):
    def test_negotiation_wait_then_cork_barrier_precedes_single_final_uncork(self):
        p=Pipeline([('async','ready','paused'),('live','paused','void')]);p.start()
        transitions=[e for e in p.events if e[0]!='read-state']
        self.assertEqual([e[0] for e in transitions],['paused','playing'])
        negotiated=[t for e,t in p.events if e=='read-state'][-1]
        self.assertAlmostEqual(transitions[-1][1]-negotiated,.65)
        self.assertTrue(all(0<d<=.05 for d in p.sleeps))
    def test_success_non_live_state_is_accepted_only_when_paused_and_no_pending(self):
        p=Pipeline([('success','paused','playing'),('success','paused','void')]);p.start()
        self.assertEqual(len([e for e in p.events if e[0]=='read-state']),2)
    def test_failed_negotiation_does_not_uncork_and_releases_pipeline(self):
        p=Pipeline([('failure','ready','void')])
        with self.assertRaisesRegex(RuntimeError,'negociación'):p.start()
        self.assertEqual([e[0] for e in p.events],['paused','read-state','null'])
    def test_missing_negotiation_has_finite_deadline_and_no_playing(self):
        p=Pipeline([('async','ready','paused')])
        with self.assertRaisesRegex(TimeoutError,'5 segundos'):p.start()
        self.assertAlmostEqual(p.now,105,places=5)
        self.assertEqual(p.events[-1][0],'null');self.assertNotIn('playing',[e[0] for e in p.events])
    def test_cancel_during_negotiation_releases_without_playing(self):
        p=Pipeline([('async','ready','paused')])
        with self.assertRaises(InterruptedError):p.start(lambda:p.now>100.07)
        self.assertLessEqual(p.now,100.1);self.assertEqual(p.events[-1][0],'null')
        self.assertNotIn('playing',[e[0] for e in p.events])
    def test_cancel_after_cork_before_uncork_releases_without_playing(self):
        p=Pipeline()
        with self.assertRaises(InterruptedError):p.start(lambda:p.now>100.2)
        self.assertLess(p.now,100.3);self.assertEqual(p.events[-1][0],'null')
        self.assertNotIn('playing',[e[0] for e in p.events])
    def test_initial_state_failure_releases_without_waiting(self):
        p=Pipeline();p.fail='paused'
        with self.assertRaises(RuntimeError):p.start()
        self.assertEqual(p.events,[('paused',100.),('null',100.)]);self.assertEqual(p.sleeps,[])
    def test_uncork_failure_releases_without_recording(self):
        p=Pipeline();p.fail='playing'
        with self.assertRaises(RuntimeError):p.start()
        self.assertEqual(p.events[-1][0],'null')
