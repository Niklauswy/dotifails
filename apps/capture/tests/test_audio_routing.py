import json
import unittest
from pathlib import Path
from unittest.mock import patch
from loomrec.devices import DEFAULT_SYSTEM_AUDIO, default_system_audio, resolve_system_audio, discover
from loomrec.capture import CaptureConfig
from loomrec.worker import capture_command


class AudioRoutingTests(unittest.TestCase):
    def pulse(self, args):
        if args == ['pactl', 'get-default-sink']:return 'bluetooth\n'
        if args[-1] == 'sinks':return json.dumps([dict(name='speakers', monitor_source='speakers.monitor'),dict(name='bluetooth', description='Headphones', monitor_source='bluetooth.monitor')])
        if args[-1] == 'sources':return json.dumps([dict(name='speakers.monitor'),dict(name='microphone'),dict(name='bluetooth.monitor')])
        if args[0] == 'xrandr':return 'Monitors: 0\n'
        raise AssertionError(args)

    def test_default_output_monitor_is_not_first_monitor_or_microphone(self):
        with patch('loomrec.devices.run', side_effect=self.pulse):
            self.assertEqual(default_system_audio(),dict(id='bluetooth.monitor',output='bluetooth',name='Headphones'))
            choices=discover()['audio']
        self.assertEqual(choices[0]['id'],DEFAULT_SYSTEM_AUDIO)
        self.assertIn('Headphones',choices[0]['name'])
        self.assertEqual([c['id'] for c in choices[1:]],['speakers.monitor','microphone','bluetooth.monitor'])

    def test_explicit_manual_and_off_never_reroute(self):
        with patch('loomrec.devices.run',side_effect=AssertionError('must not discover')):
            self.assertEqual(resolve_system_audio('speakers.monitor'),'speakers.monitor')
            self.assertIsNone(resolve_system_audio(None))

    def test_missing_default_monitor_fails_instead_of_falling_back(self):
        with patch('loomrec.devices.run',side_effect=self.pulse):
            with self.assertRaisesRegex(ValueError,'monitor disponible'):
                default_system_audio([dict(name='speakers.monitor')])

    def test_disconnected_default_sink_never_uses_unrelated_source(self):
        with patch('loomrec.devices.run',side_effect=['missing', '[]']):
            with self.assertRaisesRegex(ValueError,'monitor disponible'):
                default_system_audio([dict(name='speakers.monitor')])

    def test_each_segment_resolves_once_preserving_selection_and_track_mapping(self):
        config=CaptureConfig('/tmp/owned',':0',[0,0,320,180],mic='microphone',system_audio=DEFAULT_SYSTEM_AUDIO)
        with patch('loomrec.devices.default_system_audio',side_effect=[{'id':'a.monitor'},{'id':'b.monitor'}]) as resolve:
            first=capture_command(config,Path('/tmp/owned'),'first',origin=42)
            resumed=capture_command(config,Path('/tmp/owned'),'second',origin=44)
        self.assertEqual(resolve.call_count,2)
        self.assertIn('a.monitor',first);self.assertNotIn('b.monitor',first)
        self.assertIn('b.monitor',resumed)
        self.assertEqual(config.system_audio,DEFAULT_SYSTEM_AUDIO)
        self.assertIn('1:a:0',first);self.assertIn('2:a:0',first)
        self.assertIn('asetpts=PTS-42/TB,aresample=async=1',first)
