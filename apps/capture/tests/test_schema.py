import json
import tempfile
import unittest
from pathlib import Path
from loomrec.schema import *

class SchemaTests(unittest.TestCase):
    def project(self):
        return Project(sources=[Source('s','source.mkv',duration=5)],clips=[Clip('s',1,4)])
    def test_roundtrip_and_reorder(self):
        p=self.project();p.clips.append(Clip('s',0,1));p.clips.reverse()
        p.annotations=[Annotation('mask',0,1)]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'project.json';save_project(p,path)
            self.assertEqual(load_project(path),p);self.assertEqual(p.duration,4)
    def test_reject_bad_media_and_ranges(self):
        p=self.project()
        for path in ['/private/file','../private/file']:
            p.sources[0].path=path
            with self.assertRaises(ValueError):validate(p)
        p=self.project();p.clips[0].out_s=6
        with self.assertRaises(ValueError):validate(p)
    def test_bad_rect_and_nan(self):
        p=self.project();p.crop=[.8,0,.4,1]
        with self.assertRaises(ValueError):validate(p)
        p=self.project();p.sources[0].gain=float('nan')
        with self.assertRaises(ValueError):validate(p)
    def test_atomic_save_preserves_valid_file(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'p.json';p=self.project();save_project(p,path)
            before=path.read_bytes();p.version=2
            with self.assertRaises(ValueError):save_project(p,path)
            self.assertEqual(path.read_bytes(),before)
    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'escape').symlink_to('/tmp')
            with self.assertRaises(ValueError):media_path(Path(d)/'p.json',Source('a','escape/a'))
