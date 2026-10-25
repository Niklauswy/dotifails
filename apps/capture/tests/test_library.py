import tempfile
import unittest
from loomrec.schema import Project,Source,Clip,Annotation,Subtitle,save_project
from loomrec.library import Library


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.library=Library(self.temp.name); self.path=self.library.new_directory()/'project.json'
        save_project(Project(sources=[Source('s','original.mkv',duration=10)],clips=[Clip('s',0,10)],annotations=[Annotation('mask',2,8)],subtitles=[Subtitle(2,8,'private')]),self.path)
    def test_library_reversible_private_original(self):
        media=self.path.parent/'original.mkv'; media.write_bytes(b'unchanged')
        self.library.rename(self.path,'Ensayo'); self.library.organize(self.path,'Curso')
        self.assertEqual(len(self.library.entries('curso')),1)
        trashed=self.library.delete(self.path); self.assertFalse(self.path.exists()); self.assertEqual(len(self.library.entries(trash=True)),1)
        restored=self.library.restore(trashed); self.assertEqual((restored.parent/'original.mkv').read_bytes(),b'unchanged')


if __name__=='__main__':unittest.main()
