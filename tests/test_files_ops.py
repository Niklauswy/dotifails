import importlib.util
import errno
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

repository = Path(__file__).resolve().parent
if repository.name == 'tests':
    repository = repository.parent
spec = importlib.util.spec_from_file_location('files_ops', repository / 'apps/orbit/files_ops.py')
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


class FileOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'document.txt'
        self.source.write_text('original')
        self.dest = self.root / 'destination'
        self.dest.mkdir()

    def test_copy_preserves_original_and_rejects_collision(self):
        result = ops.execute_operation('copy', [str(self.source)], str(self.dest))
        self.assertEqual(Path(result[0]).read_text(), 'original')
        self.source.write_text('changed')
        with self.assertRaises(FileExistsError):
            ops.execute_operation('copy', [str(self.source)], str(self.dest))
        self.assertEqual((self.dest / self.source.name).read_text(), 'original')

    def test_symlink_copy_preserves_link_including_dangling(self):
        link = self.root / 'link'
        link.symlink_to('missing')
        ops.execute_operation('copy', [str(link)], str(self.dest))
        self.assertTrue((self.dest / 'link').is_symlink())
        self.assertEqual((self.dest / 'link').readlink(), Path('missing'))
        self.assertEqual(Path(ops.unique_destination(str(self.dest), 'link')).name, 'link (2)')

    def test_directory_symlinks_are_not_followed(self):
        folder = self.root / 'folder'
        folder.mkdir()
        (folder / 'linked').symlink_to(self.source)
        ops.execute_operation('copy', [str(folder)], str(self.dest))
        self.assertTrue((self.dest / 'folder/linked').is_symlink())

    def test_self_copy_through_symlink_is_rejected(self):
        folder = self.root / 'folder'
        folder.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(folder, target_is_directory=True)
        for kind in ('copy', 'move'):
            with self.assertRaises(ValueError):
                ops.execute_operation(kind, [str(folder)], str(alias))

    def test_rename_and_move(self):
        renamed = self.root / 'renamed.txt'
        self.assertEqual(ops.execute_operation('rename', [str(self.source)], str(renamed)), [str(renamed)])
        self.assertFalse(self.source.exists())
        ops.execute_operation('move', [str(renamed)], str(self.dest))
        self.assertEqual((self.dest / renamed.name).read_text(), 'original')
        self.assertFalse(renamed.exists())

    def test_preflight_batch_collision_does_not_move_anything(self):
        extra = self.root / 'extra'
        extra.write_text('extra')
        (self.dest / 'extra').write_text('existing')
        with self.assertRaises(FileExistsError):
            ops.execute_operation('move', [str(self.source), str(extra)], str(self.dest))
        self.assertTrue(self.source.exists())

    def test_copy_failure_cleans_only_new_destination(self):
        with patch.object(ops.shutil, 'copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                ops.execute_operation('copy', [str(self.source)], str(self.dest))
        self.assertFalse((self.dest / self.source.name).exists())
        self.assertEqual(self.source.read_text(), 'original')

    def test_trash_uses_gio_and_never_falls_back_to_delete(self):
        with patch.object(ops.subprocess, 'run') as run:
            run.return_value.returncode = 1
            run.return_value.stderr = 'Trash unavailable'
            with self.assertRaises(OSError):
                ops.execute_operation('trash', [str(self.source)])
            self.assertEqual(run.call_args.args[0], ['gio', 'trash', '--', str(self.source)])
        self.assertTrue(self.source.exists())

    def test_names_and_mkdir(self):
        for name in ('', '.', '..', 'a/b', 'a\x00b'):
            with self.assertRaises(ValueError):
                ops.validate_name(name)
        target = self.root / 'Nueva carpeta'
        ops.execute_operation('mkdir', [], str(target))
        self.assertTrue(target.is_dir())
        with self.assertRaises(FileExistsError):
            ops.execute_operation('mkdir', [], str(target))

    def test_empty_source_is_not_interpreted_as_working_directory(self):
        with self.assertRaises(ValueError):
            ops.execute_operation('trash', [''])

    def test_cross_device_move_copies_then_removes_original(self):
        with patch.object(ops, '_rename_exclusive', side_effect=OSError(errno.EXDEV, 'different filesystem')):
            result = ops.execute_operation('move', [str(self.source)], str(self.dest))
        self.assertEqual(result, [str(self.dest / self.source.name)])
        self.assertEqual(Path(result[0]).read_text(), 'original')
        self.assertFalse(self.source.exists())

    def test_cross_device_move_copy_failure_preserves_original(self):
        with patch.object(ops, '_rename_exclusive', side_effect=OSError(errno.EXDEV, 'different filesystem')):
            with patch.object(ops.shutil, 'copy2', side_effect=OSError(errno.ENOSPC, 'disk full')):
                with self.assertRaises(OSError):
                    ops.execute_operation('move', [str(self.source)], str(self.dest))
        self.assertEqual(self.source.read_text(), 'original')
        self.assertFalse((self.dest / self.source.name).exists())


if __name__ == '__main__':
    unittest.main()
