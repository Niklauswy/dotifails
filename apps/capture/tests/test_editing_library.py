import tempfile
import unittest
from pathlib import Path
from loomrec.schema import Project,Source,Clip,Annotation,Subtitle,save_project,load_project
from loomrec.editing import Editor
from loomrec.library import Library
from loomrec.integration import shortcut_conflicts

class EditingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.library=Library(self.temp.name); self.path=self.library.new_directory()/'project.json'
        save_project(Project(sources=[Source('s','original.mkv',duration=10)],clips=[Clip('s',0,10)],annotations=[Annotation('mask',2,8)],subtitles=[Subtitle(2,8,'private')]),self.path)
        self.editor=Editor(self.path)
    def test_trim_maps_annotations_and_undo_persists(self):
        self.editor.trim(0,3,9)
        p=load_project(self.path); self.assertEqual(p.duration,6); self.assertEqual((p.annotations[0].start,p.annotations[0].end),(0,5))
        self.editor.undo(); self.assertEqual(load_project(self.path).duration,10)
        self.editor.redo(); self.assertEqual(load_project(self.path).duration,6)
    def test_invalid_edit_is_atomic(self):
        before=self.path.read_bytes()
        with self.assertRaises(ValueError): self.editor.trim(0,-1,9)
        self.assertEqual(self.path.read_bytes(),before); self.assertEqual(self.editor.undo_stack,[])
    def test_split_delete_reorder_join(self):
        self.editor.split(0,5); self.editor.move(0,1)
        p=self.editor.project; self.assertEqual(p.clips[0].in_s,5)
        self.assertEqual([(a.start,a.end) for a in p.annotations],[(0,3),(7,10)])
        self.editor.move(1,0); self.editor.join(0); self.assertEqual(len(self.editor.project.clips),1)
        self.editor.split(0,5); self.editor.delete(0); self.assertEqual(self.editor.project.duration,5)
    def test_library_reversible_private_original(self):
        media=self.path.parent/'original.mkv'; media.write_bytes(b'unchanged')
        self.library.rename(self.path,'Ensayo'); self.library.organize(self.path,'Curso')
        self.assertEqual(len(self.library.entries('curso')),1)
        trashed=self.library.delete(self.path); self.assertFalse(self.path.exists()); self.assertEqual(len(self.library.entries(trash=True)),1)
        restored=self.library.restore(trashed); self.assertEqual((restored.parent/'original.mkv').read_bytes(),b'unchanged')
    def test_srt_no_overwrite(self):
        output=self.path.parent/'sub.srt'; self.editor.export_srt(output)
        self.assertIn('00:00:02,000 --> 00:00:08,000',output.read_text())
        with self.assertRaises(FileExistsError): self.editor.export_srt(output)
    def test_shortcut_expansion(self):
        self.assertTrue(shortcut_conflicts('ctrl + alt + {F9,F10}\n    command','alt + ctrl + F10'))
        self.assertFalse(shortcut_conflicts('super + r\n    other','ctrl + alt + F10'))

    def test_reviewed_silences_merge_and_preserve_sources(self):
        self.editor.remove_ranges([(2,4),(3,5),(8,9)])
        p=self.editor.project
        self.assertEqual(p.duration,6)
        self.assertEqual([(c.in_s,c.out_s) for c in p.clips],[(0,2),(5,8),(9,10)])
        self.assertEqual(len(p.sources),1)
        self.assertEqual([(s.start,s.end) for s in p.subtitles],[(2,5)])
        self.editor.undo();self.assertEqual(self.editor.project.duration,10)

if __name__=='__main__':unittest.main()
